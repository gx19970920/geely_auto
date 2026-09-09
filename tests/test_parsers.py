"""Tests for pure response parsers using sanitized fixtures."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from custom_components.geely_auto.api import (
    GeelyProtocolError,
    parse_vehicle_list,
    parse_vehicle_status,
    vin_hash,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_vehicle_list_from_verified_fixture() -> None:
    summaries = parse_vehicle_list(load("gric_favorite_vehicles.json"))

    assert len(summaries) == 1
    vehicle = summaries[0]
    assert vehicle.vin == "VIN00000000000001"
    assert vehicle.vin_hash == vin_hash("VIN00000000000001")
    assert vehicle.brand_code == "GEELY"
    assert vehicle.model_code == "KX11-A3-ICE"
    assert vehicle.engine_type == "ICE"
    assert vehicle.tsp_platform == 2
    assert vehicle.tsp_host == "https://gric-hf-api.geely.com"
    assert vehicle.is_default is True
    assert vehicle.is_owner is False
    assert vehicle.plate_no_masked == "<plate>"


def test_parse_vehicle_list_accepts_cache_shape() -> None:
    payload = {
        "vehicleList": [{"vin": "VIN00000000000001", "modelCode": "KX11-A3-ICE"}]
    }

    summaries = parse_vehicle_list(payload)

    assert len(summaries) == 1
    assert summaries[0].model_code == "KX11-A3-ICE"
    assert summaries[0].series_name is None


def test_parse_vehicle_list_rejects_error_envelope() -> None:
    with pytest.raises(GeelyProtocolError, match="code='500'"):
        parse_vehicle_list({"code": "500", "msg": "boom"})


def test_parse_vehicle_list_rejects_entry_without_vin() -> None:
    with pytest.raises(GeelyProtocolError, match="vin"):
        parse_vehicle_list({"code": "0", "data": [{"modelCode": "X"}]})


def test_parse_vehicle_status_from_status_fixture() -> None:
    state = parse_vehicle_status(
        load("vehicle_status_latest.json"), vin="VIN00000000000001"
    )

    assert state.vin_hash == vin_hash("VIN00000000000001")
    assert state.fuel_range_km == 302.0
    assert state.fuel_level_pct == 55.0
    assert state.usage_mode == "ECO"
    assert state.pre_climate_active is False
    assert state.climate_fan_active is False
    assert state.updated_at == datetime.fromtimestamp(1788427322000 / 1000, tz=UTC)


def test_unverified_lock_semantics_stay_unknown() -> None:
    state = parse_vehicle_status(
        load("vehicle_status_latest.json"), vin="VIN00000000000001"
    )

    # Enum semantics for "1"/"0" are not verified, so booleans stay None
    # even though the raw keys are present.
    assert state.locked is None
    assert state.charging is None
    assert set(state.doors) == {
        "doorLockStatusDriver",
        "doorLockStatusDriverRear",
        "doorLockStatusPassenger",
        "doorLockStatusPassengerRear",
    }
    assert all(value is None for value in state.doors.values())
    assert all(value is None for value in state.windows.values())


def test_parse_vehicle_status_requires_basic_section() -> None:
    with pytest.raises(GeelyProtocolError, match="Neither basic nor basicVehicleStatus"):
        parse_vehicle_status({"code": "0", "data": {}})


def test_parse_vehicle_status_from_real_xingyue_l_capture() -> None:
    payload = {
        "code": "0",
        "data": {
            "runningStatus": {
                "fuelLevelPct": "67",
                "fuelLevel": "35.8",
                "engineCoolantTemperature": "21.000",
                "aveFuelConsumption": "9.1",
            },
            "climateStatus": {
                "interiorTemp": "21.700",
                "winPosDriver": "0",
                "winPosPassenger": "0",
                "winPosDriverRear": "0",
                "winPosPassengerRear": "0",
                "sunroofPos": "0",
            },
            "updateTime": "1788769362470",
            "drivingSafetyStatus": {
                "centralLockingStatus": "1",
                "electricParkBrakeStatus": "1",
                "doorOpenStatusDriver": "0",
                "doorOpenStatusPassenger": "0",
                "doorOpenStatusDriverRear": "0",
                "doorOpenStatusPassengerRear": "0",
                "trunkOpenStatus": "0",
                "engineHoodOpenStatus": "0",
            },
            "basic": {
                "distanceToEmpty": "260",
                "usageMode": "1",
                "position": {"latitude": 43.8336058, "longitude": 125.2647439},
            },
            "additionalMaintenanceStatus": {
                "odometer": "12836.000",
                "voltage": "11.950",
                "daysToService": "308",
                "distanceToService": "9118",
                "tyreStatusDriver": "260.870",
                "tyreStatusPassenger": "258.124",
                "tyreStatusDriverRear": "255.378",
                "tyreStatusPassengerRear": "241.648",
                "tyreTempDriver": "45.000",
                "tyreTempPassenger": "42.000",
                "tyreTempDriverRear": "37.000",
                "tyreTempPassengerRear": "20.000",
            },
        },
    }

    state = parse_vehicle_status(payload, vin="VIN_XINGYUE_L_REAL")

    assert state.fuel_range_km == 260.0
    assert state.fuel_level_pct == 67.0
    assert state.fuel_level_l == 35.8
    assert state.odometer_km == 12836.0
    assert state.battery_voltage == 11.95
    assert state.coolant_temperature_c == 21.0
    assert state.avg_fuel_consumption == 9.1
    assert state.days_to_service == 308
    assert state.distance_to_service_km == 9118.0
    assert state.interior_temperature_c == 21.7
    assert state.locked is True
    assert state.handbrake_active is True
    assert state.latitude == 43.8336058
    assert state.longitude == 125.2647439

    # 门与窗
    assert state.doors["door_driver"] is False
    assert state.doors["trunk"] is False
    assert state.windows["driver"] is False
    assert state.windows["sunroof"] is False

    # 胎压与胎温
    assert state.tyre_pressure_kpa["front_left"] == 260.870
    assert state.tyre_pressure_kpa["rear_right"] == 241.648
    assert state.tyre_temp_c["front_left"] == 45.0
    assert state.tyre_temp_c["rear_right"] == 20.0


def test_vin_hash_is_stable_and_short() -> None:
    assert vin_hash("VIN00000000000001") == vin_hash("VIN00000000000001")
    assert len(vin_hash("VIN00000000000001")) == 16
    assert "VIN00000000000001" not in vin_hash("VIN00000000000001")


def test_parse_vehicle_list_extracts_custom_name() -> None:
    payload = {
        "vehicleList": [
            {
                "vin": "VIN00000000000001",
                "modelCode": "KX11-A3-ICE",
                "customName": "星越L·东方曜",
            },
            {
                "vin": "VIN00000000000002",
                "modelCode": "KX11-A3-ICE",
                "carNickName": "小黑",
            },
            {
                "vin": "VIN00000000000003",
                "modelCode": "KX11-A3-ICE",
                "nickName": "大白",
            },
        ]
    }
    summaries = parse_vehicle_list(payload)
    assert len(summaries) == 3
    assert summaries[0].custom_name == "星越L·东方曜"
    assert summaries[1].custom_name == "小黑"
    assert summaries[2].custom_name == "大白"


