"""Huawei ``gasSensor`` read-only gas measurements adapter.

Default contract source
    prodId   : ``2GEB``
    Profile  : https://smarthome-drcn.dbankcdn.com/device/guide/2GEB/2GEB.json
    common   : specialized gas-detector measurements
    verified : implementation follows the Profile's read-only ``current``
               integer (0..100) and ``level`` enum (1/2/3); a real projection
               is still required

Bind entities in this order: current gas percentage, then an optional
qualitative level. The Profile does not define thresholds for deriving
``level`` from ``current``, so the adapter never guesses it.
"""

from __future__ import annotations

import math

from ..models import ServiceRef


class GasSensorServiceAdapter:
    service_id = "gasSensor"
    _LEVELS = {
        "1": 1,
        "normal": 1,
        "正常": 1,
        "2": 2,
        "harmful": 2,
        "有害": 2,
        "3": 3,
        "seriously harmful": 3,
        "严重有害": 3,
    }

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "gas":
            raise ValueError("gasSensor requires st: gas")
        if service.contract:
            raise ValueError("gasSensor does not accept contract overrides")

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if (
            not 1 <= len(entity_ids) <= 2
            or len(set(entity_ids)) != len(entity_ids)
            or any(not entity_id.startswith("sensor.") for entity_id in entity_ids)
        ):
            raise ValueError(
                "gasSensor requires a current sensor and an optional distinct level sensor"
            )

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        result: dict[str, object] = {}

        current = hass.states.get(entity_ids[0])
        if current is not None and current.state not in {"unknown", "unavailable"}:
            value = _current_value(current.state)
            if value is not None:
                result["current"] = value

        if len(entity_ids) == 2:
            level = hass.states.get(entity_ids[1])
            if level is not None and level.state not in {"unknown", "unavailable"}:
                value = self._LEVELS.get(str(level.state).strip().casefold())
                if value is not None:
                    result["level"] = value
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


def _current_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(number) or not 0 <= number <= 100:
        return None
    return int(round(number))


ADAPTER = GasSensorServiceAdapter()
