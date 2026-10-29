from datetime import datetime, timedelta, date, time
from typing import Optional, Dict

class CollisionProcessor:
    def __init__(self, event_repository, logger, default_duration_hours: int = 1):
        self.repo = event_repository
        self.logger = logger
        self.default_duration = timedelta(hours=default_duration_hours)

    def check(self, target_date: date, new_start_time: time, new_end_time: time) -> Optional[Dict]:
        new_start_dt = datetime.combine(target_date, new_start_time)
        new_end_dt = datetime.combine(target_date, new_end_time)

        next_event = self.repo.get_next_event(target_date, new_start_time)
        if next_event:
            next_start_dt = datetime.combine(target_date, next_event["time"])
            if next_start_dt < new_end_dt:
                return next_event

        prev_event = self.repo.get_previous_event(target_date, new_start_time)
        if prev_event:
            prev_start_dt = datetime.combine(target_date, prev_event["time"])
            prev_end_dt = prev_start_dt + self.default_duration
            if prev_end_dt > new_start_dt:
                return prev_event

        return None