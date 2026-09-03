"""Tests for normalized vehicle models."""

from custom_components.geely_auto.api.models import (
    VehicleCapabilities,
    VehicleState,
)


def test_unknown_vehicle_state_remains_unknown() -> None:
    state = VehicleState(vin_hash="vehicle-01")

    assert state.soc is None
    assert state.locked is None
    assert state.charging is None
    assert state.doors == {}
    assert state.windows == {}
    assert state.latitude is None
    assert state.longitude is None


def test_capability_lookup_is_explicit() -> None:
    capabilities = VehicleCapabilities(frozenset({"soc", "tire_pressure"}))

    assert capabilities.supports("soc") is True
    assert capabilities.supports("remote_unlock") is False
