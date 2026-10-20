"""Huawei `brightness.brightness` service adapter with a configurable range."""

from __future__ import annotations

from ..models import ServiceRef


class BrightnessServiceAdapter:
    service_id = "brightness"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "brightness":
            raise ValueError("brightness requires st: brightness")
        unknown = set(dict(service.contract)) - {"min", "max", "step"}
        if unknown:
            raise ValueError(
                f"brightness has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        _limits(service)

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("light."):
            raise ValueError("brightness requires exactly one light entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state != "on":
            return {}
        brightness = state.attributes.get("brightness")
        if isinstance(brightness, bool) or not isinstance(brightness, int):
            return {}
        if not 0 <= brightness <= 255:
            return {}
        minimum, maximum, step = _limits(service)
        value = minimum + round(brightness * (maximum - minimum) / 255)
        value = minimum + round((value - minimum) / step) * step
        return {"brightness": min(maximum, value)}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        brightness = payload.get("brightness")
        if isinstance(brightness, bool) or not isinstance(brightness, int):
            return
        minimum, maximum, step = _limits(service)
        if (
            not minimum <= brightness <= maximum
            or (brightness - minimum) % step != 0
        ):
            return
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": entity_ids[0],
                "brightness_pct": round(
                    (brightness - minimum) * 100 / (maximum - minimum)
                ),
            },
            blocking=True,
        )


ADAPTER = BrightnessServiceAdapter()


def _limits(service: ServiceRef) -> tuple[int, int, int]:
    minimum = service.contract_value("min", 0)
    maximum = service.contract_value("max", 255)
    step = service.contract_value("step", 1)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (minimum, maximum, step)):
        raise ValueError("brightness contract min, max, and step must be integers")
    if not 0 <= minimum < maximum <= 255 or step <= 0:
        raise ValueError("brightness contract must be within 0..255 with a positive step")
    if (maximum - minimum) % step != 0:
        raise ValueError("brightness contract step must divide its range")
    return minimum, maximum, step
