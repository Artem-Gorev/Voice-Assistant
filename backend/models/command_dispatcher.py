from datetime import datetime, timedelta
from models.collision_processor import CollisionProcessor

class CommandDispatcher:
    def __init__(self, collision_proc: CollisionProcessor, EventRepository, SemanticSearchServce):
        self.collision_proc = collision_proc
        self.db = EventRepository
        self.search = SemanticSearchServce

        self.current_query: dict = {}
        self._has_collision = False
        self._collision_text = ""
        self._fetched_events = []
        self._target_date = None
        self._search_query = ""

    def process_llm_response(self, llm_json: dict) -> str:
        self.current_query = llm_json
        action = llm_json.get("action")
        self._has_collision = False

        if action == "create_event":
            self._handle_create_event()
        elif action == "list_events":
            self._handle_list_events()
        elif action == "search_events":
            self._handle_search_events()
        elif action == "clarify" or action == "chat":
            pass

        return self._generate_tts_text()

    def _handle_create_event(self):
        data = self.current_query.get("data", {})

        start_dt = datetime.fromisoformat(data["start_time"])
        target_date = start_dt.date()
        start_time = start_dt.time()

        if data.get("end_time"):
            end_dt = datetime.fromisoformat(data["end_time"])
            end_time = end_dt.time()
        else:
            end_dt = start_dt + timedelta(hours=1)
            end_time = end_dt.time()

        conflict = self.collision_proc.check(target_date, start_time, end_time)

        if conflict:
            self._has_collision = True
            self._collision_text = f"Внимание! На это время уже есть событие: {conflict['text']}."
        else:
            self.db.create_event(data)

    def _handle_list_events(self):
        data = self.current_query.get("data", {})
        self._target_date = datetime.fromisoformat(data["date"]).date()
        self._fetched_events = self.db.get_events_by_date(self._target_date)

    def _handle_search_events(self):
        data = self.current_query.get("data", {})
        self._search_query = data.get("query", "")
        self._fetched_events = self.search.semantic_search(self._search_query, data.get("date_from"),
                                                           data.get("date_to"))

    def _generate_tts_text(self) -> str:
        if self._has_collision:
            return self._collision_text

        action = self.current_query.get("action")
        llm_reply = self.current_query.get("reply_text")

        if action in ["create_event", "clarify", "chat"]:
            return llm_reply or "Готово."

        if action == "list_events":
            if not self._fetched_events:
                return f"На {self._target_date.strftime('%d.%m.%Y')} у вас ничего не запланировано."
            text = "Вот ваши планы: "
            for e in self._fetched_events:
                t = e['time'].strftime("%H:%M") if e.get('time') else ""
                text += f"В {t} — {e['text']}. "  # Используем поля из БД (time, text)
            return text

        if action == "search_events":
            if not self._fetched_events:
                return f"Я не нашел ничего по запросу «{self._search_query}»."
            text = "Я нашел следующее: "
            for e in self._fetched_events:
                d = e['date'].strftime("%d.%m") if e.get('date') else ""
                text += f"{d} — {e['text']}. "
            return text

        return "Я не знаю, что ответить."