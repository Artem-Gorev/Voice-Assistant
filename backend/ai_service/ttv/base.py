import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence

from .result import SearchResult, TextVectors


class TextVectorizer(ABC):
    _METHODS = {}

    def __init__(self, config, logger=None):
        self._config = config
        self._logger = logger or logging.getLogger(self.__class__.__module__)

    @classmethod
    def register(cls, name):
        def decorator(subclass):
            cls._METHODS[name.lower()] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, model_name, config=None, logger=None):
        key = model_name.lower().replace("-", "_")
        implementation = cls._METHODS.get(key)
        if implementation is None:
            available = ", ".join(sorted(cls._METHODS))
            raise ValueError(f"TTV-модель '{model_name}' не найдена. Доступные модели: {available}")
        return implementation(config=config, logger=logger)

    @abstractmethod
    def encode(self, texts: str | Sequence[str]) -> TextVectors:
        pass

    @abstractmethod
    def search(self, query: str, corpus: Sequence[str], top_k: int = 5) -> list[SearchResult]:
        pass
