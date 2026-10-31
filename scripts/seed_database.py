import argparse
import csv
import logging
import os
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import psycopg2

from backend.ai_service.ttv import RuBertTiny2Config, TextVectorizer
from backend.database.config import get_db_config
from backend.dal.nlp_utils import classify_event, lemmatize_text

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT_DIR / "data" / "cleaned_events_1000.csv"
FALLBACK_CSV = ROOT_DIR / "data" / "voice_assistant_events_1000.csv"
logger = logging.getLogger("seed_database")


def _connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(**get_db_config())


def _parse_event_date(row: dict[str, str], line_number: int) -> datetime:
    normalized = {str(key).strip().lstrip("\ufeff").casefold(): value for key, value in row.items()}
    raw_datetime = next(
        (normalized[key] for key in ("datetime", "scheduled_at", "start_time") if normalized.get(key)),
        None,
    )
    if raw_datetime:
        try:
            return datetime.fromisoformat(raw_datetime.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Строка {line_number}: некорректная дата/время {raw_datetime!r}") from exc

    raw_date = next((normalized[key] for key in ("date", "дата") if normalized.get(key)), None)
    raw_time = next((normalized[key] for key in ("time", "время") if normalized.get(key)), "00:00")
    if not raw_date:
        raise ValueError(f"Строка {line_number}: нет колонки date/datetime")
    try:
        return datetime.combine(date.fromisoformat(raw_date.strip()), time.fromisoformat(raw_time.strip()))
    except ValueError as exc:
        raise ValueError(f"Строка {line_number}: некорректная дата или время") from exc


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _read_events(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.is_file():
        if csv_path == DEFAULT_CSV and FALLBACK_CSV.is_file():
            csv_path = FALLBACK_CSV
        else:
            raise FileNotFoundError(f"CSV не найден: {csv_path}")

    events: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("CSV пустой или не содержит заголовка")
        headers = {header.strip().lstrip("\ufeff").casefold() for header in reader.fieldnames}
        text_column = next((name for name in ("original_text", "text", "title", "event", "описание", "событие") if name in headers), None)
        if text_column is None:
            raise ValueError("В CSV должна быть колонка text/title/event")

        for line_number, row in enumerate(reader, start=2):
            normalized = {str(key).strip().lstrip("\ufeff").casefold(): value for key, value in row.items()}
            text = (normalized.get(text_column) or "").strip()
            if not text:
                continue
            start = _parse_event_date(row, line_number)
            end_raw = normalized.get("end_time")
            try:
                if not end_raw:
                    end = start
                else:
                    try:
                        end = datetime.fromisoformat(end_raw.strip().replace("Z", "+00:00"))
                    except ValueError:
                        end = datetime.combine(start.date(), time.fromisoformat(end_raw.strip()))
            except ValueError as exc:
                raise ValueError(f"Строка {line_number}: некорректное end_time {end_raw!r}") from exc
            start, end = _as_utc(start), _as_utc(end)
            if end < start:
                start, end = end, start

            lemmatized = normalized.get("lemmatized_text") or lemmatize_text(text)
            event_type = normalized.get("event_type") or classify_event(text)
            status = normalized.get("status") or ("completed" if start.date() < date.today() else "pending")

            events.append({
                "text": text,
                "lemmatized_text": lemmatized,
                "event_type": event_type,
                "status": status,
                "start_time": start,
                "end_time": end,
            })

    if not events:
        raise ValueError("В CSV не найдено ни одной записи с текстом события")
    return events


def seed_database(csv_path: Path = DEFAULT_CSV, *, confirm_clear: bool = False) -> int:
    if not confirm_clear:
        raise ValueError("Очистка events отключена. Для подтверждения передайте --confirm-clear.")

    events = _read_events(Path(csv_path).expanduser().resolve())
    logger.info("Прочитано событий: %d; вычисляю эмбеддинги RuBERT…", len(events))
    vectorizer = TextVectorizer.create("rubert_tiny2", config=RuBertTiny2Config(), logger=logger)
    vectors = vectorizer.encode([event["text"] for event in events]).vectors
    if len(vectors) != len(events):
        raise RuntimeError("Модель вернула неожиданное число эмбеддингов")

    insert_sql = """
        INSERT INTO events
            (original_text, lemmatized_text, event_type, status, start_time, end_time, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
    """
    values = []
    for event, embedding in zip(events, vectors, strict=True):
        vector_literal = "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"
        values.append((
            event["text"], event["lemmatized_text"], event["event_type"], event["status"],
            event["start_time"], event["end_time"], vector_literal,
        ))

    connection = _connection()
    try:
        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE events RESTART IDENTITY")
            cursor.executemany(insert_sql, values)
        connection.commit()
    except Exception:
        connection.rollback()
        logger.exception("Не удалось заменить данные событий; транзакция отменена")
        raise
    finally:
        connection.close()

    logger.info("Готово: загружено %d событий с эмбеддингами", len(values))
    return len(values)


def main() -> int:
    parser = argparse.ArgumentParser(description="Очистить таблицу events и загрузить CSV с векторами RuBERT.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help=f"CSV для загрузки (по умолчанию: {DEFAULT_CSV})")
    parser.add_argument("--confirm-clear", action="store_true", help="подтвердить очистку текущей таблицы events перед загрузкой")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[ %(levelname)s ] %(message)s")
    try:
        seed_database(args.csv, confirm_clear=args.confirm_clear)
    except Exception as exc:
        logger.error("Загрузка не выполнена: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
