"""Config flow for Geely Auto."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_VERSION,
    CONF_CUSTOM_VEHICLE_NAME,
    CONF_DEMO_MODE,
    CONF_DEVICE_ID,
    CONF_REFRESH_TOKEN,
    DEFAULT_APP_VERSION,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)

try:
    import voluptuous as vol
except ImportError:

    class _VolStub:
        def Schema(self, schema: Any) -> Any:  # noqa: N802
            return schema

        def Required(self, key: Any, default: Any = None) -> Any:  # noqa: N802, ARG002
            return key

        def Optional(self, key: Any, default: Any = None) -> Any:  # noqa: N802, ARG002
            return key

        def In(self, choices: Any) -> Any:  # noqa: N802
            return choices

    vol = _VolStub()


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Optional(CONF_DEVICE_ID, default=""): str,
        vol.Optional(CONF_REFRESH_TOKEN, default=""): str,
        vol.Optional(CONF_APP_VERSION, default=DEFAULT_APP_VERSION): str,
    }
)


class GeelyAutoConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for Geely Auto."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the user configuration step: direct token input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            access_token = str(user_input.get(CONF_ACCESS_TOKEN, "")).strip()
            if not access_token:
                errors["base"] = "invalid_auth"
            else:
                return self._create_entry_from_input(
                    demo=False,
                    access_token=access_token,  # nosec-secret-scan
                    refresh_token=str(user_input.get(CONF_REFRESH_TOKEN, "")).strip(),  # nosec-secret-scan
                    device_id=str(user_input.get(CONF_DEVICE_ID, "")).strip(),
                    app_version=str(user_input.get(CONF_APP_VERSION, "")).strip(),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle explicit token configuration step."""
        return await self.async_step_user(user_input)

    def _create_entry_from_input(
        self,
        *,
        demo: bool = False,
        access_token: str,
        refresh_token: str = "",
        device_id: str = "",
        app_version: str = "",
    ) -> FlowResult:
        """Construct the config entry result."""
        dev_id = device_id or str(uuid.uuid4())
        version = app_version or DEFAULT_APP_VERSION
        title = "吉利汽车 (星越L演示)" if demo else f"吉利汽车 ({dev_id[:8]})"
        return self.async_create_entry(
            title=title,
            data={
                CONF_DEMO_MODE: demo,
                CONF_ACCESS_TOKEN: access_token,  # nosec-secret-scan
                CONF_REFRESH_TOKEN: refresh_token,  # nosec-secret-scan
                CONF_DEVICE_ID: dev_id,
                CONF_APP_VERSION: version,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return GeelyAutoOptionsFlowHandler(config_entry)


class GeelyAutoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Geely Auto integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options (e.g. custom vehicle name)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_name = (
            self.config_entry.options.get(CONF_CUSTOM_VEHICLE_NAME)
            or self.config_entry.data.get(CONF_CUSTOM_VEHICLE_NAME)
            or "星越L·东方曜"
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_CUSTOM_VEHICLE_NAME, default=current_name): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
