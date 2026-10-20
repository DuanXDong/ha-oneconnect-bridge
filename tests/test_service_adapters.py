from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


_BUSINESS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "oneconnect_bridge"
    / "business"
)
_INTEGRATION_PATH = _BUSINESS_PATH.parent
_integration_package = ModuleType("custom_components.oneconnect_bridge")
_integration_package.__path__ = [str(_INTEGRATION_PATH)]
sys.modules.setdefault("custom_components.oneconnect_bridge", _integration_package)
_business_package = ModuleType("custom_components.oneconnect_bridge.business")
_business_package.__path__ = [str(_BUSINESS_PATH)]
sys.modules.setdefault("custom_components.oneconnect_bridge.business", _business_package)

from custom_components.oneconnect_bridge.business.adapters import get_service_adapter
from custom_components.oneconnect_bridge.business.models import ServiceRef


class _FakeServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object], bool]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict[str, object],
        *,
        blocking: bool,
    ) -> None:
        self.calls.append((domain, service, data, blocking))


class _FakeHass:
    def __init__(self, states: dict[str, object]) -> None:
        self.services = _FakeServices()
        self.states = SimpleNamespace(get=states.get)


def _state(value: str, **attributes: object) -> SimpleNamespace:
    return SimpleNamespace(state=value, attributes=attributes)


def test_service_adapters_convert_the_verified_light_contract() -> None:
    hass = _FakeHass(
        {
            "light.living_room": _state(
                "on", brightness=255, color_temp_kelvin=2000, rgb_color=(10, 20, 30)
            )
        }
    )
    entity_ids = ("light.living_room",)

    switch = ServiceRef("binarySwitch", "switch")
    brightness = ServiceRef("brightness", "brightness")
    cct = ServiceRef("cct", "cct")
    colour = ServiceRef("colour", "colour")

    assert asyncio.run(get_service_adapter("switch").read_state(hass, switch, entity_ids)) == {
        "on": 1
    }
    assert asyncio.run(get_service_adapter("brightness").read_state(hass, brightness, entity_ids)) == {
        "brightness": 255
    }
    assert asyncio.run(get_service_adapter("cct").read_state(hass, cct, entity_ids)) == {
        "colorTemperature": 2000
    }
    assert asyncio.run(get_service_adapter("colour").read_state(hass, colour, entity_ids)) == {
        "red": 10,
        "green": 20,
        "blue": 30,
    }

    asyncio.run(get_service_adapter("switch").apply_command(hass, switch, entity_ids, {"on": 0}))
    asyncio.run(
        get_service_adapter("brightness").apply_command(
            hass, brightness, entity_ids, {"brightness": 75}
        )
    )
    asyncio.run(
        get_service_adapter("cct").apply_command(
            hass, cct, entity_ids, {"colorTemperature": 6500}
        )
    )
    asyncio.run(
        get_service_adapter("colour").apply_command(hass, colour, entity_ids, {"red": 100})
    )

    assert hass.services.calls == [
        ("light", "turn_off", {"entity_id": "light.living_room"}, True),
        (
            "light",
            "turn_on",
            {"entity_id": "light.living_room", "brightness_pct": 29},
            True,
        ),
        (
            "light",
            "turn_on",
            {"entity_id": "light.living_room", "color_temp_kelvin": 6500},
            True,
        ),
        (
            "light",
            "turn_on",
            {"entity_id": "light.living_room", "rgb_color": (100, 20, 30)},
            True,
        ),
    ]


def test_service_adapters_reject_wrong_json_types_and_domains() -> None:
    hass = _FakeHass({"light.living_room": _state("on")})
    entity_ids = ("light.living_room",)

    switch = ServiceRef("binarySwitch", "switch")
    brightness = ServiceRef("brightness", "brightness")
    cct = ServiceRef("cct", "cct")
    colour = ServiceRef("colour", "colour")
    asyncio.run(get_service_adapter("switch").apply_command(hass, switch, entity_ids, {"on": True}))
    asyncio.run(
        get_service_adapter("brightness").apply_command(
            hass, brightness, entity_ids, {"brightness": True}
        )
    )
    asyncio.run(
        get_service_adapter("cct").apply_command(
            hass, cct, entity_ids, {"colorTemperature": 6501}
        )
    )
    asyncio.run(
        get_service_adapter("colour").apply_command(hass, colour, entity_ids, {"red": "1"})
    )

    assert hass.services.calls == []
    with pytest.raises(ValueError, match="brightness requires exactly one light"):
        get_service_adapter("brightness").validate_entities(("switch.living_room",))


def test_switch_distinguishes_bool_and_binary_switch_contracts() -> None:
    hass = _FakeHass({"light.living_room": _state("off")})
    adapter = get_service_adapter("switch")
    binary = ServiceRef("binarySwitch", "switch")
    boolean = ServiceRef("switch", "switch", (("on_type", "bool"),))

    asyncio.run(adapter.apply_command(hass, binary, ("light.living_room",), {"on": 1}))
    asyncio.run(adapter.apply_command(hass, boolean, ("light.living_room",), {"on": 1}))
    asyncio.run(adapter.apply_command(hass, boolean, ("light.living_room",), {"on": True}))

    assert hass.services.calls == [
        ("light", "turn_on", {"entity_id": "light.living_room"}, True),
        ("light", "turn_on", {"entity_id": "light.living_room"}, True),
    ]


def test_switch_defaults_to_int_even_when_the_profile_service_type_is_switch() -> None:
    hass = _FakeHass({"light.living_room": _state("on")})
    adapter = get_service_adapter("switch")
    service = ServiceRef("switch", "switch")

    assert asyncio.run(adapter.read_state(hass, service, ("light.living_room",))) == {
        "on": 1
    }
    asyncio.run(adapter.apply_command(hass, service, ("light.living_room",), {"on": 0}))

    assert hass.services.calls == [
        ("light", "turn_off", {"entity_id": "light.living_room"}, True)
    ]


def test_brightness_contract_override_preserves_percent_profiles() -> None:
    hass = _FakeHass({"light.living_room": _state("on", brightness=255)})
    service = ServiceRef(
        "brightness", "brightness", (("min", 1), ("max", 100), ("step", 1))
    )
    adapter = get_service_adapter("brightness")

    assert asyncio.run(adapter.read_state(hass, service, ("light.living_room",))) == {
        "brightness": 100
    }
    asyncio.run(
        adapter.apply_command(
            hass, service, ("light.living_room",), {"brightness": 75}
        )
    )

    assert hass.services.calls == [
        (
            "light",
            "turn_on",
            {"entity_id": "light.living_room", "brightness_pct": 75},
            True,
        )
    ]


def test_cct_contract_override_enforces_the_declared_profile_range() -> None:
    hass = _FakeHass({"light.living_room": _state("on", color_temp_kelvin=3000)})
    service = ServiceRef("cct", "cct", (("min", 2700), ("max", 5000), ("step", 100)))
    adapter = get_service_adapter("cct")

    assert asyncio.run(adapter.read_state(hass, service, ("light.living_room",))) == {
        "colorTemperature": 3000
    }
    asyncio.run(
        adapter.apply_command(
            hass, service, ("light.living_room",), {"colorTemperature": 2600}
        )
    )

    assert hass.services.calls == []


def test_mapping_selects_services_and_leaves_conversion_out_of_yaml(tmp_path) -> None:
    pytest.importorskip("yaml")
    from custom_components.oneconnect_bridge.business.mapping_config import (
        load_enabled_mapping,
    )

    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        """
schema: 1
enabled: true
children:
  living_room_light:
    product:
      prod_id: 2QQQ
      sub_prod_id: ""
      device_type: "112"
      manufacturer: hdo
      model: HF-HM-PBD-D1
      device_name: 客厅灯
      protocol_type: 1
      setup_type: 0
      known_fields_only: true
      services:
        - st: switch
          sid: switch
        - st: brightness
          sid: brightness
        - st: cct
          sid: cct
        - st: colour
          sid: colour
    bindings:
      - sid: switch
        entities: [light.living_room]
      - sid: brightness
        entities: [light.living_room]
      - sid: cct
        entities: [light.living_room]
      - sid: colour
        entities: [light.living_room]
""".strip(),
        encoding="utf-8",
    )

    plan = load_enabled_mapping(mapping)

    assert plan is not None
    child = plan.children[0]
    assert [service.service_id for service in child.services] == [
        "switch",
        "brightness",
        "cct",
        "colour",
    ]
    assert child.bindings[0].entity_ids == ("light.living_room",)


def test_mapping_rejects_unknown_service_and_removed_inline_rules(tmp_path) -> None:
    pytest.importorskip("yaml")
    from custom_components.oneconnect_bridge.business.mapping_config import (
        MappingConfigError,
        load_enabled_mapping,
    )

    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        """
schema: 1
enabled: true
children:
  invalid:
    adapter: light.0001
    product:
      prod_id: 2QQQ
      sub_prod_id: ""
      device_type: "112"
      manufacturer: hdo
      model: model
      device_name: 灯
      protocol_type: 1
      setup_type: 0
      known_fields_only: true
      services: []
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(MappingConfigError, match="removed adapter configuration"):
        load_enabled_mapping(mapping)


def test_mapping_rejects_inline_conversion_fields(tmp_path) -> None:
    pytest.importorskip("yaml")
    from custom_components.oneconnect_bridge.business.mapping_config import (
        MappingConfigError,
        load_enabled_mapping,
    )

    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        """
schema: 1
enabled: true
children:
  invalid:
    product:
      prod_id: 100z
      sub_prod_id: ""
      device_type: 01B
      manufacturer: 02B
      model: C21BB-QE27-10W-RGB/30-80-W
      device_name: 灯
      protocol_type: 1
      setup_type: 0
      known_fields_only: true
      services:
        - st: binarySwitch
          sid: switch
          fields: {on: bool}
    bindings:
      - sid: switch
        entities: [light.test]
        ha_to_huawei: {type: state_map}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(MappingConfigError, match="service has unsupported fields"):
        load_enabled_mapping(mapping)
