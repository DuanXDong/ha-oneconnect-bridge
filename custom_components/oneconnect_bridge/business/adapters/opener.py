"""华为 ``opener`` 服务：窗帘 / 卷帘 / 开窗器的开合百分比。

`sid`           : ``opener``（取自 Profile 的 ``serviceId``，保持原样）
`serviceType`   : ``opener``
默认契约来源
    prodId   : ``2IHJ`` —— 开合帘，``current`` 只读、``target`` 读写，0..100、step 1
    Profile  : https://smarthome-drcn.dbankcdn.com/device/guide/2IHJ/2IHJ.json
    常见性   : 全量目录中 119 个单品使用 ``serviceId=opener``；其中 113 个的字段是
               ``current`` + ``target``（``current`` 只读、``target`` 读写，多数为
               ``0..100`` / ``step 1``）。其余 6 个为门控布尔、只有收藏位、
               字段名不同（``Current`` + ``opener``）或范围越界（``current 0..102``），
               都不属于“位置百分比”语义
    已验证   : 2026-10-22，5 个不同品类 Profile 绑同一台真实 HA ``cover`` 实测：
               ``2IHJ``（开合帘 ``01C``）、``117Q``（窗帘 ``01C``）、
               ``144R``（卷帘 ``04D``）、``2ACW``（开窗器 ``02C``）、
               ``141R``（百叶帘 ``01C``）。全部使用 ``contract: {invert: true}``：
               - 上报：5 台 ``current`` 一致，静止时同时上报 ``target``，
                 ``dataSync accepted errcode=0``
               - 下发：App 拖动滑块后 5 台都收到 ``target`` 并驱动
                 ``cover.set_cover_position``，物理方向正确
               - 无 ``unhandled value``，无命令处理错误

contract（全部可选）
    min/max : 特性范围（整数）—— **未验证**：5 个实测 Profile 都用默认 ``0`` / ``100``，
              非默认范围只有单测覆盖
    step    : 特性步长（整数）—— **未验证**：实测 Profile 的 ``step`` 取 1 或未声明，
              非 1 步长只有单测覆盖
    invert  : 布尔，位置取反 —— **已验证必需**：本适配器的 5 个实测 Profile 都需要
              ``invert: true``。它同时覆盖两种来源：
              ① Profile 的 ``target`` 语义是“关闭百分比”（如 ``2IHJ`` 的 descCh）
              ② 绑定的 HA 实体本身方向相反（例如 ZHA 里开了“已反转”的电机）
              两者都以实测物理方向为准，不要按 descCh 字面推断

HA 转换
    绑定：恰好 1 个 ``cover``
    上报：``current`` 始终上报；供厂商卡片摆放滑块用的 ``target`` 仅在静止
          （``open`` / ``closed``）时上报，运动过程中留空，由云端保留用户目标
    下发：``target`` → ``cover.set_cover_position``；越界或不符合步长时按未知值
          告警一次并跳过，不误发其它命令

字段名（``current`` / ``target``，``Current`` / ``Target`` 作为兼容别名）留在 Python
内；Profile 之间的范围、步长、方向差异通过 contract 表达，不新增同义适配器。

未验证
    - ``Current`` / ``Target`` 别名：实测 Profile 都使用小写字段名，别名只有单测覆盖
    - ``min`` / ``max`` / ``step`` 的非默认取值：同上
    - 未支持形态：只有门控布尔、只有收藏位、字段名为 ``Current`` + ``opener``、
      以及 ``current`` 范围越界（``0..102``）的 6 个单品
"""

from __future__ import annotations

import logging

from ..models import ServiceRef


_LOGGER = logging.getLogger(__name__)

_WARNED: set[tuple[str, object]] = set()


def _warn_unhandled(name: str, value: object) -> None:
    key = (name, value)
    if key in _WARNED:
        return
    _WARNED.add(key)
    _LOGGER.warning("%s: unhandled value %r has no Home Assistant mapping", name, value)


class OpenerServiceAdapter:
    service_id = "opener"
    # 字段名兼容（个别 Profile 用大写 Current）
    _current_fields = ("current", "Current")
    _target_fields = ("target", "Target")
    # 窗帘静止（未在运动）时，目标开合度等于当前位置
    _idle_states = frozenset({"open", "closed"})

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "opener":
            raise ValueError("opener requires st: opener")
        unknown = set(dict(service.contract)) - {"min", "max", "step", "invert"}
        if unknown:
            raise ValueError(
                f"opener has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        minimum = service.contract_value("min", 0)
        maximum = service.contract_value("max", 100)
        for name, value in (("min", minimum), ("max", maximum)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"opener contract {name} must be an integer")
        step = service.contract_value("step", 1)
        if isinstance(step, bool) or not isinstance(step, int) or step <= 0:
            raise ValueError("opener contract step must be a positive integer")
        if not 0 <= minimum < maximum <= 100:
            raise ValueError("opener contract must be within 0..100")
        if (maximum - minimum) % step != 0:
            raise ValueError("opener contract step must divide its range")
        if not isinstance(service.contract_value("invert", False), bool):
            raise ValueError("opener contract invert must be boolean")

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1 or not entity_ids[0].startswith("cover."):
            raise ValueError("opener requires exactly one cover entity")

    def _bounds(self, service: ServiceRef) -> tuple[int, int, int, bool]:
        """返回 (min, max, step, invert)。"""

        return (
            int(service.contract_value("min", 0)),
            int(service.contract_value("max", 100)),
            int(service.contract_value("step", 1)),
            bool(service.contract_value("invert", False)),
        )

    def _to_cloud(self, service: ServiceRef, position: int) -> int:
        """把 HA 的 0..100 位置换算成 Profile 范围内的值（含方向与步长）。"""

        minimum, maximum, step, invert = self._bounds(service)
        percent = 100 - position if invert else position
        value = minimum + round(percent * (maximum - minimum) / 100)
        value = minimum + round((value - minimum) / step) * step
        return max(minimum, min(maximum, value))

    def _to_position(self, service: ServiceRef, value: int) -> int | None:
        """把 Profile 值换算回 HA 的 0..100；越界或不符合步长时返回 ``None``。"""

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
        payload: dict[str, object] = {"current": value}
        # 静止时目标等于当前位置；运动过程中不报，让云端保留用户设定的目标
        if state.state in self._idle_states:
            payload["target"] = value
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
        raw = next(
            (payload[field] for field in self._target_fields if field in payload), None
        )
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return
        value = int(round(float(raw)))
        position = self._to_position(service, value)
        if position is None:
            _warn_unhandled("opener/target", value)
            return
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": entity_ids[0], "position": position},
            blocking=True,
        )


ADAPTER = OpenerServiceAdapter()
