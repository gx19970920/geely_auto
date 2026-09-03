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


def test_no_entity_or_control_platform_exists() -> None:
    prohibited = {
        "binary_sensor.py",
        "button.py",
        "climate.py",
        "device_tracker.py",
        "sensor.py",
        "switch.py",
    }

    assert prohibited.isdisjoint(path.name for path in INTEGRATION.iterdir())
