from abc import ABC, abstractmethod
from datetime import datetime

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
            self.logger.info(f"Обнаружена коллизия с событием: {conflict['text']}")
            return f"Внимание! На это время уже есть событие: {conflict['text']}."

        self.repo.create_event(data)
        return llm_output.get("reply_text") or "Готово."


@BaseActionHandler.register("list_events")
class ListEventsHandler(BaseActionHandler):
    def run(self) -> str:
        llm_output = self.dispatcher.current_query
        data = llm_output.get("data", {})
        target_date = datetime.fromisoformat(data["date"]).date()

        events = self.repo.get_events_by_date(target_date)

        if not events:
            return f"На {target_date.strftime('%d.%m.%Y')} у вас ничего не запланировано."

        text = "Вот ваши планы: "
        for e in events:
            t = e['time'].strftime("%H:%M") if e.get('time') else ""
            text += f"В {t} — {e['text']}. "
        return text

@BaseActionHandler.register("search_events")
class SearchEventsHandler(BaseActionHandler):
    def run(self) -> str:
        llm_output = self.dispatcher.current_query
        query = llm_output.get("data", {}).get("query", "")

        all_tasks = self.repo.get_all_events()
        ranked_results = self.search.search_events_by_vector(query, all_tasks)

        if not ranked_results:
            return f"Я не нашел ничего по запросу «{query}»."

        top_results = ranked_results[:3]

        text = "Я нашел следующее: "
        for e in top_results:
            date_str = e.get('date', '')
            if isinstance(date_str, datetime) or hasattr(date_str, 'strftime'):
                date_str = date_str.strftime("%d.%m")
            text += f"{date_str} — {e.get('text')}. "
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
            self.logger.warning(f"Неизвестный action: {action}")
            return llm_output.get("reply_text") or "Извините, я не понял команду."

        return handler.run()