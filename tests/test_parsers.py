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
        "vehicleList": [
            {"vin": "VIN00000000000001", "modelCode": "KX11-A3-ICE"}
        ]
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
    assert state.updated_at == datetime.fromtimestamp(
        1788427322000 / 1000, tz=UTC
    )


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
    with pytest.raises(GeelyProtocolError, match="basicVehicleStatus"):
        parse_vehicle_status({"code": "0", "data": {}})


def test_vin_hash_is_stable_and_short() -> None:
    assert vin_hash("VIN00000000000001") == vin_hash("VIN00000000000001")
    assert len(vin_hash("VIN00000000000001")) == 16
    assert "VIN00000000000001" not in vin_hash("VIN00000000000001")
