"""Huawei ``mode`` service: working mode of an air conditioner.

Default contract source
    prodId    : ``A0NQ`` -- wall-mounted air conditioner
    Profile   : https://smarthome-drcn.dbankcdn.com/device/guide/A0NQ/A0NQ.json
    common    : yes -- air conditioners expose a ``mode`` enum
    verified  : candidate, 2026-10-22 -- the enum mapping is checked field by
                field against the Profile and has run for months on the legacy
                bridge (full panel, voice control). It is **not** verified over
                this repository's projection yet; promote it only after the five
                acceptance steps in ``docs/service-adapter-contributing.md``.

Contract
    The default Profile enum is ``1`` auto / ``2`` cool / ``3`` heat /
    ``4`` fan_only / ``5`` dry. A Profile with a different enum can override it
    with ``contract.values``; keys are Home Assistant HVAC modes and values are
    the Huawei integer enum values.

Two rules from the device itself:

* An unmapped value is never reported. Passing a raw vendor value through makes
  the cloud drop the whole service (the air conditioner then shows only its
  power switch in the app).
* ``off`` has no enum value in the Profile, so the mode service stays silent
  while the entity is off. Power belongs to the ``switch`` service, which can
  bind the same climate entity and use ``contract.on_mode`` when turning it on.
"""

from __future__ import annotations

from ..models import ServiceRef

_DEFAULT_HA_TO_MODE = {"auto": 1, "cool": 2, "heat": 3, "fan_only": 4, "dry": 5}


class ModeServiceAdapter:
    service_id = "mode"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "mode":
            raise ValueError("mode requires st: mode")
        unknown = set(dict(service.contract)) - {"values"}
        if unknown:
            raise ValueError(
                f"mode has unsupported contract keys: {', '.join(sorted(unknown))}"
            )

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("climate."):
            raise ValueError("mode requires exactly one climate entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None:
            return {}
        mode = _mode_values(service).get(state.state)
        return {} if mode is None else {"mode": mode}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        mode = _wire_int(payload.get("mode"))
        mode_to_ha = {value: name for name, value in _mode_values(service).items()}
        hvac_mode = mode_to_ha.get(mode) if mode is not None else None
        if hvac_mode is None:
            return
        state = hass.states.get(entity_ids[0])
        allowed = state.attributes.get("hvac_modes") if state else None
        if isinstance(allowed, list) and allowed and hvac_mode not in allowed:
            return
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": entity_ids[0], "hvac_mode": hvac_mode},
            blocking=True,
        )


ADAPTER = ModeServiceAdapter()


def _mode_values(service: ServiceRef) -> dict[str, int]:
    raw = service.contract_value("values", _DEFAULT_HA_TO_MODE)
    if not isinstance(raw, dict) or not raw:
        raise ValueError("mode contract values must be a non-empty mapping")
    values: dict[str, int] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name:
            raise ValueError("mode contract values must use non-empty text keys")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("mode contract values must be integers")
        values[name] = value
    if len(set(values.values())) != len(values):
        raise ValueError("mode contract values must be unique")
    return values


def _wire_int(value: object) -> int | None:
    """Accept only wire-plausible numbers (int or integral float); reject bool/str."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
