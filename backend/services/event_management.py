import calendar
import re
from datetime import datetime, time, timedelta
from typing import Any
from uuid import uuid4

from backend.ai_service.llm.temporal import resolve_date
from backend.dal.nlp_utils import lemmatize_text


class EventManagementService:
    def __init__(self, repository, collision_processor, logger):
        self.repo = repository
        self.collision = collision_processor
        self.logger = logger
        self._last_ids: dict[str, list[int]] = {}
        self._pending: dict[str, dict[str, Any]] = {}

    def remember(self, session_id: str, events: list[dict[str, Any]]) -> None:
        self._last_ids[session_id] = [event["id"] for event in events if event.get("id") is not None]

    def followup(self, text: str, session_id: str) -> str | None:
        pending = self._pending.get(session_id)
        if not pending:
            return None

        normalized = re.sub(r"[\ud800-\udfff]", "", text.casefold().replace("ё", "е"))
        normalized = " ".join(re.sub(r"[,;.!?]+", " ", normalized).split())
        if re.match(r"^(?:нет\b|не надо\b|не нужно\b|не переноси\b|не ставь\b|отмена\b|отмени\b|оставь как есть\b)", normalized) and not re.search(r"\b(?:лучше|вместо|другое)\b", normalized):
            self._pending.pop(session_id, None)
            return "Хорошо, действие отменено."

        if pending["kind"] in {"conflict", "reschedule"}:
            if re.match(r"^(?:какие|что у меня|найди|покажи|расскажи|привет|удали|отметь|поставь|запланируй|создай|перенеси\s+(?:встречу|задачу|событие))\b", normalized):
                self._pending.pop(session_id, None)
                return None
            proposed = datetime.fromisoformat(pending["data"]["start_time" if pending["action"] == "create_event" else "new_start_time"]) if pending["kind"] == "conflict" else datetime.fromisoformat(pending["start_time"])
            new_date = resolve_date(normalized, datetime.now().astimezone())
            new_time = _followup_time(normalized)
            if new_date or new_time:
                chosen = datetime.combine(new_date or proposed.date(), new_time or proposed.time())
                if pending["kind"] == "reschedule":
                    self._pending.pop(session_id, None)
                    return self.process("update_event", {"event_id": pending["event_id"], "new_start_time": chosen.isoformat()}, session_id)
                updated = dict(pending["data"])
                if pending["action"] == "create_event":
                    duration = datetime.fromisoformat(updated["end_time"]) - proposed
                    updated.update(start_time=chosen.isoformat(), end_time=(chosen + duration).isoformat())
                else:
                    updated.update(new_start_time=chosen.isoformat(), new_date=None, new_time=None)
                self._pending.pop(session_id, None)
                return self.process(pending["action"], updated, session_id)
            if re.fullmatch(r"(?:да|ага|конечно|хорошо|ок|окей|давай|согласен|согласна|подходит|подтверждаю|перенеси|переносим)(?:\s+(?:перенеси|переносим|поставь|добавь|давай))?", normalized):
                self._pending.pop(session_id, None)
                if pending["kind"] == "reschedule":
                    return self.process("update_event", {"event_id": pending["event_id"], "new_start_time": proposed.isoformat()}, session_id)
                return self.process(pending["action"], pending["data"], session_id)
            return f"Предлагаю {proposed:%d.%m в %H:%M}. Можно согласиться, назвать другое время или отменить."

        if re.match(r"^(?:какие|что у меня|найди|покажи|поставь|запланируй|создай|расскажи|привет|перенеси|удали|отметь)\b", normalized):
            self._pending.pop(session_id, None)
            return None

        if pending["kind"] == "count":
            count = _spoken_count(normalized)
            if count is None:
                return "Сколько повторений создать? Назовите число от двух до пятидесяти двух."

            if not 2 <= count <= 52:
                return "Назовите число повторений от двух до пятидесяти двух."
            self._pending.pop(session_id, None)
            data = dict(pending["data"], recurrence_count=count)
            return self.create(data, session_id)

        if pending["kind"] == "target":
            candidates = pending["candidates"]
            match = re.search(r"\b(\d+)\b", normalized)
            ordinal = _spoken_count(normalized)
            index = len(candidates) if "последн" in normalized else (int(match.group(1)) if match else ordinal)
            selected = candidates[index - 1] if index and 1 <= index <= len(candidates) else None

            if selected is None:
                ignored_words = {"выбрать", "вариант", "номер", "событие", "задача", "встреча", "это", "этот", "тот", "который"}
                choice_words = set(lemmatize_text(normalized).split()) - ignored_words
                matches = [event for event in candidates if choice_words and choice_words <= set(lemmatize_text(event["text"]).split())]
                selected = matches[0] if len(matches) == 1 else None
            if selected is None:
                return self._choice_question(candidates)
            self._pending.pop(session_id, None)
            return self.process(pending["action"], dict(pending["data"], event_id=selected["id"]), session_id)
        return None

    def create(self, data: dict[str, Any], session_id: str) -> str:
        start = datetime.fromisoformat(data["start_time"])
        end = datetime.fromisoformat(data["end_time"]) if data.get("end_time") else start + self.collision.default_duration
        frequency = data.get("recurrence")
        count = data.get("recurrence_count")

        if frequency and count is None:
            self._pending[session_id] = {"kind": "count", "data": data}
            return f"Сколько раз повторить «{data['title']}»? Назовите число от двух до пятидесяти двух."

        if not frequency and count:
            return "Уточните, как часто повторять событие: каждый день, неделю или месяц."

        occurrences = self._occurrences(start, end, frequency, count or 1)
        normalized_title = lemmatize_text(data["title"].replace("ё", "е"))
        for occurrence_start, occurrence_end in occurrences:
            same_title = [event for event in self.repo.get_events_by_date(occurrence_start.date()) if lemmatize_text(event["text"].replace("ё", "е")) == normalized_title]
            duplicate = next((event for event in same_title if event.get("time") == occurrence_start.time()), None)
            if duplicate is not None:
                return f"«{data['title']}» уже есть в расписании на {occurrence_start:%d.%m в %H:%M}."
            active_same_title = [event for event in same_title if event.get("status") != "completed"]
            if active_same_title:
                if len(occurrences) == 1 and len(active_same_title) == 1:
                    existing = active_same_title[0]
                    self._pending[session_id] = {"kind": "reschedule", "event_id": existing["id"], "start_time": occurrence_start.isoformat()}
                    return f"«{data['title']}» уже запланирован на {existing['date']:%d.%m} в {existing['time']:%H:%M}. Перенести на {occurrence_start:%H:%M}?"
                return f"На {occurrence_start:%d.%m} уже есть «{data['title']}». Уточните, какое событие перенести."
            conflict = self.collision.check_interval(occurrence_start, occurrence_end)
            if conflict:
                suggestion = self.collision.suggest(occurrence_start, occurrence_end)
                if suggestion and len(occurrences) == 1:
                    new_data = dict(data, start_time=suggestion.isoformat(), end_time=(suggestion + (occurrence_end - occurrence_start)).isoformat())
                    self._pending[session_id] = {"kind": "conflict", "action": "create_event", "data": new_data}
                    return f"В {occurrence_start:%d.%m в %H:%M} уже есть «{conflict['text']}». Перенести «{data['title']}» на {suggestion:%H:%M}?"
                return f"Не добавила «{data['title']}»: {occurrence_start:%d.%m в %H:%M} занято событием «{conflict['text']}». Назовите другое время."

        series_id = str(uuid4()) if frequency else None
        ids = []
        for occurrence_start, occurrence_end in occurrences:
            event_data = dict(data, start_time=occurrence_start.isoformat(), end_time=occurrence_end.isoformat() if data.get("end_time") else None, series_id=series_id)
            event_id = self.repo.create_event(event_data)
            if event_id is not None:
                ids.append(event_id)
        self._last_ids[session_id] = ids

        if frequency:
            return f"Добавила «{data['title']}» в расписание: {len(ids)} повторений, первое {start:%d.%m в %H:%M}."
        return f"Добавила «{data['title']}» в расписание на {start:%d.%m в %H:%M}."

    def process(self, action: str, data: dict[str, Any], session_id: str) -> str:
        if action == "create_event":
            return self.create(data, session_id)

        candidates = self._find_candidates(data, session_id)
        if data.get("scope") == "series":
            unique = {}
            for candidate in candidates:
                unique.setdefault(candidate.get("series_id") or candidate["id"], candidate)
            candidates = list(unique.values())

        if not candidates:
            return "Не нашла подходящее событие. Уточните название или дату."

        if len(candidates) > 1 and data.get("scope") != "all":
            self._pending[session_id] = {"kind": "target", "action": action, "data": data, "candidates": candidates}
            return self._choice_question(candidates)

        event = candidates[0]
        targets = candidates if data.get("scope") == "all" else (self.repo.get_series_events(event["series_id"]) if data.get("scope") == "series" and event.get("series_id") else [event])
        if action == "delete_event":
            for target in targets:
                self.repo.delete_event(target["id"])
            self._last_ids.pop(session_id, None)
            if len(targets) > 1 and data.get("scope") == "all":
                return f"Удалила {len(targets)} событий по запросу «{data.get('query')}»."
            return f"Удалила «{event['text']}»" + (" и все повторения." if len(targets) > 1 else ".")

        if action == "complete_event":
            for target in targets:
                self.repo.complete_event(target["id"])
            self.remember(session_id, targets)
            return f"Отметила «{event['text']}» выполненным" + (" вместе со всеми повторениями." if len(targets) > 1 else ".")

        if action == "update_event":
            return self._update(event, targets, data, session_id)
        return "Неизвестное действие."

    def _update(self, event: dict[str, Any], targets: list[dict[str, Any]], data: dict[str, Any], session_id: str) -> str:
        new_title = data.get("new_title")
        new_start = data.get("new_start_time")
        new_date = data.get("new_date")
        new_time = data.get("new_time")
        if not any((new_title, new_start, new_date, new_time)):
            return "Что изменить: название, дату или время события?"

        first_start = event["start_time"]
        if isinstance(first_start, str):
            first_start = datetime.fromisoformat(first_start)
        if new_start:
            desired = datetime.fromisoformat(new_start) if isinstance(new_start, str) else new_start
        elif new_date:
            desired_date = datetime.fromisoformat(new_date).date() if isinstance(new_date, str) else new_date
            desired = datetime.combine(desired_date, datetime.strptime(new_time, "%H:%M").time() if new_time else first_start.time())
        elif new_time:
            desired = datetime.combine(first_start.date(), datetime.strptime(new_time, "%H:%M").time())
        else:
            desired = first_start

        delta = desired - first_start
        if not delta and (new_date or new_time or new_start) and not new_title:
            return f"«{event['text']}» уже стоит на {first_start:%d.%m в %H:%M}."
        target_ids = {item["id"] for item in targets}
        changes = []
        for target in targets:
            start = target["start_time"]
            if isinstance(start, str):
                start = datetime.fromisoformat(start)

            end = target.get("end_time")
            if isinstance(end, str):
                end = datetime.fromisoformat(end)

            duration = end - start if isinstance(end, datetime) and end > start else self.collision.default_duration
            shifted = start + delta
            changes.append((target, shifted, shifted + duration))

        if delta:
            for target, shifted, shifted_end in changes:
                conflict = self.collision.check_interval(shifted, shifted_end, target_ids)
                if conflict:
                    suggestion = self.collision.suggest(shifted, shifted_end, target_ids)

                    if suggestion and len(targets) == 1:
                        proposal = dict(data, event_id=event["id"], new_start_time=suggestion.isoformat(), new_date=None)
                        self._pending[session_id] = {"kind": "conflict", "action": "update_event", "data": proposal}
                        return f"В {shifted:%d.%m в %H:%M} уже есть «{conflict['text']}». Перенести «{event['text']}» на {suggestion:%H:%M}?"
                    return f"Не перенесла «{event['text']}»: время {shifted:%d.%m в %H:%M} занято событием «{conflict['text']}»."

        for target, shifted, shifted_end in changes:
            self.repo.update_event(target["id"], title=new_title, start_time=shifted if delta else None, end_time=shifted_end if delta else None)
        self.remember(session_id, targets)
        name = new_title or event["text"]

        if delta:
            return f"Перенесла «{name}» на {desired:%d.%m в %H:%M}" + (" со всеми повторениями." if len(targets) > 1 else ".")
        return f"Переименовала событие в «{name}»" + (" со всеми повторениями." if len(targets) > 1 else ".")

    def _find_candidates(self, data: dict[str, Any], session_id: str) -> list[dict[str, Any]]:
        event_id = data.get("event_id")
        if event_id:
            event = self.repo.get_event_by_id(event_id)
            candidates = [event] if event else []
            return self._filter_candidates(candidates, data)

        query = str(data.get("query") or "").casefold().replace("ё", "е").strip()
        if not query or query in {"её", "ее", "его", "это", "эту задачу", "эту встречу", "последнюю"}:
            candidates = [event for identifier in self._last_ids.get(session_id, []) if (event := self.repo.get_event_by_id(identifier))]
            return self._filter_candidates(candidates, data)

        words = set(lemmatize_text(query.replace("ё", "е")).split()) - {"задача", "встреча", "событие", "по", "с", "и", "в", "на", "мне", "слушать"}
        if not words:
            return []
        candidates = [event for event in self.repo.get_all_events() if words <= set(lemmatize_text(event["text"].replace("ё", "е")).split())]
        return self._filter_candidates(candidates, data)

    @staticmethod
    def _filter_candidates(events: list[dict[str, Any]], data: dict[str, Any]) -> list[dict[str, Any]]:
        target_date = data.get("target_date")
        if isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date).date()
        target_time = data.get("target_time")
        if isinstance(target_time, str):
            target_time = datetime.strptime(target_time, "%H:%M").time()
        return [event for event in events if (target_date is None or event.get("date") == target_date) and (target_time is None or event.get("time") == target_time)]

    @staticmethod
    def _choice_question(events: list[dict[str, Any]]) -> str:
        options = "; ".join(f"{index}. {event['text']} — {event['date']:%d.%m} в {event['time']:%H:%M}" for index, event in enumerate(events[:5], 1))
        return f"Уточните, какое событие имеется в виду: {options}? Назовите номер, например «четвёртое событие», или часть названия."

    @staticmethod
    def _occurrences(start: datetime, end: datetime, frequency: str | None, count: int) -> list[tuple[datetime, datetime]]:
        result = []
        for index in range(count):
            if frequency == "daily":
                occurrence = start + timedelta(days=index)
            elif frequency == "weekly":
                occurrence = start + timedelta(weeks=index)
            elif frequency == "monthly":
                month_offset = start.month - 1 + index
                year = start.year + month_offset // 12
                month = month_offset % 12 + 1
                occurrence = start.replace(year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1]))
            else:
                occurrence = start
            result.append((occurrence, occurrence + (end - start)))
        return result


def _spoken_count(text: str) -> int | None:
    words = {
        "ноль": 0, "нуль": 0, "один": 1, "одна": 1, "одно": 1, "первый": 1, "первая": 1, "первое": 1, "первую": 1,
        "два": 2, "две": 2, "второй": 2, "вторая": 2, "второе": 2, "вторую": 2, "три": 3, "третий": 3, "третья": 3, "третье": 3,
        "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11,
        "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
        "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    }
    if digits := re.search(r"\b(\d{1,2})\b", text):
        return int(digits.group(1))
    tokens = re.findall(r"[а-яё]+", text)
    ordinal_patterns = (
        (r"^перв(?:ый|ая|ое|ую|ого|ому|ым|ом)$", 1),
        (r"^втор(?:ой|ая|ое|ую|ого|ому|ым|ом)$", 2),
        (r"^трет(?:ий|ья|ье|ью|ьего|ьему|ьим|ьем)$", 3),
        (r"^четверт(?:ый|ая|ое|ую|ого|ому|ым|ом)$", 4),
        (r"^пят(?:ый|ая|ое|ую|ого|ому|ым|ом)$", 5),
        (r"^шест(?:ой|ая|ое|ую|ого|ому|ым|ом)$", 6),
        (r"^седьм(?:ой|ая|ое|ую|ого|ому|ым|ом)$", 7),
        (r"^восьм(?:ой|ая|ое|ую|ого|ому|ым|ом)$", 8),
        (r"^девят(?:ый|ая|ое|ую|ого|ому|ым|ом)$", 9),
        (r"^десят(?:ый|ая|ое|ую|ого|ому|ым|ом)$", 10),
    )
    for index, token in enumerate(tokens):
        for pattern, ordinal_value in ordinal_patterns:
            if re.match(pattern, token):
                return ordinal_value
        if token not in words:
            continue
        value = words[token]
        if value in {20, 30, 40} and index + 1 < len(tokens) and tokens[index + 1] in words and 1 <= words[tokens[index + 1]] <= 9:
            value += words[tokens[index + 1]]
        return value
    return None


def _followup_time(text: str) -> time | None:
    numeric = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if numeric:
        hour, minute = int(numeric.group(1)), int(numeric.group(2))
        return time(hour, minute) if hour < 24 and minute < 60 else None
    for match in re.finditer(r"\b(?:в|на|к)\s+([а-яё]+|\d{1,2})(?:\s+час(?:а|ов)?)?(?:\s+(утра|вечера|дня|ночи))?\b", text):
        hour = _spoken_count(match.group(1))
        if hour is None or hour > 23:
            continue
        modifier = match.group(2)
        if hour <= 12 and modifier is None:
            continue
        if modifier in {"вечера", "дня"} and hour < 12:
            hour += 12
        if modifier in {"утра", "ночи"} and hour == 12:
            hour = 0
        return time(hour, 0)
    return None
