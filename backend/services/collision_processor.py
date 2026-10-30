from datetime import date, datetime, time, timedelta
from typing import Any

class CollisionProcessor:
    def __init__(self, event_repository, logger, default_duration_hours: int = 1):
        self.repo = event_repository
        self.logger = logger
        self.default_duration = timedelta(hours=default_duration_hours)

    def check(self, target_date: date, new_start_time: time, new_end_time: time, exclude_ids: set[int] | None = None) -> dict[str, Any] | None:
        start = datetime.combine(target_date, new_start_time)
        end = datetime.combine(target_date, new_end_time)
        if end <= start:
            end += timedelta(days=1)
        return self.check_interval(start, end, exclude_ids)

    def check_interval(self, start: datetime, end: datetime, exclude_ids: set[int] | None = None) -> dict[str, Any] | None:
        self.logger.info(f"[SERVICES]: Проверка коллизий с {start} до {end}")
        excluded = exclude_ids or set()
        for event in self.repo.get_events_by_date_range(start.date() - timedelta(days=1), end.date()):
            if event.get("id") in excluded or event.get("status") == "completed":
                continue
            event_start = event.get("start_time")
            if not isinstance(event_start, datetime):
                if event.get("date") is None or event.get("time") is None:
                    continue
                event_start = datetime.combine(event["date"], event["time"])
            event_end = event.get("end_time")
            if not isinstance(event_end, datetime) or event_end <= event_start:
                event_end = event_start + self.default_duration
            if start < event_end and end > event_start:
                return event
        return None

    def suggest(self, start: datetime, end: datetime, exclude_ids: set[int] | None = None) -> datetime | None:
        duration = end - start
        candidate = start + timedelta(minutes=30)
        for _ in range(32):
            if candidate.date() != start.date():
                return None
            conflict = self.check_interval(candidate, candidate + duration, exclude_ids)
            if conflict is None:
                return candidate
            conflict_end = conflict.get("end_time")
            candidate = conflict_end if isinstance(conflict_end, datetime) and conflict_end > candidate else candidate + timedelta(minutes=30)
        return None
