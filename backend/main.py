from datetime import datetime, date, time
import sys
import logging

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("main")

from dal.event_repository import EventRepository
from models.collision_processor import CollisionProcessor
from models.command_dispatcher import CommandDispatcher

class MockEventRepository:
    def __init__(self):
        self.events = [
            {"id": 1, "text": "Обед", "date": date(2026, 10, 28), "time": time(14, 30)},
        ]

    def get_next_event(self, target_date, target_time):
        future = [e for e in self.events if e["date"] == target_date and e["time"] > target_time]
        return min(future, key=lambda x: x["time"]) if future else None

    def get_previous_event(self, target_date, target_time):
        past = [e for e in self.events if e["date"] == target_date and e["time"] < target_time]
        return max(past, key=lambda x: x["time"]) if past else None

    def get_events_by_date(self, target_date):
        return [e for e in self.events if e["date"] == target_date]

    def get_all_events(self):
        return self.events

    def create_event(self, data):
        logger.info(f"[MOCK] Сохраняем в БД: {data['title']}")
        dt = datetime.fromisoformat(data["start_time"])
        self.events.append({"id": 99, "text": data["title"], "date": dt.date(), "time": dt.time()})


class MockSemanticSearchService:
    def search_events_by_vector(self, query: str, tasks: list) -> list:
        logger.info(f"[MOCK SEARCH] Ищем по вектору: '{query}' среди {len(tasks)} тасков")
        return [t for t in tasks if query.lower() in t["text"].lower()]

def main():
    event_repository = None
    if EventRepository:
        try:
            event_repository = EventRepository()
            logger.info("Успешно подключились к реальной БД PostgreSQL!")
        except Exception as e:
            logger.error(f"Не удалось подключиться к БД: {e}")
            logger.info("Переключаемся на MOCK-базу данных.")

    if not event_repository:
        event_repository = MockEventRepository()

    semantic_search_service = MockSemanticSearchService()

    collision_proc = CollisionProcessor(event_repository=event_repository, logger=logger)

    dispatcher = CommandDispatcher(
        collision_proc=collision_proc,
        event_repository=event_repository,
        semantic_search_service=semantic_search_service,
        logger=logger
    )

    print("\n=== ТЕСТ 1: Создание встречи (Проверка коллизии) ===")
    llm_res_collision = {
        "action": "create_event",
        "data": {"title": "Созвон с научником", "start_time": "2026-10-28T14:00:00", "end_time": "2026-10-28T15:00:00"},
        "reply_text": "Запланировал созвон."
    }
    print(f"Ответ для TTS: {dispatcher.process_llm_response(llm_res_collision)}\n")

    print("=== ТЕСТ 2: Запрос расписания ===")
    llm_res_list = {
        "action": "list_events",
        "data": {"date": "2026-10-28"},
        "reply_text": None
    }
    print(f"Ответ для TTS: {dispatcher.process_llm_response(llm_res_list)}\n")

    print("=== ТЕСТ 3: Поиск события ===")
    llm_res_search = {
        "action": "search_events",
        "data": {"query": "созвон"},
        "reply_text": None
    }
    print(f"Ответ для TTS: {dispatcher.process_llm_response(llm_res_search)}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
