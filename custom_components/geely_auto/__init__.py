"""Geely Auto integration setup.

The config flow still aborts while the signature gate is closed, so no
entry can be created from the UI yet. The setup path below is the full
production wiring that activates once the gate opens; entities then show
"unknown" for values the protocol reports as unknown.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import GeelyAutoApi
from .api.signing import GeelyHmacSigner, TspRequestContext
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_VERSION,
    CONF_CUSTOM_VEHICLE_NAME,
    CONF_DEMO_MODE,
    CONF_DEVICE_ID,
    CONF_GEELY_POINTS,
    DOMAIN,
)
from .coordinator import GeelyAutoDataUpdateCoordinator
from .runtime import GeelyAutoRuntime

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:  # noqa: ARG001
    """Set up Geely Auto component at startup."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the runtime, coordinator and platforms for one entry."""
    session = async_get_clientsession(hass)
    context = _context_from_entry(entry)
    api = GeelyAutoApi(session, signer=GeelyHmacSigner(), context=context)
    demo_mode = bool(entry.data.get(CONF_DEMO_MODE, False))
    custom_name = entry.options.get(CONF_CUSTOM_VEHICLE_NAME) or entry.data.get(CONF_CUSTOM_VEHICLE_NAME)
    geely_points = entry.options.get(CONF_GEELY_POINTS) or entry.data.get(CONF_GEELY_POINTS)
    runtime = GeelyAutoRuntime(
        api,
        access_token=entry.data.get(CONF_ACCESS_TOKEN),  # nosec-secret-scan (passthrough)
        context=context,
        demo_mode=demo_mode,
        custom_vehicle_name=custom_name,
        geely_points=geely_points,
    )
    coordinator = GeelyAutoDataUpdateCoordinator(hass, _LOGGER, runtime)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    from .webhook import async_register_webhook
    async_register_webhook(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and drop the coordinator."""
    from .webhook import async_unregister_webhook
    async_unregister_webhook(hass)

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.setdefault(DOMAIN, {}).pop(entry.entry_id, None)
    return bool(unloaded)


def _context_from_entry(entry: ConfigEntry) -> TspRequestContext | None:
    """Build the TSP header context from stored entry data when present."""
    device_id = entry.data.get(CONF_DEVICE_ID)  # nosec-secret-scan (config key lookup)
    if not device_id:
        device_id = "82798da7-4664-490a-94ab-9867b57d4045"  # nosec-secret-scan (default device ID)
    return TspRequestContext(
        device_id=str(device_id),
        app_version=str(entry.data.get(CONF_APP_VERSION, "3.55.0")),
        device_brand="samsung",
        device_model="SM-S9380",
        device_os_version="Android 16 (API 36)",
    )
