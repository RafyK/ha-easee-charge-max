"""Async Easee Cloud REST API client.

API endpoints and payload shapes are derived from the evcc Go implementation:
  charger/easee/identity.go  — authentication / token refresh
  charger/easee/types.go     — ChargerSettings, CircuitSettings, ChargerStatus
  charger/easee.go           — Enable(), MaxCurrent(), Phases1p3p()
"""
from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_CHARGER_CMD,
    API_CHARGER_CONFIG,
    API_CHARGER_SETTINGS,
    API_CHARGER_SITE,
    API_CHARGER_STATE,
    API_CHARGERS,
    API_CIRCUIT_SETTINGS,
    API_LOGIN,
    API_REFRESH,
    MIN_CURRENT,
    MAX_CURRENT,
    PHASE_MODE_1P,
    PHASE_MODE_AUTO,
)

_LOGGER = logging.getLogger(__name__)


class EaseeAuthError(Exception):
    """Raised when credentials are rejected."""


class EaseeClient:
    """Minimal async client for the Easee Cloud REST API."""

    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0

    # ── Authentication ────────────────────────────────────────────────────────

    async def authenticate(self) -> None:
        """Obtain a new access/refresh token pair using username + password."""
        payload = {"userName": self._username, "password": self._password}
        async with self._session.post(API_LOGIN, json=payload) as resp:
            if resp.status == 401:
                raise EaseeAuthError("Invalid Easee credentials")
            resp.raise_for_status()
            data = await resp.json()
        self._store_tokens(data)

    async def _refresh(self) -> None:
        payload = {
            "accessToken": self._access_token,
            "refreshToken": self._refresh_token,
        }
        async with self._session.post(API_REFRESH, json=payload) as resp:
            if resp.status in (400, 401):
                _LOGGER.debug("Token refresh failed — re-authenticating")
                await self.authenticate()
                return
            resp.raise_for_status()
            data = await resp.json()
        self._store_tokens(data)

    def _store_tokens(self, data: dict) -> None:
        self._access_token = data["accessToken"]
        self._refresh_token = data["refreshToken"]
        # subtract 60 s to refresh before actual expiry
        self._token_expiry = time.monotonic() + float(data.get("expiresIn", 3600)) - 60

    async def _token(self) -> str:
        """Return a valid bearer token, refreshing automatically."""
        if self._access_token is None:
            await self.authenticate()
        elif time.monotonic() >= self._token_expiry:
            await self._refresh()
        return self._access_token  # type: ignore[return-value]

    def _hdrs(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def get_chargers(self) -> list[dict[str, Any]]:
        """Return all chargers on the account."""
        tok = await self._token()
        async with self._session.get(API_CHARGERS, headers=self._hdrs(tok)) as r:
            r.raise_for_status()
            return await r.json()

    async def get_site(self, charger_id: str) -> dict[str, Any]:
        """Return the site/circuit topology for a charger."""
        tok = await self._token()
        url = API_CHARGER_SITE.format(charger_id=charger_id)
        async with self._session.get(url, headers=self._hdrs(tok)) as r:
            r.raise_for_status()
            return await r.json()

    # ── State & Config ────────────────────────────────────────────────────────

    async def get_state(self, charger_id: str) -> dict[str, Any]:
        """Runtime state: op-mode, power, currents, energies, etc."""
        tok = await self._token()
        url = API_CHARGER_STATE.format(charger_id=charger_id)
        async with self._session.get(url, headers=self._hdrs(tok)) as r:
            r.raise_for_status()
            return await r.json()

    async def get_config(self, charger_id: str) -> dict[str, Any]:
        """Static config: maxChargerCurrent, phaseMode, enabled, etc."""
        tok = await self._token()
        url = API_CHARGER_CONFIG.format(charger_id=charger_id)
        async with self._session.get(url, headers=self._hdrs(tok)) as r:
            r.raise_for_status()
            return await r.json()

    # ── Commands (start / stop / pause / resume) ──────────────────────────────

    async def send_command(self, charger_id: str, cmd: str) -> None:
        """Send a control command (start_charging, stop_charging, …).

        The HTTP response is 200 (sync) or 202 (async — the charger will
        confirm via SignalR, which this client does not implement).
        Both are treated as success here.
        """
        tok = await self._token()
        url = API_CHARGER_CMD.format(charger_id=charger_id, cmd=cmd)
        async with self._session.post(url, headers=self._hdrs(tok)) as r:
            if r.status not in (200, 202):
                r.raise_for_status()

    # ── Settings ──────────────────────────────────────────────────────────────

    async def set_charger_settings(self, charger_id: str, payload: dict) -> None:
        """POST /chargers/{id}/settings with an arbitrary subset of fields.

        Mirrors evcc ChargerSettings (types.go): only supplied keys are sent
        (omitempty equivalent achieved by only including keys in payload).
        """
        tok = await self._token()
        url = API_CHARGER_SETTINGS.format(charger_id=charger_id)
        async with self._session.post(url, json=payload, headers=self._hdrs(tok)) as r:
            if r.status not in (200, 202):
                r.raise_for_status()

    async def set_circuit_settings(
        self, site_id: int, circuit_id: int, payload: dict
    ) -> None:
        """POST /sites/{siteId}/circuits/{circuitId}/settings."""
        tok = await self._token()
        url = API_CIRCUIT_SETTINGS.format(site_id=site_id, circuit_id=circuit_id)
        async with self._session.post(url, json=payload, headers=self._hdrs(tok)) as r:
            if r.status not in (200, 202):
                r.raise_for_status()

    # ── High-level helpers ───────────────────────────────────────────────────

    async def set_enabled(self, charger_id: str, enabled: bool) -> None:
        """Enable or disable the charger hardware."""
        await self.set_charger_settings(charger_id, {"enabled": enabled})

    async def set_dynamic_current(self, charger_id: str, current: float, hw_max: float = MAX_CURRENT) -> None:
        """Set real-time dynamic charging current (A).

        Mirrors evcc MaxCurrent(): clamps to hw_max before sending.
        """
        clamped = max(MIN_CURRENT, min(float(current), float(hw_max) if hw_max > 0 else MAX_CURRENT))
        await self.set_charger_settings(charger_id, {"dynamicChargerCurrent": clamped})

    async def set_max_charger_current(self, charger_id: str, current: int) -> None:
        """Set the persistent hardware max current limit (integer A)."""
        await self.set_charger_settings(charger_id, {"maxChargerCurrent": int(current)})

    async def set_phase_mode(self, charger_id: str, phase_mode: int) -> None:
        """Set charger-level phase mode (1 = 1-phase, 2 = auto/3-phase).

        Mirrors evcc Phases1p3p() charger-level path.
        """
        await self.set_charger_settings(charger_id, {"phaseMode": phase_mode})

    async def set_circuit_phases(
        self,
        site_id: int,
        circuit_id: int,
        phases: int,
        max_p1: float,
        max_p2: float,
        max_p3: float,
    ) -> None:
        """Set phase count at circuit level for TN-grid single-charger circuits.

        Mirrors evcc Phases1p3p() circuit-level path:
          1-phase: P1=max, P2=0, P3=0
          3-phase: P1=max, P2=max, P3=max
        """
        if phases == 1:
            payload = {
                "dynamicCircuitCurrentP1": max_p1,
                "dynamicCircuitCurrentP2": 0.0,
                "dynamicCircuitCurrentP3": 0.0,
            }
        else:
            payload = {
                "dynamicCircuitCurrentP1": max_p1,
                "dynamicCircuitCurrentP2": max_p2,
                "dynamicCircuitCurrentP3": max_p3,
            }
        await self.set_circuit_settings(site_id, circuit_id, payload)

    async def set_smart_charging(self, charger_id: str, enabled: bool) -> None:
        """Enable/disable smart charging (LED turns blue in smart mode)."""
        await self.set_charger_settings(charger_id, {"smartCharging": enabled})
