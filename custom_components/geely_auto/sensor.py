"""Per-vehicle sensors fed by the coordinator snapshot.

Values that are unknown (``None``) render as HA "unknown", never as a
fabricated zero or off state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .const import DOMAIN
from .entity import GeelyAutoVehicleEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .api.models import VehicleState, VehicleSummary
    from .coordinator import GeelyAutoDataUpdateCoordinator


@dataclass(frozen=True, slots=True)
class SensorSpec:
    """Description of one state-backed sensor."""

    key: str
    name: str
    unit: str | None
    device_class: SensorDeviceClass | None = None
    getter: Callable[[VehicleState], Any] | None = None
    icon: str | None = None


SENSOR_SPECS: tuple[SensorSpec, ...] = (
    # 燃油动力
    SensorSpec(key="fuel_level_pct", name="燃油 - 剩余油量", unit="%"),
    SensorSpec(key="fuel_level_l", name="燃油 - 剩余燃油升数", unit="L"),
    SensorSpec(
        key="fuel_range_km",
        name="燃油 - 续航里程",
        unit="km",
        device_class=SensorDeviceClass.DISTANCE,
    ),
    SensorSpec(
        key="avg_fuel_consumption",
        name="燃油 - 平均油耗",
        unit="L/100km",
    ),
    # 整车车况
    SensorSpec(
        key="odometer_km",
        name="车况 - 总里程",
        unit="km",
        device_class=SensorDeviceClass.DISTANCE,
    ),
    SensorSpec(
        key="battery_voltage",
        name="车况 - 12V蓄电池电压",
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    SensorSpec(
        key="coolant_temperature_c",
        name="车况 - 发动机水温",
        unit="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorSpec(
        key="interior_temperature_c",
        name="车况 - 车内实时温度",
        unit="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorSpec(key="usage_mode", name="车况 - 使用模式", unit=None),
    SensorSpec(
        key="updated_at",
        name="车况 - 数据更新时间",
        unit=None,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    # 维保服务
    SensorSpec(key="days_to_service", name="维保 - 保养倒计时", unit="d"),
    SensorSpec(
        key="distance_to_service_km",
        name="维保 - 保养剩余里程",
        unit="km",
        device_class=SensorDeviceClass.DISTANCE,
    ),
    # 轮胎监测（左前/右前/左后/右后 胎压与胎温成对归类）
    SensorSpec(
        key="tyre_pressure_front_left",
        name="轮胎 - 左前胎压",
        unit="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        getter=lambda s: s.tyre_pressure_kpa.get("front_left"),
    ),
    SensorSpec(
        key="tyre_temp_front_left",
        name="轮胎 - 左前胎温",
        unit="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        getter=lambda s: s.tyre_temp_c.get("front_left"),
    ),
    SensorSpec(
        key="tyre_pressure_front_right",
        name="轮胎 - 右前胎压",
        unit="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        getter=lambda s: s.tyre_pressure_kpa.get("front_right"),
    ),
    SensorSpec(
        key="tyre_temp_front_right",
        name="轮胎 - 右前胎温",
        unit="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        getter=lambda s: s.tyre_temp_c.get("front_right"),
    ),
    SensorSpec(
        key="tyre_pressure_rear_left",
        name="轮胎 - 左后胎压",
        unit="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        getter=lambda s: s.tyre_pressure_kpa.get("rear_left"),
    ),
    SensorSpec(
        key="tyre_temp_rear_left",
        name="轮胎 - 左后胎温",
        unit="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        getter=lambda s: s.tyre_temp_c.get("rear_left"),
    ),
    SensorSpec(
        key="tyre_pressure_rear_right",
        name="轮胎 - 右后胎压",
        unit="kPa",
        device_class=SensorDeviceClass.PRESSURE,
        getter=lambda s: s.tyre_pressure_kpa.get("rear_right"),
    ),
    SensorSpec(
        key="tyre_temp_rear_right",
        name="轮胎 - 右后胎温",
        unit="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        getter=lambda s: s.tyre_temp_c.get("rear_right"),
    ),
    # 用户权益与签到
    SensorSpec(
        key="geely_points",
        name="吉分",
        unit="分",
        icon="mdi:star-circle",
        getter=lambda s: s.geely_points,
    ),
    SensorSpec(
        key="sign_in_status",
        name="签到状态",
        unit=None,
        icon="mdi:calendar-check",
        getter=lambda s: s.sign_in_status or "未签到",
    ),
)


class GeelyAutoValueSensor(GeelyAutoVehicleEntity, SensorEntity):
    """Read one numeric/string field from the vehicle state."""

    def __init__(
        self,
        coordinator: GeelyAutoDataUpdateCoordinator,
        entry_id: str,
        summary: VehicleSummary,
        spec: SensorSpec,
    ) -> None:
        """Bind the sensor to one state field."""
        super().__init__(entry_id, summary)
        self._coordinator = coordinator
        self._summary = summary
        self._spec = spec
        self._attr_unique_id = f"{entry_id}:{summary.vin_hash}:{spec.key}"
        self._attr_translation_key = spec.key
        self._attr_name = spec.name
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        if spec.icon:
            self._attr_icon = spec.icon

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state field, or None when unknown."""
        snapshot = self._coordinator.data
        if snapshot is None:
            return None
        state = snapshot.states.get(self._summary.vin_hash)
        if state is None:
            return None
        if self._spec.getter is not None:
            val = self._spec.getter(state)
        else:
            val = getattr(state, self._spec.key, None)
        if val is not None and hasattr(val, "isoformat") and callable(val.isoformat):
            return str(val.isoformat())
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return float(val)
        if isinstance(val, str):
            return val
        return None

    @property
    def icon(self) -> str | None:
        """Return dynamic icon for sensor."""
        if self._spec.key == "sign_in_status":
            val = self.native_value
            if val == "已签到":
                return "mdi:calendar-check"
            return "mdi:calendar-remove-outline"
        return self._spec.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return sensor extra attributes."""
        if self._spec.key == "sign_in_status":
            snapshot = self._coordinator.data
            if snapshot:
                state = snapshot.states.get(self._summary.vin_hash)
                if state:
                    return {
                        "last_checkin_date": state.last_checkin_date,
                        "is_signed_in": (state.sign_in_status == "已签到"),
                    }
        return None

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
    """Create one sensor set per known vehicle in the snapshot."""
    coordinator: GeelyAutoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    snapshot = coordinator.data
    entities = [
        GeelyAutoValueSensor(coordinator, entry.entry_id, summary, spec)
        for summary in (snapshot.summaries if snapshot else ())
        for spec in SENSOR_SPECS
    ]
    async_add_entities(entities)
