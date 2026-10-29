import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from models import LLMResponseSchema

RUSSIAN_WEEKDAYS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]


@dataclass
class DialogSession:
    missing_field: str
    partial_data: Dict[str, Any]
    last_reply_text: Optional[str] = None
    updated_at: datetime = field(default_factory=datetime.now)


def make_fallback_response() -> Dict[str, Any]:
    return {
        "action": "chat",
        "data": {},
        "reply_text": "К сожалению, произошла ошибка обработки команды. Повторите, пожалуйста.",
    }


FALLBACK_RESPONSE = make_fallback_response()


def parse_json_payload(raw_text: str) -> Dict[str, Any]:
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


class NLUSimulator:
    def __init__(self):
        self.search_triggers = ["найди", "поищи", "когда у меня", "поиск"]
        self.create_triggers = ["создай", "поставь", "запланируй", "напомни", "добавь", "запиши"]
        self.list_triggers = ["расписание", "планы", "дела", "что у меня", "список"]
        self.months = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
        }

    def process(
        self,
        user_text: str,
        session: Optional[DialogSession],
        now: datetime,
    ) -> Dict[str, Any]:
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
                reply = f"Запланировал '{title}' на {date_label} с {time_str}{end_str}."
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

        if any(tr in text_lower for tr in self.search_triggers) and not any(
            w in text_lower for w in self.create_triggers
        ):
            query = user_text
            for tr in self.search_triggers + ["пожалуйста"]:
                query = re.sub(rf"\b{tr}\b", "", query, flags=re.IGNORECASE)
            return {
                "action": "search_events",
                "data": {"query": query.strip(" :?!."), "date_from": None, "date_to": None},
                "reply_text": None,
            }

        if any(tr in text_lower for tr in self.list_triggers):
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
                        r"\b(\d{1,2})\s+(октября|ноября|декабря|января|февраля|марта|апреля|мая|июня|июля|августа|сентября)\b",
                        text_lower,
                    )
                    if date_ru_match:
                        day_num = int(date_ru_match.group(1))
                        mon_num = self.months[date_ru_match.group(2)]
                        target_date = date(now.year, mon_num, day_num)

            return {
                "action": "list_events",
                "data": {"date": target_date.isoformat()},
                "reply_text": None,
            }

        if any(tr in text_lower for tr in self.create_triggers) or "созвон" in text_lower or "встреч" in text_lower:
            start_dt, end_dt = self._extract_datetime_span(user_text, now)

            clean_title = user_text
            for tr in self.create_triggers + ["пожалуйста", "встречу", "событие"]:
                clean_title = re.sub(rf"\b{tr}\b", "", clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r"\b(на\s+завтра|на\s+сегодня|завтра|сегодня)\b", "", clean_title, flags=re.IGNORECASE)
            clean_title = re.sub(r"\b(с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2})\b", "", clean_title, flags=re.IGNORECASE)
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
                    "category": "Встреча" if ("созвон" in text_lower or "встреч" in text_lower) else "Другое",
                    "description": None,
                },
                "reply_text": f"Запланировал {clean_title.lower()} на {date_label} с {time_str}{end_str}.",
            }

        return {
            "action": "chat",
            "data": {},
            "reply_text": "Привет! Я голосовой ассистент. Могу запланировать встречу, показать расписание или найти событие.",
        }

    def _extract_datetime_span(
        self, text: str, now: datetime
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
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


class LLMOrchestrator:
    _extract_json = staticmethod(parse_json_payload)

    def __init__(
        self,
        credentials: Optional[str] = None,
        scope: Optional[str] = None,
        model: Optional[str] = None,
        verify_ssl_certs: bool = False,
        mock_mode: bool = False,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ):
        self.logger = logger or logging.getLogger("LLMOrchestrator")
        self.sessions: Dict[str, DialogSession] = {}
        self.mock_mode = mock_mode
        self.simulator = NLUSimulator()

        creds = credentials or os.getenv("GIGACHAT_CREDENTIALS")
        self.scope = scope or os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = model or os.getenv("GIGACHAT_MODEL", "GigaChat")
        self.verify_ssl_certs = verify_ssl_certs

        self.client = None
        if not self.mock_mode and creds:
            try:
                self.client = GigaChat(
                    credentials=creds,
                    scope=self.scope,
                    model=self.model,
                    verify_ssl_certs=self.verify_ssl_certs,
                )
                self.logger.info("[LLM]: Клиент GigaChat успешно инициализирован")
            except Exception as e:
                self.logger.warning(f"[LLM]: Не удалось инициализировать клиент GigaChat: {e}")
                self.client = None
        elif self.mock_mode or not creds:
            self.logger.info("[LLM]: Запуск в режиме NLU-симулятора")

    def build_system_prompt(self, current_dt: Optional[datetime] = None) -> str:
        now = current_dt or datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        weekday_str = RUSSIAN_WEEKDAYS[now.weekday()]

        grid_lines = []
        for offset in range(14):
            day = now.date() + timedelta(days=offset)
            w_name = RUSSIAN_WEEKDAYS[day.weekday()]
            tag = " (СЕГОДНЯ)" if offset == 0 else (" (ЗАВТРА)" if offset == 1 else "")
            grid_lines.append(f"  - {day.strftime('%Y-%m-%d')} ({w_name}){tag}")
        calendar_grid = "\n".join(grid_lines)

        return f"""Ты — интеллектуальный ассистент-органайзер для работы с расписанием, задачами и встречами.
Твоя задача — проанализировать запрос пользователя и вернуть СТРОГО JSON-объект определенной структуры.

=== ТЕКУЩИЙ ВРЕМЕННОЙ КОНТЕКСТ ===
- Текущая дата: {date_str}
- Текущее время: {time_str}
- Текущий день недели: {weekday_str}

=== КАЛЕНДАРНАЯ СЕТКА НА 14 ДНЕЙ ===
{calendar_grid}

=== ПРАВИЛА РАЗРЕШЕНИЯ ДАТ И ВРЕМЕНИ ===
1. Относительные даты ("сегодня", "завтра", "послезавтра", "в эту пятницу", "в следующий понедельник", "через 2 часа") ВСЕГДА переводи в точные даты по сетке календаря.
2. Формат даты и времени для start_time и end_time: строгий ISO 8601 (YYYY-MM-DDTHH:MM:SS), например '2026-10-28T14:00:00'.
3. Если пользователь указал время (например, 'в 14:00'), но НЕ указал дату:
   - Если указанное время позже текущего времени ({time_str}), считай дату СЕГОДНЯ ({date_str}).
   - Если указанное время уже прошло сегодня, считай дату ЗАВТРА.
4. Если указан интервал ("с 14:00 до 15:00" или "на 2 часа"), вычисли точный end_time. Если длительность не указана, поле end_time можно оставить null.

=== ДОСТУПНЫЕ ДЕЙСТВИЯ (action) ===
1. 'create_event':
   - Создание нового события, задачи, встречи, звонка, созвона.
   - КРИТИЧЕСКОЕ ПРАВИЛО (Slot Filling): если пользователь хочет запланировать событие, но НЕ указал дату/время начала (start_time), ЗАПРЕЩЕНО выдумывать время!
     В этом случае ты ОБЯЗАН вернуть action='clarify', data={{"missing_field": "start_time", "partial_data": {{"title": "<название события>"}}}}, и в reply_text задать вежливый уточняющий вопрос (например: 'На какое время запланировать <название>?').
   - Если время известно:
     action: 'create_event'
     data: {{
       "title": "название события",
       "start_time": "YYYY-MM-DDTHH:MM:SS",
       "end_time": "YYYY-MM-DDTHH:MM:SS" (или null),
       "category": "Встреча" / "Работа" / "Другое",
       "description": null
     }}
     reply_text: короткое понятное подтверждение для пользователя (например: 'Запланировал созвон с научником на завтра с 14:00 до 15:00.').

2. 'list_events':
   - Запрос планов, расписания, списка событий или дел на конкретный день (например: 'какие планы на сегодня?', 'что у меня на 28 октября?', 'расписание на завтра').
   - data: {{"date": "YYYY-MM-DD"}}
   - reply_text: null

3. 'search_events':
   - Поиск событий по ключевым словам, смыслу или теме (например: 'найди совещания по буткемпу', 'когда у меня встреча с врачом?').
   - data: {{"query": "строка поиска", "date_from": null, "date_to": null}}
   - reply_text: null

4. 'clarify':
   - Запрос недостающей обязательной информации у пользователя (например, времени начала).
   - data: {{"missing_field": "start_time", "partial_data": {{"title": "..."}}}}
   - reply_text: вопрос пользователю.

5. 'chat':
   - Приветствие, благодарность, общий разговор или вопрос не по функционалу органайзера.
   - data: {{}}
   - reply_text: ответ пользователю.

=== ТРЕБОВАНИЕ К ФОРМАТУ ВЫВОДА ===
Отвечай ТОЛЬКО валидным JSON-объектом в формате:
{{
  "action": "create_event" | "list_events" | "search_events" | "clarify" | "chat",
  "data": {{ ... }},
  "reply_text": "текст ответа или null"
}}
Никакого окружающего текста или markdown-разметки вне JSON."""

    def process(
        self,
        user_text: str,
        session_id: str = "default",
        current_dt: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = current_dt or datetime.now()
        session = self.sessions.get(session_id)
        self.logger.info(f"[LLM]: Обработка запроса (сессия '{session_id}'): '{user_text}'")

        try:
            if self.mock_mode or self.client is None:
                simulated_raw = self.simulator.process(user_text, session, now)
                validated = LLMResponseSchema.model_validate(simulated_raw).model_dump()
                self._update_fsm(session_id, validated)
                self.logger.info(f"[LLM]: Распознано действие: '{validated['action']}'")
                return validated

            system_prompt = self.build_system_prompt(now)
            messages = [Messages(role=MessagesRole.SYSTEM, content=system_prompt)]

            if session and session.missing_field == "start_time":
                title = session.partial_data.get("title", "")
                last_reply = session.last_reply_text or ""
                self.logger.info(f"[LLM]: Слот-филлинг для события '{title}'")
                context_msg = (
                    f"[КОНТЕКСТ ДИАЛОГА]\n"
                    f"Ранее пользователь просил запланировать событие: '{title}'.\n"
                    f"Ассистент задал вопрос: '{last_reply}'.\n"
                    f"Сейчас пользователь ответил: '{user_text}'.\n"
                    f"Объедини название из контекста ('{title}') с указанным временем и сформируй действие 'create_event'."
                )
                messages.append(Messages(role=MessagesRole.USER, content=context_msg))
            else:
                messages.append(Messages(role=MessagesRole.USER, content=user_text))

            payload = Chat(
                messages=messages,
                temperature=0.1,
            )
            response = self.client.chat(payload)
            raw_content = response.choices[0].message.content

            parsed_json = parse_json_payload(raw_content)
            validated_response = LLMResponseSchema.model_validate(parsed_json).model_dump()

            self._update_fsm(session_id, validated_response)
            self.logger.info(f"[LLM]: Распознано действие: '{validated_response['action']}'")
            return validated_response

        except Exception as error:
            self.logger.exception(f"[LLM]: Ошибка обработки запроса: {error}")
            return make_fallback_response()

    def _update_fsm(self, session_id: str, response: Dict[str, Any]) -> None:
        action = response.get("action")
        if action == "clarify":
            data = response.get("data", {})
            self.sessions[session_id] = DialogSession(
                missing_field=data.get("missing_field", "start_time"),
                partial_data=data.get("partial_data", {}),
                last_reply_text=response.get("reply_text"),
                updated_at=datetime.now(),
            )
        else:
            self.sessions.pop(session_id, None)
