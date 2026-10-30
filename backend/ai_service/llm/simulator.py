import re
from datetime import date, datetime, time, timedelta
from typing import Any

from .constants import (
    CREATE_TRIGGERS,
    LIST_TRIGGERS,
    RUSSIAN_MONTH_PATTERN,
    RUSSIAN_MONTHS,
    SEARCH_TRIGGERS,
)
from .session import DialogSession

DateTimeSpan = tuple[datetime | None, datetime | None]


class NLUSimulator:
    def process(self, user_text: str, session: DialogSession | None, now: datetime) -> dict[str, Any]:
        text_lower = user_text.lower().strip()

        if session and session.missing_field == "start_time":
            title = session.partial_data.get("title", "Событие")
            start_dt, end_dt = self._extract_datetime_span(user_text, now)
            if start_dt:
                time_str = start_dt.strftime("%H:%M")
                date_label = (
                    "завтра"
                    if start_dt.date() == (now.date() + timedelta(days=1))
                    else ("сегодня" if start_dt.date() == now.date() else start_dt.strftime("%d.%m"))
                )
                end_str = f" до {end_dt.strftime('%H:%M')}" if end_dt else ""
                reply = f"Добавила «{title}» в расписание на {date_label} с {time_str}{end_str}."
                return {
                    "action": "create_event",
                    "data": {
                        "title": title,
                        "start_time": start_dt.isoformat(),
                        "end_time": end_dt.isoformat() if end_dt else None,
                        "category": "Другое",
                        "description": None,
                    },
                    "reply_text": reply,
                }

        if any(tr in text_lower for tr in SEARCH_TRIGGERS) and not any(
            word in text_lower for word in CREATE_TRIGGERS
        ):
            query = user_text
            for tr in (*SEARCH_TRIGGERS, "пожалуйста"):
                query = re.sub(rf"\b{tr}\b", "", query, flags=re.IGNORECASE)
            return {
                "action": "search_events",
                "data": {"query": query.strip(" :?!."), "date_from": None, "date_to": None},
                "reply_text": None,
            }

        if any(tr in text_lower for tr in LIST_TRIGGERS):
            target_date = now.date()
            if "завтра" in text_lower:
                target_date += timedelta(days=1)
            elif "послезавтра" in text_lower:
                target_date += timedelta(days=2)
            else:
                date_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text_lower)
                if date_match:
                    target_date = date.fromisoformat(date_match.group(0))
                else:
                    date_ru_match = re.search(
                        rf"\b(\d{{1,2}})\s+({RUSSIAN_MONTH_PATTERN})\b",
                        text_lower,
                    )
                    if date_ru_match:
                        day_num = int(date_ru_match.group(1))
                        mon_num = RUSSIAN_MONTHS[date_ru_match.group(2)]
                        target_date = date(now.year, mon_num, day_num)

            return {
                "action": "list_events",
                "data": {"date": target_date.isoformat()},
                "reply_text": None,
            }

        is_create_request = (
            any(trigger in text_lower for trigger in CREATE_TRIGGERS)
            or "созвон" in text_lower
            or "встреч" in text_lower
        )
        if is_create_request:
            start_dt, end_dt = self._extract_datetime_span(user_text, now)

            clean_title = user_text
            for tr in (*CREATE_TRIGGERS, "пожалуйста", "встречу", "событие"):
                clean_title = re.sub(rf"\b{tr}\b", "", clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(
                r"\b(на\s+завтра|на\s+сегодня|завтра|сегодня)\b",
                "",
                clean_title,
                flags=re.IGNORECASE,
            )
            clean_title = re.sub(
                r"\b(с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2})\b",
                "",
                clean_title,
                flags=re.IGNORECASE,
            )
            clean_title = re.sub(r"\b(в\s+\d{1,2}:\d{2})\b", "", clean_title, flags=re.IGNORECASE)
            clean_title = " ".join(clean_title.strip(" :?!.").split())
            if not clean_title:
                clean_title = "Новое событие"
            clean_title = clean_title[0].upper() + clean_title[1:]

            if not start_dt:
                return {
                    "action": "clarify",
                    "data": {
                        "missing_field": "start_time",
                        "partial_data": {"title": clean_title},
                    },
                    "reply_text": f"На какое время запланировать {clean_title.lower()}?",
                }

            time_str = start_dt.strftime("%H:%M")
            date_label = (
                "завтра"
                if start_dt.date() == (now.date() + timedelta(days=1))
                else ("сегодня" if start_dt.date() == now.date() else start_dt.strftime("%d.%m"))
            )
            end_str = f" до {end_dt.strftime('%H:%M')}" if end_dt else ""
            return {
                "action": "create_event",
                "data": {
                    "title": clean_title,
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat() if end_dt else None,
                    "category": (
                        "Встреча"
                        if "созвон" in text_lower or "встреч" in text_lower
                        else "Другое"
                    ),
                    "description": None,
                },
                "reply_text": (
                    f"Добавила «{clean_title}» в расписание на {date_label} "
                    f"с {time_str}{end_str}."
                ),
            }

        return {
            "action": "chat",
            "data": {},
            "reply_text": (
                "Привет! Я голосовая ассистентка. Могу запланировать встречу, "
                "показать расписание или найти событие."
            ),
        }

    def _extract_datetime_span(self, text: str, now: datetime) -> DateTimeSpan:
        text_lower = text.lower()
        target_date = None

        if "завтра" in text_lower:
            target_date = now.date() + timedelta(days=1)
        elif "послезавтра" in text_lower:
            target_date = now.date() + timedelta(days=2)
        elif "сегодня" in text_lower:
            target_date = now.date()
        else:
            iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text_lower)
            if iso_match:
                target_date = date.fromisoformat(iso_match.group(1))

        span_match = re.search(
            r"с\s+(\d{1,2}):(\d{2})\s+до\s+(\d{1,2}):(\d{2})", text_lower
        )
        if span_match:
            sh, sm, eh, em = map(int, span_match.groups())
            if target_date is None:
                start_candidate = time(sh, sm)
                target_date = (
                    now.date()
                    if start_candidate > now.time()
                    else (now.date() + timedelta(days=1))
                )
            start_dt = datetime.combine(target_date, time(sh, sm))
            end_dt = datetime.combine(target_date, time(eh, em))
            return start_dt, end_dt

        time_match = re.search(r"(?:в|на)\s+(\d{1,2}):(\d{2})", text_lower)
        if time_match:
            h, m = map(int, time_match.groups())
            if target_date is None:
                single_time = time(h, m)
                target_date = (
                    now.date()
                    if single_time > now.time()
                    else (now.date() + timedelta(days=1))
                )
            start_dt = datetime.combine(target_date, time(h, m))
            return start_dt, None

        return None, None
