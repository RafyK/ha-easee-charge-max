"""Number platform — dynamic current and hardware max current."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_CURRENT, MIN_CURRENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EaseeDynamicCurrentNumber(coord, entry),
            EaseeMaxChargerCurrentNumber(coord, entry),
        ]
    )


class EaseeDynamicCurrentNumber(CoordinatorEntity, NumberEntity):
    """Real-time charging current limit (dynamicChargerCurrent).

    This is the value evcc sets on every charge cycle via MaxCurrent().
    Upper bound is automatically capped to the hardware max stored on the charger.
    Range: 6–32 A (IEC 61851 minimum to Charge MAX rated max).
    """

    _attr_name = "Charging Current"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = float(MIN_CURRENT)
    _attr_native_max_value = float(MAX_CURRENT)
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:current-ac"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._charger_id: str = entry.data["charger_id"]
        self._attr_unique_id = f"{self._charger_id}_dynamic_current"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("state", {}).get("dynamicChargerCurrent")

    @property
    def native_max_value(self) -> float:
        """Cap slider at the charger's hardware max (maxChargerCurrent)."""
        hw = self.coordinator.data.get("config", {}).get("maxChargerCurrent", 0)
        return float(hw) if hw and hw > 0 else float(MAX_CURRENT)

    async def async_set_native_value(self, value: float) -> None:
        hw_max = self.native_max_value
        await self.coordinator.client.set_dynamic_current(
            self._charger_id, value, hw_max
        )
        await self.coordinator.async_request_refresh()


class EaseeMaxChargerCurrentNumber(CoordinatorEntity, NumberEntity):
    """Persistent hardware maximum current (maxChargerCurrent).

    Stored on the charger and survives reboots. Integer amps only.
    Setting this also acts as the upper bound for dynamicChargerCurrent.
    """

    _attr_name = "Max Charger Current (Hardware Limit)"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = float(MIN_CURRENT)
    _attr_native_max_value = float(MAX_CURRENT)
    _attr_native_step = 1.0
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:current-ac"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._charger_id: str = entry.data["charger_id"]
        self._attr_unique_id = f"{self._charger_id}_max_charger_current"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("config", {}).get("maxChargerCurrent")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_max_charger_current(self._charger_id, int(value))
        await self.coordinator.async_request_refresh()
