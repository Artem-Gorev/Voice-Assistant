from datetime import date, time, datetime
from typing import Optional, Any, Union


def _normalize_date(val: Union[date, str, datetime, None]) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val)
    return val


def _normalize_time(val: Union[time, str, datetime, None]) -> Optional[time]:
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


def _normalize_datetime(val: Union[datetime, date, str, None]) -> Optional[datetime]:
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


def _extract_date_time(val: Any) -> tuple[Optional[date], Optional[time]]:
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
