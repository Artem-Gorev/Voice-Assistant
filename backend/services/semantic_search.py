import logging
from collections.abc import Sequence
from typing import Any

from backend.ai_service.ttv import TextVectorizer
from backend.dal.event_repository import EventRepository


class SemanticSearchService:
    def __init__(self, repository: EventRepository, vectorizer: TextVectorizer, logger: logging.Logger, min_score: float = 0.75):
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score должен быть в диапазоне от 0 до 1")
        self._repository = repository
        self._vectorizer = vectorizer
        self._logger = logger
        self._min_score = min_score

    def search_events_by_vector(self, query: str, tasks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        events = list(tasks) or self._repository.get_all_events()
        events = [event for event in events if event.get("text", "").strip()]
        if not events:
            self._logger.info(f"[SERVICES]: Поиск '{query}' пропущен: событий нет")
            return []

        self._logger.info(f"[SERVICES]: Семантический поиск '{query}' среди {len(events)} событий")
        descriptions = [event["text"] for event in events]
        ranked = self._vectorizer.search(query, descriptions, top_k=5)
        self._logger.info(f"[SERVICES]: Оценки кандидатов: {', '.join(f'{item.score:.3f}' for item in ranked)}; порог: {self._min_score:.2f}")
        qualified = [item for item in ranked if item.score >= self._min_score]
        if qualified:
            best_score = qualified[0].score
            qualified = [item for item in qualified if best_score - item.score <= 0.03]
        results = [events[item.index] for item in qualified]
        self._logger.info(f"[SERVICES]: Поиск вернул {len(results)} близких результатов выше порога")
        return results
