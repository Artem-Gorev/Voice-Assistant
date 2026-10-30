import logging
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from backend.ai_service.llm import LLMConfig, LLMOrchestrator
from backend.dal.event_repository import EventRepository
from backend.services import CollisionProcessor, CommandDispatcher
from backend.text_normalizer import normalize_text_for_speech
from backend.voice_assistant import VoiceAssistant


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

    def test_ambiguous_target_accepts_ordinal_phrase(self):
        titles = ("Купить билеты", "Купить билеты до конца недели", "Купить билеты до конца месяца", "Купить билеты на концерт")
        for hour, title in enumerate(titles, 9):
            self.create(title, f"2026-10-31T{hour:02d}:00:00")

        response = self.dispatcher.process_llm_response({"action": "delete_event", "data": {"query": "Купить билеты"}}, "test")
        self.assertIn("Уточните", response)
        self.assertIn("Удалила", self.send("Четвёртое событие"))
        self.assertNotIn("Купить билеты на концерт", [event["text"] for event in self.repo.events.values()])

    def test_ambiguous_target_accepts_title_fragment(self):
        self.create("Купить билеты до конца недели", "2026-10-31T09:00:00")
        self.create("Купить билеты до конца месяца", "2026-10-31T10:00:00")

        response = self.dispatcher.process_llm_response({"action": "complete_event", "data": {"query": "Купить билеты"}}, "test")
        self.assertIn("часть названия", response)
        self.assertIn("Отметила", self.send("Событие до конца месяца"))
        self.assertEqual(self.repo.events[2]["status"], "completed")

    def test_conflict_offers_and_accepts_alternative(self):
        self.create("Встреча с Иваном", "2026-10-31T13:00:00")
        self.assertIn("Перенести", self.create("Встреча с командой", "2026-10-31T13:00:00"))
        self.assertEqual(len(self.repo.events), 1)
        self.assertIn("Добавила", self.send("да"))
        self.assertEqual(len(self.repo.events), 2)
        times = sorted(event["time"] for event in self.repo.events.values())
        self.assertEqual(times, [datetime(2026, 10, 31, 13).time(), datetime(2026, 10, 31, 14).time()])

    def test_conflict_accepts_natural_confirmation(self):
        self.create("Обед", "2026-10-31T13:00:00")
        self.create("Созвон с командой", "2026-10-31T13:00:00")
        response = self.send("Да перенеси")
        self.assertIn("Добавила", response)
        self.assertEqual(self.repo.events[2]["time"].hour, 14)

    def test_conflict_accepts_another_time(self):
        self.create("Обед", "2026-10-31T13:00:00")
        self.create("Созвон с командой", "2026-10-31T13:00:00")
        response = self.send("Нет, лучше на 15:00")
        self.assertIn("Добавила", response)
        self.assertEqual(self.repo.events[2]["time"].hour, 15)

    def test_reschedule_accepts_natural_confirmation(self):
        self.create("Ужин", "2026-10-31T20:00:00")
        self.create("Ужин", "2026-10-31T21:00:00")
        self.assertIn("Перенесла", self.send("Да, перенеси"))
        self.assertEqual(self.repo.events[1]["time"].hour, 21)

    def test_generic_meeting_asks_title_and_keeps_time(self):
        response = '{"action":"create_event","data":{"title":"Встречу на субботу","start_time":"2026-10-31T13:00:00"}}'
        llm = LLMOrchestrator(config=LLMConfig())
        llm._client = SimpleNamespace(chat=lambda _: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))]))
        first = llm.process("Поставь встречу на субботу в 13:00", session_id="meeting", current_dt=self.now)
        self.assertEqual(first.action, "clarify")
        self.assertIn("С кем", first.reply_text)
        second = llm.process("с Иваном", session_id="meeting", current_dt=self.now)
        self.assertEqual(second.action, "create_event")
        self.assertEqual(second.data["title"], "Встреча с Иваном")
        self.assertEqual(second.data["start_time"], "2026-10-31T13:00:00")

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

    def test_existing_event_does_not_claim_it_was_added(self):
        self.create("Ужин", "2026-11-01T09:00:00")
        response = self.create("Ужин", "2026-11-01T09:00:00")
        self.assertIn("уже есть", response)
        self.assertEqual(len(self.repo.events), 1)

    def test_same_title_on_same_day_offers_reschedule(self):
        self.create("Ужин", "2026-11-01T20:00:00")
        response = self.create("Ужин", "2026-11-01T21:00:00")
        self.assertIn("Перенести", response)
        self.assertEqual(len(self.repo.events), 1)
        self.assertIn("Перенесла", self.send("да"))
        self.assertEqual(self.repo.events[1]["time"].hour, 21)

    def test_cancel_voice_command_filters_date_and_spoken_time(self):
        self.create("Встреча с командой", "2026-10-31T18:00:00")
        self.create("Встреча с командой", "2026-11-01T18:00:00")
        response = self.send("мне нужно отменить встречу с командой на завтра в восемнадцать ноль ноль")
        self.assertIn("Удалила", response)
        self.assertEqual(len(self.repo.events), 1)
        self.assertEqual(self.repo.events[2]["date"], date(2026, 11, 1))

    def test_move_by_title_uses_new_date_as_destination(self):
        self.create("Встреча с командой", "2026-10-30T18:00:00")
        response = self.send("перенеси встречу с командой на завтра")
        self.assertIn("Перенесла", response)
        self.assertEqual(self.repo.events[1]["date"], date(2026, 10, 31))

    def test_delete_all_matching_meetings(self):
        self.create("Встреча с командой", "2026-10-31T18:00:00")
        self.create("Встреча с командой", "2026-11-01T18:00:00")
        response = self.send("удали все встречи с командой")
        self.assertIn("2 событий", response)
        self.assertFalse(self.repo.events)

    def test_ambiguous_spoken_hour_requires_clarification(self):
        response = '{"action":"create_event","data":{"title":"Ужин","start_time":"2026-10-31T09:00:00"}}'
        llm = LLMOrchestrator(config=LLMConfig())
        llm._client = SimpleNamespace(chat=lambda _: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=response))]))
        first = llm.process("Добавь ужин завтра в девять часов", session_id="hour", current_dt=self.now)
        self.assertEqual(first.action, "clarify")
        self.assertIn("21:00", first.reply_text)
        second = llm.process("вечером", session_id="hour", current_dt=self.now)
        self.assertEqual(second.action, "create_event")
        self.assertEqual(second.data["start_time"], "2026-10-31T21:00:00")

    def test_database_time_keeps_existing_wall_clock(self):
        repo = EventRepository.__new__(EventRepository)
        repo._logger = logging.getLogger("event-management-tests")
        row = {"id": 1, "original_text": "Ужин", "start_time": datetime(2026, 11, 1, 12, tzinfo=timezone(timedelta(hours=3))), "end_time": None}
        self.assertEqual(repo._format_row(row)["time"].hour, 9)

    def test_pasted_log_prefix_is_removed(self):
        clean = VoiceAssistant._clean_input("[ INFO ] Пользователь: [ INFO ] Пользователь: добавь ужин завтра")
        self.assertEqual(clean, "добавь ужин завтра")

    def test_damaged_unicode_is_removed_from_user_input(self):
        self.assertEqual(VoiceAssistant._clean_input("Четвертое событ\udcd0ие"), "Четвертое событие")

    def test_tts_normalizer_converts_list_numbers_dates_and_times(self):
        text = "2. Купить билеты — 31.10 в 09:00; 4. Купить билеты — 05.11 в 13:00. Назовите номер."
        normalized = normalize_text_for_speech(text)
        self.assertIn("второе", normalized)
        self.assertIn("четвёртое", normalized)
        self.assertIn("тридцать первого октября", normalized)
        self.assertIn("в девять часов", normalized)
        self.assertNotRegex(normalized, r"\d")


if __name__ == "__main__":
    unittest.main()
