from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_ACCOUNT_NAME,
    CONF_PASSWORD,
    CONF_REFRESH_HOUR,
    CONF_REFRESH_MINUTE,
    CONF_USERNAME,
    DOMAIN,
    PLATFORMS,
    DEFAULT_REFRESH_HOUR,
    DEFAULT_REFRESH_MINUTE,
    DEFAULT_REFRESH_SECOND,
    SERVICE_RENEW_ALL,
    SERVICE_RENEW_LOAN,
    SERVICE_REFRESH,
)
from .coordinator import LeitirCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def handle_renew_loan(call: ServiceCall) -> None:
        loan_id = call.data["loan_id"]
        for coord in hass.data[DOMAIN].values():
            await coord.renew_loan(loan_id)

    async def handle_renew_all(call: ServiceCall) -> None:
        for coord in hass.data[DOMAIN].values():
            await coord.renew_all()

    async def handle_refresh(call: ServiceCall) -> None:
        for coord in hass.data[DOMAIN].values():
            await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_RENEW_LOAN,
        handle_renew_loan,
        schema=vol.Schema({vol.Required("loan_id"): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_RENEW_ALL, handle_renew_all)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord = LeitirCoordinator(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_ACCOUNT_NAME],
    )
    hass.data[DOMAIN][entry.entry_id] = coord
    await coord.async_config_entry_first_refresh()

    refresh_hour = entry.options.get(CONF_REFRESH_HOUR, DEFAULT_REFRESH_HOUR)
    refresh_minute = entry.options.get(CONF_REFRESH_MINUTE, DEFAULT_REFRESH_MINUTE)

    async def _daily_refresh(now) -> None:
        await coord.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(
            hass,
            _daily_refresh,
            hour=refresh_hour,
            minute=refresh_minute,
            second=DEFAULT_REFRESH_SECOND,
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
