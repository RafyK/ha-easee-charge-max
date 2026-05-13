"""Config flow for Easee Charge MAX."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EaseeAuthError, EaseeClient
from .const import CONF_CHARGER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EaseeChargeMaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow for Easee Charge MAX."""

    VERSION = 1

    # Temporary storage between steps
    _username: str = ""
    _password: str = ""
    _chargers: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = EaseeClient(user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session)
            try:
                await client.authenticate()
                chargers = await client.get_chargers()
            except EaseeAuthError:
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Easee setup")
                errors["base"] = "unknown"
            else:
                charger_id = user_input.get(CONF_CHARGER_ID, "").strip()

                if not charger_id:
                    if len(chargers) == 1:
                        charger_id = chargers[0]["id"]
                    else:
                        # Multiple chargers — show picker
                        self._chargers = chargers
                        self._username = user_input[CONF_USERNAME]
                        self._password = user_input[CONF_PASSWORD]
                        return await self.async_step_pick_charger()

                await self.async_set_unique_id(charger_id)
                self._abort_if_unique_id_configured()
                return self._create_entry(
                    charger_id, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_CHARGER_ID, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_charger(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            charger_id = user_input[CONF_CHARGER_ID]
            await self.async_set_unique_id(charger_id)
            self._abort_if_unique_id_configured()
            return self._create_entry(charger_id, self._username, self._password)

        options = {c["id"]: f"{c.get('name', c['id'])} ({c['id']})" for c in self._chargers}
        return self.async_show_form(
            step_id="pick_charger",
            data_schema=vol.Schema({vol.Required(CONF_CHARGER_ID): vol.In(options)}),
            errors=errors,
        )

    def _create_entry(self, charger_id: str, username: str, password: str):
        return self.async_create_entry(
            title=f"Easee Charge MAX ({charger_id})",
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_CHARGER_ID: charger_id,
            },
        )
