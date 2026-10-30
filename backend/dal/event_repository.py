import logging
import os
from datetime import date, time, datetime
from typing import Any
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.dal.datetime_utils import _normalize_date, _normalize_time, _normalize_datetime, _extract_date_time
from backend.dal.nlp_utils import lemmatize_text, classify_event


class EventRepository:
    DEFAULT_DSN = "postgresql://assistant_user:assistant_pass@localhost:5432/assistant_db"

    def __init__(self, connection=None, dsn: str | None = None, logger=None, **kwargs):
        self._logger = logger or logging.getLogger(self.__class__.__module__)

        conn = connection or kwargs.get("conn")
        if conn is not None:
            self.conn = conn
        else:
            db_url = dsn or kwargs.get("db_url") or os.getenv("DATABASE_URL", self.DEFAULT_DSN)
            try:
                self.conn = psycopg2.connect(db_url)
            except Exception as e:
                self._logger.info(f"[DAL]: Ошибка подключения к базе данных: {e}")
                raise

        try:
            self.conn.autocommit = True
        except Exception as e:
            self._logger.info(f"[DAL]: Ошибка при установке autocommit: {e}")
            raise

    def _get_cursor(self):
        self._logger.info("[DAL]: Получение курсора базы данных")
        try:
            return self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            self._logger.info(f"[DAL]: Ошибка получения курсора: {e}")
            raise

    def _format_row(self, row: Any, description: Any | None = None) -> dict[str, Any] | None:
        self._logger.info("[DAL]: Форматирование строки события")
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

    def get_next_event(self, target_date: date | str, target_time: time | str | datetime) -> dict[str, Any] | None:
        self._logger.info("[DAL]: Запрос на получение следующего события")
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
            self._logger.info(f"[DAL]: Ошибка при получении следующего события: {e}")
            raise

    def get_previous_event(self, target_date: date | str, target_time: time | str | datetime) -> dict[str, Any] | None:
        self._logger.info("[DAL]: Запрос на получение предыдущего события")
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
            self._logger.info(f"[DAL]: Ошибка при получении предыдущего события: {e}")
            raise

    def get_events_by_date(self, target_date: date | str) -> list[dict[str, Any]]:
        self._logger.info("[DAL]: Запрос на получение событий по дате")
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
            self._logger.info(f"[DAL]: Ошибка при получении событий по дате: {e}")
            raise

    def get_events_by_date_range(self, start_date: date | str, end_date: date | str) -> list[dict[str, Any]]:
        self._logger.info("[DAL]: Запрос на получение событий по диапазону дат")
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
            self._logger.info(f"[DAL]: Ошибка при получении событий по диапазону дат: {e}")
            raise

    def create_event(self, data: dict[str, Any]) -> None:
        self._logger.info("[DAL]: Создание нового события")
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

        duplicate_query = """
            SELECT id
            FROM events
            WHERE lemmatized_text = %(lemmatized_text)s
              AND start_time = %(start_time)s
            LIMIT 1;
        """
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
                cur.execute(duplicate_query, params)
                if cur.fetchone():
                    self._logger.info(f"[DAL]: Пропущено повторное событие '{raw_text}' на {start_dt}")
                    return
                cur.execute(query, params)
            self.conn.commit()
        except Exception as e:
            self._logger.info(f"[DAL]: Ошибка при создании события: {e}")
            raise

    def get_all_events(self) -> list[dict[str, Any]]:
        self._logger.info("[DAL]: Получение всех событий для семантического анализа")
        query = (
            "SELECT id, original_text, lemmatized_text, start_time "
            "FROM events ORDER BY id ASC;"
        )
        try:
            with self._get_cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                desc = getattr(cur, "description", None)
                return [
                    self._format_row(row, desc)
                    for row in (rows or [])
                ]
        except Exception as e:
            self._logger.info(f"[DAL]: Ошибка при получении всех событий: {e}")
            raise

    def close(self) -> None:
        self._logger.info("[DAL]: Закрытие соединения с базой данных")
        if self.conn:
            closed_attr = getattr(self.conn, "closed", 0)
            if isinstance(closed_attr, (int, bool)) and closed_attr:
                return
            try:
                self.conn.close()
            except Exception as e:
                self._logger.info(f"[DAL]: Ошибка при закрытии соединения: {e}")
                raise

    def __enter__(self):
        self._logger.info("[DAL]: Вход в контекстный менеджер репозитория")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._logger.info("[DAL]: Выход из контекстного менеджера репозитория")
        self.close()
