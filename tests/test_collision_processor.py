import logging
import unittest
from datetime import date, datetime, time, timedelta

from backend.services.collision_processor import CollisionProcessor


class MockEventRepository:
    def __init__(self, events=None):
        self._events = events or []

    def get_events_by_date_range(self, start_date: date, end_date: date):
        result = []
        for event in self._events:
            ev_date = event.get("date")
            if ev_date is None and isinstance(event.get("start_time"), datetime):
                ev_date = event["start_time"].date()
            if ev_date and start_date <= ev_date <= end_date:
                result.append(event)
        return result


class TestCollisionProcessor(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("TestCollisionProcessor")
        self.target_date = date(2026, 10, 31)

    def test_no_collision_when_no_events(self):
        repo = MockEventRepository([])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(10, 0), time(11, 0))
        self.assertIsNone(conflict)

    def test_exact_overlap_detected(self):
        event = {
            "id": 1,
            "text": "Встреча по архитектуре",
            "date": self.target_date,
            "time": time(14, 0),
            "start_time": datetime(2026, 10, 31, 14, 0),
            "end_time": datetime(2026, 10, 31, 15, 0),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(14, 0), time(15, 0))
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["id"], 1)

    def test_partial_overlap_starts_inside(self):
        event = {
            "id": 2,
            "text": "Синхрон",
            "date": self.target_date,
            "time": time(14, 0),
            "start_time": datetime(2026, 10, 31, 14, 0),
            "end_time": datetime(2026, 10, 31, 15, 0),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(14, 30), time(15, 30))
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["id"], 2)

    def test_partial_overlap_ends_inside(self):
        event = {
            "id": 3,
            "text": "Демо",
            "date": self.target_date,
            "time": time(14, 0),
            "start_time": datetime(2026, 10, 31, 14, 0),
            "end_time": datetime(2026, 10, 31, 15, 0),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(13, 30), time(14, 30))
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict["id"], 3)

    def test_touching_boundaries_do_not_collide(self):
        event = {
            "id": 4,
            "text": "Созвон с лидом",
            "date": self.target_date,
            "time": time(14, 0),
            "start_time": datetime(2026, 10, 31, 14, 0),
            "end_time": datetime(2026, 10, 31, 15, 0),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        before_conflict = processor.check(self.target_date, time(13, 0), time(14, 0))
        self.assertIsNone(before_conflict)
        after_conflict = processor.check(self.target_date, time(15, 0), time(16, 0))
        self.assertIsNone(after_conflict)

    def test_exclude_ids_skips_collision(self):
        event = {
            "id": 5,
            "text": "Планерка",
            "date": self.target_date,
            "time": time(10, 0),
            "start_time": datetime(2026, 10, 31, 10, 0),
            "end_time": datetime(2026, 10, 31, 11, 0),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(10, 0), time(11, 0), exclude_ids={5})
        self.assertIsNone(conflict)

    def test_completed_event_does_not_block_slot(self):
        event = {
            "id": 6,
            "text": "Завершенная задача",
            "date": self.target_date,
            "time": time(11, 0),
            "start_time": datetime(2026, 10, 31, 11, 0),
            "end_time": datetime(2026, 10, 31, 12, 0),
            "status": "completed",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(11, 0), time(12, 0))
        self.assertIsNone(conflict)

    def test_suggest_finds_next_free_slot(self):
        event = {
            "id": 7,
            "text": "Длинный митинг",
            "date": self.target_date,
            "time": time(10, 0),
            "start_time": datetime(2026, 10, 31, 10, 0),
            "end_time": datetime(2026, 10, 31, 11, 30),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        start_slot = datetime(2026, 10, 31, 10, 0)
        end_slot = datetime(2026, 10, 31, 11, 0)
        suggestion = processor.suggest(start_slot, end_slot)
        self.assertIsNotNone(suggestion)
        self.assertGreaterEqual(suggestion, datetime(2026, 10, 31, 11, 30))
        self.assertEqual(suggestion.date(), self.target_date)

    def test_suggest_returns_none_when_day_is_full(self):
        events = []
        for hour in range(24):
            st = datetime(2026, 10, 31, hour, 0)
            et = st + timedelta(hours=1)
            events.append({
                "id": 100 + hour,
                "text": f"Занятость {hour}",
                "date": self.target_date,
                "time": time(hour, 0),
                "start_time": st,
                "end_time": et,
                "status": "pending",
            })
        repo = MockEventRepository(events)
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        start_slot = datetime(2026, 10, 31, 23, 0)
        end_slot = datetime(2026, 10, 31, 23, 30)
        suggestion = processor.suggest(start_slot, end_slot)
        self.assertIsNone(suggestion)

    def test_log_prefixed_event_ignored_as_noise(self):
        event = {
            "id": 99,
            "text": "[ INFO ] Служебный лог",
            "date": self.target_date,
            "time": time(16, 0),
            "start_time": datetime(2026, 10, 31, 16, 0),
            "end_time": datetime(2026, 10, 31, 17, 0),
            "status": "pending",
        }
        repo = MockEventRepository([event])
        processor = CollisionProcessor(event_repository=repo, logger=self.logger)
        conflict = processor.check(self.target_date, time(16, 0), time(17, 0))
        self.assertIsNone(conflict)


if __name__ == "__main__":
    unittest.main()
