import threading
import warnings
from time import perf_counter

import numpy as np
import torch

from backend.text_normalizer import normalize_text_for_speech

from .base import SpeechSynthesizer
from .config import SileroConfig
from .result import SpeechAudio


@SpeechSynthesizer.register("silero")
class SileroSynthesizer(SpeechSynthesizer):
    def __init__(self, config: SileroConfig = None, logger=None):
        super().__init__(config or SileroConfig(), logger)
        self._model = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model

            try:
                torch.set_num_threads(self._config.torch_threads)
                self._logger.info(f"[TTS]: Загрузка модели Silero TTS '{self._config.model_id}'")

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message="TypedStorage is deprecated", category=UserWarning)
                    self._model, _ = torch.hub.load("snakers4/silero-models", "silero_tts", language="ru",
                                                    speaker=self._config.model_id)

                self._model.to(torch.device(self._config.device))
            except Exception as error:
                raise RuntimeError(f"Не удалось загрузить Silero TTS: {error}")

        return self._model

    def synthesize(self, text: str) -> SpeechAudio:
        normalized_text = normalize_text_for_speech(" ".join((text or "").split()))
        if not normalized_text:
            raise ValueError("Текст для синтеза не должен быть пустым")

        if len(normalized_text) > self._config.max_text_characters:
            raise ValueError(f"Текст превышает лимит {self._config.max_text_characters} символов")

        started = perf_counter()
        try:
            with self._inference_lock, torch.inference_mode():
                tensor = self._load_model().apply_tts(text=normalized_text, speaker=self._config.voice,
                                                      sample_rate=self._config.sample_rate)
        except RuntimeError:
            raise

        except Exception as error:
            self._logger.exception(f"[TTS]: Ошибка синтеза Silero: {error}")
            raise RuntimeError(f"[TTS]: Ошибка синтеза Silero: {error}")

        samples = tensor.detach().cpu().numpy().astype(np.float32, copy=False).squeeze()
        if samples.ndim != 1 or samples.size == 0 or not np.isfinite(samples).all():
            raise RuntimeError("Silero вернула некорректные аудиоданные")

        processing_time = perf_counter() - started
        duration = len(samples) / self._config.sample_rate
        self._logger.info(f"[TTS]: Silero создала {duration:.2f} сек. аудио за {processing_time:.2f} сек.")
        return SpeechAudio(samples=samples, sample_rate=self._config.sample_rate, model_name="Silero TTS v5_ru",
                           processing_time_seconds=processing_time, voice=self._config.voice)
