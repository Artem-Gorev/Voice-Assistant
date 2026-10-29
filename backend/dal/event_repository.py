import logging
import os
from datetime import date, time, datetime
from typing import Optional, List, Dict, Any, Union
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.dal.datetime_utils import _normalize_date, _normalize_time
from backend.dal.nlp_utils import lemmatize_text, classify_event

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("event_repository")


def _normalize_datetime(val: Union[datetime, date, str, None]) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, time(0, 0))
    if isinstance(val, str):
        clean_str = val.strip()
        if not clean_str:
            return None
        return datetime.fromisoformat(clean_str.replace("Z", "+00:00"))
    return None


def _extract_date_time(val: Any) -> tuple[Optional[date], Optional[time]]:
    if val is None:
        return None, None
    if isinstance(val, datetime):
        t = val.time()
        if t.tzinfo is not None:
            t = t.replace(tzinfo=None)
        return val.date(), t
    if isinstance(val, date):
        return val, None
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            t = dt.time()
            if t.tzinfo is not None:
                t = t.replace(tzinfo=None)
            return dt.date(), t
        except Exception as e:
            logger.info(f"Ошибка при извлечении даты и времени: {e}")
            raise
    return None, None


class EventRepository:
    DEFAULT_DSN = "postgresql://assistant_user:assistant_pass@localhost:5432/assistant_db"

    def __init__(self, connection=None, dsn: Optional[str] = None, **kwargs):
        logger.info("Инициализация репозитория событий")
        conn = connection or kwargs.get("conn")
        if conn is not None:
            self.conn = conn
        else:
            db_url = dsn or kwargs.get("db_url") or os.getenv("DATABASE_URL", self.DEFAULT_DSN)
            try:
                self.conn = psycopg2.connect(db_url)
            except Exception as e:
                logger.info(f"Ошибка подключения к базе данных: {e}")
                raise

        try:
            self.conn.autocommit = True
        except Exception as e:
            logger.info(f"Ошибка при установке autocommit: {e}")
            raise

    def _get_cursor(self):
        logger.info("Получение курсора базы данных")
        try:
            return self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            logger.info(f"Ошибка получения курсора: {e}")
            raise

    @staticmethod
    def _format_row(row: Any, description: Optional[Any] = None) -> Optional[dict]:
        logger.info("Форматирование строки события")
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
            raw_id = row[0] if len(row) > 0 else None
            raw_text = row[1] if len(row) > 1 else ""
            raw_start = row[5] if len(row) > 5 else None
            ev_date, ev_time = _extract_date_time(raw_start)
            return {
                "id": int(raw_id) if raw_id is not None else None,
                "text": str(raw_text) if raw_text is not None else "",
                "date": ev_date,
                "time": ev_time,
            }

        text_val = (
            data.get("original_text")
            if "original_text" in data and data.get("original_text") is not None
            else (
                data.get("text")
                if "text" in data and data.get("text") is not None
                else data.get("title", "")
            )
        )
        start_val = data.get("start_time")
        ev_date, ev_time = _extract_date_time(start_val)
        if ev_date is None and ("event_date" in data or "date" in data):
            ev_date = _normalize_date(data.get("event_date") or data.get("date"))
        if ev_time is None and ("event_time" in data or "time" in data):
            ev_time = _normalize_time(data.get("event_time") or data.get("time"))

        return {
            "id": int(data["id"]) if data.get("id") is not None else None,
            "text": str(text_val) if text_val is not None else "",
            "date": ev_date,
            "time": ev_time,
        }

    _map_row = _format_row

    def get_next_event(
        self, target_date: Union[date, str], target_time: Union[time, str, datetime]
    ) -> Optional[dict]:
        logger.info("Запрос на получение следующего события")
        t_date = _normalize_date(target_date)
        t_time = _normalize_time(target_time)
        target_dt = datetime.combine(t_date, t_time)

        query = (
            "SELECT * FROM events "
            "WHERE start_time::date = %(target_date)s AND start_time > %(target_dt)s "
            "ORDER BY start_time ASC LIMIT 1;"
        )
        params = {"target_date": t_date, "target_dt": target_dt}
        try:
            with self._get_cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return self._format_row(row, getattr(cur, "description", None))
        except Exception as e:
            logger.info(f"Ошибка при получении следующего события: {e}")
            raise

    def get_previous_event(
        self, target_date: Union[date, str], target_time: Union[time, str, datetime]
    ) -> Optional[dict]:
        logger.info("Запрос на получение предыдущего события")
        t_date = _normalize_date(target_date)
        t_time = _normalize_time(target_time)
        target_dt = datetime.combine(t_date, t_time)

        query = (
            "SELECT * FROM events "
            "WHERE start_time::date = %(target_date)s AND start_time < %(target_dt)s "
            "ORDER BY start_time DESC LIMIT 1;"
        )
        params = {"target_date": t_date, "target_dt": target_dt}
        try:
            with self._get_cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return self._format_row(row, getattr(cur, "description", None))
        except Exception as e:
            logger.info(f"Ошибка при получении предыдущего события: {e}")
            raise

    def get_events_by_date(self, target_date: Union[date, str]) -> List[dict]:
        logger.info("Запрос на получение событий по дате")
        t_date = _normalize_date(target_date)

        query = (
            "SELECT * FROM events "
            "WHERE start_time::date = %(target_date)s "
            "ORDER BY start_time ASC;"
        )
        params = {"target_date": t_date}
        try:
            with self._get_cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                desc = getattr(cur, "description", None)
                return [self._format_row(r, desc) for r in (rows or [])]
        except Exception as e:
            logger.info(f"Ошибка при получении событий по дате: {e}")
            raise

    def get_events_by_date_range(
        self, start_date: Union[date, str], end_date: Union[date, str]
    ) -> List[dict]:
        logger.info("Запрос на получение событий по диапазону дат")
        s_date = _normalize_date(start_date)
        e_date = _normalize_date(end_date)

        query = (
            "SELECT * FROM events "
            "WHERE start_time::date BETWEEN %(start_date)s AND %(end_date)s "
            "ORDER BY start_time ASC;"
        )
        params = {"start_date": s_date, "end_date": e_date}
        try:
            with self._get_cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                desc = getattr(cur, "description", None)
                return [self._format_row(r, desc) for r in (rows or [])]
        except Exception as e:
            logger.info(f"Ошибка при получении событий по диапазону дат: {e}")
            raise

    def create_event(self, data: dict) -> None:
        logger.info("Создание нового события")
        raw_text = (
            data.get("original_text")
            if "original_text" in data and data.get("original_text") is not None
            else (
                data.get("text")
                if "text" in data and data.get("text") is not None
                else data.get("title", "")
            )
        )
        if raw_text is None:
            raw_text = ""
        raw_text = str(raw_text)

        start_time_raw = data.get("start_time")
        if start_time_raw is not None:
            start_dt = _normalize_datetime(start_time_raw)
        else:
            raw_date = data.get("date") if "date" in data else data.get("event_date")
            d = _normalize_date(raw_date)
            raw_time = data.get("time") if "time" in data else data.get("event_time")
            t = _normalize_time(raw_time) or time(0, 0)
            start_dt = datetime.combine(d, t) if d else datetime.now()

        end_time_raw = data.get("end_time")
        if end_time_raw is not None:
            end_dt = _normalize_datetime(end_time_raw)
        else:
            end_dt = start_dt

        if start_dt is not None and end_dt is not None and end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt

        normalized_text = data.get("lemmatized_text") or data.get("normalized_text")
        if normalized_text is None:
            normalized_text = lemmatize_text(raw_text)

        event_type = data.get("event_type")
        if not event_type:
            event_type = classify_event(raw_text)

        status = data.get("status", "pending")

        embedding = data.get("embedding")
        if embedding is not None and isinstance(embedding, (list, tuple)):
            embedding_val = "[" + ", ".join(str(float(x)) for x in embedding) + "]"
        else:
            embedding_val = embedding

        query = """
            INSERT INTO events (original_text, lemmatized_text, event_type, status, start_time, end_time, embedding)
            VALUES (%(original_text)s, %(lemmatized_text)s, %(event_type)s, %(status)s, %(start_time)s, %(end_time)s, %(embedding)s);
        """
        params = {
            "original_text": raw_text,
            "lemmatized_text": normalized_text,
            "text": raw_text,
            "normalized_text": normalized_text,
            "event_type": event_type,
            "status": status,
            "start_time": start_dt,
            "end_time": end_dt,
            "embedding": embedding_val,
        }
        try:
            with self._get_cursor() as cur:
                cur.execute(query, params)
            self.conn.commit()
        except Exception as e:
            logger.info(f"Ошибка при создании события: {e}")
            raise

    def get_all_events(self) -> List[Dict[str, Any]]:
        logger.info("Получение всех событий для семантического анализа")
        query = "SELECT id, text, normalized_text, start_time, embedding FROM events ORDER BY id ASC;"
        try:
            with self._get_cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                desc = getattr(cur, "description", None)
                results = []
                for r in (rows or []):
                    if isinstance(r, dict):
                        results.append(dict(r))
                    elif hasattr(r, "_asdict"):
                        results.append(r._asdict())
                    elif desc:
                        col_names = [d[0] for d in desc]
                        results.append(dict(zip(col_names, r)))
                    else:
                        results.append(r)
                return results
        except Exception as e:
            logger.info(f"Ошибка при получении всех событий: {e}")
            raise

    def close(self) -> None:
        logger.info("Закрытие соединения с базой данных")
        if self.conn:
            closed_attr = getattr(self.conn, "closed", 0)
            if isinstance(closed_attr, (int, bool)) and closed_attr:
                return
            try:
                self.conn.close()
            except Exception as e:
                logger.info(f"Ошибка при закрытии соединения: {e}")
                raise

    def __enter__(self):
        logger.info("Вход в контекстный менеджер репозитория")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Выход из контекстного менеджера репозитория")
        self.close()
