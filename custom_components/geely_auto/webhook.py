"""Webhook handler for Geely Auto token automatic refresh.

Allows external automations (Reqable, Tasker, Shortcuts, etc.) to push
fresh tokens directly into Home Assistant without requiring manual user intervention.
"""

from __future__ import annotations

import base64
from datetime import datetime
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components import webhook

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CUSTOM_VEHICLE_NAME,
    CONF_DEVICE_ID,
    CONF_GEELY_POINTS,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
DEFAULT_WEBHOOK_ID = "geely_auto_update_token"


def _extract_token_from_payload(raw_content: str | dict[str, Any]) -> str | None:
    """Extract a JWT access token from JSON data or raw text."""
    if isinstance(raw_content, dict):
        # Check direct keys
        for key in ("token", "access_token", "authorization", "auth", "Authorization"):
            val = raw_content.get(key)
            if val and isinstance(val, str):
                token = val.strip()
                if token.lower().startswith("bearer "):
                    token = token[7:].strip()
                if token.startswith("eyJ"):
                    return token
        # Check nested headers
        headers = raw_content.get("headers")
        if isinstance(headers, dict):
            return _extract_token_from_payload(headers)
        # Search anywhere in string representation
        raw_content = json.dumps(raw_content)

    if isinstance(raw_content, str):
        # Look for authorization: Bearer ... or plain eyJ... token
        match = re.search(r"(?:authorization:\s*(?:Bearer\s*)?|bearer\s+)?(eyJ[a-zA-Z0-9_\-\.]+)", raw_content, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Safely decode the unverified JWT payload for metadata."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode("utf-8"))
    except Exception:
        return None


async def async_handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming token update push."""
    _LOGGER.debug("Received Geely Auto webhook request on %s", webhook_id)

    raw_payload: str | dict[str, Any]
    try:
        if request.content_type == "application/json":
            raw_payload = await request.json()
        else:
            raw_payload = await request.text()
    except Exception as err:
        _LOGGER.warning("Failed to parse Geely Auto webhook payload: %s", err)
        return web.json_response(
            {"status": "error", "message": f"Malformed payload: {err}"}, status=400
        )

    token = _extract_token_from_payload(raw_payload)
    if not token:
        _LOGGER.warning("No valid JWT token found in Geely Auto webhook push")
        return web.json_response(
            {
                "status": "error",
                "message": "No valid JWT access token found in request payload.",
            },
            status=400,
        )

    payload = _decode_jwt_payload(token) or {}
    user_id = payload.get("userId")
    exp = payload.get("exp")
    device_id = payload.get("deviceId")
    exp_str = ""
    if exp:
        try:
            exp_str = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            exp_str = str(exp)

    # Locate the target config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return web.json_response(
            {"status": "error", "message": "No Geely Auto integration configured."},
            status=404,
        )

    # If entry_id is specified in query parameters, prioritize it
    target_entry: ConfigEntry | None = None
    query_entry_id = request.query.get("entry_id")
    if query_entry_id:
        target_entry = next((e for e in entries if e.entry_id == query_entry_id), None)

    if not target_entry:
        target_entry = entries[0]

    # Update entry data persistently
    new_data = dict(target_entry.data)
    new_data[CONF_ACCESS_TOKEN] = token
    if device_id:
        new_data[CONF_DEVICE_ID] = device_id

    custom_name: str | None = None
    points: int | None = None
    if isinstance(raw_payload, dict):
        custom_name = raw_payload.get("custom_name") or raw_payload.get("vehicle_name")
        pts = raw_payload.get("points")
        if pts is None:
            pts = raw_payload.get("geely_points")
        if pts is not None:
            try:
                points = int(pts)
            except (ValueError, TypeError):
                pass

    new_options = dict(target_entry.options)
    if custom_name:
        new_options[CONF_CUSTOM_VEHICLE_NAME] = str(custom_name)
    if points is not None:
        new_options[CONF_GEELY_POINTS] = points

    hass.config_entries.async_update_entry(target_entry, data=new_data, options=new_options)
    _LOGGER.info(
        "Geely Auto access token updated via webhook for user %s (valid until %s)",
        user_id,
        exp_str,
    )

    # Hot-update runtime in memory and trigger refresh
    coordinator = hass.data.get(DOMAIN, {}).get(target_entry.entry_id)
    if coordinator and hasattr(coordinator, "runtime"):
        coordinator.runtime.access_token = token
        if custom_name:
            coordinator.runtime.custom_vehicle_name = str(custom_name)
        if points is not None:
            coordinator.runtime.geely_points = points
        await coordinator.async_refresh()

    # Create persistent notification in HA to notify user
    try:
        if hasattr(hass, "components") and hasattr(
            hass.components, "persistent_notification"
        ):
            hass.components.persistent_notification.async_create(
                f"吉利汽车访问凭据已通过手机 Webhook 自动更新成功！\n"
                f"用户ID: {user_id or '未知'}\n"
                f"最新有效期至: {exp_str}",
                title="吉利汽车凭据自动续期成功",
                notification_id="geely_auto_token_updated",
            )
    except Exception as notify_err:
        _LOGGER.debug("Could not send persistent notification: %s", notify_err)

    return web.json_response(
        {
            "status": "success",
            "message": "Token successfully updated and vehicle status refreshed",
            "user_id": user_id,
            "device_id": device_id,
            "expires_at": exp,
            "expires_at_readable": exp_str,
        }
    )


def async_register_webhook(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Register the auto-refresh webhook for Geely Auto."""
    webhook_id = DEFAULT_WEBHOOK_ID
    # Unregister first if already registered
    try:
        webhook.async_unregister(hass, webhook_id)
    except Exception:
        pass

    webhook.async_register(
        hass,
        DOMAIN,
        "Geely Auto Token Auto-Updater",
        webhook_id,
        async_handle_webhook,
    )
    _LOGGER.info(
        "Registered Geely Auto webhook: /api/webhook/%s",
        webhook_id,
    )
    return webhook_id


def async_unregister_webhook(hass: HomeAssistant) -> None:
    """Unregister the auto-refresh webhook."""
    try:
        webhook.async_unregister(hass, DEFAULT_WEBHOOK_ID)
    except Exception:
        pass
