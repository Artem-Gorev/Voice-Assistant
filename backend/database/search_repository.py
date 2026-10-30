import logging
from typing import Any

import psycopg2

from backend.database.config import get_db_config


class SearchRepository:
    def __init__(self, logger: logging.Logger, db_config: dict[str, str] | None = None):
        self._logger = logger
        self._db_config = db_config or get_db_config()

    def search_events_by_vector(self, query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit должен быть не меньше 1")

        query = """
            SELECT
                id,
                original_text,
                event_type,
                status,
                start_time,
                end_time,
                1 - (embedding <=> %s::vector) AS similarity
            FROM events
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        self._logger.info(f"[DB]: Поиск событий по вектору, лимит {limit}")

        connection = None
        try:
            connection = psycopg2.connect(**self._db_config)
            with connection.cursor() as cursor:
                cursor.execute(query, (query_vector, query_vector, limit))
                rows = cursor.fetchall()

            results = [
                {
                    "id": row[0],
                    "original_text": row[1],
                    "event_type": row[2],
                    "status": row[3],
                    "start_time": row[4],
                    "end_time": row[5],
                    "similarity": float(row[6]),
                }
                for row in rows
            ]
            self._logger.info(f"[DB]: Найдено событий: {len(results)}")
            return results
        except Exception:
            self._logger.exception("[DB]: Ошибка поиска событий по вектору")
            raise
        finally:
            if connection is not None:
                connection.close()
