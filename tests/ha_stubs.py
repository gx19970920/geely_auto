"""Shared Home Assistant stubs for offline integration tests.

Home Assistant is not installed in this environment; the stubs mirror the
tiny API surface the integration actually touches so imports succeed and
behaviour stays honest.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Generic, TypeVar

_T = TypeVar("_T")


def install_homeassistant_stubs() -> None:
    """Install (or refresh) the minimal homeassistant module stubs."""
    homeassistant = ModuleType("homeassistant")
    config_entries = ModuleType("homeassistant.config_entries")
    core = ModuleType("homeassistant.core")
    const = ModuleType("homeassistant.const")
    helpers = ModuleType("homeassistant.helpers")
    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    components = ModuleType("homeassistant.components")
    sensor_module = ModuleType("homeassistant.components.sensor")
    entity_component = ModuleType("homeassistant.helpers.entity_component")

    class _Platform:
        SENSOR = "sensor"

    const.Platform = _Platform
    aiohttp_client.async_get_clientsession = lambda hass: object()

    class ConfigFlow:
        def __init_subclass__(cls, *, domain=None, **kwargs):
            del domain
            super().__init_subclass__(**kwargs)

        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}

    class ConfigEntry:
        def __init__(self, data=None, options=None, entry_id="test-entry"):
            self.data = data or {}
            self.options = options or {}
            self.entry_id = entry_id

    class HomeAssistant:
        pass

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator(Generic[_T]):
        def __init__(self, hass, logger, *, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None
            self.last_update_success = True

        async def async_config_entry_first_refresh(self):
            await self._async_update_data()

        async def _async_update_data(self):
            raise NotImplementedError

        async def async_refresh(self):
            try:
                self.data = await self._async_update_data()
                self.last_update_success = True
            except UpdateFailed:
                self.last_update_success = False

    class SensorEntity:
        _attr_available = True
        _attr_native_value = None
        _attr_unique_id = None

    class EntityComponent:
        pass

    config_entries.ConfigFlow = ConfigFlow
    config_entries.ConfigEntry = ConfigEntry
    core.HomeAssistant = HomeAssistant
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    sensor_module.SensorEntity = SensorEntity
    entity_component.EntityComponent = EntityComponent

    homeassistant.config_entries = config_entries
    homeassistant.core = core
    homeassistant.const = const
    homeassistant.helpers = helpers
    helpers.update_coordinator = update_coordinator
    helpers.aiohttp_client = aiohttp_client
    helpers.entity_component = entity_component
    homeassistant.components = components
    components.sensor = sensor_module

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.entity_component"] = entity_component
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.sensor"] = sensor_module


def reload_integration_modules() -> list[str]:
    """Reload integration modules after stub installation."""
    installed: list[str] = []
    for module_name in (
        "custom_components.geely_auto.const",
        "custom_components.geely_auto.api.exceptions",
        "custom_components.geely_auto.api.models",
        "custom_components.geely_auto.api.endpoints",
        "custom_components.geely_auto.api.signing",
        "custom_components.geely_auto.api.parsers",
        "custom_components.geely_auto.api.client",
        "custom_components.geely_auto.api",
        "custom_components.geely_auto.runtime",
        "custom_components.geely_auto.coordinator",
        "custom_components.geely_auto.entity",
        "custom_components.geely_auto.sensor",
        "custom_components.geely_auto",
    ):
        sys.modules.pop(module_name, None)
    for module_name in (
        "custom_components.geely_auto.const",
        "custom_components.geely_auto.api.exceptions",
        "custom_components.geely_auto.api.models",
        "custom_components.geely_auto.api.endpoints",
        "custom_components.geely_auto.api.signing",
        "custom_components.geely_auto.api.parsers",
        "custom_components.geely_auto.api.client",
        "custom_components.geely_auto.api",
        "custom_components.geely_auto.runtime",
        "custom_components.geely_auto.coordinator",
        "custom_components.geely_auto.entity",
        "custom_components.geely_auto.sensor",
        "custom_components.geely_auto",
    ):
        importlib.import_module(module_name)
        installed.append(module_name)
    return installed
