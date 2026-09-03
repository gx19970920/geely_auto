"""Base entity for Geely Auto vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from custom_components.geely_auto.api.models import VehicleSummary


class GeelyAutoVehicleEntity(SensorEntity):
    """Shared identity for all per-vehicle entities."""

    _attr_has_entity_name = True

    def __init__(self, entry_id: str, summary: VehicleSummary) -> None:
        """Bind the entity to one vehicle identity."""
        self._attr_unique_id = f"{entry_id}:{summary.vin_hash}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, summary.vin_hash)},
            "name": summary.model_name or summary.series_name or "Geely vehicle",
            "manufacturer": summary.brand_code or "Geely",
            "model": summary.model_code,
        }
