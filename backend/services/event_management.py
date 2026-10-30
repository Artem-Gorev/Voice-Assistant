import calendar
import re
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

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
        normalized = text.casefold().strip(" .!?")
        if normalized in {"нет", "не надо", "отмена", "отмени"}:
            self._pending.pop(session_id, None)
            return "Хорошо, действие отменено."
        if re.match(r"^(?:какие|что у меня|найди|покажи|поставь|запланируй|создай|расскажи|привет|перенеси|удали|отметь)\b", normalized):
            self._pending.pop(session_id, None)
            return None
        if pending["kind"] == "conflict":
            if normalized in {"да", "давай", "согласен", "согласна", "подходит"}:
                self._pending.pop(session_id, None)
                return self.process(pending["action"], pending["data"], session_id)
            clock = re.search(r"\b(\d{1,2}):(\d{2})\b", normalized)
            if clock and int(clock.group(1)) < 24 and int(clock.group(2)) < 60:
                updated = dict(pending["data"])
                start = datetime.fromisoformat(updated["start_time"] if pending["action"] == "create_event" else updated["new_start_time"])
                replacement = start.replace(hour=int(clock.group(1)), minute=int(clock.group(2)))
                if pending["action"] == "create_event":
                    end = datetime.fromisoformat(updated["end_time"])
                    updated["start_time"] = replacement.isoformat()
                    updated["end_time"] = (replacement + (end - start)).isoformat()
                else:
                    updated["new_start_time"] = replacement.isoformat()
                self._pending.pop(session_id, None)
                return self.process(pending["action"], updated, session_id)
            return "Подтвердите предложенное время словом «да» или назовите другое время в формате 14:30."
        if pending["kind"] == "count":
            match = re.search(r"\b(\d{1,2})\b", normalized)
            if not match:
                return "Сколько повторений создать? Назовите число от 2 до 52."
            count = int(match.group(1))
            if not 2 <= count <= 52:
                return "Назовите число повторений от 2 до 52."
            self._pending.pop(session_id, None)
            data = dict(pending["data"], recurrence_count=count)
            return self.create(data, session_id)
        if pending["kind"] == "target":
            candidates = pending["candidates"]
            match = re.search(r"\b(\d+)\b", normalized)
            ordinal = {"первое": 1, "первую": 1, "второе": 2, "вторую": 2, "третье": 3, "третью": 3}.get(normalized)
            index = int(match.group(1)) if match else ordinal
            selected = candidates[index - 1] if index and 1 <= index <= len(candidates) else None
            if selected is None:
                selected = next((event for event in candidates if normalized in event["text"].casefold()), None)
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
            return f"Сколько раз повторить «{data['title']}»? Назовите число от 2 до 52."
        if not frequency and count:
            return "Уточните, как часто повторять событие: каждый день, неделю или месяц."
        occurrences = self._occurrences(start, end, frequency, count or 1)
        for occurrence_start, occurrence_end in occurrences:
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
        if len(candidates) > 1:
            self._pending[session_id] = {"kind": "target", "action": action, "data": data, "candidates": candidates}
            return self._choice_question(candidates)
        event = candidates[0]
        targets = self.repo.get_series_events(event["series_id"]) if data.get("scope") == "series" and event.get("series_id") else [event]
        if action == "delete_event":
            for target in targets:
                self.repo.delete_event(target["id"])
            self._last_ids.pop(session_id, None)
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
            return [event] if event else []
        query = str(data.get("query") or "").casefold().replace("ё", "е").strip()
        if not query or query in {"её", "ее", "его", "это", "эту задачу", "эту встречу", "последнюю"}:
            return [event for identifier in self._last_ids.get(session_id, []) if (event := self.repo.get_event_by_id(identifier))]
        words = set(lemmatize_text(query.replace("ё", "е")).split()) - {"задача", "встреча", "событие", "по", "с", "и"}
        if not words:
            return []
        return [event for event in self.repo.get_all_events() if words <= set(lemmatize_text(event["text"].replace("ё", "е")).split())]

    @staticmethod
    def _choice_question(events: list[dict[str, Any]]) -> str:
        options = "; ".join(f"{index}. {event['text']} — {event['date']:%d.%m} в {event['time']:%H:%M}" for index, event in enumerate(events[:5], 1))
        return f"Уточните, какое событие имеется в виду: {options}? Назовите номер."

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
