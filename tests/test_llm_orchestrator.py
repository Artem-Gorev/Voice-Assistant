import logging
import os
import sys
import unittest
from datetime import date, datetime
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "ai-service")))

from models import (
    ClarifyData,
    CreateEventData,
    ListEventsData,
    LLMResponseSchema,
    SearchEventsData,
)
from llm_adapter import (
    DialogSession,
    FALLBACK_RESPONSE,
    LLMOrchestrator,
    parse_json_payload,
)
from models.collision_processor import CollisionProcessor
from models.command_dispatcher import CommandDispatcher


class DummyDB:
    def __init__(self):
        self.events = []

    def get_next_event(self, target_date, target_time):
        return None

    def get_previous_event(self, target_date, target_time):
        return None

    def create_event(self, data):
        dt = datetime.fromisoformat(data["start_time"])
        self.events.append({"text": data["title"], "date": dt.date(), "time": dt.time()})

    def get_events_by_date(self, target_date):
        return [e for e in self.events if e["date"] == target_date]


class DummySearch:
    def semantic_search(self, query, date_from, date_to):
        return [{"date": date(2026, 10, 20), "text": "Найдено: " + query}]


class TestLLMOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orchestrator = LLMOrchestrator(mock_mode=True)
        self.test_now = datetime(2026, 10, 27, 10, 0, 0)

    def test_schemas_validation_success(self):
        create_data = CreateEventData(
            title="Тестовая встреча",
            start_time="2026-10-28T14:00:00",
            end_time="2026-10-28T15:00:00",
        )
        self.assertEqual(create_data.title, "Тестовая встреча")

        list_data = ListEventsData(date="2026-10-28")
        self.assertEqual(list_data.date, "2026-10-28")

        search_data = SearchEventsData(query="проект", date_from="2026-10-01", date_to="2026-10-31")
        self.assertEqual(search_data.query, "проект")

        clarify_data = ClarifyData(missing_field="start_time", partial_data={"title": "Помыть машину"})
        self.assertEqual(clarify_data.missing_field, "start_time")

        envelope = LLMResponseSchema.model_validate({
            "action": "create_event",
            "data": create_data.model_dump(),
            "reply_text": "Создано.",
        })
        self.assertEqual(envelope.action, "create_event")
        self.assertEqual(envelope.data["title"], "Тестовая встреча")

    def test_schemas_validation_failure(self):
        with self.assertRaises(ValidationError):
            CreateEventData(title="Ошибка", start_time="invalid-iso-date")

        with self.assertRaises(ValidationError):
            CreateEventData(title="   ", start_time="2026-10-28T14:00:00")

        with self.assertRaises(ValidationError):
            CreateEventData(
                title="Встреча в прошлом",
                start_time="2026-10-28T15:00:00",
                end_time="2026-10-28T14:00:00",
            )

        with self.assertRaises(ValidationError):
            ListEventsData(date="28-10-2026")

        with self.assertRaises(ValidationError):
            ListEventsData(date="2026-10-28T14:00:00")

        with self.assertRaises(ValidationError):
            LLMResponseSchema.model_validate({
                "action": "create_event",
                "data": {"title": "Встреча", "start_time": "неправильное_время"},
            })

    def test_dynamic_system_prompt(self):
        prompt = self.orchestrator.build_system_prompt(self.test_now)
        self.assertIn("2026-10-27", prompt)
        self.assertIn("10:00", prompt)
        self.assertIn("вторник", prompt)
        self.assertIn("КАЛЕНДАРНАЯ СЕТКА", prompt)
        self.assertIn("create_event", prompt)
        self.assertIn("clarify", prompt)
        self.assertIn("start_time", prompt)

    def test_slot_filling_fsm_flow(self):
        session_id = "test_user_fsm"

        res1 = self.orchestrator.process(
            "Напомни забрать посылку",
            session_id=session_id,
            current_dt=self.test_now,
        )
        self.assertEqual(res1["action"], "clarify")
        self.assertEqual(res1["data"]["missing_field"], "start_time")
        self.assertEqual(res1["data"]["partial_data"]["title"], "Забрать посылку")
        self.assertIn(session_id, self.orchestrator.sessions)
        self.assertIsInstance(self.orchestrator.sessions[session_id], DialogSession)

        res2 = self.orchestrator.process(
            "Завтра в 17:00",
            session_id=session_id,
            current_dt=self.test_now,
        )
        self.assertEqual(res2["action"], "create_event")
        self.assertEqual(res2["data"]["title"], "Забрать посылку")
        self.assertEqual(res2["data"]["start_time"], "2026-10-28T17:00:00")
        self.assertNotIn(session_id, self.orchestrator.sessions)

    def test_dispatcher_compatibility(self):
        db = DummyDB()
        search = DummySearch()
        collision_proc = CollisionProcessor(EventRepository=db)
        dispatcher = CommandDispatcher(collision_proc, EventRepository=db, SemanticSearchServce=search)

        queries = [
            "Поставь встречу на завтра с 12:00 до 13:00",
            "Какие планы на завтра?",
            "Найди договор",
            "Напомни позвонить маме",
            "Привет, как дела?",
        ]

        for q in queries:
            llm_res = self.orchestrator.process(q, session_id="disp_test", current_dt=self.test_now)
            tts_res = dispatcher.process_llm_response(llm_res)
            self.assertIsInstance(tts_res, str)
            self.assertTrue(len(tts_res) > 0)

    def test_parse_json_payload(self):
        raw_clean = '{"action": "chat", "data": {}, "reply_text": "Привет"}'
        self.assertEqual(parse_json_payload(raw_clean)["action"], "chat")

        raw_markdown = '```json\n{"action": "chat", "data": {}, "reply_text": "Тест"}\n```'
        self.assertEqual(parse_json_payload(raw_markdown)["action"], "chat")

        with self.assertRaises(ValueError):
            parse_json_payload("совершенно не валидный текст")

    def test_process_fallback_on_crash(self):
        self.orchestrator.simulator = None
        fallback_res = self.orchestrator.process("Любая команда", session_id="crash_test")
        self.assertEqual(fallback_res, FALLBACK_RESPONSE)
        self.assertEqual(fallback_res["action"], "chat")

    def test_custom_logger_injection(self):
        custom_logger = logging.getLogger("CustomTestLogger")
        orch = LLMOrchestrator(mock_mode=True, logger=custom_logger)
        self.assertEqual(orch.logger, custom_logger)


if __name__ == "__main__":
    unittest.main()
