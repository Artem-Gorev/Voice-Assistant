from typing import Any
import psycopg2
from backend.database.etl_migration import DB_CONFIG


def search_events_by_vector(query_vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

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

    cur.execute(query, (query_vector, query_vector, limit))
    rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "original_text": r[1],
            "event_type": r[2],
            "status": r[3],
            "start_time": r[4],
            "end_time": r[5],
            "similarity": float(r[6]),
        })

    cur.close()
    conn.close()
    return results
