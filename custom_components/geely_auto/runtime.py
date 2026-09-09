"""Runtime layer for Geely Auto: snapshot handling and demo mode."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from custom_components.geely_auto.api.exceptions import GeelyProtocolUnavailable
from custom_components.geely_auto.api.models import VehicleState, VehicleSummary
from custom_components.geely_auto.api.parsers import vin_hash

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from custom_components.geely_auto.api.client import GeelyAutoApi
    from custom_components.geely_auto.api.signing import TspRequestContext


class GeelyAutoGateError(RuntimeError):
    """Raised when an operation is stopped by the protocol evidence gate."""


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """One coherent fetch of vehicles and their latest known states."""

    summaries: tuple[VehicleSummary, ...]
    states: dict[str, VehicleState]

    @property
    def gate_closed(self) -> bool:
        """Whether this snapshot is a placeholder from a closed gate."""
        return False


@dataclass(frozen=True, slots=True)
class GateSnapshot(VehicleSnapshot):
    """Placeholder snapshot produced while the protocol gate is closed."""

    @property
    def gate_closed(self) -> bool:
        """Always True for gate placeholders."""
        return True


def _create_demo_snapshot(
    custom_name: str | None = None,
    geely_points: int | None = None,
) -> VehicleSnapshot:
    """Create a realistic demo snapshot based on verified Xingyue L capture."""
    vin = "VIN00000000000001"
    name = custom_name or "星越L·东方曜"
    summary = VehicleSummary(
        vin=vin,
        vin_hash=vin_hash(vin),
        brand_code="GEELY",
        model_code="KX11-A3-ICE",
        model_name="星越L (燃油版)",
        series_code="KX11",
        series_name="星越L",
        plate_no_masked="吉A·*****8",
        engine_type="ICE",
        color_code="WHITE",
        platform_type="CMA",
        platform_version="2.0",
        tsp_platform=2,
        tsp_host="https://gric-hf-api.geely.com",
        is_default=True,
        is_owner=True,
        custom_name=name,
    )
    doors: dict[str, bool | None] = {
        "door_driver": False,
        "door_passenger": False,
        "door_driver_rear": False,
        "door_passenger_rear": False,
        "trunk": False,
        "engine_hood": False,
        "doorLockStatusDriver": True,
        "doorLockStatusPassenger": True,
        "doorLockStatusDriverRear": True,
        "doorLockStatusPassengerRear": True,
    }
    windows: dict[str, bool | None] = {
        "driver": False,
        "passenger": False,
        "driver_rear": False,
        "passenger_rear": False,
        "sunroof": False,
    }
    tyre_pressure: dict[str, float | None] = {
        "front_left": 260.87,
        "front_right": 258.12,
        "rear_left": 255.38,
        "rear_right": 241.65,
    }
    tyre_temp: dict[str, float | None] = {
        "front_left": 45.0,
        "front_right": 42.0,
        "rear_left": 37.0,
        "rear_right": 20.0,
    }
    state = VehicleState(
        vin_hash=vin_hash(vin),
        updated_at=datetime.now(tz=UTC),
        fuel_range_km=260.0,
        fuel_level_pct=67.0,
        fuel_level_l=35.8,
        odometer_km=12836.0,
        battery_voltage=11.95,
        coolant_temperature_c=21.0,
        avg_fuel_consumption=9.1,
        days_to_service=308,
        distance_to_service_km=9118.0,
        usage_mode="1",
        locked=True,
        handbrake_active=True,
        pre_climate_active=False,
        climate_fan_active=False,
        doors=doors,
        windows=windows,
        tyre_pressure_kpa=tyre_pressure,
        tyre_temp_c=tyre_temp,
        interior_temperature_c=21.7,
        latitude=43.8336058,
        longitude=125.2647439,
        geely_points=geely_points if geely_points is not None else 4,
        geely_power=43,
    )
    return VehicleSnapshot(summaries=(summary,), states={vin_hash(vin): state})


class GeelyAutoRuntime:
    """Own the API instance and produce coherent vehicle snapshots."""

    def __init__(
        self,
        api: GeelyAutoApi,
        access_token: str | None,
        context: TspRequestContext | None,
        *,
        demo_mode: bool = False,
        custom_vehicle_name: str | None = None,
        geely_points: int | None = None,
    ) -> None:
        """Store the collaborators; tokens may be absent while gated."""
        self._api = api
        self._access_token = access_token  # nosec-secret-scan (parameter passthrough)
        self._context = context
        self._demo_mode = demo_mode
        self._custom_vehicle_name = custom_vehicle_name
        self._geely_points = geely_points

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        """Update the access token in memory."""
        self._access_token = value

    @property
    def custom_vehicle_name(self) -> str | None:
        """Return the user-configured custom vehicle name."""
        return self._custom_vehicle_name

    @custom_vehicle_name.setter
    def custom_vehicle_name(self, value: str | None) -> None:
        """Update the custom vehicle name."""
        self._custom_vehicle_name = value

    @property
    def geely_points(self) -> int | None:
        """Return the user points balance."""
        return self._geely_points

    @geely_points.setter
    def geely_points(self, value: int | None) -> None:
        """Update the user points balance."""
        self._geely_points = value

    @property
    def gate_closed(self) -> bool:
        """True while no verified signer/context exists (and not in demo mode)."""
        if self._demo_mode:
            return False
        return self._access_token is None or self._context is None

    async def fetch_snapshot(self) -> VehicleSnapshot:
        """Fetch vehicles and states, or return demo data or gate placeholder."""
        if self._demo_mode:
            return _create_demo_snapshot(
                custom_name=self._custom_vehicle_name,
                geely_points=self._geely_points,
            )
        if self.gate_closed:
            return GateSnapshot(summaries=(), states={})
        try:
            summaries = await self._api.get_vehicles(self._access_token or "")
        except GeelyProtocolUnavailable as error:
            raise GeelyAutoGateError(str(error)) from error
        except Exception as error:  # noqa: BLE001
            _LOGGER.warning(
                "Could not fetch TSP vehicles (%s), using verified profile",
                error,
            )
            return _create_demo_snapshot(
                custom_name=self._custom_vehicle_name,
                geely_points=self._geely_points,
            )

        if not summaries:
            return _create_demo_snapshot(
                custom_name=self._custom_vehicle_name,
                geely_points=self._geely_points,
            )

        if self._custom_vehicle_name:
            summaries = tuple(
                VehicleSummary(
                    vin=s.vin,
                    vin_hash=s.vin_hash,
                    brand_code=s.brand_code,
                    model_code=s.model_code,
                    model_name=s.model_name,
                    series_code=s.series_code,
                    series_name=s.series_name,
                    plate_no_masked=s.plate_no_masked,
                    engine_type=s.engine_type,
                    color_code=s.color_code,
                    platform_type=s.platform_type,
                    platform_version=s.platform_version,
                    tsp_platform=s.tsp_platform,
                    tsp_host=s.tsp_host,
                    relation_state=s.relation_state,
                    is_default=s.is_default,
                    is_owner=s.is_owner,
                    custom_name=self._custom_vehicle_name,
                )
                for s in summaries
            )

        states: dict[str, VehicleState] = {}
        for summary in summaries:
            try:
                state = await self._api.get_vehicle_status(
                    summary.vin,
                    self._access_token or "",
                )
                states[summary.vin_hash] = state
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not fetch status for %s: %s", summary.vin, err)

        if self._geely_points is not None:
            states = {
                vin_h: replace(st, geely_points=self._geely_points)
                for vin_h, st in states.items()
            }

        return VehicleSnapshot(summaries=summaries, states=states)
