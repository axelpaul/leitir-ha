from typing import Any

DOMAIN = "leitir"
PLATFORMS = ["sensor"]

CONF_ACCOUNT_NAME = "account_name"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REFRESH_HOUR = "refresh_hour"
CONF_REFRESH_MINUTE = "refresh_minute"
CONF_REFRESH_TIMES = "refresh_times"

DEFAULT_REFRESH_HOUR = 18
DEFAULT_REFRESH_MINUTE = 0
DEFAULT_REFRESH_SECOND = 0

SERVICE_RENEW_LOAN = "renew_loan"
SERVICE_RENEW_ALL = "renew_all"
SERVICE_REFRESH = "refresh"


def _parse_time(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("invalid time")
    hour_text, minute_text = parts
    if not hour_text.isdigit() or not minute_text.isdigit():
        raise ValueError("invalid time")
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("invalid time")
    return hour, minute


def parse_refresh_times(value: Any) -> list[tuple[int, int]]:
    if value is None:
        return []
    parts: list[str] = []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                if item:
                    parts.append(item)
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                if all(isinstance(part, int) for part in item):
                    parts.append(f"{item[0]}:{item[1]}")
    else:
        return []
    times: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for part in parts:
        hour, minute = _parse_time(part)
        key = (hour, minute)
        if key in seen:
            continue
        seen.add(key)
        times.append(key)
    return times


def normalize_refresh_times(value: Any) -> list[str]:
    return [f"{hour:02d}:{minute:02d}" for hour, minute in parse_refresh_times(value)]
