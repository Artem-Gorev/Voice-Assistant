import logging
import unittest
from datetime import date, datetime, timedelta

from backend.ai_service.llm import LLMConfig, LLMOrchestrator
from backend.services import CollisionProcessor, CommandDispatcher


class MemoryRepository:
    def __init__(self):
        self.events = {}
        self.next_id = 1

    def create_event(self, data):
        start = datetime.fromisoformat(data["start_time"])
        for event in self.events.values():
            if event["text"] == data["title"] and event["start_time"] == start:
                return event["id"]
        identifier = self.next_id
        self.next_id += 1
        self.events[identifier] = {"id": identifier, "text": data["title"], "date": start.date(), "time": start.time(),
                                   "start_time": start, "end_time": datetime.fromisoformat(data["end_time"]) if data.get("end_time") else start,
                                   "status": "pending", "series_id": data.get("series_id")}
        return identifier

    def get_event_by_id(self, identifier):
        return self.events.get(identifier)

    def get_all_events(self):
        return list(self.events.values())

    def get_events_by_date_range(self, start, end):
        return [event for event in self.events.values() if start <= event["date"] <= end]

    def get_events_by_date(self, target):
        return self.get_events_by_date_range(target, target)

    def get_series_events(self, series_id):
        return [event for event in self.events.values() if event["series_id"] == series_id]

    def update_event(self, identifier, *, title=None, start_time=None, end_time=None):
        event = self.events[identifier]
        if title:
            event["text"] = title
        if start_time:
            event.update(start_time=start_time, end_time=end_time, date=start_time.date(), time=start_time.time())

    def delete_event(self, identifier):
        del self.events[identifier]

    def complete_event(self, identifier):
        self.events[identifier]["status"] = "completed"


class EventManagementTests(unittest.TestCase):
    def setUp(self):
        logger = logging.getLogger("event-management-tests")
        self.repo = MemoryRepository()
        self.collision = CollisionProcessor(self.repo, logger)
        self.dispatcher = CommandDispatcher(self.collision, self.repo, None, logger)
        self.llm = LLMOrchestrator(config=LLMConfig(mock_mode=True), logger=logger)
        self.now = datetime(2026, 10, 30, 10, 0)

    def send(self, text):
        followup = self.dispatcher.process_followup(text, "test")
        if followup is not None:
            return followup
        result = self.llm.process(text, session_id="test", current_dt=self.now)
        return self.dispatcher.process_llm_response(result.model_dump(mode="json"), session_id="test")

    def create(self, title, start, recurrence=None, count=None):
        data = {"title": title, "start_time": start, "end_time": None, "recurrence": recurrence, "recurrence_count": count}
        return self.dispatcher.process_llm_response({"action": "create_event", "data": data}, "test")

    def test_move_by_pronoun_preserves_time(self):
        self.create("Отправить отчёт", "2026-10-30T13:00:00")
        response = self.send("А перенеси ее на завтра")
        self.assertIn("Перенесла", response)
        self.assertEqual(next(iter(self.repo.events.values()))["start_time"], datetime(2026, 10, 31, 13))

    def test_delete_and_complete_by_voice_text(self):
        self.create("Купить билеты", "2026-10-31T09:00:00")
        self.assertIn("Отметила", self.send("Отметь эту задачу выполненной"))
        self.assertEqual(next(iter(self.repo.events.values()))["status"], "completed")
        self.assertIn("Удалила", self.send("Удали эту задачу"))
        self.assertFalse(self.repo.events)

    def test_ambiguous_target_requires_selection(self):
        self.create("Позвонить Ивану", "2026-10-31T09:00:00")
        self.create("Позвонить Ивану", "2026-11-01T09:00:00")
        self.assertIn("Уточните", self.send("Удали Позвонить Ивану"))
        self.assertEqual(len(self.repo.events), 2)
        self.assertIn("Удалила", self.send("2"))
        self.assertEqual(len(self.repo.events), 1)

    def test_conflict_offers_and_accepts_alternative(self):
        self.create("Встреча с Иваном", "2026-10-31T13:00:00")
        self.assertIn("Перенести", self.create("Встреча с командой", "2026-10-31T13:00:00"))
        self.assertEqual(len(self.repo.events), 1)
        self.assertIn("Добавила", self.send("да"))
        self.assertEqual(len(self.repo.events), 2)
        times = sorted(event["time"] for event in self.repo.events.values())
        self.assertEqual(times, [datetime(2026, 10, 31, 13).time(), datetime(2026, 10, 31, 14).time()])

    def test_recurrence_and_series_update(self):
        self.create("Тренировка", "2026-10-30T18:00:00", "weekly", 3)
        self.assertEqual(len(self.repo.events), 3)
        self.assertEqual(len({event["series_id"] for event in self.repo.events.values()}), 1)
        result = self.dispatcher.process_llm_response({"action": "update_event", "data": {"event_id": 1, "new_time": "19:00", "scope": "series"}}, "test")
        self.assertIn("Перенесла", result)
        self.assertTrue(all(event["time"].hour == 19 for event in self.repo.events.values()))

    def test_recurrence_count_is_clarified(self):
        self.assertIn("Сколько раз", self.create("Тренировка", "2026-10-30T18:00:00", "weekly"))
        self.assertIn("3 повторений", self.send("3 раза"))
        self.assertEqual(len(self.repo.events), 3)

    def test_series_delete_and_single_occurrence_completion(self):
        self.create("Тренировка", "2026-10-30T18:00:00", "weekly", 3)
        self.dispatcher.process_llm_response({"action": "complete_event", "data": {"event_id": 1, "scope": "one"}}, "test")
        self.assertEqual(sum(event["status"] == "completed" for event in self.repo.events.values()), 1)
        response = self.dispatcher.process_llm_response({"action": "delete_event", "data": {"query": "Тренировка", "scope": "series"}}, "test")
        self.assertIn("все повторения", response)
        self.assertFalse(self.repo.events)

    def test_conflicting_move_does_not_change_original_event(self):
        self.create("Встреча с Иваном", "2026-10-31T13:00:00")
        self.create("Отчёт", "2026-10-30T13:00:00")
        response = self.dispatcher.process_llm_response({"action": "update_event", "data": {"event_id": 2, "new_date": "2026-10-31"}}, "test")
        self.assertIn("Перенести", response)
        self.assertEqual(self.repo.events[2]["date"], date(2026, 10, 30))
        self.assertIn("действие отменено", self.send("нет"))

    def test_title_lookup_accepts_word_forms(self):
        self.create("Отправить отчёт", "2026-10-31T13:00:00")
        self.assertIn("Отметила", self.send("Отметь отчет выполненным"))
        self.assertEqual(self.repo.events[1]["status"], "completed")

    def test_nlu_management_and_recurrence(self):
        result = self.llm.process("Перенеси ее на завтра", current_dt=self.now)
        self.assertEqual(result.action, "update_event")
        self.assertEqual(result.data["new_date"], date(2026, 10, 31))
        result = self.llm.process("Запланируй тренировку завтра в 18:00 каждую неделю 4 раза", current_dt=self.now)
        self.assertEqual(result.action, "create_event")
        self.assertEqual(result.data["recurrence"], "weekly")
        self.assertEqual(result.data["recurrence_count"], 4)


if __name__ == "__main__":
    unittest.main()
