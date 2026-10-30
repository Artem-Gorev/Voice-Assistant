import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from backend.event_text import clean_event_title

from .base import LanguageModel
from .config import LLMConfig
from .constants import RUSSIAN_WEEKDAYS
from .intent import extract_event_lookup_query
from .prompts import build_system_prompt as create_system_prompt
from .result import LLMResult
from .session import DialogSession, SessionStore
from .simulator import NLUSimulator
from .temporal import resolve_date, resolve_daypart, resolve_event_datetime, resolve_period


def make_fallback_response() -> LLMResult:
    return LLMResult(
        action="chat",
        data={},
        reply_text=(
            "К сожалению, произошла ошибка обработки команды. "
            "Повторите, пожалуйста."
        ),
    )


FALLBACK_RESPONSE = make_fallback_response()


def parse_json_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(cleaned[start : end + 1])

    raise ValueError(f"Не удалось обнаружить валидный JSON в ответе: {raw_text}")


@LanguageModel.register("gigachat")
class LLMOrchestrator(LanguageModel):
    _extract_json = staticmethod(parse_json_payload)

    def __init__(self, config: LLMConfig | None = None, logger=None, session_store: SessionStore | None = None):
        super().__init__(config or LLMConfig.from_env(), logger)
        self._sessions = session_store or SessionStore()
        self._simulator = NLUSimulator()
        self._client = None

        if not self._config.mock_mode and self._config.credentials:
            try:
                self._client = GigaChat(
                    credentials=self._config.credentials,
                    scope=self._config.scope,
                    model=self._config.model,
                    verify_ssl_certs=self._config.verify_ssl_certs,
                )
                self._logger.info("[LLM]: Клиент GigaChat успешно инициализирован")
            except Exception as error:
                self._logger.warning(f"[LLM]: Не удалось инициализировать клиент GigaChat: {error}")
        else:
            self._logger.info("[LLM]: Запуск в режиме NLU-симулятора")

    @property
    def sessions(self) -> SessionStore:
        return self._sessions

    @property
    def simulator(self) -> NLUSimulator:
        return self._simulator

    @simulator.setter
    def simulator(self, value: NLUSimulator | None) -> None:
        self._simulator = value

    def build_system_prompt(self, current_dt: datetime | None = None) -> str:
        return create_system_prompt(current_dt or datetime.now())

    def process(self, user_text: str, session_id: str = "default", current_dt: datetime | None = None) -> LLMResult:
        user_text = _normalize_user_text(user_text)
        now = current_dt or datetime.now()
        session = self._sessions.get(session_id)
        self._logger.info(f"[LLM]: Обработка запроса (сессия '{session_id}'): '{user_text}'")

        try:
            management = _parse_management_command(user_text, now)
            if management:
                result = LLMResult.model_validate(management)
                self._sessions.delete(session_id)
                self._logger.info(f"[LLM]: Распознано действие: '{result.action}'")
                return result
            if session:
                if self._is_session_continuation(user_text, session):
                    session_result = self._resolve_session_turn(user_text, session, now)
                    result = LLMResult.model_validate(session_result)
                    result.reply_text = _feminize_reply(result.reply_text)
                    self._update_fsm(session_id, result)
                    self._logger.info(f"[LLM]: Распознано действие: '{result.action}'")
                    return result
                self._sessions.delete(session_id)
                session = None

            if self._config.mock_mode or self._client is None:
                simulated_raw = self._simulator.process(user_text, session, now)
                simulated_raw = self._apply_temporal_rules(simulated_raw, user_text, now)
                simulated_raw = self._normalize_create_intent(simulated_raw, user_text, now)
                simulated_raw = self._ensure_event_clarification(simulated_raw, user_text, now)
                simulated_raw = _add_recurrence(simulated_raw, user_text)
                result = LLMResult.model_validate(simulated_raw)
                result.reply_text = _feminize_reply(result.reply_text)
                self._update_fsm(session_id, result)
                self._logger.info(f"[LLM]: Распознано действие: '{result.action}'")
                return result

            system_prompt = self.build_system_prompt(now)
            messages = [Messages(role=MessagesRole.SYSTEM, content=system_prompt)]

            messages.append(Messages(role=MessagesRole.USER, content=user_text))

            response = self._client.chat(Chat(messages=messages, temperature=0.1))
            raw_content = response.choices[0].message.content
            try:
                payload = parse_json_payload(raw_content)
            except ValueError:
                fallback_query = _extract_search_query(user_text)
                if fallback_query is None:
                    raise
                self._logger.warning(f"[LLM]: Ответ не был JSON; использую резервный поиск по запросу '{fallback_query}'")
                payload = {
                    "action": "search_events",
                    "data": {"query": fallback_query, "date_from": None, "date_to": None},
                    "reply_text": None,
                }
            payload = self._apply_temporal_rules(payload, user_text, now)
            payload = self._normalize_create_intent(payload, user_text, now)
            payload = self._ensure_event_clarification(payload, user_text, now)
            payload = _add_recurrence(payload, user_text)
            result = LLMResult.model_validate(payload)
            result.reply_text = _feminize_reply(result.reply_text)
            self._update_fsm(session_id, result)
            self._logger.info(f"[LLM]: Распознано действие: '{result.action}'")
            return result

        except Exception as error:
            self._logger.exception(f"[LLM]: Ошибка обработки запроса: {error}")
            return make_fallback_response()

    @staticmethod
    def _apply_temporal_rules(payload: dict[str, Any], user_text: str, now: datetime) -> dict[str, Any]:
        if payload.get("action") in {"update_event", "delete_event", "complete_event"}:
            return payload
        lookup_query = extract_event_lookup_query(user_text)
        if lookup_query is None and payload.get("action") != "create_event":
            lookup_query = _extract_search_query(user_text)
        if lookup_query:
            payload["action"] = "search_events"
            search_data: dict[str, Any] = {"query": lookup_query, "date_from": None, "date_to": None}
            period = resolve_period(user_text, now)
            if period:
                search_data["date_from"] = period[0].isoformat()
                search_data["date_to"] = period[1].isoformat()
            else:
                target_date = resolve_date(user_text, now)
                if target_date:
                    search_data["date_from"] = target_date.isoformat()
                    search_data["date_to"] = target_date.isoformat()
            payload["data"] = search_data
            payload["reply_text"] = None
            return payload

        action = payload.get("action")

        if action == "list_events":
            list_data = dict(payload.get("data") or {})
            period = resolve_period(user_text, now)
            if period:
                list_data.update({
                    "date_from": period[0].isoformat(),
                    "date_to": period[1].isoformat(),
                })
                list_data.pop("date", None)
            else:
                target_date = resolve_date(user_text, now)
                if target_date:
                    list_data.update({"date": target_date.isoformat()})
                    list_data.pop("date_from", None)
                    list_data.pop("date_to", None)
            daypart = resolve_daypart(user_text)
            if daypart:
                list_data.update({"time_from": daypart[0], "time_to": daypart[1]})
            payload["data"] = list_data

        elif action == "create_event":
            start_dt = resolve_event_datetime(user_text, now)
            data = dict(payload.get("data") or {})
            data["title"] = clean_event_title(str(data.get("title") or ""))
            if start_dt:
                old_start = _parse_datetime(data.get("start_time"))
                old_end = _parse_datetime(data.get("end_time"))
                duration = old_end - old_start if old_start and old_end else None

                data["start_time"] = start_dt.isoformat()
                if duration and duration > timedelta(0):
                    data["end_time"] = (start_dt + duration).isoformat()
                payload["data"] = data

                title = str(data.get("title") or "событие").lower()
                if start_dt.date() == now.date():
                    date_phrase = "сегодня"
                elif start_dt.date() == now.date() + timedelta(days=1):
                    date_phrase = "завтра"
                else:
                    weekday = RUSSIAN_WEEKDAYS[start_dt.weekday()]
                    date_phrase = f"в {weekday}, {start_dt:%d.%m.%Y}"

                reply = f"Добавила «{title}» в расписание на {date_phrase} в {start_dt:%H:%M}"
                if data.get("end_time"):
                    end_dt = datetime.fromisoformat(data["end_time"])
                    reply = f"Добавила «{title}» в расписание на {date_phrase} с {start_dt:%H:%M} до {end_dt:%H:%M}"
                payload["reply_text"] = reply + "."
            payload["data"] = data

        return payload

    @staticmethod
    def _ensure_event_clarification(payload: dict[str, Any], user_text: str, now: datetime) -> dict[str, Any]:
        action = payload.get("action")
        data = dict(payload.get("data") or {})
        if action == "clarify" and data.get("missing_field") in {"date", "date_and_time"}:
            return payload
        title = str(data.get("title") or "").strip(" \t\n.,!?«»\"'")
        title_is_missing = _is_placeholder_title(title)
        if action == "create_event" and title_is_missing:
            scheduled_date = resolve_date(user_text, now, for_event=True)
            scheduled_start = resolve_event_datetime(user_text, now)
            partial = {
                "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
                "start_time": scheduled_start.isoformat() if scheduled_start else None,
            }
            data["missing_field"] = "title"
            data["partial_data"] = partial
            payload.update(action="clarify", data=data, reply_text=LLMOrchestrator._title_question(partial, now))
        elif action == "clarify":
            partial = dict(data.get("partial_data") or {})
            scheduled_date = resolve_date(user_text, now, for_event=True)
            if scheduled_date:
                partial["scheduled_date"] = scheduled_date.isoformat()
            scheduled_start = resolve_event_datetime(user_text, now)
            if scheduled_start:
                partial["start_time"] = scheduled_start.isoformat()
            if title:
                partial.setdefault("title", title)
            title = str(partial.get("title") or "").strip()
            if title:
                title = clean_event_title(title)
                partial["title"] = title
            if _is_placeholder_title(title):
                partial.pop("title", None)
                data["missing_field"] = "title"
                data["partial_data"] = partial
                payload["reply_text"] = LLMOrchestrator._title_question(partial, now)
            elif title:
                scheduled_start = resolve_event_datetime(user_text, now)
                if not scheduled_start and partial.get("start_time"):
                    scheduled_start = _parse_datetime(partial["start_time"])
                if scheduled_start:
                    payload.update(LLMOrchestrator._create_event_result(title, scheduled_start))
                    return payload
                data["missing_field"] = "start_time"
                data["partial_data"] = partial
                payload["reply_text"] = LLMOrchestrator._time_question(partial)
            payload["data"] = data
        return payload

    @staticmethod
    def _normalize_create_intent(payload: dict[str, Any], user_text: str, now: datetime) -> dict[str, Any]:
        if payload.get("action") not in {"chat", "clarify"} or not _is_create_intent(user_text):
            return payload

        data = dict(payload.get("data") or {})
        partial = dict(data.get("partial_data") or {})
        title = str(data.get("title") or partial.get("title") or "").strip()
        if _is_placeholder_title(title):
            title = ""
        if not title:
            title = clean_event_title(user_text)
        if _is_placeholder_title(title):
            title = ""

        target_date = resolve_date(user_text, now, for_event=True)
        clock_time = _extract_clock_time(user_text)
        if target_date and clock_time and title:
            start_dt = datetime.combine(target_date, datetime.strptime(clock_time, "%H:%M").time())
            return LLMOrchestrator._create_event_result(title, start_dt)

        partial = {
            "title": title or None,
            "scheduled_date": target_date.isoformat() if target_date else None,
            "scheduled_time": clock_time,
        }
        if not title:
            missing_field = "title"
            reply = LLMOrchestrator._title_question(partial, now)
        elif not target_date and not clock_time:
            missing_field = "date_and_time"
            reply = LLMOrchestrator._date_time_question(partial)
        elif not target_date:
            missing_field = "date"
            reply = LLMOrchestrator._date_question(partial)
        else:
            missing_field = "start_time"
            reply = LLMOrchestrator._time_question(partial)

        return {
            "action": "clarify",
            "data": {"missing_field": missing_field, "partial_data": partial},
            "reply_text": reply,
        }

    @staticmethod
    def _is_session_continuation(user_text: str, session: DialogSession) -> bool:
        normalized = user_text.lower()
        if any(trigger in normalized for trigger in ("поставь", "запланируй", "создай", "напомни", "добавь", "запиши")):
            return False
        if any(trigger in normalized for trigger in ("найди", "поищи", "расписание", "планы", "что у меня", "расскажи", "привет")):
            return False
        if session.missing_field == "start_time":
            return bool(re.search(r"\d{1,2}\s*:\s*\d{2}", _normalize_user_text(user_text))
                        or re.search(r"\d{1,2}[./]\d{1,2}|завтра|сегодня|послезавтра", normalized))

        return bool(user_text.strip())

    @staticmethod
    def _title_question(partial_data: dict[str, Any], now: datetime) -> str:
        scheduled_date = partial_data.get("scheduled_date")
        if scheduled_date:
            day = datetime.fromisoformat(scheduled_date).date()
            if day == now.date() + timedelta(days=1):
                date_phrase = "на завтра"
            elif day == now.date():
                date_phrase = "на сегодня"
            else:
                date_phrase = f"на {day:%d.%m.%Y}"
            return f"Какую именно задачу нужно запланировать {date_phrase}?"
        return "Какую именно задачу нужно запланировать?"

    @staticmethod
    def _date_time_question(partial_data: dict[str, Any]) -> str:
        title = str(partial_data.get("title") or "эту задачу")
        return f"На какую дату и время запланировать «{title}»?"

    @staticmethod
    def _date_question(partial_data: dict[str, Any]) -> str:
        title = str(partial_data.get("title") or "эту задачу")
        scheduled_time = partial_data.get("scheduled_time")
        if scheduled_time:
            return f"На какую дату запланировать «{title}» в {scheduled_time}?"
        return f"На какую дату запланировать «{title}»?"

    @staticmethod
    def _resolve_session_turn(user_text: str, session: DialogSession, now: datetime) -> dict[str, Any] | None:
        partial = dict(session.partial_data)
        if session.missing_field == "title":
            title = clean_event_title(user_text.strip(" \t\n.,!?«»\"'"))
            if not _is_placeholder_title(title):
                partial["title"] = title

        target_date = resolve_date(user_text, now, for_event=True)
        if target_date:
            partial["scheduled_date"] = target_date.isoformat()
        clock_time = _extract_clock_time(user_text)
        if clock_time:
            partial["scheduled_time"] = clock_time

        title = str(partial.get("title") or "").strip()
        scheduled_date = partial.get("scheduled_date")
        scheduled_time = partial.get("scheduled_time")
        if title and scheduled_date and scheduled_time:
            start_dt = datetime.combine(date.fromisoformat(scheduled_date),
                                        datetime.strptime(scheduled_time, "%H:%M").time())
            result = LLMOrchestrator._create_event_result(title, start_dt)
            result["data"]["recurrence"] = partial.get("recurrence")
            result["data"]["recurrence_count"] = partial.get("recurrence_count")
            return result

        if not title:
            missing_field = "title"
            reply = LLMOrchestrator._title_question(partial, now)
        elif not scheduled_date and not scheduled_time:
            missing_field = "date_and_time"
            reply = LLMOrchestrator._date_time_question(partial)
        elif not scheduled_date:
            missing_field = "date"
            reply = LLMOrchestrator._date_question(partial)
        else:
            missing_field = "start_time"
            reply = LLMOrchestrator._time_question(partial)

        return {
            "action": "clarify",
            "data": {"missing_field": missing_field, "partial_data": partial},
            "reply_text": reply,
        }

    @staticmethod
    def _create_event_result(title: str, start_dt: datetime) -> dict[str, Any]:
        reply = f"Добавила «{title}» в расписание на {start_dt:%d.%m} в {start_dt:%H:%M}."
        return {
            "action": "create_event",
            "data": {
                "title": title,
                "start_time": start_dt.isoformat(),
                "end_time": None,
                "category": "Другое",
                "description": None,
            },
            "reply_text": reply,
        }

    @staticmethod
    def _time_question(partial_data: dict[str, Any]) -> str:
        title = str(partial_data.get("title") or "эту задачу")
        return f"На какое время запланировать «{title}»?"

    def _update_fsm(self, session_id: str, response: LLMResult) -> None:
        if response.action == "clarify":
            data = response.data
            self._sessions.save(session_id, DialogSession(missing_field=data.get("missing_field", "start_time"), partial_data=data.get("partial_data", {}), last_reply_text=response.reply_text))
        else:
            self._sessions.delete(session_id)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_placeholder_title(title: str) -> bool:
    normalized = re.sub(r"^(?:мне\s+)?", "", title.casefold()).strip()
    normalized = re.sub(r"\s+(?:на\s+(?:сегодня|завтра))$", "", normalized)
    return normalized in {
        "эту задачу", "задачу", "эту встречу", "встречу", "встреча",
        "это дело", "дело", "это событие", "событие", "задача", "новое событие", "",
    }


def _normalize_user_text(text: str) -> str:
    return re.sub(r"(?<=\d)[\ud800-\udfff]+(?=:)", "", text).strip()


def _extract_clock_time(text: str) -> str | None:
    normalized = _normalize_user_text(text)
    match = re.search(r"\b(?:в|к|с)?\s*(\d{1,2}):(\d{2})\b", normalized.lower())
    if not match:
        return None
    hour, minute = map(int, match.groups())
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _feminize_reply(text: str | None) -> str | None:
    if not text:
        return text
    replacements = (
        (r"\bЗапланировал\b", "Запланировала"),
        (r"\bзапланировал\b", "запланировала"),
        (r"\bЯ не нашел\b", "Я не нашла"),
        (r"\bЯ не нашёл\b", "Я не нашла"),
        (r"\bя не нашел\b", "я не нашла"),
        (r"\bя не нашёл\b", "я не нашла"),
        (r"\bЯ нашел\b", "Я нашла"),
        (r"\bЯ нашёл\b", "Я нашла"),
        (r"\bя нашел\b", "я нашла"),
        (r"\bя нашёл\b", "я нашла"),
        (r"\bготов помочь\b", "готова помочь"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _is_create_intent(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    if any(word in normalized for word in ("планы", "расписание", "найди", "поищи", "когда у меня")):
        return False
    if re.match(r"^(?:ну\s+)?(?:хорошо\s+)?(?:пожалуйста\s+)?(?:поставь|запланируй|создай|напомни|добавь|запиши)\b", normalized):
        return True
    if re.search(r"\b(?:хочу|планирую|собираюсь|надо|нужно)\b.{0,40}\b(?:сходить|пойти|съездить|попить|купить|позвонить|отправить|забрать|встретиться|сделать|записаться)\b", normalized):
        return True
    return bool(re.match(r"^(?:сходить|пойти|съездить|попить|купить|позвонить|отправить|забрать|встретиться|сделать|записаться|помыть|приготовить)\b", normalized))


def _extract_search_query(text: str) -> str | None:
    normalized = text.casefold()
    search_match = re.search(r"\b(?:найди|поищи|отыщи)\b", normalized)
    if not search_match and not re.search(r"\bкогда\s+(?:у\s+меня\s+)?был[аои]?\b", normalized):
        return None
    if search_match:
        before_verb = normalized[:search_match.start()]
        if re.search(r"\b(?:по|про|о)\s+[а-яё]+", before_verb):
            normalized = before_verb
        else:
            normalized = normalized[search_match.end():]
    normalized = re.sub(r"\b(?:я|когда-то|ставил|поставил|создавал|создал|мне|у|меня|задачу|задача|по|найди|поищи|отыщи|ее|её|это|встреча|встречу|была|был|были)\b", " ", normalized)
    normalized = re.sub(r"[^а-яёa-z0-9\s-]", " ", normalized)
    query_words = normalized.split()
    query = " ".join(query_words)
    return query or None


def _parse_management_command(text: str, now: datetime) -> dict[str, Any] | None:
    normalized = text.casefold().strip()
    action = None
    verb_pattern = None
    if re.search(r"\b(?:перенеси|перенести|передвинь|сдвинь|измени|поменяй|переименуй)\b", normalized):
        action = "update_event"
        verb_pattern = r"\b(?:перенеси|перенести|передвинь|сдвинь|измени|поменяй|переименуй)\b"
    elif re.search(r"\b(?:удали|удалить|отмени|убери)\b", normalized):
        action = "delete_event"
        verb_pattern = r"\b(?:удали|удалить|отмени|убери)\b"
    elif re.search(r"\b(?:отметь|пометь)\b.*\b(?:выполненн\w*|сделанн\w*)\b", normalized) or re.search(r"\b(?:выполнил[аи]?|сделал[аи]?)\b", normalized):
        action = "complete_event"
        verb_pattern = r"\b(?:отметь|пометь|выполнил[аи]?|сделал[аи]?)\b"
    if action is None:
        return None
    data: dict[str, Any] = {"query": None, "scope": "series" if re.search(r"\b(?:все|всю серию|каждое|каждую|все повторения)\b", normalized) else "one"}
    remainder = re.sub(r"^.*?" + verb_pattern, "", normalized, count=1).strip()
    if action == "update_event":
        target_date = resolve_date(remainder, now)
        clock = _extract_clock_time(remainder)
        if target_date:
            data["new_date"] = target_date.isoformat()
        if clock:
            data["new_time"] = clock
        rename = re.search(r"\b(?:переименуй|название)\b.*?\bв\s+(.+)$", normalized)
        if rename:
            data["new_title"] = clean_event_title(rename.group(1).strip(" .!?"))
            remainder = remainder[:remainder.find(" в ")] if " в " in remainder else remainder
        remainder = re.sub(r"\b(?:на|к|в)\s+(?:сегодня|завтра|послезавтра)\b", " ", remainder)
        remainder = re.sub(r"\b(?:на|к|в)\s+\d{1,2}[./]\d{1,2}(?:[./]\d{4})?\b", " ", remainder)
        remainder = re.sub(r"\b(?:на|к|в)\s+\d{1,2}\s+[а-яё]+(?:\s+\d{4})?\b", " ", remainder)
        remainder = re.sub(r"\b(?:на|к|в)\s+\d{1,2}:\d{2}\b", " ", remainder)
    query = re.sub(r"\b(?:задачу|задача|встречу|встреча|событие|дело|как|выполненной|выполненным|сделанной|сделанным|пожалуйста|все|всю|серию|повторения|эту|этот|это)\b", " ", remainder)
    query = " ".join(query.strip(" .!?").split())
    data["query"] = query or None
    return {"action": action, "data": data, "reply_text": None}


def _add_recurrence(payload: dict[str, Any], user_text: str) -> dict[str, Any]:
    if payload.get("action") not in {"create_event", "clarify"}:
        return payload
    normalized = user_text.casefold()
    frequency = None
    if re.search(r"\bкажд(?:ый|ую|ое)\s+(?:день|утро|вечер|сутки)\b|\bежедневно\b", normalized):
        frequency = "daily"
    elif re.search(r"\bкажд(?:ую|ый|ое)\s+(?:недел\w*|понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)\b|\bеженедельно\b", normalized):
        frequency = "weekly"
    elif re.search(r"\bкажд(?:ый|ую)\s+месяц\b|\bежемесячно\b", normalized):
        frequency = "monthly"
    if frequency:
        data = dict(payload.get("data") or {})
        is_clarify = payload["action"] == "clarify"
        target = dict(data.get("partial_data") or {}) if is_clarify else data
        target["recurrence"] = frequency
        count_match = re.search(r"\b(\d{1,2})\s+(?:раз[а]?|повторени[яй]|дн(?:я|ей)|недел[ьиь]?|месяц(?:а|ев)?)\b", normalized)
        if count_match:
            target["recurrence_count"] = int(count_match.group(1))
        title = str(target.get("title") or "")
        title = re.sub(r"\bкажд(?:ый|ую|ое)\s+(?:день|утро|вечер|сутки|недел\w*|понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье|месяц)\b", " ", title, flags=re.IGNORECASE)
        title = re.sub(r"\bежедневно|еженедельно|ежемесячно\b", " ", title, flags=re.IGNORECASE)
        title = re.sub(r"\b\d{1,2}\s+(?:раз[а]?|повторени[яй]|дн(?:я|ей)|недел[ьиь]?|месяц(?:а|ев)?)\b", " ", title, flags=re.IGNORECASE)
        title = " ".join(title.split()).strip(" ,.!?")
        if title:
            target["title"] = title
        else:
            target.pop("title", None)
        if is_clarify:
            data["partial_data"] = target
        elif not title:
            start = datetime.fromisoformat(data["start_time"])
            payload.update(action="clarify", data={"missing_field": "title", "partial_data": {"scheduled_date": start.date().isoformat(), "scheduled_time": start.strftime("%H:%M"), "recurrence": frequency, "recurrence_count": target.get("recurrence_count")}}, reply_text="Что именно нужно повторять?")
            return payload
        payload["data"] = data
    return payload

