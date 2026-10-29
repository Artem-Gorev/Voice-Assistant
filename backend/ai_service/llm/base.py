import logging
from abc import ABC, abstractmethod
from datetime import datetime

from .config import LLMConfig
from .result import LLMResult


class LanguageModel(ABC):
    _METHODS = {}

    def __init__(self, config: LLMConfig, logger=None):
        self._config = config
        self._logger = logger or logging.getLogger(self.__class__.__module__)

    @classmethod
    def register(cls, name):
        def decorator(subclass):
            cls._METHODS[name.lower()] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, provider: str, config: LLMConfig | None = None, logger=None):
        key = provider.lower().replace("-", "_")
        implementation = cls._METHODS.get(key)
        if implementation is None:
            available = ", ".join(sorted(cls._METHODS))
            raise ValueError(f"LLM-провайдер '{provider}' не найден. Доступные провайдеры: {available}")
        return implementation(config=config or LLMConfig(provider=key), logger=logger)

    @abstractmethod
    def process(self, user_text: str, session_id: str = "default",
                current_dt: datetime | None = None) -> LLMResult:
        pass
