import unittest
from datetime import date, datetime, time, timezone

from backend.dal.datetime_utils import (
    _extract_date_time,
    _normalize_date,
    _normalize_datetime,
    _normalize_time,
)
from backend.dal.nlp_utils import classify_event, lemmatize_text


class TestDalUtils(unittest.TestCase):
    def test_normalize_date_from_various_types(self):
        self.assertIsNone(_normalize_date(None))
        self.assertEqual(_normalize_date(date(2026, 11, 1)), date(2026, 11, 1))
        self.assertEqual(_normalize_date(datetime(2026, 11, 1, 14, 30)), date(2026, 11, 1))
        self.assertEqual(_normalize_date("2026-11-01"), date(2026, 11, 1))

    def test_normalize_time_from_various_types(self):
        self.assertIsNone(_normalize_time(None))
        self.assertEqual(_normalize_time(time(14, 30)), time(14, 30))
        self.assertEqual(_normalize_time(datetime(2026, 11, 1, 14, 30)), time(14, 30))
        self.assertEqual(_normalize_time("14:30:00"), time(14, 30))
        tz_time = time(14, 30, tzinfo=timezone.utc)
        self.assertIsNone(_normalize_time(tz_time).tzinfo)

    def test_normalize_datetime_from_various_types(self):
        self.assertIsNone(_normalize_datetime(None))
        self.assertIsNone(_normalize_datetime("   "))
        self.assertEqual(_normalize_datetime(datetime(2026, 11, 1, 12, 0)), datetime(2026, 11, 1, 12, 0))
        self.assertEqual(_normalize_datetime(date(2026, 11, 1)), datetime(2026, 11, 1, 0, 0))
        self.assertEqual(_normalize_datetime("2026-11-01T14:30:00"), datetime(2026, 11, 1, 14, 30))

    def test_extract_date_time_tuple(self):
        d, t = _extract_date_time(None)
        self.assertIsNone(d)
        self.assertIsNone(t)

        d, t = _extract_date_time(datetime(2026, 11, 1, 15, 45))
        self.assertEqual(d, date(2026, 11, 1))
        self.assertEqual(t, time(15, 45))

        d, t = _extract_date_time("2026-11-01T15:45:00")
        self.assertEqual(d, date(2026, 11, 1))
        self.assertEqual(t, time(15, 45))

    def test_classify_event_triggers(self):
        self.assertEqual(classify_event("Встреча с клиентом"), "meeting")
        self.assertEqual(classify_event("Срочный созвон"), "meeting")
        self.assertEqual(classify_event("Демо для инвесторов"), "meeting")
        self.assertEqual(classify_event("Планёрка отдела"), "meeting")
        self.assertEqual(classify_event("Напомни выпить таблетки"), "reminder")
        self.assertEqual(classify_event("Сделать коммит и запушить код"), "task")
        self.assertEqual(classify_event(None), "task")

    def test_lemmatize_text_basic(self):
        self.assertEqual(lemmatize_text(""), "")
        self.assertEqual(lemmatize_text(None), "")
        result = lemmatize_text("Встреча с клиентом")
        self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main()
