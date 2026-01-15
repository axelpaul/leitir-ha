from __future__ import annotations

import logging
from datetime import date, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LeitirCoordinator
from .loan import (
    loan_author,
    loan_due_date,
    loan_id,
    loan_raw,
    loan_renewable,
    loan_status,
    loan_summary,
    loan_title,
    loan_title_clean,
    loans_from_data,
)

_LOGGER = logging.getLogger(__name__)


def _parse_yyyymmdd(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    if len(value) != 8 or not value.isdigit():
        return None
    return datetime.strptime(value, "%Y%m%d").date()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    coord: LeitirCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LeitirSummarySensor(coord, entry.entry_id),
        LeitirRenewableCountSensor(coord, entry.entry_id),
        LeitirNextDueDateSensor(coord, entry.entry_id),
    ]

    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_loan_"
    known_loan_ids: set[str] = set()
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain != "sensor" or reg_entry.platform != DOMAIN:
            continue
        unique_id = reg_entry.unique_id
        if not unique_id or not unique_id.startswith(prefix):
            continue
        known_loan_ids.add(unique_id[len(prefix):])

    added_loan_ids: set[str] = set()
    last_loan_ids: set[str] = set()

    def _current_loan_ids() -> set[str]:
        data = coord.data or {}
        if isinstance(data, dict):
            return {str(loan_id_value) for loan_id_value in data.keys()}
        return set()

    current_loan_ids = _current_loan_ids()
    for loan_id_value in sorted(known_loan_ids | current_loan_ids):
        added_loan_ids.add(loan_id_value)
        entities.append(LeitirLoanSensor(coord, entry.entry_id, loan_id_value))
    last_loan_ids = set(current_loan_ids)

    async_add_entities(entities)

    def _handle_coordinator_update() -> None:
        nonlocal last_loan_ids

        current_loan_ids = _current_loan_ids()
        added_ids = sorted(current_loan_ids - last_loan_ids)
        removed_ids = sorted(last_loan_ids - current_loan_ids)
        if added_ids:
            _LOGGER.debug("Detected new loan ids: %s", added_ids)
        if removed_ids:
            _LOGGER.debug("Detected removed loan ids: %s", removed_ids)

        new_entity_ids = current_loan_ids - added_loan_ids
        if new_entity_ids:
            async_add_entities(
                [
                    LeitirLoanSensor(coord, entry.entry_id, loan_id_value)
                    for loan_id_value in sorted(new_entity_ids)
                ]
            )
            added_loan_ids.update(new_entity_ids)

        last_loan_ids = current_loan_ids

    entry.async_on_unload(coord.async_add_listener(_handle_coordinator_update))


class LeitirSummarySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coord: LeitirCoordinator, entry_id: str):
        super().__init__(coord)
        self._attr_unique_id = f"{entry_id}_summary"
        self._attr_name = f"{coord.account_name} Loans"
        self._attr_suggested_object_id = f"{coord.account_name}_loans"

    @property
    def native_value(self):
        return len(loans_from_data(self.coordinator.data))

    @property
    def extra_state_attributes(self):
        return {
            "loans": [loan_summary(loan) for loan in loans_from_data(self.coordinator.data)]
        }


class LeitirRenewableCountSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coord: LeitirCoordinator, entry_id: str):
        super().__init__(coord)
        self._attr_unique_id = f"{entry_id}_renewable_count"
        self._attr_name = f"{coord.account_name} Renewable Loans"
        self._attr_suggested_object_id = f"{coord.account_name}_renewable_count"

    @property
    def native_value(self):
        count = 0
        for loan in loans_from_data(self.coordinator.data):
            if loan_renewable(loan) is True:
                count += 1
        return count


class LeitirNextDueDateSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coord: LeitirCoordinator, entry_id: str):
        super().__init__(coord)
        self._attr_unique_id = f"{entry_id}_next_due"
        self._attr_name = f"{coord.account_name} Next Due"
        self._attr_suggested_object_id = f"{coord.account_name}_next_due"

    @property
    def native_value(self):
        due_dates = []
        for loan in loans_from_data(self.coordinator.data):
            due_raw = loan_due_date(loan)
            if isinstance(due_raw, str):
                parsed = _parse_yyyymmdd(due_raw)
                if parsed:
                    due_dates.append(parsed)
        return min(due_dates) if due_dates else None


class LeitirLoanSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coord: LeitirCoordinator, entry_id: str, loan_id: str):
        super().__init__(coord)
        self._loan_id = loan_id
        self._attr_unique_id = f"{entry_id}_loan_{loan_id}"
        self._attr_name = f"{coord.account_name} Loan {loan_id}"
        self._attr_suggested_object_id = f"{coord.account_name}_loan_{loan_id}"

    def _loan(self):
        data = self.coordinator.data or {}
        if isinstance(data, dict):
            loan = data.get(self._loan_id)
            if isinstance(loan, dict):
                return loan
        for loan in loans_from_data(self.coordinator.data):
            if str(loan_id(loan)) == self._loan_id:
                return loan
        return None

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        return self._loan() is not None

    @property
    def name(self) -> str | None:
        loan = self._loan() or {}
        title = loan_title_clean(loan) or loan_title(loan)
        if title:
            return f"{self.coordinator.account_name} {title}"
        return self._attr_name

    @property
    def native_value(self):
        loan = self._loan()
        if not loan:
            return None
        due_date = loan_due_date(loan)
        if due_date is not None:
            return due_date
        title = loan_title_clean(loan) or loan_title(loan)
        if title is not None:
            return str(title)
        return None

    @property
    def extra_state_attributes(self):
        loan = self._loan() or {}
        return {
            "title": loan_title(loan),
            "title_clean": loan_title_clean(loan),
            "author": loan_author(loan),
            "due_date": loan_due_date(loan),
            "status": loan_status(loan),
            "renewable": loan_renewable(loan),
            "loan_id": loan_id(loan),
            "details": loan_raw(loan),
        }
