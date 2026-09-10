"""Normalized, server-independent Geely Auto data models.

Field availability follows the verified captures and the app-side status
schema; unknown values stay ``None`` instead of being interpreted as zero
or as an explicit off/locked state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class TokenBundle:
    """Authentication material held only in memory or protected HA storage."""

    access_token: str
    refresh_token: str
    expires_at: datetime | None = None
    user_id: str | None = None


@dataclass(frozen=True, slots=True)
class VehicleSummary:
    """A vehicle from the verified favorite-vehicles list response."""

    vin: str
    vin_hash: str
    brand_code: str | None = None
    model_code: str | None = None
    model_name: str | None = None
    series_code: str | None = None
    series_name: str | None = None
    plate_no_masked: str | None = None
    engine_type: str | None = None
    color_code: str | None = None
    platform_type: str | None = None
    platform_version: str | None = None
    tsp_platform: int | None = None
    tsp_host: str | None = None
    relation_state: int | None = None
    is_default: bool | None = None
    is_owner: bool | None = None
    custom_name: str | None = None


@dataclass(frozen=True, slots=True)
class VehicleCapabilities:
    """Verified capabilities for one vehicle."""

    names: frozenset[str] = field(default_factory=frozenset)

    def supports(self, capability: str) -> bool:
        """Return whether the normalized capability is available."""
        return capability in self.names


@dataclass(frozen=True, slots=True)
class VehicleState:
    """Normalized vehicle state; missing data remains unknown.

    Door, window, trunk, and tyre semantics come from sections of the
    status payload whose enum values are not yet verified, so the parser
    fills them with ``None`` entries instead of guessing a boolean.
    """

    vin_hash: str
    model: str | None = None
    updated_at: datetime | None = None
    soc: float | None = None
    electric_range_km: float | None = None
    fuel_range_km: float | None = None
    odometer_km: float | None = None
    fuel_level_pct: float | None = None
    fuel_level_l: float | None = None
    battery_voltage: float | None = None
    coolant_temperature_c: float | None = None
    avg_fuel_consumption: float | None = None
    days_to_service: int | None = None
    distance_to_service_km: float | None = None
    usage_mode: str | None = None
    locked: bool | None = None
    charging: bool | None = None
    handbrake_active: bool | None = None
    pre_climate_active: bool | None = None
    climate_fan_active: bool | None = None
    doors: dict[str, bool | None] = field(default_factory=dict)
    windows: dict[str, bool | None] = field(default_factory=dict)
    tyre_pressure_kpa: dict[str, float | None] = field(default_factory=dict)
    tyre_temp_c: dict[str, float | None] = field(default_factory=dict)
    interior_temperature_c: float | None = None
    exterior_temperature_c: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    geely_points: int | None = None
    geely_power: int | None = None
    sign_in_status: str | None = None
    last_checkin_date: str | None = None
    raw_capabilities: frozenset[str] = field(default_factory=frozenset)
