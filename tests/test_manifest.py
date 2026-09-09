"""Tests for the integration manifest and safety boundaries."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "geely_auto"


def test_manifest_declares_expected_identity() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["domain"] == "geely_auto"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["requirements"] == []


def test_no_control_platform_exists() -> None:
    """The integration is read-only: no actuating platform may ever exist."""
    prohibited = {
        "climate.py",
        "cover.py",
        "device_tracker.py",
        "lock.py",
        "switch.py",
        "vacuum.py",
        "valve.py",
    }

    assert prohibited.isdisjoint(path.name for path in INTEGRATION.iterdir())


def test_sensor_platform_is_read_only() -> None:
    """Sensor entities must exist and must not expose service calls."""
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")

    assert "async_setup_entry" in sensor_source
    forbidden_markers = (
        "async_handle",
        "call_service",
        "async_turn_on",
        "async_turn_off",
    )
    assert all(marker not in sensor_source for marker in forbidden_markers)
