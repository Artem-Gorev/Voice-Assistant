from abc import ABC, abstractmethod
from datetime import datetime, time

from backend.event_text import clean_event_title


def _remove_duplicate_events(events: list[dict]) -> list[dict]:
    unique_events = []
    seen = set()
    for event in events:
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
        llm_output = self.dispatcher.current_query
        data = llm_output.get("data", {})

        start_dt = datetime.fromisoformat(data["start_time"])
        target_date = start_dt.date()
        start_time = start_dt.time()

        if data.get("end_time"):
            end_time = datetime.fromisoformat(data["end_time"]).time()
        else:
            end_time = (start_dt + self.dispatcher.collision_proc.default_duration).time()

        conflict = self.dispatcher.collision_proc.check(target_date, start_time, end_time)

        if conflict:
            self.logger.info(f"[SERVICES]: Обнаружена коллизия с событием: {conflict['text']}")
            return f"Внимание! На это время уже есть событие: {conflict['text']}."

        self.repo.create_event(data)
        if llm_output.get("reply_text"):
            return llm_output["reply_text"]
        end_label = f" до {end_time:%H:%M}" if data.get("end_time") else ""
        return f"Добавила «{data['title']}» в расписание на {target_date:%d.%m} в {start_time:%H:%M}{end_label}."


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

class CommandDispatcher:
    def __init__(self, collision_proc, event_repository, semantic_search_service, logger):
        self.collision_proc = collision_proc
        self.repo = event_repository
        self.search = semantic_search_service
        self.logger = logger

        self.current_query: dict = {}

    def process_llm_response(self, llm_output: dict) -> str:
        self.current_query = llm_output
        action = llm_output.get("action")

        handler = BaseActionHandler.create(action, self)
        if handler is None:
            self.logger.warning(f"[SERVICES]: Неизвестный action: {action}")
            return llm_output.get("reply_text") or "Извините, я не понял команду."

        return handler.run()
