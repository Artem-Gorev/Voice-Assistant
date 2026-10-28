import os
from datetime import date, datetime, time
from typing import Any, List, Optional, Union

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

try:
    from .nlp_utils import classify_event, lemmatize_text
except ImportError:
    from backend.dal.nlp_utils import classify_event, lemmatize_text


def _normalize_date(val: Union[date, str, datetime, None]) -> Optional[date]:
    """Преобразование строки или datetime в объект date."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val)
    return val


def _normalize_time(val: Union[time, str, datetime, None]) -> Optional[time]:
    """Преобразование строки или datetime в объект time без часового пояса."""
    if val is None:
        return None
    if isinstance(val, time):
        return val.replace(tzinfo=None) if val.tzinfo is not None else val
    if isinstance(val, datetime):
        t = val.time()
        return t.replace(tzinfo=None) if t.tzinfo is not None else t
    if isinstance(val, str):
        t = time.fromisoformat(val)
        return t.replace(tzinfo=None) if t.tzinfo is not None else t
    return val


class EventRepository:
    """
    Репозиторий доступа к данным (DAL) для управления событиями в PostgreSQL.
    Обеспечивает автокоммит, структурирование данных в словари и NLP-обработку.
    """

    DEFAULT_DSN = "postgresql://assistant_user:assistant_pass@localhost:5432/assistant_db"

    def __init__(self, connection=None, dsn: Optional[str] = None, **kwargs):
        """Инициализация репозитория с существующим или новым подключением к базе данных."""
        conn = connection or kwargs.get("conn")
        if conn is not None:
            self.conn = conn
        else:
            if psycopg2 is None:
                raise ImportError(
                    "psycopg2 is required to establish a database connection. "
                    "Please install psycopg2 or psycopg2-binary."
                )
            db_url = dsn or kwargs.get("db_url") or os.getenv("DATABASE_URL", self.DEFAULT_DSN)
            self.conn = psycopg2.connect(db_url)

        try:
            self.conn.autocommit = True
        except Exception:
            pass

    def _get_cursor(self):
        """Получение курсора базы данных с поддержкой словарей (RealDictCursor)."""
        if RealDictCursor is not None:
            try:
                return self.conn.cursor(cursor_factory=RealDictCursor)
            except (TypeError, AttributeError):
                pass
        return self.conn.cursor()

    @staticmethod
    def _map_row(row: Any, description: Optional[Any] = None) -> Optional[dict]:
        """
        Преобразование строки базы данных в словарь формата:
        {"id": int, "text": str, "date": date, "time": time}
        """
        if row is None:
            return None

        if isinstance(row, dict):
            data = row
        elif hasattr(row, "_asdict"):
            data = row._asdict()
        elif description:
            col_names = [desc[0] for desc in description]
            data = dict(zip(col_names, row))
        else:
            # Резервный разбор кортежа согласно схеме таблицы:
            # id, event_type, title, normalized_text, event_date, event_time, status, created_at
            raw_id = row[0] if len(row) > 0 else None
            raw_title = row[2] if len(row) > 2 else (row[1] if len(row) > 1 else "")
            raw_date = row[4] if len(row) > 4 else None
            raw_time = row[5] if len(row) > 5 else None
            return {
                "id": int(raw_id) if raw_id is not None else None,
                "text": str(raw_title) if raw_title is not None else "",
                "date": _normalize_date(raw_date),
                "time": _normalize_time(raw_time),
            }

        text_val = data.get("title") if "title" in data else data.get("text")
        date_val = data.get("event_date") if "event_date" in data else data.get("date")
        time_val = data.get("event_time") if "event_time" in data else data.get("time")

        return {
            "id": int(data["id"]) if data.get("id") is not None else None,
            "text": str(text_val) if text_val is not None else "",
            "date": _normalize_date(date_val),
            "time": _normalize_time(time_val),
        }

    def get_next_event(self, target_date: Union[date, str], target_time: Union[time, str]) -> Optional[dict]:
        """Получение ближайшего предстоящего события на указанную дату строго позже заданного времени."""
        t_date = _normalize_date(target_date)
        t_time = _normalize_time(target_time)

        query = (
            "SELECT * FROM events "
            "WHERE event_date = %s AND event_time > %s "
            "ORDER BY event_time ASC LIMIT 1;"
        )
        with self._get_cursor() as cur:
            cur.execute(query, (t_date, t_time))
            row = cur.fetchone()
            return self._map_row(row, getattr(cur, "description", None))

    def get_previous_event(self, target_date: Union[date, str], target_time: Union[time, str]) -> Optional[dict]:
        """Получение ближайшего прошедшего события на указанную дату строго раньше заданного времени."""
        t_date = _normalize_date(target_date)
        t_time = _normalize_time(target_time)

        query = (
            "SELECT * FROM events "
            "WHERE event_date = %s AND event_time < %s "
            "ORDER BY event_time DESC LIMIT 1;"
        )
        with self._get_cursor() as cur:
            cur.execute(query, (t_date, t_time))
            row = cur.fetchone()
            return self._map_row(row, getattr(cur, "description", None))

    def get_events_by_date(self, target_date: Union[date, str]) -> List[dict]:
        """Получение всех событий на указанную дату в хронологическом порядке."""
        t_date = _normalize_date(target_date)

        query = (
            "SELECT * FROM events "
            "WHERE event_date = %s "
            "ORDER BY event_time ASC;"
        )
        with self._get_cursor() as cur:
            cur.execute(query, (t_date,))
            rows = cur.fetchall()
            desc = getattr(cur, "description", None)
            return [self._map_row(r, desc) for r in (rows or [])]

    def create_event(self, data: dict) -> None:
        """
        Создание нового события в базе данных.
        Выполняет преобразование строки ISO в дату и время, лемматизацию текста
        и определение типа события.
        """
        title = data.get("title") if "title" in data and data.get("title") is not None else data.get("text", "")
        if title is None:
            title = ""

        start_time_raw = data.get("start_time")
        if start_time_raw:
            if isinstance(start_time_raw, str):
                dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
            elif isinstance(start_time_raw, datetime):
                dt = start_time_raw
            else:
                dt = datetime.fromisoformat(str(start_time_raw))
            event_date = dt.date()
            event_time = dt.time()
            if event_time.tzinfo is not None:
                event_time = event_time.replace(tzinfo=None)
        else:
            raw_date = data.get("date") if "date" in data else data.get("event_date")
            event_date = _normalize_date(raw_date)

            raw_time = data.get("time") if "time" in data else data.get("event_time")
            event_time = _normalize_time(raw_time)

        normalized_text = data.get("normalized_text")
        if normalized_text is None:
            normalized_text = lemmatize_text(title)

        event_type = data.get("event_type")
        if not event_type:
            event_type = classify_event(title)

        status = data.get("status", "pending")

        query = """
            INSERT INTO events (event_type, title, normalized_text, event_date, event_time, status)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        with self._get_cursor() as cur:
            cur.execute(query, (event_type, title, normalized_text, event_date, event_time, status))

        try:
            self.conn.commit()
        except Exception:
            pass

    def get_events_by_date_range(
        self, start_date: Union[date, str], end_date: Union[date, str]
    ) -> List[dict]:
        """Получение всех событий в заданном диапазоне дат включительно."""
        s_date = _normalize_date(start_date)
        e_date = _normalize_date(end_date)

        query = """
            SELECT * FROM events
            WHERE event_date BETWEEN %s AND %s
            ORDER BY event_date ASC, event_time ASC;
        """
        with self._get_cursor() as cur:
            cur.execute(query, (s_date, e_date))
            rows = cur.fetchall()
            desc = getattr(cur, "description", None)
            return [self._map_row(r, desc) for r in (rows or [])]

    def close(self) -> None:
        """Закрытие соединения с базой данных."""
        if self.conn:
            # В psycopg2 conn.closed — целочисленный статус (0 = открыто, 1 или 2 = закрыто)
            closed_attr = getattr(self.conn, "closed", 0)
            if isinstance(closed_attr, (int, bool)) and closed_attr:
                return
            try:
                self.conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
