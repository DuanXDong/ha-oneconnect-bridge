"""Huawei ``cleanerRobot`` service: robot vacuum status and commands.

Default contract source
    prodId    : ``103K`` -- robot vacuum
    Profile   : https://smarthome-drcn.dbankcdn.com/device/guide/103K/103K.json
    common    : partly -- robot vacuums exist, but the Profile aggregates
                everything into this single vendor-defined service, so the
                enums below are that Profile's contract, not a general one
    verified  : candidate, 2026-10-22 -- enums checked against the Profile and
                running on the legacy bridge (start / pause / return-to-base via
                voice). Not verified over this repository's projection yet;
                promote after the five acceptance steps in
                ``docs/service-adapter-contributing.md``.

Profile characteristics
    status   : int, ``1`` returning / ``2`` cleaning / ``3`` standby /
               ``4`` charging / ``5`` scheduled run finished / ``6`` charge
               complete / ``7`` fault / ``8`` DC charging
    command  : int, ``1`` return to base / ``2`` start cleaning / ``3`` pause
    battery  : int 0..100
    mode / area / time are read by the Profile as well; this adapter neither
    reports nor commands them (room-cleaning selection stays on the Home
    Assistant side).

Status is reported from the Home Assistant vacuum state so the app card shows
activity instead of standby: cleaning 2 / paused 3 / returning 1 / docked 6 /
idle 3 / error 7. Unmapped states and commands are skipped rather than
forwarded; a value the cloud rejects takes the whole service down with it.
"""

from __future__ import annotations

from ..models import ServiceRef

_HA_STATE_TO_STATUS = {
    "cleaning": 2,
    "paused": 3,
    "returning": 1,
    "docked": 6,
    "idle": 3,
    "error": 7,
}
_COMMAND_TO_ACTION = {1: "return_to_base", 2: "start", 3: "pause"}


class CleanerRobotServiceAdapter:
    service_id = "cleanerRobot"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "cleanerRobot":
            raise ValueError("cleanerRobot requires st: cleanerRobot")
        unknown = set(dict(service.contract))
        if unknown:
            raise ValueError(
                "cleanerRobot has unsupported contract keys: "
                f"{', '.join(sorted(unknown))}"
            )

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("vacuum."):
            raise ValueError("cleanerRobot requires exactly one vacuum entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None:
            return {}
        data: dict[str, object] = {}
        status = _HA_STATE_TO_STATUS.get(state.state)
        if status is not None:
            data["status"] = status
        battery = _number(state.attributes.get("battery_level"))
        if battery is not None and 0 <= battery <= 100:
            data["battery"] = round(battery)
        return data

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        command = _wire_int(payload.get("command"))
        action = _COMMAND_TO_ACTION.get(command) if command is not None else None
        if action is None:
            return
        await hass.services.async_call(
            "vacuum", action, {"entity_id": entity_ids[0]}, blocking=True
        )


ADAPTER = CleanerRobotServiceAdapter()


def _number(value: object) -> float | None:
    """Coerce an HA state/attribute (int, float or numeric string) to float."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _wire_int(value: object) -> int | None:
    """Accept only wire-plausible numbers (int or integral float); reject bool/str."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
