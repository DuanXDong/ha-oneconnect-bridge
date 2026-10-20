from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .business.adapters import get_service_adapter
from .business.models import ChildPlan


_LOGGER = logging.getLogger(__name__)


class HAEntityBridge:
    """Delegate every selected Huawei service to its service adapter."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    def read_child_state(self, child: ChildPlan) -> dict[str, dict[str, object]]:
        result = self._run(self._async_read_child_state(child))
        _LOGGER.debug("HA adapter state snapshot child=%s state=%s", child.key, result)
        return result

    def apply_child_command(
        self, child: ChildPlan, service_id: str, payload: dict[str, object]
    ) -> None:
        _LOGGER.debug(
            "HA adapter command received child=%s sid=%s payload=%s",
            child.key,
            service_id,
            payload,
        )
        self._run(self._async_apply_child_command(child, service_id, payload))

    def setup_state_listener(self, plan, callback):
        """Forward adapter-bound HA state changes to the gateway worker."""

        entity_ids = {
            entity_id
            for child in plan.children
            for binding in child.bindings
            for entity_id in binding.entity_ids
            if entity_id
        }
        if not entity_ids:
            return lambda: None

        async def state_changed(event) -> None:
            entity_id = event.data.get("entity_id")
            for child in plan.children:
                if not any(
                    entity_id in binding.entity_ids
                    for binding in child.bindings
                ):
                    continue
                snapshot = await self._async_read_child_state(child)
                _LOGGER.debug(
                    "HA adapter state event child=%s entity=%s snapshot=%s",
                    child.key,
                    entity_id,
                    snapshot,
                )
                callback(child.key, snapshot)

        return async_track_state_change_event(self._hass, entity_ids, state_changed)

    def schedule_startup_sync(self, plan, callback, *, attempts: int = 12):
        """Retry adapter snapshots while HA entities/cloud session restore."""

        remaining = attempts
        cancel_handle = None

        async def retry(_now) -> None:
            nonlocal remaining, cancel_handle
            pending = False
            for child in plan.children:
                snapshot = await self._async_read_child_state(child)
                if snapshot:
                    _LOGGER.debug(
                        "Startup adapter snapshot child=%s state=%s",
                        child.key,
                        snapshot,
                    )
                    if callback(child.key, snapshot) is False:
                        pending = True
                else:
                    pending = True
            remaining -= 1
            if pending and remaining > 0:
                cancel_handle = async_call_later(self._hass, 5, retry)

        cancel_handle = async_call_later(self._hass, 2, retry)

        def cancel() -> None:
            if cancel_handle is not None:
                cancel_handle()

        return cancel

    def _run(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._hass.loop)
        return future.result(timeout=15)

    async def _async_read_child_state(
        self, child: ChildPlan
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        services = {service.service_id: service for service in child.services}
        for binding in child.bindings:
            data = await get_service_adapter(binding.service_id).read_state(
                self._hass, services[binding.service_id], binding.entity_ids
            )
            if data:
                result[binding.service_id] = data
        return result

    async def _async_apply_child_command(
        self, child: ChildPlan, service_id: str, payload: dict[str, object]
    ) -> None:
        binding = next(
            (item for item in child.bindings if item.service_id == service_id), None
        )
        if binding is None:
            _LOGGER.warning(
                "Ignoring command for unbound child service child=%s sid=%s",
                child.key,
                service_id,
            )
            return
        await get_service_adapter(service_id).apply_command(
            self._hass,
            next(item for item in child.services if item.service_id == service_id),
            binding.entity_ids,
            payload,
        )
