"""Huawei ``humidity`` measurement service adapter."""

from __future__ import annotations

import math

from ..models import ServiceRef


class HumidityServiceAdapter:
    service_id = "humidity"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "humidity":
            raise ValueError("humidity requires st: humidity")
        unknown = set(dict(service.contract)) - {"field", "target_field", "scale"}
        if unknown:
            raise ValueError(
                "humidity has unsupported contract keys: "
                f"{', '.join(sorted(unknown))}"
            )
        _measurement_contract(service)

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1:
            raise ValueError("humidity requires exactly one sensor or climate entity")
        domain, separator, object_id = entity_ids[0].partition(".")
        if not separator or not object_id or domain not in {"sensor", "climate"}:
            raise ValueError("humidity requires exactly one sensor or climate entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state in {"unknown", "unavailable"}:
            return {}
        field, target_field, scale = _measurement_contract(service)
        domain = entity_ids[0].partition(".")[0]
        if domain == "sensor":
            if field is None:
                return {}
            value = _humidity_value(state.state)
            return {field: _wire_number(value * scale)} if value is not None else {}

        attributes = state.attributes
        result: dict[str, object] = {}
        current = _humidity_value(attributes.get("current_humidity"))
        if field is not None and current is not None:
            result[field] = _wire_number(current * scale)
        target = _humidity_value(attributes.get("humidity"))
        if target is None:
            target = _humidity_value(attributes.get("target_humidity"))
        if target_field is not None and target is not None:
            result[target_field] = _wire_number(target * scale)
        return result

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        if entity_ids[0].partition(".")[0] != "climate":
            return
        _field, target_field, scale = _measurement_contract(service)
        if target_field is None:
            return
        wire_target = _command_number(payload.get(target_field))
        if wire_target is None:
            return
        target = wire_target / scale
        if not 0 <= target <= 100:
            return
        await hass.services.async_call(
            "climate",
            "set_humidity",
            {"entity_id": entity_ids[0], "humidity": target},
            blocking=True,
        )


def _measurement_contract(
    service: ServiceRef,
) -> tuple[str | None, str | None, float]:
    """Map HA percent to the Huawei field using ``scale`` in both directions."""

    field = service.contract_value("field", "current")
    target_field = service.contract_value("target_field", "target")
    scale = service.contract_value("scale", 1)
    if field == "":
        field = None
    elif not isinstance(field, str):
        raise ValueError("humidity contract field must be text")
    if target_field == "":
        target_field = None
    elif not isinstance(target_field, str):
        raise ValueError("humidity contract target_field must be text")
    if field is None and target_field is None:
        raise ValueError("humidity contract must enable a current or target field")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)):
        raise ValueError("humidity contract scale must be numeric")
    try:
        scale = float(scale)
    except (OverflowError, ValueError) as error:
        raise ValueError("humidity contract scale must be finite") from error
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("humidity contract scale must be positive and finite")
    return field, target_field, scale


def _humidity_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and 0 <= number <= 100 else None


def _command_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def _wire_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


ADAPTER = HumidityServiceAdapter()
