"""Shared Home Assistant stubs for offline integration tests.

Home Assistant is not installed in this environment; the stubs mirror the
tiny API surface the integration actually touches so imports succeed and
behaviour stays honest.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any, Generic, TypeVar

_T = TypeVar("_T")


def install_homeassistant_stubs() -> None:  # noqa: C901, PLR0915
    """Install (or refresh) the minimal homeassistant module stubs."""

    if "homeassistant" in sys.modules and hasattr(
        sys.modules["homeassistant"], "config_entries"
    ):
        return
    homeassistant = ModuleType("homeassistant")

    config_entries = ModuleType("homeassistant.config_entries")
    core = ModuleType("homeassistant.core")
    core.callback = lambda func: func
    const = ModuleType("homeassistant.const")
    helpers = ModuleType("homeassistant.helpers")
    update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
    aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
    components = ModuleType("homeassistant.components")
    sensor_module = ModuleType("homeassistant.components.sensor")
    entity_component = ModuleType("homeassistant.helpers.entity_component")

    entity_module = ModuleType("homeassistant.helpers.entity")

    class _Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        BUTTON = "button"

    const.Platform = _Platform
    aiohttp_client.async_get_clientsession = lambda hass: object()

    class ConfigFlow:
        def __init_subclass__(cls, *, domain=None, **kwargs):
            del domain
            super().__init_subclass__(**kwargs)

        def async_abort(self, *, reason: str) -> dict[str, str]:
            return {"type": "abort", "reason": reason}

        def async_show_menu(
            self,
            *,
            step_id: str,
            menu_options: list[str],
            description_placeholders: dict[str, str] | None = None,
        ) -> dict[str, object]:
            return {
                "type": "menu",
                "step_id": step_id,
                "menu_options": menu_options,
            }

        def async_external_step(
            self,
            *,
            step_id: str,
            url: str,
            description_placeholders: dict[str, str] | None = None,
        ) -> dict[str, object]:
            return {
                "type": "external",
                "step_id": step_id,
                "url": url,
            }

        def async_external_step_done(
            self,
            *,
            next_step_id: str,
        ) -> dict[str, object]:
            return {
                "type": "external_done",
                "step_id": next_step_id,
            }

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: object = None,
            errors: dict[str, str] | None = None,
        ) -> dict[str, object]:
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(
            self,
            *,
            title: str,
            data: dict[str, object],
        ) -> dict[str, object]:
            return {"type": "create_entry", "title": title, "data": data}

        async def async_set_unique_id(
            self, unique_id: str, *, raise_on_progress: bool = True
        ) -> None:
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            pass

    class OptionsFlow:
        def __init__(self, config_entry: Any = None) -> None:
            self.config_entry = config_entry

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: object = None,
            errors: dict[str, str] | None = None,
        ) -> dict[str, object]:
            return {"type": "form", "step_id": step_id, "errors": errors or {}}

        def async_create_entry(
            self,
            *,
            title: str = "",
            data: dict[str, object],
        ) -> dict[str, object]:
            return {"type": "create_entry", "title": title, "data": data}

    class ConfigEntry:
        def __init__(self, data=None, options=None, entry_id="test-entry"):
            self.data = data or {}
            self.options = options or {}
            self.entry_id = entry_id

    class FlowManager:
        async def async_configure(self, flow_id: str, user_input=None):
            return {"type": "configure", "flow_id": flow_id}

    class ConfigEntries:
        def __init__(self):
            self.flow = FlowManager()
            self._entries: list[Any] = []

        def async_entries(self, domain: str | None = None) -> list[Any]:
            return list(self._entries)

        def async_update_entry(
            self,
            entry: Any,
            data: dict[str, Any] | None = None,
            options: dict[str, Any] | None = None,
        ) -> None:
            if data is not None:
                entry.data.update(data)
            if options is not None:
                entry.options.update(options)

        async def async_forward_entry_setups(self, entry: Any, platforms: list[Any]) -> None:
            pass

        async def async_unload_platforms(self, entry: Any, platforms: list[Any]) -> bool:
            return True

    webhook_module = ModuleType("homeassistant.components.webhook")
    webhook_module.async_register = lambda hass, domain, name, webhook_id, handler: None
    webhook_module.async_unregister = lambda hass, webhook_id: None
    webhook_module.async_generate_url = lambda hass, webhook_id: f"/api/webhook/{webhook_id}"
    sys.modules["homeassistant.components.webhook"] = webhook_module

    class HttpComponent:
        def register_view(self, view: Any) -> None:
            pass

    class HomeAssistant:
        def __init__(self):
            self.data: dict[str, Any] = {}
            self.config_entries = ConfigEntries()
            self.http = HttpComponent()
            self.config: dict[str, Any] = {}

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

    class Entity:
        _attr_has_entity_name = False
        _attr_unique_id = None
        _attr_device_info = None
        _attr_name = None
        _attr_translation_key = None
        _attr_available = True

        @property
        def unique_id(self) -> str | None:
            return self._attr_unique_id

        def async_write_ha_state(self) -> None:
            pass

        def async_on_remove(self, func) -> None:
            pass

    class SensorDeviceClass:
        BATTERY = "battery"
        DISTANCE = "distance"
        PRESSURE = "pressure"
        TEMPERATURE = "temperature"
        TIMESTAMP = "timestamp"
        VOLTAGE = "voltage"
        VOLUME_STORAGE = "volume_storage"

    class SensorEntity(Entity):
        _attr_available = True
        _attr_native_value = None
        _attr_unique_id = None
        _attr_native_unit_of_measurement = None
        _attr_device_class = None

    sensor_module.SensorDeviceClass = SensorDeviceClass
    sensor_module.SensorEntity = SensorEntity

    binary_sensor_module = ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorEntity(Entity):
        _attr_available = True
        _attr_is_on = None
        _attr_unique_id = None
        _attr_device_class = None

    class BinarySensorDeviceClass:
        DOOR = "door"
        WINDOW = "window"
        LOCK = "lock"
        RUNNING = "running"
        BATTERY_CHARGING = "battery_charging"

    binary_sensor_module.BinarySensorEntity = BinarySensorEntity
    binary_sensor_module.BinarySensorDeviceClass = BinarySensorDeviceClass

    button_module = ModuleType("homeassistant.components.button")

    class ButtonEntity(Entity):
        _attr_available = True
        _attr_unique_id = None
        _attr_device_class = None

        async def async_press(self) -> None:
            pass

    button_module.ButtonEntity = ButtonEntity
    button_module.ButtonDeviceClass = object()

    class EntityComponent:
        pass

    entity_module.Entity = Entity
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
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
    helpers.entity = entity_module
    helpers.update_coordinator = update_coordinator
    helpers.aiohttp_client = aiohttp_client
    helpers.entity_component = entity_component
    http_module = ModuleType("homeassistant.components.http")

    class HomeAssistantView:
        url = ""
        name = ""
        requires_auth = True

        def json(self, result: Any, status_code: int = 200) -> Any:
            return {"result": result, "status": status_code}

        def json_message(
            self, message: str, status_code: int = 200, message_code: str | None = None
        ) -> Any:
            return {"message": message, "status": status_code}

    http_module.HomeAssistantView = HomeAssistantView
    components.http = http_module
    components.button = button_module

    homeassistant.components = components
    components.sensor = sensor_module
    components.binary_sensor = binary_sensor_module
    components.button = button_module
    components.http = http_module

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.entity"] = entity_module
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.entity_component"] = entity_component
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.sensor"] = sensor_module
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor_module
    sys.modules["homeassistant.components.button"] = button_module
    sys.modules["homeassistant.components.http"] = http_module


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
        "custom_components.geely_auto.binary_sensor",
        "custom_components.geely_auto.button",
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
        "custom_components.geely_auto.binary_sensor",
        "custom_components.geely_auto.button",
        "custom_components.geely_auto",
    ):
        importlib.import_module(module_name)
        installed.append(module_name)
    return installed
