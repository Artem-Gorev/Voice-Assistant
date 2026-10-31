import unittest

from backend.event_text import clean_event_title


class TestEventText(unittest.TestCase):
    def test_clean_removes_parasite_verbs(self):
        title = "поставь встречу с дизайнером"
        cleaned = clean_event_title(title)
        self.assertEqual(cleaned, "Встречу с дизайнером")

    def test_clean_removes_embedded_dates_and_times(self):
        title = "напомни мне купить молока завтра в 18:30"
        cleaned = clean_event_title(title)
        self.assertNotIn("завтра", cleaned.lower())
        self.assertNotIn("18:30", cleaned)
        self.assertEqual(cleaned, "Купить молока")

    def test_clean_removes_relative_weekdays(self):
        title = "создай митинг на следующую среду в 15:00"
        cleaned = clean_event_title(title)
        self.assertNotIn("среду", cleaned.lower())
        self.assertEqual(cleaned, "Митинг")

    def test_clean_preserves_plain_titles(self):
        plain = "Обед с коллегами"
        self.assertEqual(clean_event_title(plain), plain)

    def test_clean_capitalizes_result(self):
        title = "напомни забрать ключи"
        cleaned = clean_event_title(title)
        self.assertTrue(cleaned.startswith("З"))
        self.assertEqual(cleaned, "Забрать ключи")


if __name__ == "__main__":
    unittest.main()
