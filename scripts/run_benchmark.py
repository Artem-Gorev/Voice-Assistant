import argparse
import csv
import json
import logging
import re
import statistics
import time
from collections import Counter
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

from backend.ai_service.llm import LLMConfig, LLMOrchestrator
from backend.ai_service.ttv import RuBertTiny2Config, TextVectorizer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "data" / "eval_cases.json"
DEFAULT_EVENTS = ROOT / "data" / "cleaned_events_1000.csv"
FALLBACK_EVENTS = ROOT / "data" / "voice_assistant_events_1000.csv"
DEFAULT_REPORT = ROOT / "docs" / "benchmark_report.md"
LABELS = ("create_event", "update_event", "delete_event", "complete_event", "search_events", "list_events")
logger = logging.getLogger("benchmark")


def percentile(values: list[float], number: int) -> float:
    return float(np.percentile(values, number)) if values else 0.0


def weekday_index(name: str) -> int:
    names = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
    for index, full_name in enumerate(names):
        if full_name.startswith(name.casefold()):
            return index
    raise ValueError(f"Неизвестный день недели: {name}")


def expected_value(value: str, reference: datetime) -> str | tuple[str, str]:
    if value.startswith("relative:"):
        days = {"today": 0, "tomorrow": 1, "day_after_tomorrow": 2}[value.split(":", 1)[1]]
        return (reference.date() + timedelta(days=days)).isoformat()
    if value.startswith("weekday:"):
        name = value.split(":", 1)[1]
        is_next = name.startswith("следующ")
        if is_next:
            name = name.split("_", 1)[1]
        index = weekday_index(name)
        ahead = (index - reference.weekday()) % 7
        if is_next and ahead == 0:
            ahead = 7
        return (reference.date() + timedelta(days=ahead)).isoformat()
    if value == "range:this_week":
        start = reference.date() - timedelta(days=reference.weekday())
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if value == "range:next_week":
        start = reference.date() - timedelta(days=reference.weekday()) + timedelta(days=7)
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    return value


def predicted_date(data: dict[str, Any]) -> str | None:
    start = data.get("start_time")
    if start:
        try:
            return datetime.fromisoformat(str(start)).date().isoformat()
        except ValueError:
            pass
    for field in ("date", "new_date", "target_date", "scheduled_date"):
        if data.get(field):
            return str(data[field])[:10]
    return None


def predicted_time(data: dict[str, Any]) -> str | None:
    start = data.get("start_time")
    if start:
        try:
            return datetime.fromisoformat(str(start)).strftime("%H:%M")
        except ValueError:
            pass
    for field in ("time", "new_time", "target_time", "scheduled_time"):
        if data.get(field):
            try:
                return clock_time.fromisoformat(str(data[field])).strftime("%H:%M")
            except ValueError:
                return str(data[field])[:5]
    return None


def title_tokens(data: dict[str, Any]) -> set[str]:
    value = data.get("title") or data.get("new_title") or ""
    return set(re.findall(r"[а-яёa-z0-9]+", str(value).casefold()))


def macro_f1(expected: list[str], predicted: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(a == label and b == label for a, b in zip(expected, predicted))
        fp = sum(a != label and b == label for a, b in zip(expected, predicted))
        fn = sum(a == label and b != label for a, b in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return statistics.mean(scores)


def score_slots(results: list[tuple[dict[str, Any], dict[str, Any]]], reference: datetime) -> dict[str, Any]:
    tp = fp = fn = exact = checked = 0
    for case, data in results:
        slots = case.get("expected_slots", {})
        got_title = title_tokens(data)
        wanted = set(slots.get("title_keywords", []))
        if wanted:
            matched = bool(got_title) and wanted <= got_title
            tp += int(matched)
            fp += int(bool(got_title) and not matched)
            fn += int(not matched)
            checked += 1
            exact += matched
        if slots.get("title"):
            wanted_title = set(re.findall(r"[а-яёa-z0-9]+", slots["title"].casefold()))
            matched = got_title == wanted_title
            tp += int(matched)
            fp += int(bool(got_title) and not matched)
            fn += int(not matched)
            checked += 1
            exact += matched
        if slots.get("date"):
            expected = expected_value(slots["date"], reference)
            if isinstance(expected, tuple):
                matched = (data.get("date_from"), data.get("date_to")) == expected
                has_value = bool(data.get("date_from") or data.get("date_to"))
            else:
                matched = predicted_date(data) == expected
                has_value = predicted_date(data) is not None
            tp += int(matched)
            fp += int(has_value and not matched)
            fn += int(not matched)
            checked += 1
            exact += matched
        if slots.get("time"):
            got = predicted_time(data)
            matched = got == slots["time"]
            tp += int(matched)
            fp += int(got is not None and not matched)
            fn += int(not matched)
            checked += 1
            exact += matched
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "exact": exact,
        "checked": checked,
    }


def run_nlu(cases: list[dict[str, Any]], reference: datetime, live: bool) -> dict[str, Any]:
    config = LLMConfig.from_env() if live else LLMConfig(mock_mode=True)
    if live and not config.credentials:
        raise RuntimeError("Для --live задайте GIGACHAT_CREDENTIALS")
    orchestrator = LLMOrchestrator(config=config, logger=logger)
    if live and orchestrator._client is None:
        raise RuntimeError("GigaChat не инициализирован; проверьте credentials и настройки сети")
    expected: list[str] = []
    predicted: list[str] = []
    latencies: list[float] = []
    slot_results = []
    counts: Counter[str] = Counter()
    correct: Counter[str] = Counter()

    class FormatFallbackCapture(logging.Handler):
        count = 0

        def emit(self, record: logging.LogRecord) -> None:
            if "Ответ не был JSON" in record.getMessage():
                self.count += 1

    fallback_capture = FormatFallbackCapture()
    logger.addHandler(fallback_capture)
    try:
        for case in cases:
            sid = f"benchmark-{case['id']}"
            orchestrator.sessions.delete(sid)
            for turn in case.get("history", []):
                orchestrator.process(turn, session_id=sid, current_dt=reference)
            started = time.perf_counter()
            result = orchestrator.process(case["phrase"], session_id=sid, current_dt=reference)
            latencies.append((time.perf_counter() - started) * 1000)
            expected.append(case["expected_action"])
            predicted.append(result.action)
            result_expected = case["expected_action"]
            counts[result_expected] += 1
            correct[result_expected] += result.action == result_expected
            slot_results.append((case, result.data))
    finally:
        logger.removeHandler(fallback_capture)
    total_correct = sum(a == b for a, b in zip(expected, predicted))
    return {
        "mode": "GigaChat live" if live else "NLU simulator (mock)",
        "count": len(cases),
        "accuracy": total_correct / len(cases),
        "macro_f1": macro_f1(expected, predicted),
        "format_fallbacks": fallback_capture.count,
        "latencies": latencies,
        "slots": score_slots(slot_results, reference),
        "by_action": {
            action: (correct[action], counts[action])
            for action in LABELS if counts[action]
        },
        "errors": [
            (case["id"], case["expected_action"], actual)
            for case, actual in zip(cases, predicted) if case["expected_action"] != actual
        ],
    }


def read_events(path: Path) -> list[str]:
    if not path.is_file() and path == DEFAULT_EVENTS and FALLBACK_EVENTS.is_file():
        path = FALLBACK_EVENTS
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"В CSV отсутствуют заголовки: {path}")
        text_field = next((key for key in ("original_text", "text", "title", "event") if key in reader.fieldnames), None)
        if not text_field:
            raise ValueError(f"В {path} нет колонки original_text/text/title/event")
        events = [row[text_field].strip() for row in reader if row.get(text_field, "").strip()]
    if not events:
        raise ValueError(f"В CSV нет названий событий: {path}")
    return events


def run_search(cases: list[dict[str, Any]], events_csv: Path) -> dict[str, Any]:
    cases = [case for case in cases if case.get("target_title")]
    if not cases:
        return {"count": 0, "r1": 0.0, "r3": 0.0, "mrr": 0.0, "latencies": [], "events": 0}
    events = read_events(events_csv)
    vectorizer = TextVectorizer.create("rubert_tiny2", config=RuBertTiny2Config(), logger=logger)
    warmup_start = time.perf_counter()
    matrix = vectorizer.encode(events).vectors
    warmup = time.perf_counter() - warmup_start
    hits1 = hits3 = 0
    reciprocal: list[float] = []
    latencies: list[float] = []
    misses = []
    for case in cases:
        target = case["target_title"].casefold().strip()
        targets = {i for i, title in enumerate(events) if title.casefold().strip() == target}
        if not targets:
            raise ValueError(f"Эталонный заголовок отсутствует в CSV: {case['target_title']}")
        started = time.perf_counter()
        query = vectorizer.encode(case["phrase"]).vector
        denominator = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
        scores = np.divide(matrix @ query, denominator, out=np.zeros(len(events), dtype=np.float32), where=denominator != 0)
        top = np.argsort(-scores)[:3]
        latencies.append((time.perf_counter() - started) * 1000)
        rank = next((position + 1 for position, event_index in enumerate(top) if int(event_index) in targets), None)
        if rank:
            reciprocal.append(1 / rank)
            hits1 += rank == 1
            hits3 += 1
        else:
            reciprocal.append(0.0)
            misses.append((case["id"], case["target_title"]))
    count = len(cases)
    return {
        "count": count,
        "events": len(events),
        "r1": hits1 / count,
        "r3": hits3 / count,
        "mrr": statistics.mean(reciprocal),
        "latencies": latencies,
        "warmup": warmup,
        "misses": misses,
    }


def latency_row(name: str, values: list[float]) -> str:
    if not values:
        return f"| {name} | 0 | — | — |"
    return f"| {name} | {len(values)} | {percentile(values, 50):.3f} ms | {percentile(values, 95):.3f} ms |"


def render_report(nlu: dict[str, Any], search: dict[str, Any] | None, csv_path: Path, reference: datetime) -> str:
    slots = nlu["slots"]
    output = [
        "# Отчёт о качестве Voice Assistant",
        "",
        f"**Срез:** NLU · **Модель:** {nlu['mode']} · **Запуск:** {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"**Набор:** {nlu['count']} фраз · **Опорное время:** {reference.isoformat(timespec='minutes')}",
        "",
        "## Ключевые метрики",
        "",
        "| Метрика | Результат |",
        "|---|---:|",
        f"| Intent Accuracy | {nlu['accuracy']:.1%} |",
        f"| Intent Macro-F1 (6 действий) | {nlu['macro_f1']:.3f} |",
        f"| Slot Exact Accuracy | {slots['exact'] / slots['checked']:.1%} ({slots['exact']}/{slots['checked']} слотов) |" if slots["checked"] else "| Slot Exact Accuracy | — |",
        f"| Slot Precision / Recall / F1 | {slots['precision']:.3f} / {slots['recall']:.3f} / {slots['f1']:.3f} |",
        f"| p50 / p95 задержки | {percentile(nlu['latencies'], 50):.1f} / {percentile(nlu['latencies'], 95):.1f} мс |",
        f"| Ответы без JSON (fallback) | {nlu['format_fallbacks']} |",
        "",
        "## Результаты по интентам",
        "",
        "| Интент | Верно | Всего | Accuracy |",
        "|---|---:|---:|---:|",
    ]
    for action, (ok, count) in nlu["by_action"].items():
        output.append(f"| {action} | {ok} | {count} | {ok / count:.1%} |")
    if search is not None:
        source = str(csv_path.relative_to(ROOT)) if csv_path.is_relative_to(ROOT) else str(csv_path)
        output += [
            "",
            "## Семантический поиск",
            "",
            f"Набор: {source} ({search['events']} событий).",
            f"Recall@1: {search['r1']:.1%} · Recall@3: {search['r3']:.1%} · MRR: {search['mrr']:.3f}.",
            f"Время векторизации корпуса: {search['warmup']:.2f} с; query p50/p95: {percentile(search['latencies'], 50):.1f}/{percentile(search['latencies'], 95):.1f} мс.",
        ]
    else:
        output += [
            "",
            "## Семантический поиск",
            "",
            "Не оценивался в этом запуске (--nlu-only). Метрики поиска в этом отчёте отсутствуют.",
        ]
    if nlu["errors"]:
        output += ["", "## Кейсы с несовпадением интента", "", "| Case ID | Ожидалось | Получено |", "|---|---|---|"]
        output.extend(f"| {case_id} | {expected} | {actual} |" for case_id, expected, actual in nlu["errors"])
    if search and search.get("misses"):
        output += ["", "## Пропуски поиска", "", "| Case ID | Эталонное событие |", "|---|---|"]
        output.extend(f"| {case_id} | {title} |" for case_id, title in search["misses"])
    output += [
        "",
        "## Методика",
        "",
        f"NLU измерялся через LLMOrchestrator на {nlu['count']} размеченных репликах из data/eval_cases.json. Дата для относительных выражений фиксирована на {reference.date().isoformat()}; задержка включает запрос к модели и локальную обработку.",
        "Intent Accuracy — доля точных совпадений действия; Macro-F1 — невзвешенное среднее F1 по шести интентам. Slot Exact Accuracy считает каждое размеченное поле; Slot F1 оценивает ключевые слова названия и точное совпадение даты и времени.",
        "Ограничение: этот запуск оценивает только NLU. Он не измеряет качество STT, TTS, полного API/UI-пути или семантического поиска. Для поиска запустите бенчмарк без --nlu-only.",
        "",
    ]
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="NLU and semantic-search benchmark")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", help="использовать локальный NLU-симулятор (по умолчанию)")
    mode.add_argument("--live", action="store_true", help="вызывать настроенный GigaChat")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--events-csv", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--nlu-only", action="store_true", help="пропустить векторизацию корпуса и поиск")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date.today(), help="база относительных дат YYYY-MM-DD")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.WARNING, format="[ %(levelname)s ] %(message)s")
    try:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        if not isinstance(cases, list) or not cases:
            raise ValueError("JSON cases должен быть непустым массивом")
        reference = datetime.combine(args.reference_date, clock_time(9, 0))
        nlu = run_nlu(cases, reference, args.live)
        search = None if args.nlu_only else run_search(cases, args.events_csv.expanduser().resolve())
        report = render_report(nlu, search, args.events_csv.expanduser().resolve(), reference)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(report)
        print(f"\nОтчёт сохранён: {args.report}")
    except Exception as error:
        logger.exception("Бенчмарк не завершён")
        print(f"Ошибка бенчмарка: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
