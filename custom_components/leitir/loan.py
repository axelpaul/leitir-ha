from __future__ import annotations

from typing import Any


def _normalize_loans(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def loans_from_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data:
        return []
    if isinstance(data, dict) and data:
        if all(isinstance(value, dict) for value in data.values()):
            if any(loan_id(value) is not None for value in data.values()):
                return [value for value in data.values() if isinstance(value, dict)]
    paths = (
        ("data", "loans", "loan"),
        ("loans", "loan"),
        ("data", "loan"),
        ("loan",),
    )
    for path in paths:
        cursor: Any = data
        for key in path:
            if not isinstance(cursor, dict) or key not in cursor:
                cursor = None
                break
            cursor = cursor[key]
        if cursor is not None:
            return _normalize_loans(cursor)
    return []


def _clean_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        for key in ("value", "date", "duedate", "dueDate"):
            nested = value.get(key)
            if nested not in (None, ""):
                return _clean_value(nested)
        return None
    return value


def loan_field(loan: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in loan:
            value = _clean_value(loan.get(key))
            if value is not None:
                return value
    return None


def loan_due_date(loan: dict[str, Any]) -> Any:
    return loan_field(loan, "duedate", "dueDate", "due_date")


def loan_title(loan: dict[str, Any]) -> Any:
    return loan_field(loan, "title", "title_display", "titleDisplay")


def _clean_title_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    title = str(value).strip()
    if not title:
        return None
    for sep in (" / ", " /", "/ "):
        if sep in title:
            title = title.split(sep)[0].strip()
            break
    return title or None


def loan_title_clean(loan: dict[str, Any]) -> Any:
    return _clean_title_value(loan_title(loan))


def loan_author(loan: dict[str, Any]) -> Any:
    return loan_field(loan, "author", "author_display", "authorDisplay")


def loan_status(loan: dict[str, Any]) -> Any:
    return loan_field(loan, "loanstatus", "loanStatus", "status")


def loan_id(loan: dict[str, Any]) -> Any:
    return loan_field(loan, "loanid", "loanId", "loan_id")


def loan_renewable(loan: dict[str, Any]) -> Any:
    raw = loan_field(loan, "renew", "renewable")
    if isinstance(raw, str):
        return raw.upper() == "Y"
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return None
    return bool(raw)


def loan_raw(loan: dict[str, Any]) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for key, value in loan.items():
        if value in (None, ""):
            continue
        raw[key] = value
    return raw


def loan_summary(loan: dict[str, Any]) -> dict[str, Any]:
    return {
        "loan_id": loan_id(loan),
        "title": loan_title_clean(loan) or loan_title(loan),
        "title_full": loan_title(loan),
        "author": loan_author(loan),
        "due_date": loan_due_date(loan),
        "status": loan_status(loan),
        "renewable": loan_renewable(loan),
    }
