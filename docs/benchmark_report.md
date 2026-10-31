# Отчёт о качестве Voice Assistant

**Срез:** NLU · **Модель:** NLU simulator (mock) · **Запуск:** 2026-10-31T18:49:18+03:00
**Набор:** 110 фраз · **Опорное время:** 2026-10-31T09:00

## Ключевые метрики

| Метрика | Результат |
|---|---:|
| Intent Accuracy | 90.9% |
| Intent Macro-F1 (6 действий) | 0.955 |
| Slot Exact Accuracy | 78.2% (104/133 слотов) |
| Slot Precision / Recall / F1 | 0.846 / 0.782 / 0.812 |
| p50 / p95 задержки | 0.0 / 0.6 мс |
| Ответы без JSON (fallback) | 0 |

## Результаты по интентам

| Интент | Верно | Всего | Accuracy |
|---|---:|---:|---:|
| create_event | 28 | 30 | 93.3% |
| update_event | 15 | 15 | 100.0% |
| delete_event | 13 | 13 | 100.0% |
| complete_event | 11 | 12 | 91.7% |
| search_events | 17 | 20 | 85.0% |
| list_events | 16 | 20 | 80.0% |

## Семантический поиск

Набор: data/cleaned_events_1000.csv (1000 событий).
Recall@1: 75.0% · Recall@3: 85.0% · MRR: 0.792.
Время векторизации корпуса: 13.06 с; query p50/p95: 7.2/1334.8 мс.

## Кейсы с несовпадением интента

| Case ID | Ожидалось | Получено |
|---|---|---|
| list_05 | list_events | chat |
| list_09 | list_events | clarify |
| list_11 | list_events | chat |
| list_18 | list_events | clarify |
| search_07 | search_events | chat |
| search_13 | search_events | chat |
| search_18 | search_events | chat |
| complete_08 | complete_event | chat |
| context_03 | create_event | chat |
| context_04 | create_event | chat |

## Пропуски поиска

| Case ID | Эталонное событие |
|---|---|
| search_01 | Отправить договор Иваном |
| search_03 | Проверить техническое задание по договору |
| search_14 | Подготовить отчёт |

## Методика

NLU измерялся через LLMOrchestrator на 110 размеченных репликах из data/eval_cases.json. Дата для относительных выражений фиксирована на 2026-10-31; задержка включает запрос к модели и локальную обработку.
Intent Accuracy — доля точных совпадений действия; Macro-F1 — невзвешенное среднее F1 по шести интентам. Slot Exact Accuracy считает каждое размеченное поле; Slot F1 оценивает ключевые слова названия и точное совпадение даты и времени.
Ограничение: этот запуск оценивает только NLU. Он не измеряет качество STT, TTS, полного API/UI-пути или семантического поиска. Для поиска запустите бенчмарк без --nlu-only.
