import calendar
import re
from datetime import date, datetime, time, timedelta

from .constants import RUSSIAN_MONTHS

WEEKDAY_NAMES = (
    "понедельник",
    "вторник",
    "сред",
    "четверг",
    "пятниц",
    "суббот",
    "воскресень",
)


def resolve_period(text: str, now: datetime) -> tuple[date, date] | None:
    normalized = text.lower()
    today = now.date()

    if "месяц" in normalized:
        if "следующ" in normalized:
            first_day = _first_day_of_next_month(today)
            last_day = calendar.monthrange(first_day.year, first_day.month)[1]
            return first_day, date(first_day.year, first_day.month, last_day)
        if "ближайш" in normalized:
            return today, _add_month(today)
        if any(word in normalized for word in ("этот месяц", "этом месяце", "текущий месяц")):
            last_day = calendar.monthrange(today.year, today.month)[1]
            return date(today.year, today.month, 1), date(today.year, today.month, last_day)

    if "недел" in normalized:
        monday = today - timedelta(days=today.weekday())
        if "следующ" in normalized:
            next_monday = monday + timedelta(days=7)
            return next_monday, next_monday + timedelta(days=6)
        if "ближайш" in normalized:
            return today, today + timedelta(days=6)
        if "до конца недели" in normalized:
            return today, monday + timedelta(days=6)
        if any(word in normalized for word in ("эту неделю", "этой неделе", "текущей неделе")):
            return monday, monday + timedelta(days=6)

    return None


def resolve_daypart(text: str) -> tuple[str, str] | None:
    normalized = text.casefold()
    if re.search(r"\b(?:утром|утра|на утро)\b", normalized):
        return "06:00", "12:00"
    if re.search(r"\b(?:днем|днём|дня|на день)\b", normalized):
        return "12:00", "18:00"
    if re.search(r"\b(?:вечером|вечера|на вечер)\b", normalized):
        return "18:00", "23:59"
    if re.search(r"\b(?:ночью|ночи|на ночь)\b", normalized):
        return "00:00", "06:00"
    return None


def resolve_date(text: str, now: datetime, for_event: bool = False) -> date | None:
    normalized = text.lower()

    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", normalized)
    if iso_match:
        return date.fromisoformat(iso_match.group(1))

    numeric_date = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?\b", normalized)
    if numeric_date:
        day, month = int(numeric_date.group(1)), int(numeric_date.group(2))
        year = int(numeric_date.group(3) or now.year)
        try:
            return date(year, month, day)
        except ValueError:
            return None

    today = now.date()
    if "послезавтра" in normalized:
        return today + timedelta(days=2)
    if re.search(r"\bзавтра\b", normalized):
        return today + timedelta(days=1)
    if re.search(r"\bсегодня\b", normalized):
        return today

    russian_date = re.search(
        r"\b(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4})\s*(?:года?|г\.)?)?\b",
        normalized,
    )
    if russian_date:
        day = int(russian_date.group(1))
        month_name = russian_date.group(2)
        month = RUSSIAN_MONTHS.get(month_name)
        if month is None:
            month = next(
                (number for name, number in RUSSIAN_MONTHS.items() if name.startswith(month_name)),
                None,
            )
        if month is not None:
            year = int(russian_date.group(3) or today.year)
            try:
                return date(year, month, day)
            except ValueError:
                return None

    week_range = resolve_period(text, now)
    weekday = next(
        (index for index, name in enumerate(WEEKDAY_NAMES) if name in normalized),
        None,
    )
    if weekday is not None:
        if "эту неделю" in normalized or "этой неделе" in normalized or "текущей неделе" in normalized:
            return week_range[0] + timedelta(days=weekday) if week_range else None

        days_ahead = (weekday - today.weekday()) % 7
        if "следующ" in normalized and days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    return None


def resolve_event_datetime(text: str, now: datetime) -> datetime | None:
    target_date = resolve_date(text, now, for_event=True)
    if target_date is None:
        return None

    normalized = re.sub(r"(?<=\d)[\ud800-\udfff]+(?=:)", "", text.lower())
    time_match = re.search(r"\b(?:с|в|к)?\s*(\d{1,2}):(\d{2})\b", normalized)
    if not time_match:
        return None
    try:
        event_time = time(int(time_match.group(1)), int(time_match.group(2)))
    except ValueError:
        return None
    return datetime.combine(target_date, event_time)


def _add_month(value: date) -> date:
    month_index = value.month
    year = value.year + (month_index // 12)
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _first_day_of_next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)
