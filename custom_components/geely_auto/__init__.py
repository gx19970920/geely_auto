"""Geely Auto integration setup.

The config flow still aborts while the signature gate is closed, so no
entry can be created from the UI yet. The setup path below is the full
production wiring that activates once the gate opens; entities then show
"unknown" for values the protocol reports as unknown.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import GeelyAutoApi
from .api.signing import TspRequestContext, UnverifiedSigner
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_APP_VERSION,
    CONF_DEVICE_ID,
    DOMAIN,
)
from .coordinator import GeelyAutoDataUpdateCoordinator
from .runtime import GeelyAutoRuntime

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the runtime, coordinator and platforms for one entry."""
    session = async_get_clientsession(hass)
    api = GeelyAutoApi(session, signer=UnverifiedSigner())
    runtime = GeelyAutoRuntime(
        api,
        access_token=entry.data.get(CONF_ACCESS_TOKEN),  # nosec-secret-scan (passthrough)
        context=_context_from_entry(entry),
    )
    coordinator = GeelyAutoDataUpdateCoordinator(hass, _LOGGER, runtime)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and drop the coordinator."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.setdefault(DOMAIN, {}).pop(entry.entry_id, None)
    return bool(unloaded)


def _context_from_entry(entry: ConfigEntry) -> TspRequestContext | None:
    """Build the TSP header context from stored entry data when present."""
    device_id = entry.data.get(CONF_DEVICE_ID)  # nosec-secret-scan (config key lookup)
    if not device_id:
        return None
    return TspRequestContext(
        device_id=str(device_id),
        app_version=str(entry.data.get(CONF_APP_VERSION, "unknown")),
    )
