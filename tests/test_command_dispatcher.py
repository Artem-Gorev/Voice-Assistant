import logging
import unittest
from datetime import date, datetime, time

from backend.services.collision_processor import CollisionProcessor
from backend.services.command_dispatcher import CommandDispatcher, _remove_duplicate_events


class InMemoryRepo:
    def __init__(self, events=None):
        self._events = events or []
        self._next_id = len(self._events) + 1

    def create_event(self, data):
        start = datetime.fromisoformat(data["start_time"])
        item = {
            "id": self._next_id,
            "text": data.get("title") or data.get("text"),
            "date": start.date(),
            "time": start.time(),
            "start_time": start,
            "end_time": datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            "status": "pending",
        }
        self._next_id += 1
        self._events.append(item)
        return item["id"]

    def get_events_by_date(self, target_date: date):
        return [e for e in self._events if e.get("date") == target_date]

    def get_events_by_date_range(self, start_date: date, end_date: date):
        return [e for e in self._events if start_date <= e.get("date") <= end_date]

    def get_all_events(self):
        return list(self._events)

    def get_event_by_id(self, identifier: int):
        return next((e for e in self._events if e.get("id") == identifier), None)

    def search_events_by_text(self, query: str, limit: int = 5):
        q = query.casefold()
        return [e for e in self._events if q in str(e.get("text", "")).casefold()][:limit]

    def update_event(self, identifier: int, **kwargs):
        event = self.get_event_by_id(identifier)
        if event:
            event.update(kwargs)

    def delete_event(self, identifier: int):
        self._events = [e for e in self._events if e.get("id") != identifier]

    def complete_event(self, identifier: int):
        event = self.get_event_by_id(identifier)
        if event:
            event["status"] = "completed"


class MockSearchService:
    def __init__(self, return_results=True):
        self.return_results = return_results

    def search_events_by_vector(self, query: str, all_tasks):
        if not self.return_results:
            return []
        q = query.casefold()
        return [task for task in all_tasks if q in str(task.get("text", "")).casefold()]


class TestCommandDispatcher(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("TestCommandDispatcher")
        self.repo = InMemoryRepo()
        self.collision = CollisionProcessor(self.repo, self.logger)
        self.search_service = MockSearchService()
        self.dispatcher = CommandDispatcher(
            collision_proc=self.collision,
            event_repository=self.repo,
            semantic_search_service=self.search_service,
            logger=self.logger,
        )

    def test_create_event_success(self):
        payload = {
            "action": "create_event",
            "data": {
                "title": "Презентация проекта",
                "start_time": "2026-11-01T15:00:00",
                "end_time": "2026-11-01T16:00:00",
            },
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertIn("Презентация проекта", response)
        self.assertIn("Добавила", response)
        self.assertEqual(len(self.repo.get_all_events()), 1)

    def test_list_events_found(self):
        self.repo.create_event({"title": "Утренний созвон", "start_time": "2026-11-02T09:30:00"})
        self.repo.create_event({"title": "Обед с клиентом", "start_time": "2026-11-02T13:00:00"})
        payload = {
            "action": "list_events",
            "data": {"date": "2026-11-02"},
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertIn("Вот ваши планы", response)
        self.assertIn("Утренний созвон", response)
        self.assertIn("Обед с клиентом", response)

    def test_list_events_empty(self):
        payload = {
            "action": "list_events",
            "data": {"date": "2026-11-05"},
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertIn("ничего не запланировано", response)

    def test_search_events_by_text(self):
        self.repo.create_event({"title": "Подготовить годовой отчёт", "start_time": "2026-11-03T10:00:00"})
        self.repo.create_event({"title": "Купить билеты", "start_time": "2026-11-03T18:00:00"})
        payload = {
            "action": "search_events",
            "data": {"query": "отчёт"},
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertIn("годовой отчёт", response)

    def test_search_events_not_found(self):
        self.search_service.return_results = False
        payload = {
            "action": "search_events",
            "data": {"query": "несуществующая задача"},
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertIn("Я не нашла", response)

    def test_chat_action_returns_reply_text(self):
        payload = {
            "action": "chat",
            "data": {},
            "reply_text": "Привет! Чем я могу помочь?",
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertEqual(response, "Привет! Чем я могу помочь?")

    def test_clarify_action_returns_reply_text(self):
        payload = {
            "action": "clarify",
            "data": {"missing_field": "start_time"},
            "reply_text": "В какое время поставить встречу?",
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertEqual(response, "В какое время поставить встречу?")

    def test_remove_duplicate_events_utility(self):
        events = [
            {"date": "2026-11-01", "time": "10:00", "text": "Синхрон"},
            {"date": "2026-11-01", "time": "10:00", "text": "синхрон"},
            {"date": "2026-11-01", "time": "11:00", "text": "Синхрон"},
            {"date": "2026-11-01", "time": "12:00", "text": "[ INFO ] Лог"},
        ]
        filtered = _remove_duplicate_events(events)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["time"], "10:00")
        self.assertEqual(filtered[1]["time"], "11:00")

    def test_unsupported_action_handled(self):
        payload = {
            "action": "unknown_future_action",
            "data": {},
        }
        response = self.dispatcher.process_llm_response(payload)
        self.assertIn("я не понял команду", response)


if __name__ == "__main__":
    unittest.main()
