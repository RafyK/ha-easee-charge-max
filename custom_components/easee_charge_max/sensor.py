"""Sensor platform — charger status, power, energy, currents."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OP_MODE_LABEL, REASON_FOR_NO_CURRENT_LABEL


@dataclass(frozen=True)
class EaseeSensorDescription(SensorEntityDescription):
    """Extends the base description with a value extractor callable."""
    value_fn: Callable[[dict], Any] | None = None


def _state(key: str):
    return lambda data: data.get("state", {}).get(key)


def _config(key: str):
    return lambda data: data.get("config", {}).get(key)


def _op_mode(data: dict) -> str | None:
    mode = data.get("state", {}).get("chargerOpMode")
    return OP_MODE_LABEL.get(mode) if mode is not None else None


def _power_w(data: dict) -> float | None:
    kw = data.get("state", {}).get("totalPower")
    return round(kw * 1000, 1) if kw is not None else None


def _reason_for_no_current(data: dict) -> str | None:
    val = data.get("state", {}).get("reasonForNoCurrent")
    if val is None:
        return None
    try:
        code = int(val)
    except (TypeError, ValueError):
        return str(val)
    return REASON_FOR_NO_CURRENT_LABEL.get(code, f"Code {code}")


SENSORS: tuple[EaseeSensorDescription, ...] = (
    EaseeSensorDescription(
        key="status",
        name="Charger Status",
        icon="mdi:ev-station",
        value_fn=_op_mode,
    ),
    EaseeSensorDescription(
        key="power",
        name="Charging Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_power_w,
    ),
    EaseeSensorDescription(
        key="session_energy",
        name="Session Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_state("sessionEnergy"),
    ),
    EaseeSensorDescription(
        key="lifetime_energy",
        name="Lifetime Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_state("lifetimeEnergy"),
    ),
    EaseeSensorDescription(
        key="current_l1",
        name="Current L1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("inCurrentT3"),   # T3 = L1 (evcc INT_CURRENT_T3)
    ),
    EaseeSensorDescription(
        key="current_l2",
        name="Current L2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("inCurrentT4"),   # T4 = L2
    ),
    EaseeSensorDescription(
        key="current_l3",
        name="Current L3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("inCurrentT5"),   # T5 = L3
    ),
    EaseeSensorDescription(
        key="dynamic_circuit_p1",
        name="Circuit Current P1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("dynamicCircuitCurrentP1"),
    ),
    EaseeSensorDescription(
        key="dynamic_circuit_p2",
        name="Circuit Current P2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("dynamicCircuitCurrentP2"),
    ),
    EaseeSensorDescription(
        key="dynamic_circuit_p3",
        name="Circuit Current P3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("dynamicCircuitCurrentP3"),
    ),
    EaseeSensorDescription(
        key="voltage",
        name="Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("voltage"),
    ),
    EaseeSensorDescription(
        key="cable_rating",
        name="Cable Rating",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        value_fn=_state("cableRating"),
    ),
    EaseeSensorDescription(
        key="dynamic_charger_current",
        name="Dynamic Charger Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_state("dynamicChargerCurrent"),
    ),
    EaseeSensorDescription(
        key="reason_no_current",
        name="Reason for No Current",
        icon="mdi:alert-circle-outline",
        value_fn=_reason_for_no_current,
    ),
    EaseeSensorDescription(
        key="online",
        name="Online",
        icon="mdi:cloud-check",
        value_fn=_state("isOnline"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [EaseeSensor(coord, entry, desc) for desc in SENSORS]
    )


class EaseeSensor(CoordinatorEntity, SensorEntity):
    """A single sensor reading from the Easee charger state/config."""

    entity_description: EaseeSensorDescription

    def __init__(self, coordinator, entry: ConfigEntry, description: EaseeSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        charger_id: str = entry.data["charger_id"]
        self._attr_unique_id = f"{charger_id}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> Any:
        fn = self.entity_description.value_fn
        return fn(self.coordinator.data) if fn else None
