"""Huawei `cct.colorTemperature` 2000..6500 Kelvin service adapter."""

from __future__ import annotations

from ..models import ServiceRef


class CctServiceAdapter:
    service_id = "cct"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "cct":
            raise ValueError("cct requires st: cct")
        unknown = set(dict(service.contract)) - {"min", "max", "step"}
        if unknown:
            raise ValueError(
                f"cct has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        _limits(service)

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("light."):
            raise ValueError("cct requires exactly one light entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state in {"unknown", "unavailable"}:
            return {}
        temperature = state.attributes.get("color_temp_kelvin")
        if isinstance(temperature, bool) or not isinstance(temperature, int):
            return {}
        minimum, maximum, step = _limits(service)
        if (
            not minimum <= temperature <= maximum
            or (temperature - minimum) % step != 0
        ):
            return {}
        return {"colorTemperature": temperature}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        temperature = payload.get("colorTemperature")
        if isinstance(temperature, bool) or not isinstance(temperature, int):
            return
        minimum, maximum, step = _limits(service)
        if (
            not minimum <= temperature <= maximum
            or (temperature - minimum) % step != 0
        ):
            return
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_ids[0], "color_temp_kelvin": temperature},
            blocking=True,
        )


ADAPTER = CctServiceAdapter()


def _limits(service: ServiceRef) -> tuple[int, int, int]:
    minimum = service.contract_value("min", 2000)
    maximum = service.contract_value("max", 6500)
    step = service.contract_value("step", 1)
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in (minimum, maximum, step)
    ):
        raise ValueError("cct contract min, max, and step must be integers")
    if not 1000 <= minimum < maximum <= 10000 or step <= 0:
        raise ValueError("cct contract must be within 1000..10000 with a positive step")
    if (maximum - minimum) % step != 0:
        raise ValueError("cct contract step must divide its range")
    return minimum, maximum, step
