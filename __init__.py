"""Easee Charge MAX — Home Assistant custom integration.

Provides full control over an Easee Charge MAX EV charger:
  • Start / Stop / Pause / Resume charging
  • Enable / Disable charger hardware
  • Set dynamic (real-time) charging current (6–32 A)
  • Set persistent hardware max current
  • Switch phase mode (1-phase / Auto 3-phase)
  • Smart charging toggle
  • Live sensors: status, power, energy, per-phase currents

All commands go through the Easee Cloud REST API.
State is polled every 30 s (no SignalR WebSocket connection).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EaseeClient
from .const import CONF_CHARGER_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = EaseeClient(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session)
    charger_id: str = entry.data[CONF_CHARGER_ID]

    coordinator = EaseeCoordinator(hass, client, charger_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


class EaseeCoordinator(DataUpdateCoordinator):
    """Polls /state and /config for a single charger."""

    def __init__(self, hass: HomeAssistant, client: EaseeClient, charger_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Easee Charge MAX {charger_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.charger_id = charger_id
        # Circuit info — populated on first refresh, used for TN-grid phase switching
        self.site_id: int = 0
        self.circuit_id: int = 0
        self.circuit_max: dict[str, float] = {}

    async def _async_update_data(self) -> dict:
        try:
            state, config = await asyncio.gather(
                self.client.get_state(self.charger_id),
                self.client.get_config(self.charger_id),
            )
            # Discover site/circuit on first poll
            if not self.site_id:
                await self._discover_circuit()
        except aiohttp.ClientResponseError as exc:
            raise UpdateFailed(f"Easee API {exc.status}: {exc.message}") from exc
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"Network error: {exc}") from exc
        return {"state": state, "config": config}

    async def _discover_circuit(self) -> None:
        """Find a single-charger TN circuit for circuit-level phase control.

        Mirrors evcc determineCircuit() + isTNGrid() logic.
        """
        TN_GRIDS = {1, 2, 3}  # PowerGridTN3Phase, TN2PhasePin234, TN1Phase
        try:
            config = self.data["config"]
            if config.get("detectedPowerGridType") not in TN_GRIDS:
                return
            site = await self.client.get_site(self.charger_id)
            for circuit in site.get("circuits", []):
                chargers = circuit.get("chargers", [])
                if len(chargers) != 1:
                    continue
                if chargers[0]["id"] == self.charger_id:
                    self.site_id = site["id"]
                    self.circuit_id = circuit["id"]
                    self.circuit_max = {
                        "p1": circuit.get("ratedCurrent", MAX_CURRENT),
                        "p2": circuit.get("ratedCurrent", MAX_CURRENT),
                        "p3": circuit.get("ratedCurrent", MAX_CURRENT),
                    }
                    _LOGGER.debug(
                        "Circuit-level phase control: site=%s circuit=%s",
                        self.site_id,
                        self.circuit_id,
                    )
                    return
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not discover circuit topology", exc_info=True)


# import MAX_CURRENT for use in _discover_circuit
from .const import MAX_CURRENT  # noqa: E402  (keeps const import at module level)
