import logging
import unittest
from unittest.mock import MagicMock

from backend.voice_assistant import VoiceAssistant


class TestVoiceAssistantPipeline(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("TestVoiceAssistantPipeline")
        self.assistant = VoiceAssistant.__new__(VoiceAssistant)
        self.assistant._logger = self.logger
        self.assistant._speak = False
        self.assistant._record_seconds = 5.0
        self.assistant._sample_rate = 16000
        self.assistant._repository = MagicMock()
        self.assistant._recognizer = None
        self.assistant._synthesizer = None
        self.assistant._audio_handler = None
        self.assistant._dispatcher = MagicMock()
        self.assistant._llm = MagicMock()

    def test_clean_input_removes_log_prefix(self):
        dirty = "[ INFO ] Пользователь: Напомни позвонить маме"
        cleaned = VoiceAssistant._clean_input(dirty)
        self.assertEqual(cleaned, "Напомни позвонить маме")

    def test_clean_input_removes_repeated_prefixes(self):
        dirty = "[ INFO ] Пользователь: [ DEBUG ] Пользователь: Встреча в 14:00"
        cleaned = VoiceAssistant._clean_input(dirty)
        self.assertEqual(cleaned, "Встреча в 14:00")

    def test_clean_input_removes_corrupted_unicode(self):
        dirty = "Тестовое событ\udcd0ие"
        cleaned = VoiceAssistant._clean_input(dirty)
        self.assertEqual(cleaned, "Тестовое событие")

    def test_clean_input_rejects_raw_system_logs(self):
        with self.assertRaises(ValueError):
            VoiceAssistant._clean_input("[ ERROR ] Connection lost to postgres")

    def test_process_input_text_validation(self):
        processed = self.assistant.process_input("   поставь встречу   ")
        self.assertEqual(processed, "поставь встречу")

        with self.assertRaises(ValueError):
            self.assistant.process_input("      ")

    def test_process_input_invalid_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.assistant.process_input(12345)

    def test_process_input_audio_requires_sample_rate(self):
        class MockNdArray:
            pass

        with self.assertRaises(ValueError):
            with unittest.mock.patch("backend.voice_assistant.np") as mock_np:
                mock_np.ndarray = MockNdArray
                self.assistant.process_input(MockNdArray(), sample_rate=None)

    def test_run_executes_pipeline_turn(self):
        self.assistant._dispatcher.process_followup.return_value = None
        mock_llm_result = MagicMock()
        mock_llm_result.model_dump.return_value = {"action": "create_event", "data": {"title": "Обед"}}
        mock_llm_result.model_dump_json.return_value = "{}"
        self.assistant._llm.process.return_value = mock_llm_result
        self.assistant._dispatcher.process_llm_response.return_value = "Добавила «Обед» в расписание."

        reply = self.assistant.run("Обед в 13:00", text_output=False, voice_output=False)
        self.assertEqual(reply, "Добавила «Обед» в расписание.")
        self.assistant._llm.process.assert_called_once()
        self.assistant._dispatcher.process_llm_response.assert_called_once()

    def test_run_followup_skips_llm_when_dispatcher_handles(self):
        self.assistant._dispatcher.process_followup.return_value = "Перенесла событие на завтра."
        reply = self.assistant.run("да, перенеси", text_output=False, voice_output=False)
        self.assertEqual(reply, "Перенесла событие на завтра.")
        self.assistant._llm.process.assert_not_called()

    def test_run_empty_text_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.assistant.run("   ")

    def test_close_releases_repository(self):
        self.assistant.close()
        self.assistant._repository.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
