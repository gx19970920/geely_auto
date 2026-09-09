"""Test the config flow without requiring a full HA install."""

import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, patch

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


def test_config_flow_shows_menu_on_initial_step() -> None:
    flow = _get_flow()
    result = asyncio.run(flow.async_step_user(None))

    assert result["type"] == "menu"
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["sms", "token", "demo"]


def test_config_flow_creates_entry_on_demo_mode() -> None:
    flow = _get_flow()
    result = asyncio.run(flow.async_step_user({"demo_mode": True}))

    assert result["type"] == "create_entry"
    assert "演示" in str(result["title"])
    assert result["data"]["demo_mode"] is True


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


def test_config_flow_shows_error_without_token_or_demo() -> None:
    flow = _get_flow()
    result = asyncio.run(flow.async_step_token({"access_token": ""}))

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


def test_config_flow_sms_phone_step() -> None:
    flow = _get_flow()
    result = asyncio.run(flow.async_step_sms_phone(None))
    assert result["type"] == "form"
    assert result["step_id"] == "sms_phone"

    result2 = asyncio.run(
        flow.async_step_sms_phone({"phone": "13800138000"})  # nosec-secret-scan
    )
    assert result2["type"] == "external"
    assert result2["step_id"] == "sms_captcha"
    assert "flow_id=test_flow_123" in str(result2["url"])


def test_config_flow_sms_captcha_callback_done() -> None:
    flow = _get_flow()
    flow._phone = "13800138000"  # nosec-secret-scan
    flow.hass.data = {
        "geely_auto": {
            "captcha_results": {
                "test_flow_123": {
                    "lot_number": "mock_lot",
                    "captcha_output": "mock_output",
                    "pass_token": "mock_pass",
                    "gen_time": "12345",
                }
            }
        }
    }
    result = asyncio.run(flow.async_step_sms_captcha())
    assert result["type"] == "external_done"
    assert result["step_id"] == "sms_code"
    assert flow._captcha_data is not None


def test_config_flow_sms_code_flow_lifecycle() -> None:
    flow = _get_flow()
    flow._phone = "13800138000"  # nosec-secret-scan
    flow._device_id = "test_dev_id"
    flow._captcha_data = {
        "lot_number": "mock_lot",
        "captcha_output": "mock_output",
        "pass_token": "mock_pass",
        "gen_time": "12345",
    }

    mock_api = AsyncMock()
    mock_api.validate_geetest.return_value = "certify_12345"
    mock_api.send_sms_code.return_value = True
    mock_api.sms_login.return_value = {
        "access_token": "mock_acc_token",
        "refresh_token": "mock_ref_token",
        "user_id": "8000000000000000000",
    }
    mock_api.get_vehicles.return_value = ()

    with patch.object(flow, "_get_api", return_value=mock_api):
        # Step 3a: Arrival from captcha view -> validates captcha and sends SMS
        form_result = asyncio.run(flow.async_step_sms_code(None))
        assert form_result["type"] == "form"
        assert form_result["step_id"] == "sms_code"
        mock_api.validate_geetest.assert_awaited_once()
        mock_api.send_sms_code.assert_awaited_once()

        # Step 3b: User inputs SMS verification code -> logs in and creates entry
        login_result = asyncio.run(flow.async_step_sms_code({"sms_code": "123456"}))
        assert login_result["type"] == "create_entry"
        assert login_result["data"]["access_token"] == "mock_acc_token"  # noqa: S105
        assert (
            login_result["data"]["phone"] == "13800138000"  # nosec-secret-scan
        )
        mock_api.validate_geetest.assert_awaited_with(
            lot_number="mock_lot",
            captcha_output="mock_output",
            pass_token="mock_pass",
            gen_time="12345",
            device_id="test_dev_id",
        )
        mock_api.send_sms_code.assert_awaited_with(
            phone="13800138000",  # nosec-secret-scan
            certify_id="certify_12345",
            device_id="test_dev_id",
        )


def test_config_flow_phone_sanitization() -> None:
    flow = _get_flow()
    result = asyncio.run(
        flow.async_step_sms_phone({"phone": "+86 138-0013-8000"})
    )
    assert result["type"] == "external"
    assert flow._phone == "13800138000"  # nosec-secret-scan
    assert flow._device_id is not None and len(flow._device_id) == 16


def test_config_flow_sms_code_error_handling() -> None:
    from custom_components.geely_auto.api.exceptions import GeelyAuthError

    flow = _get_flow()
    flow._phone = "13800138000"  # nosec-secret-scan
    flow._device_id = "test_dev_id"
    flow._certify_id = "cert_123"

    mock_api = AsyncMock()
    with patch.object(flow, "_get_api", return_value=mock_api):
        # Case 1: Resend code checkbox triggers redirect to captcha
        res_resend = asyncio.run(flow.async_step_sms_code({"resend_code": True}))
        assert res_resend["type"] == "external"
        assert res_resend["step_id"] == "sms_captcha"

        # Case 2: Wrong length
        res_len = asyncio.run(flow.async_step_sms_code({"sms_code": "123"}))
        assert res_len["type"] == "form"
        assert res_len["errors"]["base"] == "sms_code_format"

        # Case 3: Wrong code from server
        mock_api.sms_login.side_effect = GeelyAuthError("SMS login failed: 验证码错误")
        res_wrong = asyncio.run(flow.async_step_sms_code({"sms_code": "654321"}))
        assert res_wrong["type"] == "form"
        assert res_wrong["errors"]["base"] == "sms_code_wrong"

        # Case 4: Expired code from server
        mock_api.sms_login.side_effect = GeelyAuthError("SMS login failed: 验证码已失效，请重新获取")
        res_expired = asyncio.run(flow.async_step_sms_code({"sms_code": "654321"}))
        assert res_expired["type"] == "form"
        assert res_expired["errors"]["base"] == "sms_code_expired"


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


