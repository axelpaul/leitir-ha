from __future__ import annotations

import logging
from datetime import date, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_ACCOUNT_NAME, DOMAIN
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
    account_label = entry.data.get(CONF_ACCOUNT_NAME) or entry.title or entry.entry_id
    account_slug = slugify(account_label) or entry.entry_id
    entities = [
        LeitirSummarySensor(coord, entry.entry_id),
        LeitirRenewableCountSensor(coord, entry.entry_id),
        LeitirNextDueDateSensor(coord, entry.entry_id),
    ]

    registry = er.async_get(hass)
    loan_entities: dict[str, LeitirLoanSensor] = {}
    added_loan_ids: set[str] = set()
    last_loan_ids: set[str] = set()

    def _desired_object_id(loan_id_value: str) -> str:
        return f"{account_slug}_loan_{loan_id_value}"

    def _desired_entity_id(loan_id_value: str) -> str:
        return f"sensor.{_desired_object_id(loan_id_value)}"

    def _sync_entity_id(loan_id_value: str) -> str | None:
        unique_id = f"{entry.entry_id}_loan_{loan_id_value}"
        desired_entity_id = _desired_entity_id(loan_id_value)
        existing_entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if existing_entity_id:
            if existing_entity_id == desired_entity_id:
                return existing_entity_id
            existing_entry = registry.async_get(desired_entity_id)
            if existing_entry and existing_entry.entity_id != existing_entity_id:
                _LOGGER.warning(
                    "Entity id %s already in use; keeping %s",
                    desired_entity_id,
                    existing_entity_id,
                )
                return existing_entity_id
            _LOGGER.debug(
                "Renaming loan entity %s to %s", existing_entity_id, desired_entity_id
            )
            registry.async_update_entity(existing_entity_id, new_entity_id=desired_entity_id)
            return desired_entity_id
        existing_entry = registry.async_get(desired_entity_id)
        if existing_entry and existing_entry.unique_id != unique_id:
            _LOGGER.warning(
                "Entity id %s already in use; keeping generated id",
                desired_entity_id,
            )
            return None
        return desired_entity_id

    def _current_loan_ids() -> set[str]:
        data = coord.data or {}
        if isinstance(data, dict):
            return {str(loan_id_value) for loan_id_value in data.keys()}
        return set()

    def _build_loan_entities(loan_ids: set[str]) -> list[LeitirLoanSensor]:
        new_entities: list[LeitirLoanSensor] = []
        for loan_id_value in sorted(loan_ids):
            if loan_id_value in added_loan_ids:
                continue
            entity = LeitirLoanSensor(coord, entry.entry_id, loan_id_value, account_slug)
            entity_id = _sync_entity_id(loan_id_value)
            if entity_id:
                entity.entity_id = entity_id
            new_entities.append(entity)
            loan_entities[loan_id_value] = entity
            added_loan_ids.add(loan_id_value)
        return new_entities

    current_loan_ids = _current_loan_ids()
    prefix = f"{entry.entry_id}_loan_"
    stale_registry_ids: list[str] = []
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain != "sensor" or reg_entry.platform != DOMAIN:
            continue
        unique_id = reg_entry.unique_id
        if not unique_id or not unique_id.startswith(prefix):
            continue
        loan_id_value = unique_id[len(prefix):]
        if loan_id_value in current_loan_ids:
            continue
        stale_registry_ids.append(loan_id_value)
        _LOGGER.debug("Removing stale loan entity %s", reg_entry.entity_id)
        registry.async_remove(reg_entry.entity_id)

    if stale_registry_ids:
        _LOGGER.debug(
            "Removed stale loan ids from registry: %s", sorted(stale_registry_ids)
        )

    entities.extend(_build_loan_entities(current_loan_ids))
    last_loan_ids = set(current_loan_ids)

    async_add_entities(entities)

    def _handle_coordinator_update() -> None:
        nonlocal last_loan_ids

        if not coord.last_update_success:
            return

        current_loan_ids = _current_loan_ids()
        added_ids = sorted(current_loan_ids - last_loan_ids)
        removed_ids = sorted(last_loan_ids - current_loan_ids)
        if added_ids:
            _LOGGER.debug("Detected new loan ids: %s", added_ids)
        if removed_ids:
            _LOGGER.debug("Detected removed loan ids: %s", removed_ids)

        new_entities = _build_loan_entities(set(added_ids))
        if new_entities:
            async_add_entities(new_entities)

        for loan_id_value in removed_ids:
            added_loan_ids.discard(loan_id_value)
            entity = loan_entities.pop(loan_id_value, None)
            if entity is not None:
                hass.async_create_task(entity.async_remove())
                if entity.entity_id:
                    registry.async_remove(entity.entity_id)
            else:
                unique_id = f"{entry.entry_id}_loan_{loan_id_value}"
                entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
                if entity_id:
                    registry.async_remove(entity_id)

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
    def __init__(
        self,
        coord: LeitirCoordinator,
        entry_id: str,
        loan_id: str,
        account_slug: str,
    ):
        super().__init__(coord)
        self._loan_id = loan_id
        self._attr_unique_id = f"{entry_id}_loan_{loan_id}"
        self._attr_name = f"{coord.account_name} Loan {loan_id}"
        self._attr_suggested_object_id = f"{account_slug}_loan_{loan_id}"

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
