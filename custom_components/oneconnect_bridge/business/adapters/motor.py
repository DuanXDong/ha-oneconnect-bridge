"""Huawei ``motor`` service: curtain / drying-rack open, close and stop.

Default contract source
    prodId    : ``100K`` -- motorised curtain
    Profile   : https://smarthome-drcn.dbankcdn.com/device/guide/100K/100K.json
    common    : yes -- motorised curtains and drying racks share the same three
                button semantics (open / close / stop)
    verified  : 2026-10-21, two ``100K`` curtains -- ``mode`` 1 / 2 / 3 reach
                ``open_cover`` / ``close_cover`` / ``stop_cover`` (physical
                open / close / stop), and ``direction`` is reported from the
                Profile enum

Contract (every key is optional; the default reproduces the Profile above)
    direction       : int reported for the ``direction`` characteristic.  The
                      Profile enum is ``1`` forward (clockwise) / ``2`` reverse
                      (counter-clockwise); it is the device's static setting,
                      not an entity state.  Verified: both curtains report the
                      default ``1``; reporting ``2`` after enabling the motor's
                      reverse setting is possible, but that combination is not
                      part of the accepted configuration (candidate).
    open/close/stop : enum values of the ``mode`` characteristic (default
                      ``1`` / ``2`` / ``3``) -- candidate, only the default has
                      been observed so far.

The characteristic name (``mode``, ``operationMode`` is accepted as well) and the
HA cover services stay in this module: a Profile that names the characteristic
differently needs this adapter extended, not a new one.

If an HA cover's ``open_cover`` / ``close_cover`` move the device the opposite
way (observed on some motors), fix it at the device by
enabling its reverse setting -- that is the Profile's ``direction`` = ``2``.  Do
not put it in a contract: per the adapter contribution guide the HA call mapping
stays in Python, and a per-entity swap here would make the adapter device
specific.
"""

from __future__ import annotations

import logging

from ..models import ServiceRef


_LOGGER = logging.getLogger(__name__)

# Report an unhandled cloud value once, so a wrong contract is visible in the log
# without flooding it while the app retries the same button.
_WARNED: set[tuple[str, object]] = set()


def _warn_unhandled(adapter: str, value: object, *, mapped: object = None) -> None:
    key = (adapter, value)
    if key in _WARNED:
        return
    _WARNED.add(key)
    if mapped is None or mapped == value:
        _LOGGER.warning(
            "%s: unhandled value %r has no Home Assistant mapping", adapter, value
        )
    else:
        _LOGGER.warning(
            "%s: unhandled value %r (mapped to %r) has no Home Assistant action",
            adapter,
            value,
            mapped,
        )


class MotorServiceAdapter:
    service_id = "motor"
    # Characteristic name used by the Profile (``operationMode`` is a tolerated
    # alias seen on other products).
    _fields = ("mode", "operationMode")
    # Cloud semantics -> HA cover service; the call mapping stays in Python.
    _actions = {"open": "open_cover", "close": "close_cover", "stop": "stop_cover"}
    # Profile ``mode`` enum defaults.
    _defaults = {"open": 1, "close": 2, "stop": 3}

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "motor":
            raise ValueError("motor requires st: motor")
        unknown = set(dict(service.contract)) - {"direction", "open", "close", "stop"}
        if unknown:
            raise ValueError(
                f"motor has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        for name in ("direction", *self._defaults):
            value = service.contract_value(name, self._defaults.get(name, 1))
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"motor contract {name} must be an integer")
        direction = int(service.contract_value("direction", 1))
        if direction not in {1, 2}:
            raise ValueError("motor contract direction must be 1 or 2")
        values = list(self._values(service).values())
        if len(set(values)) != len(values):
            raise ValueError("motor contract must map open, close and stop apart")

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("cover."):
            raise ValueError("motor requires exactly one cover entity")

    def _values(self, service: ServiceRef) -> dict[str, int]:
        """Return the ``mode`` value of each action."""

        return {
            name: int(service.contract_value(name, default))
            for name, default in self._defaults.items()
        }

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        # ``direction`` is a static device setting, so there is no entity to read.
        return {"direction": int(service.contract_value("direction", 1))}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        raw = next((payload[field] for field in self._fields if field in payload), None)
        if isinstance(raw, bool) or not isinstance(raw, int):
            return
        for name, value in self._values(service).items():
            if value == raw:
                await hass.services.async_call(
                    "cover",
                    self._actions[name],
                    {"entity_id": entity_ids[0]},
                    blocking=True,
                )
                return
        # Values 4..12 (target percentage, motor reverse, tilt, ...) belong to
        # other services of the Profile, so they are reported but not handled.
        _warn_unhandled("motor/mode", raw)


ADAPTER = MotorServiceAdapter()
