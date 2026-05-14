"""Select platform — phase mode (1-phase / Auto 3-phase).

For TN-grid single-charger circuits the phase count is changed at
circuit level (dynamicCircuitCurrentP1/P2/P3), matching evcc's
Phases1p3p() circuit-level path.

For all other configurations the charger-level phaseMode setting is used.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_CURRENT,
    PHASE_MODE_1P,
    PHASE_MODE_AUTO,
    PHASE_MODE_FROM_LABEL,
    PHASE_MODE_LABEL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EaseePhaseModeSelect(coord, entry)])


class EaseePhaseModeSelect(CoordinatorEntity, SelectEntity):
    """Phase mode selector: 1-phase or Auto (3-phase).

    Charge MAX supports 1-phase (up to 7.4 kW) and 3-phase (up to 22 kW).
    """

    _attr_name = "Phase Mode"
    _attr_options = list(PHASE_MODE_LABEL.values())   # ["1-phase", "Auto (3-phase)"]
    _attr_icon = "mdi:sine-wave"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._charger_id: str = entry.data["charger_id"]
        self._attr_unique_id = f"{self._charger_id}_phase_mode"

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data.get("config", {}).get("phaseMode")
        if mode is None:
            return None
        # phaseMode 2 and 3 both mean "3-phase / auto" in Easee firmware
        if mode >= PHASE_MODE_AUTO:
            mode = PHASE_MODE_AUTO
        return PHASE_MODE_LABEL.get(mode)

    async def async_select_option(self, option: str) -> None:
        target_mode = PHASE_MODE_FROM_LABEL.get(option)
        if target_mode is None:
            _LOGGER.error("Unknown phase mode option: %s", option)
            return

        coord = self.coordinator

        if coord.circuit_id:
            # TN-grid single-charger circuit — use circuit-level current control
            # (mirrors evcc Phases1p3p circuit-level path)
            cm = coord.circuit_max
            p1 = cm.get("p1", MAX_CURRENT)
            p2 = cm.get("p2", MAX_CURRENT)
            p3 = cm.get("p3", MAX_CURRENT)
            phases = 1 if target_mode == PHASE_MODE_1P else 3
            await coord.client.set_circuit_phases(
                coord.site_id, coord.circuit_id, phases, p1, p2, p3
            )
        else:
            # Charger-level phase mode (phaseMode setting)
            await coord.client.set_phase_mode(self._charger_id, target_mode)

        await coord.async_request_refresh()
