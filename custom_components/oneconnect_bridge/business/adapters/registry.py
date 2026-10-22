"""Explicit registry of trusted Huawei service adapters."""

from __future__ import annotations

from .api import ServiceAdapter
from .alarm import ADAPTER as ALARM
from .air_detector import ADAPTER as AIR_DETECTOR
from .brightness import ADAPTER as BRIGHTNESS
from .cct import ADAPTER as CCT
from .colour import ADAPTER as COLOUR
from .gas_sensor import ADAPTER as GAS_SENSOR
from .hcho import ADAPTER as HCHO
from .humidity import ADAPTER as HUMIDITY
from .motor import ADAPTER as MOTOR
from .open_level import ADAPTER as OPEN_LEVEL
from .switch import ADAPTER as SWITCH
from .temperature import ADAPTER as TEMPERATURE


_SERVICE_ADAPTERS: dict[str, ServiceAdapter] = {
    adapter.service_id: adapter
    for adapter in (
        SWITCH,
        BRIGHTNESS,
        CCT,
        COLOUR,
        TEMPERATURE,
        HUMIDITY,
        AIR_DETECTOR,
        MOTOR,
        OPEN_LEVEL,
        HCHO,
        ALARM,
        GAS_SENSOR,
    )
}
for _service_id in ("switch1", "switch2", "switch3"):
    _SERVICE_ADAPTERS[_service_id] = SWITCH


def get_service_adapter(service_id: str) -> ServiceAdapter:
    try:
        return _SERVICE_ADAPTERS[service_id]
    except KeyError as error:
        raise ValueError(f"unknown Huawei service: {service_id}") from error
