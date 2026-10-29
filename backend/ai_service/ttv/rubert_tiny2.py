import threading
from collections.abc import Sequence
from time import perf_counter

import numpy as np
import torch
import torch.nn.functional as functional
from transformers import AutoModel, AutoTokenizer

from .base import TextVectorizer
from .config import RuBertTiny2Config
from .result import SearchResult, TextVectors


@TextVectorizer.register("rubert_tiny2")
class RuBertTiny2Vectorizer(TextVectorizer):
    def __init__(self, config: RuBertTiny2Config = None, logger=None):
        super().__init__(config or RuBertTiny2Config(), logger)
        self._tokenizer = None
        self._model = None
        self._device = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    @property
    def device(self) -> str:
        self._load_model()
        return str(self._device)

    @property
    def dimension(self) -> int:
        self._load_model()
        return int(self._model.config.hidden_size)

    def _load_model(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return
            try:
                if self._config.torch_threads is not None:
                    torch.set_num_threads(self._config.torch_threads)

                self._device = self._resolve_device()
                load_options = {"cache_dir": self._config.cache_dir,
                                "local_files_only": self._config.local_files_only}
                self._logger.info(f"[TTV]: Загрузка модели преобразования текста '{self._config.model_id}'")
                self._tokenizer = AutoTokenizer.from_pretrained(self._config.model_id, **load_options)

                self._model = AutoModel.from_pretrained(self._config.model_id, **load_options)
                self._model.to(self._device)
                self._model.eval()
            except Exception as error:
                raise RuntimeError(f"Не удалось загрузить {self._config.model_id}: {error}")

    def _resolve_device(self):
        requested = self._config.device
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA недоступна")
        if requested == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("Apple MPS недоступен")
        if requested != "auto":
            return requested
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def encode(self, texts: str | Sequence[str]) -> TextVectors:
        values = self._validate_texts(texts)
        started = perf_counter()

        try:
            with self._inference_lock:
                self._load_model()
                encoded_batches = []

                for offset in range(0, len(values), self._config.batch_size):
                    batch = values[offset : offset + self._config.batch_size]
                    tokenizer_options = {"padding": True, "truncation": True, "return_tensors": "pt"}

                    if self._config.max_length is not None:
                        tokenizer_options["max_length"] = self._config.max_length

                    tokens = self._tokenizer(list(batch), **tokenizer_options)
                    tokens = {name: tensor.to(self._device) for name, tensor in tokens.items()}

                    with torch.inference_mode():
                        output = self._model(**tokens)
                        embeddings = output.last_hidden_state[:, 0, :]

                        if self._config.normalize:
                            embeddings = functional.normalize(embeddings, p=2, dim=1)
                    encoded_batches.append(embeddings.cpu().numpy().astype(np.float32, copy=False))

        except RuntimeError:
            raise

        except Exception as error:
            self._logger.exception(f"[TTV]: Ошибка векторизации RuBERT: {error}")
            raise RuntimeError(f"[TTV]: Ошибка векторизации RuBERT: {error}")

        vectors = np.concatenate(encoded_batches, axis=0)
        processing_time = perf_counter() - started
        self._logger.info(f"[TTV]: RuBERT обработала {len(values)} текстов за {processing_time:.3f} сек.")
        return TextVectors(vectors=vectors, texts=values, processing_time_seconds=processing_time,
                           model_name="cointegrated/rubert-tiny2")

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode(text).vector

    def similarity(self, first: str, second: str) -> float:
        vectors = self.encode((first, second)).vectors
        return self._cosine_similarity(vectors[0], vectors[1])

    def search(self, query: str, corpus: Sequence[str], top_k: int = 5) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k должен быть не меньше 1")

        corpus_values = self._validate_texts(corpus)
        vectors = self.encode((query, *corpus_values)).vectors
        query_vector = vectors[0]
        corpus_vectors = vectors[1:]

        query_norm = np.linalg.norm(query_vector)
        corpus_norms = np.linalg.norm(corpus_vectors, axis=1)
        denominators = corpus_norms * query_norm

        scores = np.divide(corpus_vectors @ query_vector, denominators, out=np.zeros(len(corpus_values),
                           dtype=np.float32), where=denominators != 0)
        indices = np.argsort(-scores)[: min(top_k, len(corpus_values))]
        return [SearchResult(index=int(index), text=corpus_values[index], score=float(scores[index])) for index in indices]

    @staticmethod
    def _validate_texts(texts: str | Sequence[str]) -> tuple[str, ...]:
        values = (texts,) if isinstance(texts, str) else tuple(texts)
        if not values:
            raise ValueError("Необходимо передать хотя бы один текст")

        normalized: list[str] = []
        for text in values:
            if not isinstance(text, str):
                raise ValueError("Каждый элемент должен быть строкой")

            cleaned = " ".join(text.split())
            if not cleaned:
                raise ValueError("Текст не должен быть пустым")
            normalized.append(cleaned)
        return tuple(normalized)

    @staticmethod
    def _cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
        denominator = np.linalg.norm(first) * np.linalg.norm(second)
        if denominator == 0:
            raise RuntimeError("Модель вернула нулевой вектор")
        return float(np.dot(first, second) / denominator)
