import logging
import threading
import time

from backend.voice_assistant import VoiceAssistant


class AssistantRuntime:
    def __init__(self) -> None:
        self.logger = logging.getLogger("voice_assistant.api")
        self.assistant = VoiceAssistant(self.logger)
        self.lock = threading.RLock()
        self._recent_chats: dict[tuple[str, str], tuple[float, str]] = {}
        self._recognizer = None
        self._synthesizer = None

    def _get_recognizer(self):
        if self._recognizer is None:
            from backend.ai_service.stt import SpeechRecognizer, TOneConfig

            self._recognizer = SpeechRecognizer.create(
                "t_one", config=TOneConfig(), logger=self.logger
            )
        return self._recognizer

    def _get_synthesizer(self):
        if self._synthesizer is None:
            from backend.ai_service.tts import SileroConfig, SpeechSynthesizer

            self._synthesizer = SpeechSynthesizer.create(
                "silero", config=SileroConfig(), logger=self.logger
            )
        return self._synthesizer

    def warmup(self) -> None:
        """Load all ML models before the API reports that startup is complete."""
        self.logger.info("[STARTUP]: Прогрев TTV — текстовый векторизатор")
        self.assistant._vectorizer.warmup()
        self.logger.info("[STARTUP]: TTV готов")

        self.logger.info("[STARTUP]: Прогрев STT — распознавание речи")
        self._get_recognizer().warmup()
        self.logger.info("[STARTUP]: STT готов")

        self.logger.info("[STARTUP]: Прогрев TTS — синтез речи")
        self._get_synthesizer().warmup()
        self.logger.info("[STARTUP]: TTS готов; модели загружены")

    def chat(self, message: str, session_id: str, request_id: str | None = None) -> str:
        with self.lock:
            now = time.monotonic()
            expired = [key for key, (created_at, _) in self._recent_chats.items() if now - created_at > 120]
            for key in expired:
                self._recent_chats.pop(key, None)
            cache_key = (session_id, request_id) if request_id else None
            if cache_key and cache_key in self._recent_chats:
                return self._recent_chats[cache_key][1]
            reply = self.assistant.run(message, session_id=session_id, text_output=False)
            if cache_key:
                self._recent_chats[cache_key] = (time.monotonic(), reply)
            return reply

    def events(self, target_date):
        with self.lock:
            return self.assistant._repository.get_events_by_date(target_date)

    def transcribe_audio(self, audio, sample_rate: int) -> str:
        with self.lock:
            try:
                return self._get_recognizer().transcribe(audio, sample_rate).text
            except ImportError as exc:
                raise RuntimeError(
                    "Распознавание голоса не установлено. Установите зависимости из requirements-stt.txt."
                ) from exc

    def synthesize_speech(self, text: str) -> bytes:
        with self.lock:
            return self._get_synthesizer().synthesize(text).to_wav_bytes()

    def close(self) -> None:
        self.assistant.close()
