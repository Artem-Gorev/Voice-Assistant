from datetime import datetime, date, time, timedelta
from models.collision_processor import CollisionProcessor
from models.command_dispatcher import CommandDispatcher

class MockDB:
    """Имитация базы данных Сергея"""

    def __init__(self):
        self.events = [
            {"text": "Обед", "date": date(2026, 10, 28), "time": time(14, 30)}
        ]

    def get_next_event(self, target_date, target_time):
        future_events = [e for e in self.events if e["date"] == target_date and e["time"] > target_time]
        if not future_events:
            return None
        return min(future_events, key=lambda x: x["time"])

    def get_previous_event(self, target_date, target_time):
        past_events = [e for e in self.events if e["date"] == target_date and e["time"] < target_time]
        if not past_events:
            return None
        return max(past_events, key=lambda x: x["time"])

    def create_event(self, data):
        print(f"  [DB MOCK] 💾 Сохраняем в БД: {data['title']}")
        dt = datetime.fromisoformat(data["start_time"])
        self.events.append({"text": data["title"], "date": dt.date(), "time": dt.time()})

    def get_events_by_date(self, target_date):
        print(f"  [DB MOCK] 🔍 Запрос расписания на {target_date}")
        return [e for e in self.events if e["date"] == target_date]


class MockSearchEngine:
    def semantic_search(self, query, date_from, date_to):
        print(f"  [SEARCH MOCK] 🧠 Ищем по смыслу: '{query}'")
        return [
            {"text": "Совещание по буткемпу", "date": date(2026, 10, 15), "time": time(10, 0)},
            {"text": "Созвон с командой по буткемпу", "date": date(2026, 10, 20), "time": time(15, 0)}
        ]

def main():
    # 1. Инициализируем зависимости (то, что напишут ребята)
    db = MockDB()
    search = MockSearchEngine()

    # 2. Инициализируем наши классы
    collision_proc = CollisionProcessor(EventRepository=db)
    dispatcher = CommandDispatcher(collision_proc, EventRepository=db, SemanticSearchServce=search)

    print("=== ТЕСТ 1: Создание встречи (КОЛЛИЗИЯ) ===")
    # Пользователь просит поставить встречу с 14:00 до 15:00.
    # А в БД уже есть "Обед" на 14:30.
    llm_response_collision = {
        "action": "create_event",
        "data": {
            "title": "Созвон с научником",
            "start_time": "2026-10-28T14:00:00",
            "end_time": "2026-10-28T15:00:00"
        },
        "reply_text": "Запланировал созвон с научником на завтра с 14:00 до 15:00."
    }
    # Ожидаем: Dispatcher должен перехватить reply_text и выдать предупреждение о коллизии
    result_1 = dispatcher.process_llm_response(llm_response_collision)
    print(f"👉 Ответ для TTS: {result_1}\n")

    print("=== ТЕСТ 2: Создание встречи (БЕЗ КОЛЛИЗИИ) ===")
    # Пользователь просит поставить встречу на 16:00. Свободно.
    llm_response_ok = {
        "action": "create_event",
        "data": {
            "title": "Созвон с научником",
            "start_time": "2026-10-28T16:00:00",
            "end_time": "2026-10-28T17:00:00"
        },
        "reply_text": "Запланировал созвон с научником на завтра с 16:00 до 17:00."
    }
    # Ожидаем: Dispatcher вернет reply_text от LLM
    result_2 = dispatcher.process_llm_response(llm_response_ok)
    print(f"👉 Ответ для TTS: {result_2}\n")

    print("=== ТЕСТ 3: Запрос расписания на день ===")
    llm_response_list = {
        "action": "list_events",
        "data": {"date": "2026-10-28"},
        "reply_text": None
    }
    # Ожидаем: Dispatcher сам сгенерирует текст на основе данных из MockDB
    result_3 = dispatcher.process_llm_response(llm_response_list)
    print(f"👉 Ответ для TTS: {result_3}\n")

    print("=== ТЕСТ 4: Семантический поиск ===")
    llm_response_search = {
        "action": "search_events",
        "data": {"query": "совещание по буткемпу", "date_from": None, "date_to": None},
        "reply_text": None
    }
    # Ожидаем: Dispatcher сгенерирует текст на основе данных из MockSearchEngine
    result_4 = dispatcher.process_llm_response(llm_response_search)
    print(f"👉 Ответ для TTS: {result_4}\n")

    print("=== ТЕСТ 5: Уточняющий вопрос (Clarify) ===")
    llm_response_clarify = {
        "action": "clarify",
        "data": {"missing_field": "start_time"},
        "reply_text": "На какое время запланировать покупку продуктов?"
    }
    # Ожидаем: Dispatcher просто вернет reply_text от LLM
    result_5 = dispatcher.process_llm_response(llm_response_clarify)
    print(f"👉 Ответ для TTS: {result_5}\n")


if __name__ == "__main__":
    main()