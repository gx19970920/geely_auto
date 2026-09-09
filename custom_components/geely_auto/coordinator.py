"""HA coordinator wiring for the Geely Auto runtime."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, UPDATE_INTERVAL_SECONDS
from .runtime import GeelyAutoGateError

if TYPE_CHECKING:
    import logging

    from homeassistant.core import HomeAssistant

    from .runtime import GeelyAutoRuntime, VehicleSnapshot


class GeelyAutoDataUpdateCoordinator(DataUpdateCoordinator["VehicleSnapshot"]):
    """Poll the runtime and surface gate state as UpdateFailed."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        runtime: GeelyAutoRuntime,
    ) -> None:
        """Initialize with the shared runtime."""
        super().__init__(
            hass,
            logger,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._runtime = runtime

    @property
    def runtime(self) -> GeelyAutoRuntime:
        """Return the underlying GeelyAutoRuntime instance."""
        return self._runtime

    async def _async_update_data(self) -> VehicleSnapshot:
        """Fetch a snapshot; a closed gate becomes an explicit UpdateFailed."""
        try:
            return await self._runtime.fetch_snapshot()
        except GeelyAutoGateError as error:
            raise UpdateFailed(f"protocol gate closed: {error}") from error
