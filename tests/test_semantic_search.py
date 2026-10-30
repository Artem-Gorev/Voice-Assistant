from collections import namedtuple
import logging
import unittest

from backend.services.semantic_search import SemanticSearchService

MockSearchResult = namedtuple("MockSearchResult", ["index", "score", "text"])


class MockVectorizer:
    def __init__(self, scores_map=None):
        self.scores_map = scores_map or {}

    def search(self, query: str, texts: list[str], top_k: int = 5):
        results = []
        for index, text in enumerate(texts):
            score = self.scores_map.get(text, 0.5)
            results.append(MockSearchResult(index=index, score=score, text=text))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


class MockRepo:
    def __init__(self, events=None):
        self._events = events or []

    def get_all_events(self):
        return list(self._events)


class TestSemanticSearch(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("TestSemanticSearch")

    def test_invalid_min_score_raises_value_error(self):
        with self.assertRaises(ValueError):
            SemanticSearchService(MockRepo(), MockVectorizer(), self.logger, min_score=-0.1)

        with self.assertRaises(ValueError):
            SemanticSearchService(MockRepo(), MockVectorizer(), self.logger, min_score=1.5)

    def test_search_with_empty_events_returns_empty(self):
        service = SemanticSearchService(MockRepo([]), MockVectorizer(), self.logger, min_score=0.75)
        results = service.search_events_by_vector("созвон", tasks=[])
        self.assertEqual(results, [])

    def test_search_filters_below_threshold(self):
        events = [
            {"id": 1, "text": "Купить продукты"},
            {"id": 2, "text": "Полить цветы"},
        ]
        scores = {"Купить продукты": 0.60, "Полить цветы": 0.40}
        vectorizer = MockVectorizer(scores)
        service = SemanticSearchService(MockRepo(events), vectorizer, self.logger, min_score=0.75)
        results = service.search_events_by_vector("магазин", tasks=events)
        self.assertEqual(results, [])

    def test_search_returns_highest_ranking_candidates(self):
        events = [
            {"id": 1, "text": "Обсудить контракт с юристом"},
            {"id": 2, "text": "Согласовать договор с партнером"},
            {"id": 3, "text": "Купить кофе"},
        ]
        scores = {
            "Обсудить контракт с юристом": 0.88,
            "Согласовать договор с партнером": 0.87,
            "Купить кофе": 0.20,
        }
        vectorizer = MockVectorizer(scores)
        service = SemanticSearchService(MockRepo(events), vectorizer, self.logger, min_score=0.75)
        results = service.search_events_by_vector("юридический договор", tasks=events)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[1]["id"], 2)

    def test_search_uses_repository_fallback_when_tasks_empty(self):
        events = [{"id": 10, "text": "Забрать посылку"}]
        scores = {"Забрать посылку": 0.90}
        vectorizer = MockVectorizer(scores)
        repo = MockRepo(events)
        service = SemanticSearchService(repo, vectorizer, self.logger, min_score=0.75)
        results = service.search_events_by_vector("посылка", tasks=[])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 10)


if __name__ == "__main__":
    unittest.main()
