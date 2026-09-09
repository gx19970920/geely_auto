"""Base entity for Geely Auto vehicles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from custom_components.geely_auto.api.models import VehicleSummary


class GeelyAutoVehicleEntity(Entity):
    """Shared identity for all per-vehicle entities."""

    _attr_has_entity_name = True

    def __init__(self, entry_id: str, summary: VehicleSummary) -> None:
        """Bind the entity to one vehicle identity."""
        self._attr_unique_id = f"{entry_id}:{summary.vin_hash}"
        device_name = (
            summary.custom_name
            or summary.model_name
            or summary.series_name
            or "吉利汽车"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, summary.vin_hash)},
            "name": device_name,
            "manufacturer": "吉利汽车",
            "model": summary.model_code or summary.model_name or "吉利汽车",
        }
