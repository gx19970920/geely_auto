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
    )


def parse_vehicle_status(payload: Any, vin: str = "unknown") -> VehicleState:
    """Parse the vehicle status payload into a normalized state.

    Accepts either the bare status object (as cached by the app) or the
    enveloped response. Enum semantics for lock, window, trunk, and tyre
    sections are not verified yet, so those entries surface as ``None``.
    """
    data = _unwrap(payload)
    if isinstance(data, dict) and "basicVehicleStatus" not in data:
        nested = data.get("data", data.get("shadowTspVehicleStatus"))
        if isinstance(nested, dict):
            data = nested
    if not isinstance(data, dict) or "basicVehicleStatus" not in data:
        raise GeelyProtocolError("basicVehicleStatus section missing")

    basic = data["basicVehicleStatus"]

    updated_at: datetime | None = None
    update_time = _optional_int(data, "updateTime")
    if update_time is not None:
        updated_at = datetime.fromtimestamp(update_time / 1000, tz=UTC)

    doors: dict[str, bool | None] = {}
    door_section = data.get("vehicleDoorCoverStatus")
    if isinstance(door_section, dict):
        for key in _DOOR_LOCK_KEYS:
            if key in door_section:
                doors[key] = None

    windows: dict[str, bool | None] = {}
    window_section = data.get("vehicleWindowStatus")
    if isinstance(window_section, dict):
        windows = {str(key): None for key in window_section}

    climate = data.get("vehicleClimateStatus")

    return VehicleState(
        vin_hash=vin_hash(vin),
        updated_at=updated_at,
        fuel_range_km=_optional_float(basic, "distanceToEmpty"),
        fuel_level_pct=_optional_float(basic, "fuelLevelPct"),
        usage_mode=_optional_str(basic, "usageMode"),
        locked=None,
        pre_climate_active=_optional_bool(basic, "preClimateActive"),
        climate_fan_active=(
            _optional_bool(climate, "airBlowerActive")
            if isinstance(climate, dict)
            else None
        ),
        doors=doors,
        windows=windows,
    )
