"""Huawei ``alarm`` read-only service adapter.

Default contract source
    prodId   : ``2GEB``
    Profile  : https://smarthome-drcn.dbankcdn.com/device/guide/2GEB/2GEB.json
    common   : specialized gas-detector alarm state
    verified : implementation follows the Profile's read-only ``alarm`` bool
               enum (0 normal / 1 alarm); a real projection is still required
"""

from __future__ import annotations

from ..models import ServiceRef


class AlarmServiceAdapter:
    service_id = "alarm"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "alarm":
            raise ValueError("alarm requires st: alarm")
        if service.contract:
            raise ValueError("alarm does not accept contract overrides")

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("binary_sensor."):
            raise ValueError("alarm requires exactly one binary_sensor entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None:
            return {}
        if state.state == "on":
            return {"alarm": 1}
        if state.state == "off":
            return {"alarm": 0}
        return {}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)


ADAPTER = AlarmServiceAdapter()
