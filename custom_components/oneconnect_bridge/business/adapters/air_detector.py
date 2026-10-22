"""Huawei ``airDetector`` read-only temperature/humidity service adapter."""

from __future__ import annotations

import math

from ..models import ServiceRef


class AirDetectorServiceAdapter:
    service_id = "airDetector"
    _DEFAULT_TEMPERATURE_SCALE = 100
    _DEFAULT_HUMIDITY_SCALE = 100

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "airDetector":
            raise ValueError("airDetector requires st: airDetector")
        unknown = set(dict(service.contract)) - {
            "temperature_scale",
            "humidity_scale",
        }
        if unknown:
            raise ValueError(
                "airDetector has unsupported contract keys: "
                f"{', '.join(sorted(unknown))}"
            )
        _scales(service)

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 2 or len(set(entity_ids)) != 2:
            raise ValueError("airDetector requires two distinct sensor entities")
        if any(not entity_id.startswith("sensor.") for entity_id in entity_ids):
            raise ValueError("airDetector requires sensor entities")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        temperature_scale, humidity_scale = _scales(service)
        result: dict[str, object] = {}
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            if state is None or state.state in {"unknown", "unavailable"}:
                continue
            attributes = state.attributes
            device_class = attributes.get("device_class")
            unit = attributes.get("unit_of_measurement")
            measurement = _measurement_kind(device_class, unit)
            value = _number(state.state)
            if measurement == "temperature" and value is not None:
                value = _celsius(value, unit)
                if value is not None and -20 <= value <= 100:
                    result["temperature"] = round(value * temperature_scale)
            elif measurement == "humidity" and value is not None and 0 <= value <= 100:
                result["humidity"] = round(value * humidity_scale)
        return result

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        """The 113D Profile declares both airDetector characteristics read-only."""

        self.validate_service(service)
        self.validate_entities(entity_ids)


def _measurement_kind(device_class: object, unit: object) -> str | None:
    if device_class == "temperature":
        return "temperature"
    if device_class == "humidity":
        return "humidity"
    normalized = str(unit).strip().casefold()
    if normalized in {"°c", "c", "℃", "°f", "f", "℉", "fahrenheit", "k", "kelvin"}:
        return "temperature"
    if normalized in {"%", "%rh"}:
        return "humidity"
    return None


def _celsius(value: float, unit: object) -> float | None:
    normalized = str(unit).strip().casefold()
    if normalized in {"°f", "f", "℉", "fahrenheit"}:
        value = (value - 32) * 5 / 9
    elif normalized in {"k", "kelvin"}:
        value -= 273.15
    return value if math.isfinite(value) else None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _scales(service: ServiceRef) -> tuple[float, float]:
    values = (
        service.contract_value("temperature_scale", 100),
        service.contract_value("humidity_scale", 100),
    )
    scales: list[float] = []
    for name, value in zip(("temperature_scale", "humidity_scale"), values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"airDetector contract {name} must be numeric")
        try:
            scale = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError(f"airDetector contract {name} must be finite") from error
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"airDetector contract {name} must be positive and finite")
        scales.append(scale)
    return scales[0], scales[1]


ADAPTER = AirDetectorServiceAdapter()
