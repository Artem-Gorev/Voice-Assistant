import logging
import unittest
from datetime import datetime

from pydantic import ValidationError

from backend.ai_service.llm import (
    ClarifyData,
    CreateEventData,
    LanguageModel,
    LLMConfig,
    LLMResult,
    ListEventsData,
    LLMResponseSchema,
    SearchEventsData,
)
from backend.ai_service.llm.adapter import (
    DialogSession,
    FALLBACK_RESPONSE,
    LLMOrchestrator,
    parse_json_payload,
)


class TestLLMOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orchestrator = LLMOrchestrator(config=LLMConfig(mock_mode=True))
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
            CreateEventData(title="Встреча в прошлом", start_time="2026-10-28T15:00:00", end_time="2026-10-28T14:00:00")

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

    def test_factory_creates_gigachat_adapter(self):
        model = LanguageModel.create("gigachat", config=LLMConfig(mock_mode=True))
        self.assertIsInstance(model, LLMOrchestrator)

    def test_slot_filling_fsm_flow(self):
        session_id = "test_user_fsm"

        res1 = self.orchestrator.process(
            "Напомни забрать посылку",
            session_id=session_id,
            current_dt=self.test_now,
        )
        self.assertEqual(res1.action, "clarify")
        self.assertIsInstance(res1, LLMResult)
        self.assertEqual(res1.data["missing_field"], "date_and_time")
        self.assertEqual(res1.data["partial_data"]["title"], "Забрать посылку")
        self.assertIn(session_id, self.orchestrator.sessions)
        self.assertIsInstance(self.orchestrator.sessions[session_id], DialogSession)

        res2 = self.orchestrator.process(
            "Завтра в 17:00",
            session_id=session_id,
            current_dt=self.test_now,
        )
        self.assertEqual(res2.action, "create_event")
        self.assertEqual(res2.data["title"], "Забрать посылку")
        self.assertEqual(res2.data["start_time"], "2026-10-28T17:00:00")
        self.assertNotIn(session_id, self.orchestrator.sessions)

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
        self.assertEqual(fallback_res.action, "chat")

    def test_custom_logger_injection(self):
        custom_logger = logging.getLogger("CustomTestLogger")
        orch = LLMOrchestrator(config=LLMConfig(mock_mode=True), logger=custom_logger)
        self.assertEqual(orch._logger, custom_logger)


if __name__ == "__main__":
    unittest.main()
