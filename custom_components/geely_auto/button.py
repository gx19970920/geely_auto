"""Button entities for Geely Auto integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import aiohttp

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CHECKIN_PROXY_URL, DEFAULT_CHECKIN_PROXY_URL, DOMAIN
from .entity import GeelyAutoVehicleEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .api.models import VehicleSummary
    from .coordinator import GeelyAutoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# 自动化控制代理端点
UNRAID_TRIGGER_URL = "http://checkin.geely.com/api/trigger_checkin"


class GeelyAutoCheckinButton(GeelyAutoVehicleEntity, ButtonEntity):
    """Button to trigger Geely Auto daily check-in."""

    _attr_icon = "mdi:calendar-check"
    _attr_translation_key = "daily_checkin"

    def __init__(
        self,
        coordinator: GeelyAutoDataUpdateCoordinator,
        entry_id: str,
        summary: VehicleSummary,
    ) -> None:
        super().__init__(entry_id, summary)
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry_id}:{summary.vin_hash}:button:daily_checkin"
        self._attr_name = "每日签到"

    async def async_press(self) -> None:
        """Trigger check-in by sending a request to the proxy service."""
        entry = getattr(self._coordinator, "config_entry", None)
        proxy_url = DEFAULT_CHECKIN_PROXY_URL
        if entry is not None:
            proxy_url = entry.options.get(
                CONF_CHECKIN_PROXY_URL,
                entry.data.get(CONF_CHECKIN_PROXY_URL, DEFAULT_CHECKIN_PROXY_URL),
            )

        _LOGGER.info("正在通过代理触发吉利汽车每日签到: %s via %s", UNRAID_TRIGGER_URL, proxy_url)
        session = async_get_clientsession(self.hass)
        try:
            async with session.post(
                UNRAID_TRIGGER_URL,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _LOGGER.info("吉利汽车每日签到触发成功: %s", data)
                else:
                    _LOGGER.warning("吉利汽车每日签到触发返回 HTTP %d", resp.status)
        except Exception as err:
            _LOGGER.error("触发吉利汽车每日签到失败: %s", err)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Geely Auto button entities."""
    coordinator: GeelyAutoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    entities = [
        GeelyAutoCheckinButton(coordinator, entry.entry_id, summary)
        for summary in (snapshot.summaries if snapshot else ())
    ]
    async_add_entities(entities)
