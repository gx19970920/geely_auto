"""Unit tests for Geely Auto token auto-update webhook."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.geely_auto.const import CONF_ACCESS_TOKEN, CONF_DEVICE_ID, DOMAIN
from custom_components.geely_auto.webhook import (
    _decode_jwt_payload,
    _extract_token_from_payload,
    async_handle_webhook,
    async_register_webhook,
    async_unregister_webhook,
)

SAMPLE_JWT = (
    "eyJraWQiOiJmNDgzZmI2ZGM3MTc0ZTEwYmQ0ZWM4NTk2NWE3ZjI4ZCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0."
    "eyJzdWIiOiIzMDY5NzA5MyIsInVzZXJJZCI6IjMwNjk3MDkzIiwiZGV2aWNlSWQiOiI4Mjc5OGRhNy00NjY0LTQ5MGEt"
    "OTRhYi05ODY3YjU3ZDQwNDUiLCJleHAiOjE3ODkzODA5MDN9."
    "dummySignaturePartForTesting1234567890"
)


def run(coroutine: Any) -> Any:
    return asyncio.run(coroutine)


def test_extract_token_from_json_direct() -> None:
    """Extract token when provided directly in a dictionary."""
    assert _extract_token_from_payload({"token": SAMPLE_JWT}) == SAMPLE_JWT
    assert _extract_token_from_payload({"access_token": SAMPLE_JWT}) == SAMPLE_JWT
    assert _extract_token_from_payload({"authorization": f"Bearer {SAMPLE_JWT}"}) == SAMPLE_JWT


def test_extract_token_from_raw_headers_text() -> None:
    """Extract token from raw HTTP request headers text."""
    raw_text = f"""
GET /ms-vehicle-status/api/v2.0/vehicle/status/latest HTTP/2
host: gric-hf-api.geely.com
authorization: {SAMPLE_JWT}
x-tenant-id: GEELY
"""
    assert _extract_token_from_payload(raw_text) == SAMPLE_JWT


def test_extract_token_from_bearer_text() -> None:
    """Extract token when prefixed with Bearer in raw text."""
    raw_text = f"authorization: Bearer {SAMPLE_JWT}\nx-device-id: 123"
    assert _extract_token_from_payload(raw_text) == SAMPLE_JWT


def test_extract_token_invalid() -> None:
    """Return None when no valid JWT is present."""
    assert _extract_token_from_payload("just some random text without jwt") is None
    assert _extract_token_from_payload({"token": "not_a_jwt"}) is None


def test_decode_jwt_payload() -> None:
    """Decode unverified JWT payload."""
    payload = _decode_jwt_payload(SAMPLE_JWT)
    assert payload is not None
    assert payload.get("userId") == "30697093"
    assert payload.get("exp") == 1789380903


class MockRequest:
    """Mock aiohttp web request."""

    def __init__(self, content: Any, content_type: str = "application/json", query: dict[str, str] | None = None) -> None:
        self._content = content
        self.content_type = content_type
        self.query = query or {}

    async def json(self) -> Any:
        if isinstance(self._content, dict):
            return self._content
        raise ValueError("Not JSON")

    async def text(self) -> str:
        return str(self._content)


def test_webhook_handler_success() -> None:
    """Handle valid token update push via webhook."""
    import sys
    config_entries_module = sys.modules["homeassistant.config_entries"]
    core_module = sys.modules["homeassistant.core"]
    hass = core_module.HomeAssistant()

    entry = config_entries_module.ConfigEntry(
        data={CONF_ACCESS_TOKEN: "old-token", CONF_DEVICE_ID: "old-device"},
        entry_id="entry-geely-001",
    )
    hass.config_entries._entries.append(entry)

    mock_runtime = MagicMock()
    mock_runtime.access_token = "old-token"
    mock_coordinator = MagicMock()
    mock_coordinator.runtime = mock_runtime
    mock_coordinator.async_refresh = AsyncMock()
    hass.data[DOMAIN] = {entry.entry_id: mock_coordinator}

    req = MockRequest({"token": SAMPLE_JWT})
    resp = run(async_handle_webhook(hass, "geely_auto_update_token", req))

    assert resp.status == 200
    assert entry.data[CONF_ACCESS_TOKEN] == SAMPLE_JWT
    assert mock_runtime.access_token == SAMPLE_JWT
    mock_coordinator.async_refresh.assert_awaited_once()


def test_webhook_handler_invalid_token() -> None:
    """Return 400 when request contains no JWT token."""
    import sys
    core_module = sys.modules["homeassistant.core"]
    hass = core_module.HomeAssistant()

    req = MockRequest({"something_else": "invalid"})
    resp = run(async_handle_webhook(hass, "geely_auto_update_token", req))
    assert resp.status == 400


def test_register_and_unregister_webhook() -> None:
    """Test register and unregister webhook without errors."""
    import sys
    config_entries_module = sys.modules["homeassistant.config_entries"]
    core_module = sys.modules["homeassistant.core"]
    hass = core_module.HomeAssistant()
    entry = config_entries_module.ConfigEntry(entry_id="entry-geely-001")

    webhook_id = async_register_webhook(hass, entry)
    assert webhook_id == "geely_auto_update_token"

    async_unregister_webhook(hass)


def test_webhook_handler_points_and_custom_name() -> None:
    """Test webhook pushes points and custom_name updating options and runtime."""
    import sys
    from custom_components.geely_auto.const import CONF_GEELY_POINTS, CONF_CUSTOM_VEHICLE_NAME
    config_entries_module = sys.modules["homeassistant.config_entries"]
    core_module = sys.modules["homeassistant.core"]
    hass = core_module.HomeAssistant()

    entry = config_entries_module.ConfigEntry(
        data={CONF_ACCESS_TOKEN: "old-token"},
        entry_id="entry-geely-002",
    )
    hass.config_entries._entries.append(entry)

    mock_runtime = MagicMock()
    mock_runtime.access_token = "old-token"
    mock_runtime.custom_vehicle_name = None
    mock_runtime.geely_points = None

    mock_coordinator = MagicMock()
    mock_coordinator.runtime = mock_runtime
    mock_coordinator.async_refresh = AsyncMock()
    hass.data[DOMAIN] = {entry.entry_id: mock_coordinator}

    req = MockRequest({
        "token": SAMPLE_JWT,
        "custom_name": "星越L·东方曜",
        "geely_points": 4,
    })
    resp = run(async_handle_webhook(hass, "geely_auto_update_token", req))

    assert resp.status == 200
    assert entry.options[CONF_CUSTOM_VEHICLE_NAME] == "星越L·东方曜"
    assert entry.options[CONF_GEELY_POINTS] == 4
    assert mock_runtime.custom_vehicle_name == "星越L·东方曜"
    assert mock_runtime.geely_points == 4


def test_webhook_handler_sign_in_status() -> None:
    """Test webhook handles sign_in_status and checkin_date in payload."""
    import sys
    from custom_components.geely_auto.const import CONF_LAST_CHECKIN_DATE, CONF_SIGN_IN_STATUS
    config_entries_module = sys.modules["homeassistant.config_entries"]
    core_module = sys.modules["homeassistant.core"]
    hass = core_module.HomeAssistant()

    entry = config_entries_module.ConfigEntry(
        data={CONF_ACCESS_TOKEN: "old-token"},
        entry_id="entry-geely-003",
    )
    hass.config_entries._entries.append(entry)

    mock_runtime = MagicMock()
    mock_runtime.access_token = "old-token"
    mock_runtime.sign_in_status = "未签到"
    mock_runtime.last_checkin_date = None

    mock_coordinator = MagicMock()
    mock_coordinator.runtime = mock_runtime
    mock_coordinator.async_refresh = AsyncMock()
    hass.data[DOMAIN] = {entry.entry_id: mock_coordinator}

    req = MockRequest({
        "token": SAMPLE_JWT,
        "sign_in_status": "已签到",
        "checkin_date": "2026-09-10",
        "points": 10,
    })
    resp = run(async_handle_webhook(hass, "geely_auto_update_token", req))

    assert resp.status == 200
    assert entry.options[CONF_SIGN_IN_STATUS] == "已签到"
    assert entry.options[CONF_LAST_CHECKIN_DATE] == "2026-09-10"
    assert mock_runtime.sign_in_status == "已签到"
    assert mock_runtime.last_checkin_date == "2026-09-10"

