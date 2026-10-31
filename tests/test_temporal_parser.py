import unittest
from datetime import date, datetime

from backend.ai_service.llm.temporal import (
    resolve_date,
    resolve_daypart,
    resolve_event_datetime,
    resolve_period,
)


class TestTemporalParser(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 27, 10, 0, 0)
        self.today = self.now.date()

    def test_resolve_relative_days(self):
        self.assertEqual(resolve_date("сегодня", self.now), self.today)
        self.assertEqual(resolve_date("завтра", self.now), date(2026, 10, 28))
        self.assertEqual(resolve_date("послезавтра", self.now), date(2026, 10, 29))

    def test_resolve_iso_date(self):
        self.assertEqual(resolve_date("поставь на 2026-11-15 встречу", self.now), date(2026, 11, 15))

    def test_resolve_numeric_dates(self):
        self.assertEqual(resolve_date("15.11", self.now), date(2026, 11, 15))
        self.assertEqual(resolve_date("03/12/2026", self.now), date(2026, 12, 3))

    def test_resolve_russian_month_names(self):
        self.assertEqual(resolve_date("12 ноября", self.now), date(2026, 11, 12))
        self.assertEqual(resolve_date("5 мая 2027 года", self.now), date(2027, 5, 5))
        self.assertEqual(resolve_date("31 декабря", self.now), date(2026, 12, 31))

    def test_resolve_dayparts(self):
        self.assertEqual(resolve_daypart("встретимся утром"), ("06:00", "12:00"))
        self.assertEqual(resolve_daypart("днем в офисе"), ("12:00", "18:00"))
        self.assertEqual(resolve_daypart("днём созвон"), ("12:00", "18:00"))
        self.assertEqual(resolve_daypart("поговорим вечером"), ("18:00", "23:59"))
        self.assertEqual(resolve_daypart("работа ночью"), ("00:00", "06:00"))
        self.assertIsNone(resolve_daypart("просто текст без времени"))

    def test_resolve_periods_week_and_month(self):
        week_this = resolve_period("планы на эту неделю", self.now)
        self.assertIsNotNone(week_this)
        start_w, end_w = week_this
        self.assertEqual(start_w, date(2026, 10, 26))
        self.assertEqual(end_w, date(2026, 11, 1))

        week_next = resolve_period("на следующей неделе", self.now)
        self.assertIsNotNone(week_next)
        self.assertEqual(week_next[0], date(2026, 11, 2))
        self.assertEqual(week_next[1], date(2026, 11, 8))

        month_this = resolve_period("в этом месяце", self.now)
        self.assertIsNotNone(month_this)
        self.assertEqual(month_this[0], date(2026, 10, 1))
        self.assertEqual(month_this[1], date(2026, 10, 31))

        month_next = resolve_period("в следующем месяце", self.now)
        self.assertIsNotNone(month_next)
        self.assertEqual(month_next[0], date(2026, 11, 1))
        self.assertEqual(month_next[1], date(2026, 11, 30))

    def test_resolve_event_datetime(self):
        dt = resolve_event_datetime("поставь созвон завтра в 14:30", self.now)
        self.assertEqual(dt, datetime(2026, 10, 28, 14, 30))

        dt_after = resolve_event_datetime("послезавтра в 09:15", self.now)
        self.assertEqual(dt_after, datetime(2026, 10, 29, 9, 15))

        no_time = resolve_event_datetime("завтра просто так", self.now)
        self.assertIsNone(no_time)

    def test_resolve_weekday(self):
        self.assertEqual(resolve_date("в среду", self.now), date(2026, 10, 28))
        self.assertEqual(resolve_date("в пятницу", self.now), date(2026, 10, 30))


if __name__ == "__main__":
    unittest.main()
