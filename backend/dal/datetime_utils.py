import os
from datetime import date, time, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


def get_app_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Moscow"))


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=get_app_timezone())
    return value.astimezone(timezone.utc)


def to_local_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(get_app_timezone()).replace(tzinfo=None)


def _normalize_date(val: date | str | datetime | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val)
    return val


def _normalize_time(val: time | str | datetime | None) -> time | None:
    if val is None:
        return None
    if isinstance(val, time):
        return val.replace(tzinfo=None) if val.tzinfo is not None else val
    if isinstance(val, datetime):
        t = val.time()
        return t.replace(tzinfo=None) if t.tzinfo is not None else t
    if isinstance(val, str):
        t = time.fromisoformat(val)
        return t.replace(tzinfo=None) if t.tzinfo is not None else t
    return val


def _normalize_datetime(val: datetime | date | str | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, time(0, 0))
    if isinstance(val, str):
        clean_str = val.strip()
        if not clean_str:
            return None
        return datetime.fromisoformat(clean_str.replace("Z", "+00:00"))
    return None


def _extract_date_time(val: Any) -> tuple[date | None, time | None]:
    if val is None:
        return None, None
    if isinstance(val, datetime):
        t = val.time()
        if t.tzinfo is not None:
            t = t.replace(tzinfo=None)
        return val.date(), t
    if isinstance(val, date):
        return val, None
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            t = dt.time()
            if t.tzinfo is not None:
                t = t.replace(tzinfo=None)
            return dt.date(), t
        except Exception as e:
            raise Exception(f"Ошибка при извлечении даты и времени: {e}")
    return None, None
