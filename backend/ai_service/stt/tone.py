import threading
from time import perf_counter

import numpy as np

from .base import SpeechRecognizer
from .config import TOneConfig
from .result import Transcription, TranscriptionSegment


@SpeechRecognizer.register("t_one")
class TOneRecognizer(SpeechRecognizer):
    def __init__(self, config: TOneConfig = None, logger=None):
        super().__init__(config or TOneConfig(), logger)
        self._pipeline = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        with self._load_lock:
            if self._pipeline is not None:
                return self._pipeline

            try:
                from tone import DecoderType, StreamingCTCPipeline

                decoder_type = DecoderType.GREEDY if self._config.decoder == "greedy" else DecoderType.BEAM_SEARCH
                self._logger.info(f"[STT]: Загрузка модели T-one '{self._config.model_id}'")
                self._pipeline = StreamingCTCPipeline.from_hugging_face(decoder_type=decoder_type)

            except Exception as error:
                raise RuntimeError(f"Не удалось загрузить T-one: {error}")
        return self._pipeline

    def warmup(self) -> None:
        """Download/load the recognizer and initialize its inference path."""
        samples = np.zeros(self._config.target_sample_rate, dtype=np.int32)
        with self._inference_lock:
            self._load_pipeline().forward_offline(samples)

    def transcribe(self, audio, sample_rate: int) -> Transcription:
        samples = self._prepare_audio(audio, sample_rate)
        duration = len(samples) / self._config.target_sample_rate
        self._validate_duration(duration)

        started = perf_counter()
        try:
            with self._inference_lock:
                phrases = self._load_pipeline().forward_offline(samples)

        except RuntimeError:
            raise

        except Exception as error:
            self._logger.exception(f"[STT]: Ошибка распознавания T-one: {error}")
            raise RuntimeError(f"[STT]: Ошибка распознавания T-one: {error}")

        segments = tuple(TranscriptionSegment(text=phrase.text.strip(), start_seconds=float(phrase.start_time),
                         end_seconds=float(phrase.end_time)) for phrase in phrases if phrase.text.strip())

        text = " ".join(segment.text for segment in segments)
        if not text:
            raise RuntimeError("Речь не распознана. Говорите ближе к микрофону и повторите попытку")

        processing_time = perf_counter() - started
        self._logger.info(f"[STT]: T-one обработала {duration:.2f} сек. аудио за {processing_time:.2f} сек.")
        return Transcription(text=text, segments=segments, audio_duration_seconds=duration, processing_time_seconds=processing_time,
                             model_name="T-one", sample_rate=self._config.target_sample_rate)

    def _prepare_audio(self, audio, sample_rate: int) -> np.ndarray:
        if sample_rate <= 0:
            raise ValueError("sample_rate должен быть больше нуля")

        samples = np.asarray(audio)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)

        if samples.ndim != 1 or samples.size == 0:
            raise ValueError("Ожидается непустой одномерный массив аудио")

        if np.issubdtype(samples.dtype, np.integer):
            scale = float(max(abs(np.iinfo(samples.dtype).min), np.iinfo(samples.dtype).max))
            samples = samples.astype(np.float32) / scale
        else:
            samples = samples.astype(np.float32, copy=False)

        if not np.isfinite(samples).all():
            raise ValueError("Аудио содержит NaN или бесконечные значения")

        samples = np.clip(samples, -1.0, 1.0)
        if sample_rate != self._config.target_sample_rate:
            target_length = round(len(samples) * self._config.target_sample_rate / sample_rate)
            source_positions = np.arange(len(samples), dtype=np.float64) / sample_rate
            target_positions = np.arange(target_length, dtype=np.float64) / self._config.target_sample_rate
            samples = np.interp(target_positions, source_positions, samples).astype(np.float32, copy=False)

        return np.rint(samples * 32_767).astype(np.int32)

    def _validate_duration(self, duration: float) -> None:
        if duration < self._config.min_audio_seconds:
            raise ValueError("Аудиозапись слишком короткая")

        if duration > self._config.max_audio_seconds:
            raise ValueError(f"Аудиозапись превышает лимит {self._config.max_audio_seconds:g} сек.")
