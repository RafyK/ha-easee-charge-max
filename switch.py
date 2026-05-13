"""Switch platform — charger enable and smart charging toggle."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OP_MODE_CHARGING, OP_MODE_DISCONNECTED

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EaseeChargerEnabledSwitch(coord, entry),
            EaseeSmartChargingSwitch(coord, entry),
        ]
    )


class _EaseeSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Easee switch entities."""

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._charger_id: str = entry.data["charger_id"]


class EaseeChargerEnabledSwitch(_EaseeSwitch):
    """Enables / disables the charger hardware (isEnabled in charger config).

    When disabled the charger will not charge even if a car is connected.
    Mirrors evcc Enable(false) → POST /settings {"enabled": false}.
    """

    _attr_name = "Charger Enabled"
    _attr_icon = "mdi:power-plug"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._charger_id}_charger_enabled"

    @property
    def is_on(self) -> bool | None:
        cfg: dict = self.coordinator.data.get("config", {})
        return cfg.get("isEnabled")

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.set_enabled(self._charger_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.set_enabled(self._charger_id, False)
        await self.coordinator.async_request_refresh()


class EaseeSmartChargingSwitch(_EaseeSwitch):
    """Enables / disables smart charging mode (LED turns blue when active).

    Mirrors evcc updateSmartCharging() → POST /settings {"smartCharging": …}.
    """

    _attr_name = "Smart Charging"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._charger_id}_smart_charging"

    @property
    def is_on(self) -> bool | None:
        state: dict = self.coordinator.data.get("state", {})
        return state.get("smartCharging")

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.client.set_smart_charging(self._charger_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.client.set_smart_charging(self._charger_id, False)
        await self.coordinator.async_request_refresh()
