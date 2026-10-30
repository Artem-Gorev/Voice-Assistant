import os
import sys
import logging
from datetime import datetime
import pandas as pd
import psycopg2

from backend.dal.nlp_utils import classify_event, lemmatize_text
from backend.database.config import get_db_config

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("ETL")


def run_etl(csv_path: str = "data/voice_assistant_events_1000_77e927b5d2.csv") -> int:
    if not os.path.exists(csv_path):
        alt_path = os.path.join("..", "..", csv_path)
        if os.path.exists(alt_path):
            csv_path = alt_path
        else:
            logger.error(f"[DB]: Файл {csv_path} не найден.")
            return 1

    df = pd.read_csv(csv_path)
    logger.info(f"[DB]: Обработка {len(df)} записей из {csv_path}...")

    text_col = [c for c in df.columns if c.lower() in ["text", "title", "event", "описание", "событие"]][0]
    dt_col = [c for c in df.columns if c.lower() in ["date", "datetime", "scheduled_at", "время", "дата"]][0]

    current_date = datetime.now().date()
    records = []

    for _, row in df.iterrows():
        raw_text = str(row[text_col]).strip()
        if not raw_text:
            continue

        start_dt = pd.to_datetime(row[dt_col])
        end_dt = pd.to_datetime(row.get("end_time", start_dt))

        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt

        event_type = classify_event(raw_text)
        lemmatized = lemmatize_text(raw_text)
        status = "completed" if start_dt.date() < current_date else "pending"

        records.append((
            raw_text,
            lemmatized,
            event_type,
            status,
            start_dt,
            end_dt,
        ))

    query = """
        INSERT INTO events (original_text, lemmatized_text, event_type, status, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
    """

    conn = psycopg2.connect(**get_db_config())
    try:
        with conn.cursor() as cur:
            cur.executemany(query, records)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("[DB]: Ошибка загрузки событий из CSV")
        raise
    finally:
        conn.close()

    logger.info(f"[DB]: Успешно загружено записей: {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(run_etl() or 0)
