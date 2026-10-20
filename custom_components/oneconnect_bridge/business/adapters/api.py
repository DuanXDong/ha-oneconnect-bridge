"""Contract for one hard-coded Huawei service adapter."""

from __future__ import annotations

from typing import Protocol

from ..models import ServiceRef


class ServiceAdapter(Protocol):
    service_id: str

    def validate_service(self, service: ServiceRef) -> None:
        """Reject an unsupported Profile service type or contract override."""

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        """Reject entity bindings that cannot implement this service contract."""

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        """Convert Home Assistant state into one Huawei service payload."""

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        """Convert one Huawei service command into Home Assistant actions."""
