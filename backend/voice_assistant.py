import logging
import os
from datetime import datetime
import numpy as np

from backend.ai_service.llm import LLMConfig, LLMOrchestrator
from backend.ai_service.ttv import RuBertTiny2Config, TextVectorizer
from backend.audio import AudioHandler
from backend.dal.event_repository import EventRepository
from backend.services import CollisionProcessor, CommandDispatcher, SemanticSearchService


class VoiceAssistant:
    def __init__(self, logger: logging.Logger, voice_input: bool = False, speak: bool = False, record_seconds: float = 6.0, sample_rate: int = 16_000):
        self._logger = logger
        self._speak = speak
        self._record_seconds = record_seconds
        self._sample_rate = sample_rate
        self._repository: EventRepository | None = None
        self._recognizer = None
        self._synthesizer = None
        self._audio_handler = AudioHandler(logger) if voice_input or speak else None

        dsn = os.getenv("DATABASE_URL") or self._build_database_url()
        self._repository = EventRepository(dsn=dsn, logger=logger)

        vectorizer = TextVectorizer.create(model_name="rubert_tiny2", config=RuBertTiny2Config(), logger=logger)
        min_search_score = float(os.getenv("TTV_MIN_SIMILARITY", "0.80"))
        search_service = SemanticSearchService(self._repository, vectorizer, logger, min_score=min_search_score)
        collision_processor = CollisionProcessor(event_repository=self._repository, logger=logger)

        self._dispatcher = CommandDispatcher(collision_proc=collision_processor, event_repository=self._repository,
                                             semantic_search_service=search_service, logger=logger)
        self._llm = LLMOrchestrator(config=LLMConfig.from_env(), logger=logger)

        if voice_input:
            from backend.ai_service.stt import SpeechRecognizer, TOneConfig
            self._recognizer = SpeechRecognizer.create(model_name="t_one", config=TOneConfig(), logger=logger)

        if speak:
            from backend.ai_service.tts import SileroConfig, SpeechSynthesizer
            self._synthesizer = SpeechSynthesizer.create(model_name="silero", config=SileroConfig(), logger=logger)

    @staticmethod
    def _build_database_url() -> str:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres_password")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5433")
        database = os.getenv("POSTGRES_DB", "assistant_db")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def _transcribe_audio(self, audio: np.ndarray, sample_rate: int) -> str:
        if self._recognizer is None:
            raise RuntimeError("STT не включён. Создайте VoiceAssistant с voice_input=True.")
        transcription = self._recognizer.transcribe(audio=audio, sample_rate=sample_rate)
        self._logger.info(f"Распознано: {transcription.text}")
        return transcription.text

    def process_input(self, user_input: str | np.ndarray, sample_rate: int | None = None) -> str:
        if isinstance(user_input, str):
            normalized_text = " ".join(user_input.split())
            if not normalized_text:
                raise ValueError("Текст запроса не должен быть пустым")
            return normalized_text

        if isinstance(user_input, np.ndarray):
            if sample_rate is None:
                raise ValueError("Для аудиовхода необходимо указать sample_rate")
            return self._transcribe_audio(user_input, sample_rate)

        raise TypeError("Вход должен быть строкой текста или numpy-массивом аудио")

    def record_audio(self) -> np.ndarray:
        if self._recognizer is None or self._audio_handler is None:
            raise RuntimeError("Аудиовход не включён. Создайте VoiceAssistant с voice_input=True.")
        return self._audio_handler.record_audio(duration_seconds=self._record_seconds, sample_rate=self._sample_rate)

    def _speak_response(self, text: str) -> None:
        if not self._speak:
            raise RuntimeError("Голосовой ответ не включён. Создайте VoiceAssistant с speak=True.")

        from backend.text_normalizer import normalize_text_for_speech

        speech_text = normalize_text_for_speech(text)
        audio = self._synthesizer.synthesize(speech_text)
        self._audio_handler.play_audio(audio.to_wav_bytes())

    def run(self, text: str, text_output: bool = True, voice_output: bool = False) -> str:
        normalized_text = " ".join(text.split())
        if not normalized_text:
            raise ValueError("Текст запроса не должен быть пустым")

        self._logger.info(f"Пользователь: {normalized_text}")
        current_datetime = datetime.now().astimezone()
        result = self._llm.process(normalized_text, session_id="cli", current_dt=current_datetime)

        self._logger.debug(f"[LLM]:\n{result.model_dump_json(indent=2)}")
        response = self._dispatcher.process_llm_response(result.model_dump(mode="json"))
        if text_output:
            self._logger.info(f"Ассистент: {response}")
        if voice_output:
            self._speak_response(response)
        return response

    def close(self) -> None:
        if self._repository is not None:
            self._repository.close()
