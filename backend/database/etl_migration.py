import os
import re
import sys
import logging
from datetime import datetime
import pandas as pd
import psycopg2
import pymorphy3

logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
logger = logging.getLogger("ETL")

MEETING_TRIGGERS = (
    "встреч",
    "созвон",
    "демо",
    "обсудить",
    "планёрк",
    "планерк",
    "синхрон",
    "интервью",
    "митинг",
)

DB_CONFIG = {
    "dbname": os.getenv("POSTGRES_DB", "assistant_db"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres_password"),
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5433"),
}

morph = pymorphy3.MorphAnalyzer()


def lemmatize_text(text: str) -> str:
    words = re.findall(r"[а-яА-Яa-zA-Z0-9]+", text.lower())
    return " ".join([morph.parse(w)[0].normal_form for w in words])


def classify_event(text: str) -> str:
    lower = text.lower()
    if any(trigger in lower for trigger in MEETING_TRIGGERS):
        return "meeting"
    return "task"


def run_etl(csv_path: str = "data/voice_assistant_events_1000_77e927b5d2.csv") -> int:
    if not os.path.exists(csv_path):
        alt_path = os.path.join("..", "..", csv_path)
        if os.path.exists(alt_path):
            csv_path = alt_path
        else:
            logger.error(f"Файл {csv_path} не найден.")
            return 1

    df = pd.read_csv(csv_path)
    logger.info(f"Обработка {len(df)} записей из {csv_path}...")

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

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    query = """
        INSERT INTO events (original_text, lemmatized_text, event_type, status, start_time, end_time)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
    """

    cur.executemany(query, records)
    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Успешно загружено записей: {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(run_etl() or 0)
