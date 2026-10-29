from datetime import date, time, datetime
from typing import Optional, Union


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
