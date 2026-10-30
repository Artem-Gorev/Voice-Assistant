from abc import ABC, abstractmethod
from datetime import datetime, time
import re

from backend.event_text import clean_event_title
from backend.services.event_management import EventManagementService


def _remove_duplicate_events(events: list[dict]) -> list[dict]:
    unique_events = []
    seen = set()
    for event in events:
        if re.match(r"^\[\s*(?:INFO|DEBUG|WARNING|ERROR)\s*\]", str(event.get("text") or ""), re.IGNORECASE):
            continue
        key = (
            str(event.get("date")),
            str(event.get("time")),
            str(event.get("text", "")).strip().casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_events.append(event)
    return unique_events


class BaseActionHandler(ABC):
    _HANDLERS = {}

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.logger = dispatcher.logger

    @classmethod
    def create(cls, action: str, dispatcher) -> "BaseActionHandler | None":
        handler_cls = cls._HANDLERS.get(action)
        if handler_cls is None:
            return None
        return handler_cls(dispatcher)

    @classmethod
    def register(cls, action: str):
        def decorator(handler_cls: type["BaseActionHandler"]):
            cls._HANDLERS[action] = handler_cls
            return handler_cls

        return decorator

    @property
    def repo(self):
        return self.dispatcher.repo

    @property
    def search(self):
        return self.dispatcher.search

    @abstractmethod
    def run(self) -> str:
        pass

@BaseActionHandler.register("create_event")
class CreateEventHandler(BaseActionHandler):
    def run(self) -> str:
        return self.dispatcher.manager.create(self.dispatcher.current_query.get("data", {}), self.dispatcher.session_id)


@BaseActionHandler.register("list_events")
class ListEventsHandler(BaseActionHandler):
    def run(self) -> str:
        llm_output = self.dispatcher.current_query
        data = llm_output.get("data", {})
        if data.get("date"):
            target_date = datetime.fromisoformat(data["date"]).date()
            events = self.repo.get_events_by_date(target_date)
            period_label = target_date.strftime("%d.%m.%Y")
        else:
            start_date = datetime.fromisoformat(data["date_from"]).date()
            end_date = datetime.fromisoformat(data["date_to"]).date()
            events = self.repo.get_events_by_date_range(start_date, end_date)
            period_label = f"с {start_date:%d.%m.%Y} по {end_date:%d.%m.%Y}"

        if data.get("time_from") and data.get("time_to"):
            time_from = time.fromisoformat(data["time_from"])
            time_to = time.fromisoformat(data["time_to"])
            events = [
                event for event in events
                if event.get("time") is not None and time_from <= event["time"] < time_to
            ]
            period_label += f" с {time_from:%H:%M} до {time_to:%H:%M}"

        original_count = len(events)
        events = _remove_duplicate_events(events)
        self.dispatcher.manager.remember(self.dispatcher.session_id, events)
        if len(events) < original_count:
            self.logger.info(f"[SERVICES]: Скрыты повторяющиеся события из выдачи: {original_count - len(events)}")

        if not events:
            if data.get("date"):
                return f"На {period_label} у вас ничего не запланировано."
            return f"За период {period_label} у вас ничего не запланировано."

        text = "Вот ваши планы: "
        for e in events:
            t = e['time'].strftime("%H:%M") if e.get('time') else ""
            event_date = e.get("date")
            date_label = f"{event_date:%d.%m} " if event_date and not data.get("date") else ""
            time_label = f"В {t} " if t else ""
            title = clean_event_title(str(e.get("text") or "")) or "Событие"
            text += f"{date_label}{time_label}— {title}. "
        return text

@BaseActionHandler.register("search_events")
class SearchEventsHandler(BaseActionHandler):
    def run(self) -> str:
        llm_output = self.dispatcher.current_query
        query = llm_output.get("data", {}).get("query", "")

        all_tasks = self.repo.get_all_events()
        ranked_results = self.search.search_events_by_vector(query, all_tasks)
        ranked_results = _remove_duplicate_events(ranked_results)
        self.dispatcher.manager.remember(self.dispatcher.session_id, ranked_results[:3])

        if not ranked_results:
            return f"Я не нашла достаточно похожих записей по запросу «{query}»."

        top_results = ranked_results[:3]

        text = "Я нашла следующее: "
        for e in top_results:
            date_str = e.get('date', '')
            if isinstance(date_str, datetime) or hasattr(date_str, 'strftime'):
                date_str = date_str.strftime("%d.%m")
            title = clean_event_title(str(e.get("text") or "")) or "Событие"
            text += f"{date_str} — {title}. "
        return text

@BaseActionHandler.register("clarify")
@BaseActionHandler.register("chat")
class DefaultChatHandler(BaseActionHandler):
    def run(self) -> str:
        llm_output = self.dispatcher.current_query
        return llm_output.get("reply_text") or "Я вас слушаю."


@BaseActionHandler.register("update_event")
@BaseActionHandler.register("delete_event")
@BaseActionHandler.register("complete_event")
class EventManagementHandler(BaseActionHandler):
    def run(self) -> str:
        return self.dispatcher.manager.process(self.dispatcher.current_query["action"], self.dispatcher.current_query.get("data", {}), self.dispatcher.session_id)

class CommandDispatcher:
    def __init__(self, collision_proc, event_repository, semantic_search_service, logger):
        self.collision_proc = collision_proc
        self.repo = event_repository
        self.search = semantic_search_service
        self.logger = logger
        self.manager = EventManagementService(event_repository, collision_proc, logger)
        self.session_id = "default"

        self.current_query: dict = {}

    def process_llm_response(self, llm_output: dict, session_id: str = "default") -> str:
        self.current_query = llm_output
        self.session_id = session_id
        action = llm_output.get("action")

        handler = BaseActionHandler.create(action, self)
        if handler is None:
            self.logger.warning(f"[SERVICES]: Неизвестный action: {action}")
            return llm_output.get("reply_text") or "Извините, я не понял команду."

        return handler.run()

    def process_followup(self, text: str, session_id: str = "default") -> str | None:
        return self.manager.followup(text, session_id)
