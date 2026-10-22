"""Huawei ``hcho.current`` adapter with optional threshold-to-enum level mapping.

默认契约来源
    prodId   : ``21DA`` —— 甲醛检测设备（空气检测器品类）
    Profile  : https://smarthome-drcn.dbankcdn.com/device/guide/21DA/21DA.json
    常见性   : 常见服务 —— 34 个 Profile 使用 serviceId=hcho；字段形态以 ``current``
               （28 台）为主，另有 ``currentFloat``（3 台，mg/m³）与
               ``actual`` + 告警阈值（3 台）
    已验证   : 2026-10-21 ~ 22，全部为真实投影（注册子设备、云端 ``dataSync``
               accepted、App 卡片正常渲染）。下面五个都是物模型，绑定同一支真实
               甲醛传感器，差别只在物模型本身：
               - ``21DA`` 空气检测器 ×2：``current`` 上报（``scale`` 1、整数 µg/m³），
                 Profile 无 ``level``
               - ``2487`` 空气检测器：仅 ``current``，无 ``level``
               - ``20KX`` 空气检测器：``level`` 四值 理想 / 一般 / 有害 / 严重有害
               - ``2QBO`` 空气检测器：``level`` 三值 正常 / 超标 / 严重超标
               - ``2P3N`` 空气净化器：``level`` 三值 优 / 良 / 差；只声明 ``hcho``
                 一个服务的净化器卡片同样正常渲染

contract（全部可选，默认值即复刻 21DA 的 Profile）
    scale/min/max : 值换算与钳制（默认 1 / 0 / 10000）
    level_map     : 把浓度换算成 Profile 的 ``level`` 枚举，条目形如
                    ``{max: 80, value: 1}``。``max`` 与上报的 ``current`` 同单位，
                    按升序匹配，超出最后一档时沿用最后一档的 ``value``；不配置则
                    不上报 ``level``。
                    18 个带 ``level`` 的 Profile 用了 10 种不同枚举，因此必须按
                    Profile 配置，不能写死在代码里。实测给 Profile **未声明**
                    ``level`` 的机型上报它，App 会静默忽略。
                    注意：Profile 只提供枚举集合，阈值数值取自本地健康标准
                    （如 0.08 mg/m³ = 80 µg/m³），本项是「Profile 枚举 + 本地
                    阈值策略」的组合。
"""

from __future__ import annotations

from ..models import ServiceRef


class HchoServiceAdapter:
    service_id = "hcho"
    _domains = {"sensor", "input_number", "number"}

    def validate_service(self, service: ServiceRef) -> None:
        if service.service_type != "hcho":
            raise ValueError("hcho requires st: hcho")
        unknown = set(dict(service.contract)) - {"scale", "min", "max", "level_map"}
        if unknown:
            raise ValueError(
                f"hcho has unsupported contract keys: {', '.join(sorted(unknown))}"
            )
        _limits(service)
        _levels(service)

    def validate_entities(self, entity_ids: tuple[str, ...]) -> None:
        if len(entity_ids) != 1:
            raise ValueError("hcho requires exactly one HA entity")
        domain, separator, _object_id = entity_ids[0].partition(".")
        if not separator or domain not in self._domains:
            raise ValueError("hcho requires a sensor, input_number or number entity")

    async def read_state(
        self, hass, service: ServiceRef, entity_ids: tuple[str, ...]
    ) -> dict[str, object]:
        self.validate_service(service)
        self.validate_entities(entity_ids)
        state = hass.states.get(entity_ids[0])
        if state is None or state.state in {"unknown", "unavailable"}:
            return {}
        try:
            number = float(state.state)
        except (TypeError, ValueError):
            return {}
        number *= float(service.contract_value("scale", 1))
        minimum, maximum = _limits(service)
        value = int(round(min(max(number, minimum), maximum)))
        payload: dict[str, object] = {"current": value}
        levels = _levels(service)
        if levels:
            payload["level"] = _level(levels, value)
        return payload

    async def apply_command(
        self,
        hass,
        service: ServiceRef,
        entity_ids: tuple[str, ...],
        payload: dict[str, object],
    ) -> None:
        # ``current`` 在部分 Profile 标为 RW，但写入甲醛读数没有语义，
        # 因此云端下发的写命令一律忽略。
        return


ADAPTER = HchoServiceAdapter()


def _limits(service: ServiceRef) -> tuple[float, float]:
    """返回 (min, max)，并校验 scale / min / max 的类型与次序。"""

    for key in ("scale", "min", "max"):
        value = service.contract_value(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"hcho contract {key} must be a number")
    minimum = float(service.contract_value("min", 0))
    maximum = float(service.contract_value("max", 10000))
    if minimum >= maximum:
        raise ValueError("hcho contract min must be smaller than max")
    return minimum, maximum


def _levels(service: ServiceRef) -> tuple[tuple[float, int], ...] | None:
    """解析并校验 ``level_map``，返回 ((max, value), ...) 或 ``None``。"""

    raw = service.contract_value("level_map")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("hcho contract level_map must be a non-empty list")
    result: list[tuple[float, int]] = []
    previous: float | None = None
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"max", "value"}:
            raise ValueError("hcho contract level_map entries must be {max, value}")
        maximum = item["max"]
        value = item["value"]
        if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
            raise ValueError("hcho contract level_map max must be a number")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("hcho contract level_map value must be an integer")
        if previous is not None and float(maximum) <= previous:
            raise ValueError("hcho contract level_map max must increase")
        previous = float(maximum)
        result.append((float(maximum), value))
    return tuple(result)


def _level(levels: tuple[tuple[float, int], ...], value: int) -> int:
    """按升序阈值取枚举值；超出最后一档时沿用最后一档。"""

    for maximum, enum in levels:
        if value <= maximum:
            return enum
    return levels[-1][1]

