"""Test the config flow without requiring a full HA install."""

import asyncio
import importlib
import sys

from tests.ha_stubs import install_homeassistant_stubs


def _get_flow():
    install_homeassistant_stubs()
    module_name = "custom_components.geely_auto.config_flow"
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    flow = module.GeelyAutoConfigFlow()
    from homeassistant.core import HomeAssistant

    flow.hass = HomeAssistant()
    flow.hass.data = {}
    flow.flow_id = "test_flow_123"
    return flow


def test_config_flow_shows_form_on_initial_step() -> None:
    flow = _get_flow()
    result = asyncio.run(flow.async_step_user(None))

    assert result["type"] == "form"
    assert result["step_id"] == "user"


def test_config_flow_creates_entry_on_token() -> None:
    flow = _get_flow()
    result = asyncio.run(
        flow.async_step_user(
            {
                "access_token": "valid_test_token",  # nosec-secret-scan (test fixture)
                "device_id": "dev12345678",
            }
        )
    )

    assert result["type"] == "create_entry"
    assert result["data"]["access_token"] == "valid_test_token"  # noqa: S105
    assert result["data"]["device_id"] == "dev12345678"
    assert result["data"]["demo_mode"] is False


def test_config_flow_shows_error_when_token_empty() -> None:
    flow = _get_flow()
    result = asyncio.run(flow.async_step_user({"access_token": ""}))

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


def test_config_flow_step_token_success() -> None:
    flow = _get_flow()
    result = asyncio.run(
        flow.async_step_token(
            {
                "access_token": "manual_token_123",  # nosec-secret-scan
                "device_id": "custom_dev_id",
            }
        )
    )

    assert result["type"] == "create_entry"
    assert result["data"]["access_token"] == "manual_token_123"  # noqa: S105
    assert result["data"]["device_id"] == "custom_dev_id"


def test_options_flow_custom_name() -> None:
    from homeassistant.config_entries import ConfigEntry
    from custom_components.geely_auto.config_flow import GeelyAutoOptionsFlowHandler
    from custom_components.geely_auto.const import CONF_CUSTOM_VEHICLE_NAME

    entry = ConfigEntry(
        data={},
        options={CONF_CUSTOM_VEHICLE_NAME: "旧昵称"},
        entry_id="test-entry",
    )
    options_flow = GeelyAutoOptionsFlowHandler(entry)

    # Step 1: Initial form display
    form = asyncio.run(options_flow.async_step_init())
    assert form["type"] == "form"
    assert form["step_id"] == "init"

    # Step 2: Submit new vehicle name
    result = asyncio.run(options_flow.async_step_init({CONF_CUSTOM_VEHICLE_NAME: "星越L·东方曜"}))
    assert result["type"] == "create_entry"
    assert result["data"][CONF_CUSTOM_VEHICLE_NAME] == "星越L·东方曜"
