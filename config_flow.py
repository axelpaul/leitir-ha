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
    CONF_REFRESH_TIMES,
    CONF_USERNAME,
    DEFAULT_REFRESH_HOUR,
    DEFAULT_REFRESH_MINUTE,
    DOMAIN,
    normalize_refresh_times,
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

    def _default_refresh_times(self) -> str:
        try:
            times = normalize_refresh_times(
                self.config_entry.options.get(CONF_REFRESH_TIMES)
            )
        except ValueError:
            times = []
        if not times:
            refresh_hour = self.config_entry.options.get(
                CONF_REFRESH_HOUR, DEFAULT_REFRESH_HOUR
            )
            refresh_minute = self.config_entry.options.get(
                CONF_REFRESH_MINUTE, DEFAULT_REFRESH_MINUTE
            )
            times = [f"{refresh_hour:02d}:{refresh_minute:02d}"]
        return ", ".join(times)

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                times = normalize_refresh_times(
                    user_input.get(CONF_REFRESH_TIMES, "")
                )
                if not times:
                    raise ValueError("empty times")
                user_input[CONF_REFRESH_TIMES] = times
            except ValueError:
                errors["base"] = "invalid_refresh_times"
            else:
                return self.async_create_entry(title="", data=user_input)

        refresh_times = self._default_refresh_times()
        schema = vol.Schema(
            {
                vol.Required(CONF_REFRESH_TIMES, default=refresh_times): str,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
