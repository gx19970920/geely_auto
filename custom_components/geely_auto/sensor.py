"""Per-vehicle sensors fed by the coordinator snapshot.

Values that are unknown (``None``) render as HA "unknown", never as a
fabricated zero or off state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import DOMAIN
from .entity import GeelyAutoVehicleEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api.models import VehicleSummary
    from .coordinator import GeelyAutoDataUpdateCoordinator


@dataclass(frozen=True, slots=True)
class SensorSpec:
    """Description of one state-backed sensor."""

    key: str
    name: str
    unit: str | None


SENSOR_SPECS: tuple[SensorSpec, ...] = (
    SensorSpec(key="fuel_level_pct", name="Fuel level", unit="%"),
    SensorSpec(key="fuel_range_km", name="Fuel range", unit="km"),
    SensorSpec(key="usage_mode", name="Usage mode", unit=None),
)


class GeelyAutoValueSensor(GeelyAutoVehicleEntity):
    """Read one numeric/string field from the vehicle state."""

    def __init__(
        self,
        coordinator: GeelyAutoDataUpdateCoordinator,
        entry_id: str,
        summary: VehicleSummary,
        spec: SensorSpec,
    ) -> None:
        """Bind the sensor to one state field."""
        super().__init__(entry_id, summary)
        self._coordinator = coordinator
        self._summary = summary
        self._spec = spec
        self._attr_translation_key = spec.key
        self._attr_name = spec.name
        self._attr_native_unit_of_measurement = spec.unit

    @property
    def native_value(self) -> str | float | None:
        """Return the state field, or None when unknown."""
        snapshot = self._coordinator.data
        if snapshot is None:
            return None
        state = snapshot.states.get(self._summary.vin_hash)
        if state is None:
            return None
        return getattr(state, self._spec.key, None)

    async def async_added_to_hass(self) -> None:
        """Register the standard coordinator listener."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> None:
    """Create one sensor set per known vehicle in the snapshot."""
    coordinator: GeelyAutoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    entities = [
        GeelyAutoValueSensor(coordinator, entry.entry_id, summary, spec)
        for summary in (snapshot.summaries if snapshot else ())
        for spec in SENSOR_SPECS
    ]
    async_add_entities(entities)
