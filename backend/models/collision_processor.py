from datetime import datetime, timedelta, date, time
from typing import Optional, Dict

class CollisionProcessor:
    def __init__(self, EventRepository):
        self.db = EventRepository
        # Предполагаем, что любая встреча по умолчанию длится 1 час,
        # если Артем не передал end_time
        self.DEFAULT_DURATION = timedelta(hours=1)

    def check(self, target_date: date, new_start_time: time, new_end_time: time) -> Optional[Dict]:

        # Переводим время в datetime для удобного сравнения
        new_start_dt = datetime.combine(target_date, new_start_time)
        new_end_dt = datetime.combine(target_date, new_end_time)

        # 1. Проверяем СЛЕДУЮЩЕЕ событие (как ты и просил)
        next_event = self.db.get_next_event(target_date, new_start_time)
        if next_event:
            next_start_dt = datetime.combine(target_date, next_event["time"])

            # Если следующее событие начинается РАНЬШЕ, чем заканчивается наше — коллизия
            if next_start_dt < new_end_dt:
                return next_event

        # 2. Проверяем ПРЕДЫДУЩЕЕ событие (чтобы не поставить встречу "внутрь" уже идущей)
        prev_event = self.db.get_previous_event(target_date, new_start_time)
        if prev_event:
            prev_start_dt = datetime.combine(target_date, prev_event["time"])
            prev_end_dt = prev_start_dt + self.DEFAULT_DURATION  # Предполагаем, что старое событие длится час

            # Если предыдущее событие заканчивается ПОЗЖЕ, чем начинается наше — коллизия
            if prev_end_dt > new_start_dt:
                return prev_event

        return None