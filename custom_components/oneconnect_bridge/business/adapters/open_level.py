"""Huawei ``openLevel`` service: opening percentage (current position).

Default contract source
    prodId    : ``100K`` -- motorised curtain
    Profile   : https://smarthome-drcn.dbankcdn.com/device/guide/100K/100K.json
    common    : yes -- motorised curtains expose ``currentLevel`` / ``targetLevel``
                in percent
    verified  : 2026-10-21, two ``100K`` curtains -- the Profile range ``0..100``
                (``targetLevel`` read/write, ``currentLevel`` read-only, step 1)
                is reported and commanded; while the cover is idle
                ``targetLevel`` is reported as well, because the vendor card
                reads it back to place its slider (without it the slider starts
                in the middle).

Contract (every key is optional; the default reproduces the common Profile)
    min/max : int range of the characteristic -- candidate; the default
              ``0`` / ``100`` is what ``100K`` declares, a Profile with a
              narrower range overrides it
    step    : int step of the characteristic -- candidate
    invert  : bool, the reported/commanded percentage is mirrored -- verified
              with ``100K``: after enabling the motor's reverse setting the
              position reports mirror (position ``100`` is physically closed),
              so both curtains run with ``invert: true``

The characteristic names (``currentLevel`` / ``targetLevel``) stay in this
module: a Profile that names them differently needs this adapter extended.
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


class OpenLevelServiceAdapter:
    service_id = "openLevel"
    # While the cover is idle the target equals the current position.
    _idle_states = frozenset({"open", "closed"})

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "openLevel":
            raise ValueError("openLevel requires st: openLevel")
        unknown = set(dict(service.contract)) - {"min", "max", "step", "invert"}
        if unknown:
            raise ValueError(
                f"openLevel has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        minimum = service.contract_value("min", 0)
        maximum = service.contract_value("max", 100)
        for name, value in (("min", minimum), ("max", maximum)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"openLevel contract {name} must be an integer")
        step = service.contract_value("step", 1)
        if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
            raise ValueError("openLevel contract step must be a positive integer")
        if not 0 <= minimum < maximum <= 100:
            raise ValueError("openLevel contract must be within 0..100")
        if (maximum - minimum) % step != 0:
            raise ValueError("openLevel contract step must divide its range")
        if not isinstance(service.contract_value("invert", False), bool):
            raise ValueError("openLevel contract invert must be boolean")

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("cover."):
            raise ValueError("openLevel requires exactly one cover entity")

    def _bounds(self, service: ServiceRef) -> tuple[int, int, int, bool]:
        """Return ``(min, max, step, invert)``."""

        return (
            int(service.contract_value("min", 0)),
            int(service.contract_value("max", 100)),
            int(service.contract_value("step", 1)),
            bool(service.contract_value("invert", False)),
        )

    def _to_cloud(self, service: ServiceRef, position: int) -> int:
        """Map a 0..100 HA position onto the Profile range (direction, step)."""

        minimum, maximum, step, invert = self._bounds(service)
        percent = 100 - position if invert else position
        value = minimum + round(percent * (maximum - minimum) / 100)
        # Align to the Profile step, then clamp into the Profile range.
        value = minimum + round((value - minimum) / step) * step
        return max(minimum, min(maximum, value))

    def _to_position(self, service: ServiceRef, value: int) -> int | None:
        """Map a Profile value back onto 0..100, or ``None`` when out of range."""

        minimum, maximum, step, invert = self._bounds(service)
        if not minimum <= value <= maximum or (value - minimum) % step != 0:
            return None
        percent = (value - minimum) * 100 / (maximum - minimum)
        position = round(100 - percent if invert else percent)
        return max(0, min(100, position))

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state in {"unknown", "unavailable"}:
            return {}
        position = state.attributes.get("current_position")
        if isinstance(position, bool) or not isinstance(position, int):
            return {}
        if not 0 <= position <= 100:
            return {}
        value = self._to_cloud(service, position)
        payload: dict[str, object] = {"currentLevel": value}
        # Idle: the target is the current position.  While the cover moves the
        # field is left out so the cloud keeps the target the user asked for.
        if state.state in self._idle_states:
            payload["targetLevel"] = value
        return payload

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        target = payload.get("targetLevel")
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            return
        value = int(round(float(target)))
        position = self._to_position(service, value)
        if position is None:
            # Out of range or off the Profile step: ignore and report once.
            _warn_unhandled("openLevel/targetLevel", value)
            return
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": entity_ids[0], "position": position},
            blocking=True,
        )


ADAPTER = OpenLevelServiceAdapter()
