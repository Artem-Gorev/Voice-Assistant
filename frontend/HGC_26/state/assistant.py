"""Reflex state and user actions."""

import calendar
from datetime import datetime
from uuid import uuid4

import httpx
import reflex as rx

from ..services.assistant_api import get_events, send_message
from ..services.browser_media import (
    speak_text_script,
    start_recording_script,
    stop_recording_script,
)


class AssistantState(rx.State):
    messages: list[dict] = [
        {"role": "ai", "text": "Привет! Я твой голосовой ассистент. Чем могу помочь?"}
    ]
    events: list[dict] = []
    api_error: str = ""
    is_sending: bool = False
    is_recording: bool = False
    is_transcribing: bool = False
    recording_starting: bool = False
    speak_replies: bool = False
    processing_status: str = ""
    theme_preference: str = rx.LocalStorage("dark", name="assistant-theme")
    user_input: str = ""
    input_key: int = 0
    selected_day: str = ""
    current_month: int = datetime.now().month
    current_year: int = datetime.now().year
    today: str = str(datetime.now().day)
    request_id: str = uuid4().hex

    @rx.var
    def month_name(self) -> str:
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        return months[self.current_month - 1]

    @rx.var
    def is_light_theme(self) -> bool:
        return self.theme_preference == "light"

    @rx.var
    def month_name_genitive(self) -> str:
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return months[self.current_month - 1]

    @rx.var
    def calendar_days(self) -> list[str]:
        return [str(day) if day else "" for week in calendar.monthcalendar(self.current_year, self.current_month) for day in week]

    def prev_month(self):
        if self.current_month == 1:
            self.current_month, self.current_year = 12, self.current_year - 1
        else:
            self.current_month -= 1
        self.selected_day = ""
        self.events = []

    def next_month(self):
        if self.current_month == 12:
            self.current_month, self.current_year = 1, self.current_year + 1
        else:
            self.current_month += 1
        self.selected_day = ""
        self.events = []

    async def select_day(self, day: str):
        if day:
            self.selected_day = day
            await self.load_events(day)

    async def load_events(self, day: str):
        event_date = f"{self.current_year:04d}-{self.current_month:02d}-{int(day):02d}"
        try:
            self.events = await get_events(event_date)
            self.api_error = ""
        except (httpx.HTTPError, ValueError):
            self.events = []
            self.api_error = "Не удалось загрузить события. Проверьте, запущен ли backend."

    def set_user_input(self, value: str):
        self.user_input = value

    def toggle_speech(self):
        self.speak_replies = not self.speak_replies
        if not self.speak_replies:
            return rx.call_script(
                "window.__assistantSpeechAudio?.pause(); "
                "window.__assistantSpeechAudio = null; "
                "window.speechSynthesis?.cancel();"
            )

    def toggle_theme(self):
        self.theme_preference = "dark" if self.theme_preference == "light" else "light"

    def toggle_recording(self):
        self.api_error = ""
        if self.is_recording:
            self.is_recording = False
            self.is_transcribing = True
            self.processing_status = "Распознаю голосовое сообщение…"
            return rx.call_script(
                stop_recording_script(), callback=AssistantState.on_voice_transcription
            )
        if self.recording_starting or self.is_transcribing:
            return
        self.recording_starting = True
        self.processing_status = "Подключаю микрофон…"
        return rx.call_script(
            start_recording_script(), callback=AssistantState.on_recording_started
        )

    def on_recording_started(self, result: str):
        self.recording_starting = False
        if result == "recording":
            self.is_recording = True
            self.processing_status = "Идёт запись — нажмите кнопку ещё раз, чтобы отправить"
            return
        self.processing_status = ""
        self.api_error = (result or "").removeprefix("ERROR: ") or "Не удалось включить микрофон."

    def on_voice_transcription(self, result: str):
        self.is_transcribing = False
        self.processing_status = ""
        text = (result or "").strip()
        if text.startswith("ERROR:"):
            self.api_error = text.removeprefix("ERROR:").strip()
            return
        if not text:
            self.api_error = "Не удалось распознать речь. Попробуйте записать сообщение ещё раз."
            return
        return self._queue_message(text, uuid4().hex)

    def send_message(self, form_data: dict):
        message = (form_data.get("message") or self.user_input).strip()
        if not message:
            return

        request_id = str(form_data.get("request_id") or "")
        # A repeated browser submit carries the old hidden key after the first event advances it.
        if request_id and request_id != self.request_id:
            return
        if self.is_sending:
            return

        request_id = self.request_id
        self.request_id = uuid4().hex
        return self._queue_message(message, request_id)

    def _queue_message(self, message: str, request_id: str):
        self.messages = self.messages + [{"role": "user", "text": message}]
        self.user_input = ""
        self.input_key += 1
        self.api_error = ""
        self.is_sending = True
        self.processing_status = "Обрабатываю запрос…"
        session_id = self.router.session.client_token
        return AssistantState.process_message(message, session_id, request_id)

    async def process_message(self, message: str, session_id: str, request_id: str):
        should_speak = False
        reply = ""
        try:
            reply = await send_message(message, session_id, request_id)
            self.messages = self.messages + [{"role": "ai", "text": reply}]
            should_speak = self.speak_replies
        except (httpx.HTTPError, KeyError, ValueError):
            self.api_error = "Не удалось связаться с backend. Проверьте, что API запущен на порту 8000."
            self.messages = self.messages + [{"role": "ai", "text": self.api_error}]
        finally:
            self.is_sending = False
            self.processing_status = ""
        if should_speak:
            return rx.call_script(speak_text_script(reply))
