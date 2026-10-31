import unittest

from backend.text_normalizer import normalize_text_for_speech


class TestTextNormalizer(unittest.TestCase):
    def test_converts_dates(self):
        result = normalize_text_for_speech("Встреча назначена на 31.10.")
        self.assertIn("тридцать первого октября", result)

    def test_converts_times(self):
        result = normalize_text_for_speech("Созвон в 14:00")
        self.assertIn("в четырнадцать часов", result)

        result_half = normalize_text_for_speech("Встреча в 09:30")
        self.assertIn("девять", result_half)
        self.assertIn("тридцать", result_half)

    def test_converts_list_numbers_to_ordinals(self):
        text = "1. Первое дело; 2. Второе дело; 3. Третье дело"
        result = normalize_text_for_speech(text)
        self.assertIn("первое", result)
        self.assertIn("второе", result)
        self.assertIn("третье", result)

    def test_converts_iso_dates(self):
        result = normalize_text_for_speech("Событие на 2026-10-31 назначено.")
        self.assertIn("тридцать первого октября", result)

    def test_converts_counts_with_nouns(self):
        result = normalize_text_for_speech("Найдено 2 события и 5 встреч.")
        self.assertIn("два события", result)
        self.assertIn("пять встреч", result)

    def test_speech_output_contains_no_raw_digits(self):
        text = "1. Сдача отчёта — 15.11 в 18:45 (всего 25 страниц)."
        result = normalize_text_for_speech(text)
        self.assertNotRegex(result, r"\d")


if __name__ == "__main__":
    unittest.main()
