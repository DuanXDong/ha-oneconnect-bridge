from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductSpec:
    prod_id: str
    sub_prod_id: str
    device_type: str
    manufacturer: str
    model: str
    device_name: str
    protocol_type: int
    setup_type: int
    known_fields_only: bool = False


@dataclass(frozen=True)
class ServiceRef:
    service_type: str
    service_id: str
    contract: tuple[tuple[str, object], ...] = ()

    def contract_value(self, key: str, default: object = None) -> object:
        return dict(self.contract).get(key, default)


@dataclass(frozen=True)
class ServiceBinding:
    service_id: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChildPlan:
    key: str
    product: ProductSpec
    friendly_name: str | None
    room: str | None
    services: tuple[ServiceRef, ...]
    bindings: tuple[ServiceBinding, ...] = ()


@dataclass(frozen=True)
class GatewayPlan:
    gateway_serial: str | None
    children: tuple[ChildPlan, ...]
