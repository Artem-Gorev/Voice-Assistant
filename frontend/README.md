# Frontend

Reflex-приложение голосового ассистента.

## Структура

- `app.py` — точка входа Reflex и регистрация страницы.
- `rxconfig.py` — конфигурация Reflex.
- `frontend_core/state.py` — состояние интерфейса и обработчики событий.
- `frontend_core/components/` — компоненты чата и календаря.
- `frontend_core/assistant_service.py` — загрузка моделей, запросы к ассистенту и TTS.
- `frontend_core/audio_api.py` — обработка потоковой записи с микрофона.

## Запуск

Из корня репозитория установите зависимости и запустите базу:

```bash
python -m pip install -r requirements.txt

docker compose up -d postgres redis
cd frontend
reflex run
```

Для ответов GigaChat укажите `GIGACHAT_CREDENTIALS` в `.env`. При запуске
страницы Reflex загружает модели ассистента. Календарь читает события из
PostgreSQL.
