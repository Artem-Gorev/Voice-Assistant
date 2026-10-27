import re
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import pymorphy3

CSV_PATH = "data/voice_assistant_events_1000.csv"

DB_CONFIG = {
    "dbname": "assistant_db",
    "user": "postgres",
    "password": "postgres_password",
    "host": "localhost",
    "port": 5432
}

morph = pymorphy3.MorphAnalyzer()

def lemmatize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    words = re.findall(r'[а-яА-Яa-zA-Z0-9]+', text.lower())
    return " ".join([morph.parse(w)[0].normal_form for w in words])

def classify_event(text: str) -> str:
    lower = text.lower()
    meeting_triggers = ["встреч", "созвон", "демо", "обсудить", "планёрк", "планерк", "синхрон", "интервью", "митинг"]
    if any(t in lower for t in meeting_triggers):
        return "meeting"
    if lower.startswith("напомн") or " напомн" in lower:
        return "reminder"
    return "task"

def run_etl():
    print("[ETL] Чтение исходного CSV...")
    df = pd.read_csv(CSV_PATH)
    
    text_col = [c for c in df.columns if c.lower() in ['text', 'title', 'event', 'описание', 'событие']][0]
    dt_col = [c for c in df.columns if c.lower() in ['date', 'datetime', 'scheduled_at', 'время', 'дата']][0]

    # Ориентир текущей даты для классификации выполненных задач
    current_date = datetime.now().date()

    records = []
    print(f"[ETL] Обработка {len(df)} записей...")
    for _, row in df.iterrows():
        raw_text = str(row[text_col]).strip()
        raw_dt = str(row[dt_col]).strip()
        
        try:
            dt_obj = pd.to_datetime(raw_dt)
            e_date = dt_obj.date()
            e_time = dt_obj.time()
        except Exception:
            e_date, e_time = None, None
            
        event_type = classify_event(raw_text)
        normalized = lemmatize_text(raw_text)
        status = "completed" if (e_date and e_date < current_date) else "pending"
        
        records.append((event_type, raw_text, normalized, e_date, e_time, status))

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Защита от дублей при повторных запусках
    print("[ETL] Очистка старых данных (TRUNCATE)...")
    cur.execute("TRUNCATE TABLE events RESTART IDENTITY;")
    
    insert_query = """
        INSERT INTO events (event_type, title, normalized_text, event_date, event_time, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    execute_batch(cur, insert_query, records, page_size=200)
    conn.commit()
    cur.close()
    conn.close()
    print(f"[ETL] Успешно загружено записей: {len(records)}")

if __name__ == "__main__":
    run_etl()
