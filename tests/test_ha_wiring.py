"""Tests for the runtime and HA wiring layers (offline, stubbed HA)."""

import asyncio
import importlib
import sys

import pytest

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()
for name in (
    "custom_components.geely_auto.const",
    "custom_components.geely_auto.api.exceptions",
    "custom_components.geely_auto.api.models",
    "custom_components.geely_auto.api.endpoints",
    "custom_components.geely_auto.api.signing",
    "custom_components.geely_auto.api.parsers",
    "custom_components.geely_auto.api.client",
    "custom_components.geely_auto.api",
    "custom_components.geely_auto.runtime",
    "custom_components.geely_auto.coordinator",
    "custom_components.geely_auto.entity",
    "custom_components.geely_auto.sensor",
    "custom_components.geely_auto",
):
    sys.modules.pop(name, None)

runtime_module = importlib.import_module("custom_components.geely_auto.runtime")
coordinator_module = importlib.import_module("custom_components.geely_auto.coordinator")
sensor_module = importlib.import_module("custom_components.geely_auto.sensor")

GeelyAutoRuntime = runtime_module.GeelyAutoRuntime
GeelyAutoGateError = runtime_module.GeelyAutoGateError


class GateApi:
    """API stand-in that behaves like a closed protocol gate."""

    async def get_vehicles(self, access_token: str):
        raise __import__(
            "custom_components.geely_auto.api.exceptions",
            fromlist=["GeelyProtocolUnavailable"],
        ).GeelyProtocolUnavailable("gate closed")

    async def get_vehicle_status(self, vin: str):
        raise NotImplementedError


def run(coroutine):
    return asyncio.run(coroutine)


def test_runtime_gate_closed_without_token_or_context() -> None:
    runtime = GeelyAutoRuntime(GateApi(), access_token=None, context=None)

    assert runtime.gate_closed is True
    snapshot = run(runtime.fetch_snapshot())

    assert snapshot.gate_closed is True
    assert snapshot.summaries == ()
    assert snapshot.states == {}


def test_runtime_maps_gate_exception() -> None:
    runtime = GeelyAutoRuntime(GateApi(), access_token="token", context="ctx")

    assert runtime.gate_closed is False
    with pytest.raises(GeelyAutoGateError, match="gate closed"):
        run(runtime.fetch_snapshot())


def test_coordinator_reports_gate_as_update_failed() -> None:
    import logging

    from homeassistant.helpers.update_coordinator import UpdateFailed

    runtime = GeelyAutoRuntime(GateApi(), access_token="token", context="ctx")
    coordinator = coordinator_module.GeelyAutoDataUpdateCoordinator(
        None, logging.getLogger("test"), runtime
    )

    with pytest.raises(UpdateFailed, match="protocol gate closed"):
        run(coordinator._async_update_data())


def test_sensor_reports_unknown_without_state() -> None:
    import logging

    from custom_components.geely_auto.api.models import VehicleSummary

    runtime = GeelyAutoRuntime(GateApi(), access_token=None, context=None)
    coordinator = coordinator_module.GeelyAutoDataUpdateCoordinator(
        None, logging.getLogger("test"), runtime
    )
    summary = VehicleSummary(vin="VIN00000000000001", vin_hash="hash01")
    spec = sensor_module.SensorSpec(key="fuel_level_pct", name="Fuel level", unit="%")
    sensor = sensor_module.GeelyAutoValueSensor(
        coordinator,
        "entry-1",
        summary,
        spec,
    )

    assert sensor.native_value is None
    assert sensor._attr_unique_id == "entry-1:hash01:fuel_level_pct"
    assert sensor._attr_native_unit_of_measurement == "%"


def test_runtime_demo_mode_produces_snapshot() -> None:
    runtime = GeelyAutoRuntime(
        GateApi(), access_token=None, context=None, demo_mode=True
    )
    assert runtime.gate_closed is False

    snapshot = run(runtime.fetch_snapshot())
    assert snapshot.gate_closed is False
    assert len(snapshot.summaries) == 1
    vehicle = snapshot.summaries[0]
    assert vehicle.model_name == "星越L (燃油版)"
    assert vehicle.vin_hash in snapshot.states

    state = snapshot.states[vehicle.vin_hash]
    assert state.fuel_level_pct == 67.0
    assert state.fuel_range_km == 260.0
    assert state.odometer_km == 12836.0
    assert state.battery_voltage == 11.95
    assert state.interior_temperature_c == 21.7
    assert state.geely_points == 4



def test_binary_sensor_reports_state() -> None:
    import importlib
    import logging

    bs_module = importlib.import_module("custom_components.geely_auto.binary_sensor")
    runtime = GeelyAutoRuntime(
        GateApi(), access_token=None, context=None, demo_mode=True
    )
    coordinator = coordinator_module.GeelyAutoDataUpdateCoordinator(
        None, logging.getLogger("test"), runtime
    )
    coordinator.data = run(coordinator._async_update_data())

    summary = coordinator.data.summaries[0]

    locked_spec = bs_module.BINARY_SENSOR_SPECS[0]
    sensor = bs_module.GeelyAutoBinarySensor(
        coordinator, "entry-1", summary, locked_spec
    )
    assert sensor.is_on is True
    assert sensor._attr_unique_id == f"entry-1:{summary.vin_hash}:locked"


def test_all_binary_sensors_evaluate_properly() -> None:
    import importlib
    import logging

    bs_module = importlib.import_module("custom_components.geely_auto.binary_sensor")
    runtime = GeelyAutoRuntime(
        GateApi(), access_token=None, context=None, demo_mode=True
    )
    coordinator = coordinator_module.GeelyAutoDataUpdateCoordinator(
        None, logging.getLogger("test"), runtime
    )
    coordinator.data = run(coordinator._async_update_data())
    summary = coordinator.data.summaries[0]

    for spec in bs_module.BINARY_SENSOR_SPECS:
        sensor = bs_module.GeelyAutoBinarySensor(coordinator, "entry-1", summary, spec)
        assert sensor.unique_id == f"entry-1:{summary.vin_hash}:{spec.key}"
        # Values shouldn't raise exception
        _ = sensor.is_on


def test_geely_points_sensor() -> None:
    import logging
    from custom_components.geely_auto.api.parsers import vin_hash
    runtime = GeelyAutoRuntime(
        GateApi(), access_token=None, context=None, demo_mode=True, geely_points=4
    )
    coordinator = coordinator_module.GeelyAutoDataUpdateCoordinator(
        None, logging.getLogger("test"), runtime
    )
    coordinator.data = run(coordinator._async_update_data())
    summary = coordinator.data.summaries[0]
    spec = next(s for s in sensor_module.SENSOR_SPECS if s.key == "geely_points")
    sensor = sensor_module.GeelyAutoValueSensor(coordinator, "entry-1", summary, spec)
    assert sensor.native_value == 4
    assert isinstance(sensor.native_value, int)
    assert sensor._attr_native_unit_of_measurement == "分"
    assert sensor._attr_icon == "mdi:star-circle"

