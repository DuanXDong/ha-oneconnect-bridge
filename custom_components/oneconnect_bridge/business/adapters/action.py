"""华为 ``action`` 服务：把云端下发的动作枚举翻译成 Home Assistant 服务调用。

同一个 `sid` 在 Profile 里承载两类语义：

- **开合**：``0=关 1=开 2=暂停``、``0=升 1=降 2=暂停``、``2=暂停 1=上升 0=下降`` 等，
  绑定 cover / valve
- **家电启停**：``0=暂停 1=启动``、``0=取消 1=启用 2=暂停`` 等，绑定
  switch / light / fan / humidifier / input_boolean / vacuum / media_player

适配器不内置“开/关/暂停”的整数，而是内置一套**角色词表**，由 ``commands`` 把
Profile 的枚举值绑到角色上；角色到 HA 服务的翻译留在 Python 里，按绑定实体域决定。

`sid`           : ``action``（取自 Profile 的 ``serviceId``，保持原样）
`serviceType`   : ``action``
默认契约来源
    prodId   : ``2N8I`` —— 晾衣机，``action`` 为 ``0=升 1=降 2=暂停``
    Profile  : https://smarthome-drcn.dbankcdn.com/device/guide/2N8I/2N8I.json
    常见性   : 全量目录中 536 个单品使用 ``serviceId=action``；特征名 ``action``
               占 98.5%，93.6% 为 RW（命令通道），96% 是 enum，几乎没有 min/max/step
    已验证   : 2026-10-22，把 5 个不同 Profile 绑到同一台 HA cover 实测（只改映射，
               通过映射重载生效，未重启）：
               - ``163S``（``0=关 1=开 2=暂停``，``{0: close, 1: open, 2: stop}``）
                 开 / 关 / 暂停全部正确
               - ``2G56``（``0=关 1=开 2=暂停``，同上契约）开 / 关 / 暂停全部正确
               - ``114M``（``0=升 1=降 2=暂停``，默认契约）开（升）/ 暂停正确
               - ``2MEJ``（``2=暂停 1=上升 0=下降``，同上契约）上升 / 下降正确；
                 暂停键被厂商卡片禁用，未能触发
               - ``2J2C``（``0=关窗帘 1=开窗帘 2=停止``，同上契约）开 / 关正确；
                 暂停由厂商卡片改用 ``opener`` 下发，本适配器按未绑定服务告警并跳过
               ``idle`` 已验证：cover 静止时按 stop 角色上报对应值。
               **未验证**：``states`` 覆盖项；``on`` / ``off`` / ``start`` / ``pause``
               角色（家电类卡片在服务不全时整体禁用或改用其它服务，实测无法从 App 触发）。

HA 转换
    cover / valve          : open → open_cover / open_valve，close → close_cover /
                             close_valve，stop → stop_cover
    switch / light / fan / humidifier / input_boolean
                           : on / start → turn_on，off / pause / cancel → turn_off
    vacuum                 : start / pause / cancel(stop) / return_home(return_to_base)
    media_player           : on/off → turn_on/turn_off，start → media_play，
                             pause → media_pause，cancel → media_stop
    climate                : on/off → turn_on/turn_off
    上报：HA 状态（opening / closing / cleaning / on / off 等）按域反推角色，
    再取 ``commands`` 中对应值；``idle`` 指定静止值（cover 缺省为 stop）。

角色词表（``contract.commands`` 的取值）
    open  close  stop     —— cover / valve
    on    off             —— switch / light / fan / humidifier / input_boolean / climate
    start pause cancel    —— vacuum / media_player
    return_home           —— vacuum 回充

    开关型实体（switch / light / fan / humidifier / input_boolean）只有通断两态，
    因此也接受 ``start``（= 通电）、``pause`` / ``cancel``（= 断电）作为别名；
    这是该域的**能力上限**，``pause`` 与 ``cancel`` 在上面无法区分。

contract
    commands : 值 -> 角色，例如 ``{0: close, 1: open, 2: stop}``。缺省只对
               cover / valve 生效（``0=开 1=关 2=停``）；其它域必须显式配置，
               否则第一次读写会告警并跳过。YAML 里 ``on`` / ``off`` 必须加引号
    states   : 可选，HA 状态 -> 值，优先于角色反推（未验证）
    idle     : 可选，静止/结束时报的值；缺省用该域空闲角色的值（cover -> stop）

边界
    厂商 App 卡片并不总用 ``action`` 发命令：有的把暂停或位置改走 ``opener``，
    有的在服务不全时禁用按钮。这类情况本适配器按“未知/未绑定服务”告警并跳过，不会误发
    其它命令；需要完整卡片体验时应同时绑定该 Profile 的其它服务。
"""

from __future__ import annotations

import logging

from ..models import ServiceRef


_LOGGER = logging.getLogger(__name__)

_WARNED: set[tuple[str, str, object]] = set()

_COVER_LIKE = ("cover", "valve")
_ON_OFF = ("switch", "light", "fan", "humidifier", "input_boolean")

# 角色 -> 各域的服务名。HA 调用方式留在 Python，contract 只负责“值=哪个角色”
_ACTIONS: dict[str, dict[str, str]] = {
    "cover": {"open": "open_cover", "close": "close_cover", "stop": "stop_cover"},
    "valve": {"open": "open_valve", "close": "close_valve"},
    "vacuum": {
        "start": "start",
        "pause": "pause",
        "cancel": "stop",
        "return_home": "return_to_base",
    },
    "media_player": {
        "on": "turn_on",
        "off": "turn_off",
        "start": "media_play",
        "pause": "media_pause",
        "cancel": "media_stop",
    },
    "climate": {"on": "turn_on", "off": "turn_off"},
}
# 开关型实体：start/pause/cancel 是 on/off 的别名（该域只有通断两态）
_TURN = {"on": "turn_on", "off": "turn_off", "start": "turn_on",
         "pause": "turn_off", "cancel": "turn_off"}

# HA 状态 -> 候选角色（按顺序取第一个在 commands 里有值的）
_READ_ROLES: dict[str, dict[str, tuple[str, ...]]] = {
    "cover": {"opening": ("open",), "closing": ("close",)},
    "valve": {"opening": ("open",), "closing": ("close",)},
    "vacuum": {"cleaning": ("start", "on"), "returning": ("return_home",),
               "paused": ("pause", "off")},
    "media_player": {"playing": ("start", "on"), "paused": ("pause", "off")},
    "climate": {"heat": ("on",), "cool": ("on",), "off": ("off",)},
}
for _domain in _ON_OFF:
    _ACTIONS[_domain] = dict(_TURN)
    _READ_ROLES[_domain] = {"on": ("on", "start"), "off": ("off", "cancel", "pause")}

# 静止/结束时按哪些角色反推上报值
_IDLE_ROLES = {"cover": ("stop",), "valve": ("close",)}

_DEFAULT_COMMANDS = {0: "open", 1: "close", 2: "stop"}
_ROLES = {
    "open", "close", "stop", "on", "off",
    "start", "pause", "cancel", "return_home",
}


class ActionServiceAdapter:
    service_id = "action"

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "action":
            raise ValueError("action requires st: action")
        unknown = set(dict(service.contract)) - {"commands", "states", "idle"}
        if unknown:
            raise ValueError(
                f"action has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        _contract(service)

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1:
            raise ValueError("action requires exactly one HA entity")
        domain, separator, _object_id = entity_ids[0].partition(".")
        if not separator or domain not in _ACTIONS:
            raise ValueError(
                "action requires one of: " + ", ".join(sorted(_ACTIONS))
            )

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state in {"unknown", "unavailable"}:
            return {}
        domain = entity_ids[0].partition(".")[0]
        commands, explicit, idle = _contract(service)
        field = _field_name(service)
        if explicit is not None and state.state in explicit:
            return {field: explicit[state.state]}
        commands = _resolve(service, domain, commands, entity_ids[0])
        if commands is None:
            return {}
        candidates = _READ_ROLES[domain].get(state.state)
        if candidates:
            value = _first_value(commands, candidates)
            if value is not None:
                return {field: value}
            _warn_once(
                ("action", entity_ids[0], state.state),
                "action: no value for state %r" % (state.state,),
            )
            return {}
        if idle is None:
            idle = _first_value(commands, _IDLE_ROLES.get(domain, ()))
        return {field: idle} if idle is not None else {}

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        raw = payload.get(_field_name(service))
        if raw is None and _field_name(service) != "action":
            raw = payload.get("action")
        if isinstance(raw, bool) or not isinstance(raw, int):
            return
        domain = entity_ids[0].partition(".")[0]
        commands, _explicit, _idle = _contract(service)
        commands = _resolve(service, domain, commands, entity_ids[0])
        if commands is None:
            return
        role = commands.get(raw)
        if role is None:
            _warn_once(("action", entity_ids[0], raw), "action: unhandled value %r" % (raw,))
            return
        await hass.services.async_call(
            domain, _ACTIONS[domain][role], {"entity_id": entity_ids[0]}, blocking=True
        )


ADAPTER = ActionServiceAdapter()


def _field_name(service: ServiceRef) -> str:
    """Use the Profile characteristic name for sid aliases such as leftAction."""

    return "action" if service.service_id == "action" else service.service_id


def _contract(
    service: ServiceRef,
) -> tuple[dict[int, str], dict[str, int] | None, int | None]:
    """解析并校验 ``commands`` / ``states`` / ``idle``。"""

    raw_commands = service.contract_value("commands")
    if raw_commands is None:
        commands = dict(_DEFAULT_COMMANDS)
    elif not isinstance(raw_commands, dict) or not raw_commands:
        raise ValueError("action contract commands must be a non-empty mapping")
    else:
        commands = {}
        for value, role in raw_commands.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("action contract commands keys must be integers")
            if not isinstance(role, str) or role not in _ROLES:
                raise ValueError(
                    "action contract commands values must be one of: "
                    + ", ".join(sorted(_ROLES))
                    + " (quote YAML booleans such as 'on' / 'off')"
                )
            commands[value] = role

    raw_states = service.contract_value("states")
    if raw_states is None:
        states: dict[str, int] | None = None
    elif not isinstance(raw_states, dict) or not raw_states:
        raise ValueError("action contract states must be a non-empty mapping")
    else:
        states = {}
        for key, value in raw_states.items():
            if not isinstance(key, str) or not key:
                raise ValueError(
                    "action contract states keys must be non-empty text "
                    "(quote YAML booleans such as 'on' / 'off')"
                )
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("action contract states values must be integers")
            states[key] = value

    raw_idle = service.contract_value("idle")
    if raw_idle is None:
        idle: int | None = None
    elif isinstance(raw_idle, bool) or not isinstance(raw_idle, int):
        raise ValueError("action contract idle must be an integer")
    else:
        idle = raw_idle
    return commands, states, idle


def _resolve(
    service: ServiceRef, domain: str, commands: dict[int, str], entity: str
) -> dict[int, str] | None:
    """返回该域可用的「值 -> 角色」表；不匹配时告警一次并返回 ``None``。"""

    if service.contract_value("commands") is None and domain not in _COVER_LIKE:
        _warn_once(
            ("action", entity, "commands"),
            "action: %s needs explicit contract.commands" % domain,
        )
        return None
    supported = _ACTIONS[domain]
    bad = sorted({role for role in commands.values() if role not in supported})
    if bad:
        _warn_once(
            ("action", entity, tuple(bad)),
            "action: role %s does not apply to %s" % ("/".join(bad), domain),
        )
        return None
    return commands


def _first_value(commands: dict[int, str], roles: tuple[str, ...]) -> int | None:
    """按候选角色顺序找第一个有值可用的枚举值。"""

    for role in roles:
        for value, candidate in commands.items():
            if candidate == role:
                return value
    return None


def _warn_once(key: tuple[str, str, object], message: str) -> None:
    if key in _WARNED:
        return
    _WARNED.add(key)
    _LOGGER.warning(message)
