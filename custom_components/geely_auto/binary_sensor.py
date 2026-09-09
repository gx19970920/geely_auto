"""Per-vehicle binary sensors fed by the coordinator snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import DOMAIN
from .entity import GeelyAutoVehicleEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .api.models import VehicleState, VehicleSummary
    from .coordinator import GeelyAutoDataUpdateCoordinator


@dataclass(frozen=True, slots=True)
class BinarySensorSpec:
    """Description of one state-backed binary sensor."""

    key: str
    name: str
    device_class: BinarySensorDeviceClass | str | None
    getter: Callable[[VehicleState], bool | None]


BINARY_SENSOR_SPECS: tuple[BinarySensorSpec, ...] = (
    # 车门与车锁
    BinarySensorSpec(
        key="locked",
        name="车门 - 中控锁",
        device_class=BinarySensorDeviceClass.LOCK,
        getter=lambda s: s.locked,
    ),
    BinarySensorSpec(
        key="door_driver",
        name="车门 - 主驾门",
        device_class=BinarySensorDeviceClass.DOOR,
        getter=lambda s: (
            s.doors.get("door_driver")
            if "door_driver" in s.doors
            else s.doors.get("doorLockStatusDriver")
        ),
    ),
    BinarySensorSpec(
        key="door_passenger",
        name="车门 - 副驾门",
        device_class=BinarySensorDeviceClass.DOOR,
        getter=lambda s: (
            s.doors.get("door_passenger")
            if "door_passenger" in s.doors
            else s.doors.get("doorLockStatusPassenger")
        ),
    ),
    BinarySensorSpec(
        key="door_driver_rear",
        name="车门 - 左后门",
        device_class=BinarySensorDeviceClass.DOOR,
        getter=lambda s: (
            s.doors.get("door_driver_rear")
            if "door_driver_rear" in s.doors
            else s.doors.get("doorLockStatusDriverRear")
        ),
    ),
    BinarySensorSpec(
        key="door_passenger_rear",
        name="车门 - 右后门",
        device_class=BinarySensorDeviceClass.DOOR,
        getter=lambda s: (
            s.doors.get("door_passenger_rear")
            if "door_passenger_rear" in s.doors
            else s.doors.get("doorLockStatusPassengerRear")
        ),
    ),
    BinarySensorSpec(
        key="trunk_open",
        name="车门 - 后备箱",
        device_class=BinarySensorDeviceClass.DOOR,
        getter=lambda s: s.doors.get("trunk"),
    ),
    BinarySensorSpec(
        key="hood_open",
        name="车门 - 前机盖",
        device_class=BinarySensorDeviceClass.DOOR,
        getter=lambda s: s.doors.get("engine_hood"),
    ),
    # 车窗
    BinarySensorSpec(
        key="window_open",
        name="车窗 - 车窗状态",
        device_class=BinarySensorDeviceClass.WINDOW,
        getter=lambda s: (
            any(v for v in s.windows.values() if v is not None) if s.windows else None
        ),
    ),
    # 车况状态
    BinarySensorSpec(
        key="handbrake",
        name="车况 - 电子手刹",
        device_class=None,
        getter=lambda s: s.handbrake_active,
    ),
    BinarySensorSpec(
        key="climate_active",
        name="车况 - 空调运行",
        device_class=BinarySensorDeviceClass.RUNNING,
        getter=lambda s: (
            True
            if s.pre_climate_active or s.climate_fan_active
            else (
                False
                if s.pre_climate_active is not None and s.climate_fan_active is not None
                else None
            )
        ),
    ),
    # 动力系统
    BinarySensorSpec(
        key="charging",
        name="动力 - 充电状态",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        getter=lambda s: s.charging,
    ),
)


class GeelyAutoBinarySensor(GeelyAutoVehicleEntity, BinarySensorEntity):
    """Binary sensor for vehicle boolean states."""

    def __init__(
        self,
        coordinator: GeelyAutoDataUpdateCoordinator,
        entry_id: str,
        summary: VehicleSummary,
        spec: BinarySensorSpec,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(entry_id, summary)
        self._coordinator = coordinator
        self._summary = summary
        self._spec = spec
        self._attr_unique_id = f"{entry_id}:{summary.vin_hash}:{spec.key}"
        self._attr_translation_key = spec.key
        self._attr_name = spec.name
        self._attr_device_class = spec.device_class

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        snapshot = self._coordinator.data
        if snapshot is None:
            return None
        state = snapshot.states.get(self._summary.vin_hash)
        if state is None:
            return None
        return self._spec.getter(state)

    async def async_added_to_hass(self) -> None:
        """Register the standard coordinator listener."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: Any,
) -> None:
    """Create one binary sensor set per known vehicle in the snapshot."""
    coordinator: GeelyAutoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    entities = [
        GeelyAutoBinarySensor(coordinator, entry.entry_id, summary, spec)
        for summary in (snapshot.summaries if snapshot else ())
        for spec in BINARY_SENSOR_SPECS
    ]
    async_add_entities(entities)
