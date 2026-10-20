"""Huawei `colour.red/green/blue` RGB service adapter."""

from __future__ import annotations

from ..models import ServiceRef


class ColourServiceAdapter:
    service_id = "colour"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "colour":
            raise ValueError("colour requires st: colour")
        if service.contract:
            raise ValueError("colour does not support contract overrides")

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("light."):
            raise ValueError("colour requires exactly one light entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state in {"unknown", "unavailable"}:
            return {}
        rgb = state.attributes.get("rgb_color")
        if not _valid_rgb(rgb):
            return {}
        red, green, blue = rgb
        return {"red": red, "green": green, "blue": blue}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        if not payload or any(key not in {"red", "green", "blue"} for key in payload):
            return
        state = hass.states.get(entity_ids[0])
        current = state.attributes.get("rgb_color") if state is not None else None
        rgb = list(current) if _valid_rgb(current) else [0, 0, 0]
        indices = {"red": 0, "green": 1, "blue": 2}
        for field, value in payload.items():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
                return
            rgb[indices[field]] = value
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_ids[0], "rgb_color": tuple(rgb)},
            blocking=True,
        )


def _valid_rgb(value: object) -> bool:
    return (
        isinstance(value, (tuple, list))
        and len(value) == 3
        and all(isinstance(component, int) and not isinstance(component, bool) and 0 <= component <= 255 for component in value)
    )


ADAPTER = ColourServiceAdapter()
