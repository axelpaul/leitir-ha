from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


@dataclass
class LeitirAuth:
    token: str


class LeitirClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._base = "https://leitir.is"

    async def login(self, username: str, password: str) -> LeitirAuth:
        url = f"{self._base}/primaws/suprimaLogin?lang=is"
        payload = {
            "authenticationProfile": "Alma",
            "username": username,
            "password": password,
            "institution": "354ILC_ALM",
            "view": "354ILC_ALM:10000_UNION",
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        async with self._session.post(url, data=payload, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
        raw = data.get("jwtData")
        if not raw:
            raise RuntimeError("jwtData missing")
        return LeitirAuth(token=str(raw).strip('"'))

    async def get_loans(self, token: str) -> dict[str, Any]:
        url = (
            f"{self._base}/primaws/rest/priv/myaccount/loans?bulk=50&lang=is&offset=1&type=active"
        )
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        async with self._session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def renew_loan(self, token: str, loan_id: str) -> dict[str, Any]:
        url = f"{self._base}/primaws/rest/priv/myaccount/renew_loans?lang=is"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json;charset=UTF-8",
        }
        async with self._session.post(url, headers=headers, json={"id": loan_id}) as resp:
            resp.raise_for_status()
            return await resp.json()
