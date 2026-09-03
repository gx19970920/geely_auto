"""Geely Auto integration.

The first development stage deliberately has no runtime setup path. The config
flow never creates entries until a real, sanitized protocol capture exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reject unexpected entries while the protocol gate is closed."""
    del hass, entry
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry without side effects."""
    del hass, entry
    return True
