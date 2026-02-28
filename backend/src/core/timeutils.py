from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def interval_to_minutes(interval: str) -> int:
    value = interval.strip().lower()
    mapping = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "60m": 60,
        "1h": 60,
        "1d": 1440,
        "1wk": 10080,
    }
    if value in mapping:
        return mapping[value]
    if value.endswith("m") and value[:-1].isdigit():
        return int(value[:-1])
    if value.endswith("h") and value[:-1].isdigit():
        return int(value[:-1]) * 60
    if value.endswith("d") and value[:-1].isdigit():
        return int(value[:-1]) * 1440
    return 1440
