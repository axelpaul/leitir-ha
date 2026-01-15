from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LeitirClient
from .const import (
    CONF_ACCOUNT_NAME,
    CONF_PASSWORD,
    CONF_REFRESH_HOUR,
    CONF_REFRESH_MINUTE,
    CONF_USERNAME,
    DEFAULT_REFRESH_HOUR,
    DEFAULT_REFRESH_MINUTE,
    DOMAIN,
)


class LeitirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return LeitirOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            try:
                session = async_get_clientsession(self.hass)
                client = LeitirClient(session)
                auth = await client.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
                await client.get_loans(auth.token)
                return self.async_create_entry(
                    title=user_input[CONF_ACCOUNT_NAME], data=user_input
                )
            except Exception:
                errors["base"] = "auth_failed"

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NAME): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class LeitirOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        refresh_hour = self.config_entry.options.get(
            CONF_REFRESH_HOUR, DEFAULT_REFRESH_HOUR
        )
        refresh_minute = self.config_entry.options.get(
            CONF_REFRESH_MINUTE, DEFAULT_REFRESH_MINUTE
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_REFRESH_HOUR, default=refresh_hour): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Required(CONF_REFRESH_MINUTE, default=refresh_minute): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=59)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
