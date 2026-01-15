from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LeitirClient
from .loan import loan_id, loan_renewable, loans_from_data

_LOGGER = logging.getLogger(__name__)


class LeitirCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    def __init__(self, hass: HomeAssistant, username: str, password: str, account_name: str):
        self.hass = hass
        self.username = username
        self.password = password
        self.account_name = account_name
        self._token: str | None = None

        session = async_get_clientsession(hass)
        self.client = LeitirClient(session)

        super().__init__(
            hass,
            _LOGGER,
            name=f"Leitir {account_name}",
            update_interval=None,
        )

    async def _ensure_token(self) -> str:
        if not self._token:
            auth = await self.client.login(self.username, self.password)
            self._token = auth.token
        return self._token

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            token = await self._ensure_token()
            data = await self.client.get_loans(token)
            if data.get("status") != "ok":
                raise UpdateFailed(data)
            loans_by_id: dict[str, dict[str, Any]] = {}
            for loan in loans_from_data(data):
                loan_id_value = loan_id(loan)
                if loan_id_value is None:
                    continue
                loans_by_id[str(loan_id_value)] = loan
            _LOGGER.debug("Fetched %s loans", len(loans_by_id))
            return loans_by_id
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                self._token = None
                return await self._async_update_data()
            raise UpdateFailed(err) from err
        except Exception as err:
            raise UpdateFailed(err) from err

    async def renew_loan(self, loan_id: str) -> dict[str, Any]:
        token = await self._ensure_token()
        result = await self.client.renew_loan(token, loan_id)
        await self.async_request_refresh()
        return result

    async def renew_all(self) -> list[dict[str, Any]]:
        results = []
        for loan in (self.data or {}).values():
            if not loan_renewable(loan):
                continue
            loan_id_value = loan_id(loan)
            if loan_id_value is not None:
                results.append(await self.renew_loan(str(loan_id_value)))
        return results
