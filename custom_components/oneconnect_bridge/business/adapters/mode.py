"""Huawei ``mode`` service: working mode of an air conditioner.

Default contract source
    prodId    : ``A0NQ`` -- wall-mounted air conditioner
    Profile   : https://smarthome-drcn.dbankcdn.com/device/guide/A0NQ/A0NQ.json
    common    : yes -- air conditioners expose a ``mode`` enum
    verified  : candidate, 2026-10-22 -- the enum mapping is checked field by
                field against the Profile and has run for months on the legacy
                bridge (full panel, voice control). It is **not** verified over
                this repository's projection yet; promote it only after the five
                acceptance steps in ``docs/service-adapter-contributing.md``.

Contract (no key is opened here)
    The Profile enum is fixed: ``1`` auto / ``2`` cool / ``3`` heat /
    ``4`` fan_only / ``5`` dry. A Profile that enumerates the modes differently
    needs this adapter extended instead of a contract override.

Two rules from the device itself:

* An unmapped value is never reported. Passing a raw vendor value through makes
  the cloud drop the whole service (the air conditioner then shows only its
  power switch in the app).
* ``off`` has no enum value in the Profile, so the mode service stays silent
  while the entity is off. Power belongs to the ``switch`` service, which is
  bound with ``on_type: bool``; because that adapter rejects ``climate``
  entities the power state needs a holder switch (a template switch works).
"""

from __future__ import annotations

from ..models import ServiceRef

_HA_TO_MODE = {"auto": 1, "cool": 2, "heat": 3, "fan_only": 4, "dry": 5}
_MODE_TO_HA = {value: name for name, value in _HA_TO_MODE.items()}


class ModeServiceAdapter:
    service_id = "mode"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "mode":
            raise ValueError("mode requires st: mode")
        unknown = set(dict(service.contract))
        if unknown:
            raise ValueError(
                f"mode has unsupported contract keys: {', '.join(sorted(unknown))}"
            )

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("climate."):
            raise ValueError("mode requires exactly one climate entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None:
            return {}
        mode = _HA_TO_MODE.get(state.state)
        return {} if mode is None else {"mode": mode}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        mode = _wire_int(payload.get("mode"))
        hvac_mode = _MODE_TO_HA.get(mode) if mode is not None else None
        if hvac_mode is None:
            return
        state = hass.states.get(entity_ids[0])
        allowed = state.attributes.get("hvac_modes") if state else None
        if isinstance(allowed, list) and allowed and hvac_mode not in allowed:
            return
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": entity_ids[0], "hvac_mode": hvac_mode},
            blocking=True,
        )


ADAPTER = ModeServiceAdapter()


def _wire_int(value: object) -> int | None:
    """Accept only wire-plausible numbers (int or integral float); reject bool/str."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
