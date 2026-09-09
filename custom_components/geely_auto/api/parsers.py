"""Pure parsers for captured response structures.

Parsers accept the response payloads documented in ``docs/protocol-notes.md``
and are exercised offline against sanitized fixtures. They never touch the
network and never guess semantics: values whose meaning is not verified are
surfaced as ``None``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from custom_components.geely_auto.api.exceptions import GeelyProtocolError
from custom_components.geely_auto.api.models import VehicleState, VehicleSummary

_SUCCESS_CODES = frozenset({"0", "success"})
_DOOR_LOCK_KEYS = (
    "doorLockStatusDriver",
    "doorLockStatusDriverRear",
    "doorLockStatusPassenger",
    "doorLockStatusPassengerRear",
)


def _unwrap(payload: Any) -> Any:
    """Validate the response envelope and return its data section.

    Bare payloads without an envelope (the app cache shape) pass through;
    an explicit failure code is rejected.
    """
    if not isinstance(payload, dict):
        raise GeelyProtocolError("response payload is not an object")
    code = payload.get("code")
    if code is not None and str(code) not in _SUCCESS_CODES:
        raise GeelyProtocolError(f"response envelope reports code={code!r}")
    return payload.get("data", payload)


def _optional_str(section: dict[str, Any], key: str) -> str | None:
    value = section.get(key)
    return value if isinstance(value, str) else None


def _optional_int(section: dict[str, Any], key: str) -> int | None:
    value = section.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _optional_float(section: dict[str, Any], key: str) -> float | None:
    value = section.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _optional_bool(section: dict[str, Any], key: str) -> bool | None:
    value = section.get(key)
    return value if isinstance(value, bool) else None


def vin_hash(vin: str) -> str:
    """Return a stable non-reversible per-vehicle label for logs/entities."""
    return hashlib.sha256(vin.encode()).hexdigest()[:16]


def parse_vehicle_list(payload: Any) -> tuple[VehicleSummary, ...]:
    """Parse the verified favorite-vehicles response into summaries.

    Accepted shapes: the captured envelope (``data`` is the array) and the
    app cache shape (``{"vehicleList": [...]}``), including entries that
    embed a ``bizVehicleJson`` string.
    """
    data = _unwrap(payload)
    entries: Any = data
    if isinstance(data, dict):
        entries = data.get("data", data.get("vehicleList"))
    if isinstance(entries, dict):
        entries = entries.get("vehicleList")
    if not isinstance(entries, list):
        raise GeelyProtocolError("vehicle list section is not an array")

    return tuple(_parse_vehicle_entry(item) for item in entries)


def _parse_vehicle_entry(item: Any) -> VehicleSummary:
    """Parse one favorite-vehicles entry, merging its embedded biz JSON."""
    if not isinstance(item, dict):
        raise GeelyProtocolError("vehicle entry is not an object")
    vin = item.get("vin")
    if not isinstance(vin, str) or not vin:
        raise GeelyProtocolError("vehicle entry without a usable vin")
    merged: dict[str, Any] = dict(item)
    biz = item.get("bizVehicleJson")
    if isinstance(biz, str):
        try:
            parsed_biz = json.loads(biz)
        except ValueError:
            parsed_biz = {}
        if isinstance(parsed_biz, dict):
            for key, value in parsed_biz.items():
                merged.setdefault(key, value)
    custom_name = (
        _optional_str(merged, "customName")
        or _optional_str(merged, "carNickName")
        or _optional_str(merged, "nickName")
        or _optional_str(merged, "carName")
        or _optional_str(merged, "vehicleAlias")
        or _optional_str(merged, "alias")
    )
    return VehicleSummary(
        vin=vin,
        vin_hash=vin_hash(vin),
        brand_code=_optional_str(merged, "brandCode"),
        model_code=_optional_str(merged, "modelCode"),
        model_name=_optional_str(merged, "modelName"),
        series_code=_optional_str(merged, "seriesCode"),
        series_name=_optional_str(merged, "seriesName"),
        plate_no_masked=_optional_str(merged, "plateNo"),
        engine_type=_optional_str(merged, "engineType"),
        color_code=_optional_str(merged, "colorCode"),
        platform_type=_optional_str(merged, "platformType"),
        platform_version=_optional_str(merged, "platformVersion"),
        tsp_platform=_optional_int(merged, "tspPlatform"),
        tsp_host=_optional_str(merged, "tspHost"),
        relation_state=_optional_int(merged, "relationState"),
        is_default=_optional_bool(merged, "defaultCarFlag"),
        is_owner=_optional_bool(merged, "ownerFlag"),
        custom_name=custom_name,
    )


def parse_vehicle_status(payload: Any, vin: str = "unknown") -> VehicleState:  # noqa: C901
    """Parse the vehicle status payload into a normalized state.

    Supports the official v2.0 TSP status shape (basic, runningStatus,
    additionalMaintenanceStatus, drivingSafetyStatus, climateStatus) as well as
    the legacy/cached shape with basicVehicleStatus.
    """
    data = _unwrap(payload)
    if (
        isinstance(data, dict)
        and "basic" not in data
        and "basicVehicleStatus" not in data
    ):
        nested = data.get("data", data.get("shadowTspVehicleStatus"))
        if isinstance(nested, dict):
            data = nested

    if not isinstance(data, dict) or (
        "basic" not in data and "basicVehicleStatus" not in data
    ):
        raise GeelyProtocolError(
            "Neither basic nor basicVehicleStatus section present in status payload"
        )

    # 1. 优先适配吉利官方 v2.0 最新格式
    if "basic" in data:
        basic = data.get("basic") or {}
        running = data.get("runningStatus") or {}
        maint = data.get("additionalMaintenanceStatus") or {}
        safety = data.get("drivingSafetyStatus") or {}
        climate = data.get("climateStatus") or {}

        updated_at: datetime | None = None
        update_time = _optional_int(data, "updateTime")
        if update_time is not None:
            updated_at = datetime.fromtimestamp(update_time / 1000, tz=UTC)

        # 经纬度位置
        pos = basic.get("position") if isinstance(basic.get("position"), dict) else {}
        lat = _optional_float(pos, "latitude")
        lon = _optional_float(pos, "longitude")

        # 锁状态 (centralLockingStatus: "1"=已锁, "0"=未锁)
        cls = safety.get("centralLockingStatus")
        locked = (str(cls) == "1") if cls is not None else None

        # 电子手刹
        epb = safety.get("electricParkBrakeStatus")
        handbrake = (str(epb) == "1") if epb is not None else None

        # 车门开闭状态 (True=打开, False=关闭)
        doors: dict[str, bool | None] = {}
        for key, field_name in (
            ("door_driver", "doorOpenStatusDriver"),
            ("door_passenger", "doorOpenStatusPassenger"),
            ("door_driver_rear", "doorOpenStatusDriverRear"),
            ("door_passenger_rear", "doorOpenStatusPassengerRear"),
            ("trunk", "trunkOpenStatus"),
            ("engine_hood", "engineHoodOpenStatus"),
        ):
            val = safety.get(field_name)
            doors[key] = (str(val) == "1") if val is not None else None

        # 车窗与天窗开闭 (True=打开, False=关闭)
        windows: dict[str, bool | None] = {}
        for key, field_name in (
            ("driver", "winPosDriver"),
            ("passenger", "winPosPassenger"),
            ("driver_rear", "winPosDriverRear"),
            ("passenger_rear", "winPosPassengerRear"),
            ("sunroof", "sunroofPos"),
        ):
            val = climate.get(field_name)
            windows[key] = (str(val) != "0") if val is not None else None

        # 四轮胎压 kPa
        tyre_pressure: dict[str, float | None] = {
            "front_left": _optional_float(maint, "tyreStatusDriver"),
            "front_right": _optional_float(maint, "tyreStatusPassenger"),
            "rear_left": _optional_float(maint, "tyreStatusDriverRear"),
            "rear_right": _optional_float(maint, "tyreStatusPassengerRear"),
        }

        # 四轮胎温 摄氏度
        tyre_temp: dict[str, float | None] = {
            "front_left": _optional_float(maint, "tyreTempDriver"),
            "front_right": _optional_float(maint, "tyreTempPassenger"),
            "rear_left": _optional_float(maint, "tyreTempDriverRear"),
            "rear_right": _optional_float(maint, "tyreTempPassengerRear"),
        }

        return VehicleState(
            vin_hash=vin_hash(vin),
            updated_at=updated_at,
            fuel_range_km=_optional_float(basic, "distanceToEmpty"),
            fuel_level_pct=_optional_float(running, "fuelLevelPct"),
            fuel_level_l=_optional_float(running, "fuelLevel"),
            odometer_km=_optional_float(maint, "odometer"),
            battery_voltage=_optional_float(maint, "voltage"),
            coolant_temperature_c=_optional_float(running, "engineCoolantTemperature"),
            avg_fuel_consumption=_optional_float(running, "aveFuelConsumption"),
            days_to_service=_optional_int(maint, "daysToService"),
            distance_to_service_km=_optional_float(maint, "distanceToService"),
            usage_mode=_optional_str(basic, "usageMode"),
            locked=locked,
            charging=None,
            handbrake_active=handbrake,
            pre_climate_active=_optional_bool(climate, "preClimateActive"),
            climate_fan_active=_optional_bool(climate, "airBlowerActive"),
            doors=doors,
            windows=windows,
            tyre_pressure_kpa=tyre_pressure,
            tyre_temp_c=tyre_temp,
            interior_temperature_c=_optional_float(climate, "interiorTemp"),
            latitude=lat,
            longitude=lon,
        )

    # 2. 兼容旧版 basicVehicleStatus 格式
    basic_legacy = data["basicVehicleStatus"]
    updated_at_legacy: datetime | None = None
    update_time_legacy = _optional_int(data, "updateTime")
    if update_time_legacy is not None:
        updated_at_legacy = datetime.fromtimestamp(update_time_legacy / 1000, tz=UTC)

    doors_legacy: dict[str, bool | None] = {}
    door_section = data.get("vehicleDoorCoverStatus")
    if isinstance(door_section, dict):
        for k in _DOOR_LOCK_KEYS:
            if k in door_section:
                doors_legacy[k] = None

    windows_legacy: dict[str, bool | None] = {}
    window_section = data.get("vehicleWindowStatus")
    if isinstance(window_section, dict):
        windows_legacy = {str(k): None for k in window_section}

    climate_legacy = data.get("vehicleClimateStatus")

    return VehicleState(
        vin_hash=vin_hash(vin),
        updated_at=updated_at_legacy,
        fuel_range_km=_optional_float(basic_legacy, "distanceToEmpty"),
        fuel_level_pct=_optional_float(basic_legacy, "fuelLevelPct"),
        usage_mode=_optional_str(basic_legacy, "usageMode"),
        locked=None,
        pre_climate_active=_optional_bool(basic_legacy, "preClimateActive"),
        climate_fan_active=(
            _optional_bool(climate_legacy, "airBlowerActive")
            if isinstance(climate_legacy, dict)
            else None
        ),
        doors=doors_legacy,
        windows=windows_legacy,
    )

