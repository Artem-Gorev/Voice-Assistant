import calendar
from datetime import datetime, date, timedelta
import reflex as rx
from typing import Any
import base64
import os
import uuid
from pathlib import Path
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse

# Глобальные стили для скроллбара
style = {
    "::-webkit-scrollbar": {"width": "0px", "height": "0px", "display": "none"},
    "@keyframes pulse": {
        "0%": {"boxShadow": "0 0 0 0 rgba(255, 77, 77, 0.55)"},
        "70%": {"boxShadow": "0 0 0 8px rgba(255, 77, 77, 0)"},
        "100%": {"boxShadow": "0 0 0 0 rgba(255, 77, 77, 0)"},
    },
}

# --- 1. ПАЛИТРА ЦВЕТОВ ---
COLORS = {
    "bg_gradient": "linear-gradient(135deg, #3a2e26 0%, #2a211b 50%, #1c1612 100%)",
    "panel_bg": "rgba(20, 15, 12, 0.6)",
    "panel_border": "rgba(232, 216, 195, 0.1)",
    "text_main": "#e8d8c3",
    "text_accent": "#c4a787",
    "text_muted": "#7a6656",
    "item_bg": "rgba(60, 45, 35, 0.5)",
    "item_border": "#a88462",
    "user_msg_bg": "rgba(140, 95, 65, 0.85)",
    "ai_msg_bg": "rgba(35, 26, 20, 0.9)",
    "input_bg": "rgba(20, 15, 12, 0.8)",
    "input_border": "rgba(168, 132, 98, 0.4)",
    "btn_send_bg": "#a88462",
    "modal_content": "rgba(35, 26, 20, 0.95)",
}

# --- 2. СОСТОЯНИЕ ---
class State(rx.State):
    messages: list[dict] = [
        {"role": "ai", "text": "Привет! Я твой голосовой ассистент. Чем могу помочь?"},
        {"role": "user", "text": "Напомни мне завтра в 10 утра позвонить Ивану."},
        {"role": "ai", "text": "Готово! Я создал напоминание на завтра, 10:00 — «Позвонить Ивану»."},
    ]
    
    user_input: str = ""
    input_key: int = 0
    selected_day: str = ""
    is_recording: bool = False
    
    current_month: int = datetime.now().month
    current_year: int = datetime.now().year
    # Отдельное состояние месяца для календаря в модальном окне
    modal_month: int = datetime.now().month
    modal_year: int = datetime.now().year
    today: str = str(datetime.now().day)

    @rx.var
    def month_name(self) -> str:
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        return months[self.current_month - 1]

    @rx.var
    def month_name_genitive(self) -> str:
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return months[self.current_month - 1]

    @rx.var
    def calendar_days(self) -> list[str]:
        cal = calendar.monthcalendar(self.current_year, self.current_month)
        days = []
        for week in cal:
            for day in week:
                if day == 0:
                    days.append("")
                else:
                    days.append(str(day))
        return days

    @rx.var
    def modal_month_name(self) -> str:
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        return months[self.modal_month - 1]

    @rx.var
    def modal_month_name_genitive(self) -> str:
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return months[self.modal_month - 1]

    @rx.var
    def modal_calendar_days(self) -> list[str]:
        cal = calendar.monthcalendar(self.modal_year, self.modal_month)
        days = []
        for week in cal:
            for day in week:
                days.append("" if day == 0 else str(day))
        return days

    def modal_prev_month(self):
        if self.modal_month == 1:
            self.modal_month = 12
            self.modal_year -= 1
        else:
            self.modal_month -= 1
        self.selected_day = ""

    def modal_next_month(self):
        if self.modal_month == 12:
            self.modal_month = 1
            self.modal_year += 1
        else:
            self.modal_month += 1
        self.selected_day = ""

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.selected_day = ""

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.selected_day = ""

    def select_day(self, day: str):
        if day:
            self.selected_day = day

    def set_user_input(self, val: str):
        self.user_input = val

    def send_message(self):
        if self.user_input.strip():
            self.messages = self.messages + [{"role": "user", "text": self.user_input}]
            self.user_input = ""
            self.input_key += 1
            self.messages = self.messages + [{"role": "ai", "text": "Я пока не умею отвечать, но скоро научусь!"}]


    # --- ПОТОКОВАЯ ЗАПИСЬ: фрагменты отправляются на сервер каждые 5 секунд ---
    def start_recording(self):
        # Не переключаем UI в режим записи, пока браузер не получил микрофон
        # и сервер не создал временный файл.
        return rx.call_script("""
            (async () => {
                if (window.__voiceStarting || window.__voiceRecorder) return false;
                window.__voiceStarting = true;
                try {
                    if (!navigator.mediaDevices?.getUserMedia) {
                        throw new Error("Для доступа к микрофону откройте приложение через HTTPS или localhost.");
                    }
                    if (!window.MediaRecorder) throw new Error("Браузер не поддерживает MediaRecorder.");

                    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
                        ? "audio/webm;codecs=opus"
                        : "audio/webm";
                    const recordingId = crypto.randomUUID();
                    // Reflex frontend runs on :3000; custom ASGI routes are served by backend :8000.
                    const audioApiBase = window.location.protocol + "//" + window.location.hostname + ":8000";
                    window.__voiceAudioApiBase = audioApiBase;
                    const init = await fetch(audioApiBase + "/audio/start/" + recordingId, {method: "POST"});
                    if (!init.ok) {
                        const detail = await init.text().catch(() => "");
                        throw new Error("Сервер не смог начать запись (HTTP " + init.status + "): " + detail);
                    }

                    window.__voiceStream = stream;
                    window.__voiceRecordingId = recordingId;
                    window.__voiceUploadQueue = Promise.resolve();
                    window.__voiceUploadError = null;
                    window.__voiceStartedAt = Date.now();

                    const recorder = new MediaRecorder(stream, {mimeType});
                    window.__voiceRecorder = recorder;
                    recorder.ondataavailable = (event) => {
                        if (!event.data || !event.data.size) return;
                        // Каждый кусочек отправляется отдельно; весь файл не кодируется в Base64.
                        window.__voiceUploadQueue = window.__voiceUploadQueue.then(async () => {
                            if (window.__voiceUploadError) return;
                            const response = await fetch(
                                window.__voiceAudioApiBase + "/audio/chunk/" + recordingId,
                                {method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: event.data}
                            );
                            if (!response.ok) {
                                const detail = await response.text().catch(() => "");
                                throw new Error("Не удалось передать фрагмент аудио (HTTP " + response.status + "): " + detail);
                            }
                        }).catch(error => {
                            window.__voiceUploadError = error.message || String(error);
                            console.error("Audio chunk upload failed:", error);
                        });
                    };

                    // Небольшая визуализация громкости микрофона.
                    window.__voiceAudioContext = new (window.AudioContext || window.webkitAudioContext)();
                    window.__voiceAnalyser = window.__voiceAudioContext.createAnalyser();
                    window.__voiceAnalyser.fftSize = 128;
                    window.__voiceAudioContext.createMediaStreamSource(stream).connect(window.__voiceAnalyser);
                    window.__voiceFrequencyData = new Uint8Array(window.__voiceAnalyser.frequencyBinCount);

                    window.__voiceTimer = setInterval(() => {
                        const seconds = Math.floor((Date.now() - window.__voiceStartedAt) / 1000);
                        const timer = document.getElementById("voice-recording-timer");
                        if (timer) timer.textContent =
                            String(Math.floor(seconds / 60)).padStart(2, "0") + ":" +
                            String(seconds % 60).padStart(2, "0");
                    }, 250);

                    const animateWave = () => {
                        if (!window.__voiceAnalyser) return;
                        window.__voiceAnalyser.getByteFrequencyData(window.__voiceFrequencyData);
                        for (let i = 0; i < 28; i++) {
                            const bar = document.getElementById("voice-wave-" + i);
                            if (!bar) continue;
                            const value = window.__voiceFrequencyData[i % window.__voiceFrequencyData.length] || 0;
                            bar.style.height = (4 + value / 255 * 24) + "px";
                        }
                        window.__voiceAnimationFrame = requestAnimationFrame(animateWave);
                    };
                    animateWave();
                    recorder.start(5000); // отправка аудиофрагментов раз в 5 секунд
                    return true;
                } catch (error) {
                    console.error("Не удалось начать запись:", error);
                    alert("Не удалось начать запись: " + (error.message || error));
                    if (window.__voiceStream) window.__voiceStream.getTracks().forEach(t => t.stop());
                    window.__voiceStream = null;
                    window.__voiceRecorder = null;
                    window.__voiceRecordingId = null;
                    return false;
                } finally {
                    window.__voiceStarting = false;
                }
            })()
        """, callback=State.handle_recording_started)

    def handle_recording_started(self, result: bool):
        self.is_recording = bool(result)

    def cancel_recording(self):
        self.is_recording = False
        return rx.call_script("""
            (async () => {
                const recorder = window.__voiceRecorder;
                const recordingId = window.__voiceRecordingId;
                if (window.__voiceTimer) clearInterval(window.__voiceTimer);
                if (window.__voiceAnimationFrame) cancelAnimationFrame(window.__voiceAnimationFrame);
                if (recorder && recorder.state !== "inactive") {
                    await new Promise(resolve => {
                        recorder.onstop = resolve;
                        recorder.stop();
                    });
                }
                try {
                    await (window.__voiceUploadQueue || Promise.resolve());
                    if (recordingId) await fetch(window.__voiceAudioApiBase + "/audio/cancel/" + recordingId, {method: "DELETE"});
                } finally {
                    if (window.__voiceStream) window.__voiceStream.getTracks().forEach(t => t.stop());
                    if (window.__voiceAudioContext) await window.__voiceAudioContext.close();
                    window.__voiceStream = null;
                    window.__voiceAudioContext = null;
                    window.__voiceAnalyser = null;
                    window.__voiceRecorder = null;
                    window.__voiceRecordingId = null;
                    for (let i = 0; i < 28; i++) {
                        const bar = document.getElementById("voice-wave-" + i);
                        if (bar) bar.style.height = "4px";
                    }
                }
                return true;
            })()
        """)

    def stop_recording(self):
        self.is_recording = False
        return rx.call_script("""
            (async () => {
                const recorder = window.__voiceRecorder;
                const recordingId = window.__voiceRecordingId;
                if (!recorder || !recordingId || recorder.state === "inactive") {
                    window.__voiceStarting = false;
                    throw new Error("Запись ещё не началась или уже завершена. Нажмите на микрофон ещё раз.");
                }
                if (window.__voiceTimer) clearInterval(window.__voiceTimer);
                if (window.__voiceAnimationFrame) cancelAnimationFrame(window.__voiceAnimationFrame);

                if (recorder.state !== "inactive") {
                    await new Promise(resolve => {
                        recorder.onstop = resolve;
                        recorder.stop();
                    });
                }
                await (window.__voiceUploadQueue || Promise.resolve());
                if (window.__voiceUploadError) {
                    throw new Error("Не все фрагменты дошли до сервера: " + window.__voiceUploadError);
                }
                const response = await fetch(window.__voiceAudioApiBase + "/audio/finish/" + recordingId, {method: "POST"});
                if (!response.ok) {
                    const detail = await response.text().catch(() => "");
                    throw new Error("Сервер не смог завершить сохранение аудио (HTTP " + response.status + "): " + detail);
                }

                if (window.__voiceStream) window.__voiceStream.getTracks().forEach(t => t.stop());
                if (window.__voiceAudioContext) await window.__voiceAudioContext.close();
                window.__voiceStream = null;
                window.__voiceAudioContext = null;
                window.__voiceAnalyser = null;
                window.__voiceRecorder = null;
                window.__voiceRecordingId = null;
                const saved = await response.json();
                return "Запись сохранена на сервере: " + saved.path + " (" + saved.bytes + " байт).";
            })()
        """, callback=State.handle_chunked_audio_saved)

    def handle_chunked_audio_saved(self, result: str):
        self.messages = self.messages + [
            {"role": "user", "text": "🎙️ [Голосовое сообщение]"},
            {"role": "ai", "text": result or "Голосовая запись сохранена на сервере."},
        ]

    def set_calendar_mode(self, mode: str):
        self.calendar_mode = mode

    def previous_week(self):
        self.week_offset -= 1

    def next_week(self):
        self.week_offset += 1

    def go_to_current_week(self):
        self.week_offset = 0
        self.calendar_mode = "week"


    @rx.var
    def week_days_data(self) -> list[dict]:
        today = date.today()
        monday = today - timedelta(days=today.weekday()) + timedelta(days=self.week_offset * 7)
        result = []
        names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for i in range(7):
            d = monday + timedelta(days=i)
            result.append({
                "label": names[i],
                "date": d.strftime("%d"),
                "iso": d.isoformat(),
                "is_today": d == today,
                "full": d.strftime("%d.%m.%Y"),
            })
        return result

    @rx.var
    def week_range_label(self) -> str:
        today = date.today()
        monday = today - timedelta(days=today.weekday()) + timedelta(days=self.week_offset * 7)
        sunday = monday + timedelta(days=6)
        return f"{monday:%d.%m} — {sunday:%d.%m.%Y}"

    @rx.var
    def current_time_label(self) -> str:
        now = datetime.now()
        return now.strftime("%H:%M")

    @rx.var
    def current_time_top(self) -> str:
        now = datetime.now()
        minutes = max(0, min(14 * 60, now.hour * 60 + now.minute - 7 * 60))
        return f"{minutes * 0.6}px"

    # Переключение разделов единой панели
    active_view: str = "chat"
    calendar_mode: str = "month"
    week_offset: int = 0
    selected_date_iso: str = date.today().isoformat()

    def show_chat(self):
        self.active_view = "chat"

    def show_calendar(self):
        self.active_view = "calendar"

# --- 3. КОМПОНЕНТЫ ---
def render_message(msg: dict) -> rx.Component:
    is_user = msg["role"] == "user"
    return rx.box(
        rx.text(msg["text"], white_space="pre-wrap", line_height="1.55"),
        background=rx.cond(
            is_user,
            "linear-gradient(145deg, rgba(112,151,239,0.94), rgba(104,128,221,0.92))",
            "light-dark(rgba(255,255,255,0.72), rgba(255,255,255,0.075))",
        ),
        color=rx.cond(is_user, "#ffffff", "light-dark(#34415a, #e9efff)"),
        padding="14px 18px", border_radius="20px",
        border_bottom_right_radius=rx.cond(is_user, "6px", "20px"),
        border_bottom_left_radius=rx.cond(is_user, "20px", "6px"),
        border=rx.cond(is_user, "1px solid rgba(255,255,255,0.22)",
                       "1px solid light-dark(rgba(255,255,255,0.82), rgba(255,255,255,0.12))"),
        max_width="min(78%, 680px)",
        align_self=rx.cond(is_user, "flex-end", "flex-start"),
        box_shadow="0 8px 24px rgba(20,35,65,0.08)",
        style={"backdropFilter": "blur(18px)", "WebkitBackdropFilter": "blur(18px)"},
    )

def glass_card(*children, **kwargs):
    """Reusable translucent VisionOS-like surface."""
    base = {
        "background": "light-dark(rgba(255,255,255,0.58), rgba(30,34,46,0.48))",
        "border": "1px solid light-dark(rgba(255,255,255,0.78), rgba(255,255,255,0.13))",
        "border_radius": "26px",
        "box_shadow": "0 18px 55px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.35)",
        "style": {"backdropFilter": "blur(28px) saturate(155%)", "WebkitBackdropFilter": "blur(28px) saturate(155%)"},
    }
    base.update(kwargs)
    return rx.box(*children, **base)


def nav_button(label: str, icon: str, value: str):
    return rx.button(
        rx.hstack(rx.icon(tag=icon, size=17), rx.text(label, font_size="14px", font_weight="600"),
                  align="center", spacing="2"),
        on_click=State.show_chat if value == "chat" else State.show_calendar,
        background=rx.cond(
            State.active_view == value,
            "light-dark(rgba(255,255,255,0.82), rgba(255,255,255,0.16))",
            "transparent",
        ),
        color="light-dark(#253047, #f2f5ff)",
        border=rx.cond(State.active_view == value,
                       "1px solid light-dark(rgba(255,255,255,0.95), rgba(255,255,255,0.18))",
                       "1px solid transparent"),
        border_radius="16px", padding="10px 16px", cursor="pointer",
        box_shadow=rx.cond(State.active_view == value, "0 4px 18px rgba(0,0,0,0.08)", "none"),
        transition="all 180ms ease",
    )



def calendar_grid(days, selectable=False):
    return rx.grid(
        rx.foreach(
            days,
            lambda day: rx.box(
                rx.text(day, font_size="14px",
                        font_weight=rx.cond(day == State.today, "700", "500")),
                background=rx.cond(
                    day == "", "transparent",
                    rx.cond(
                        (State.current_month == datetime.now().month) &
                        (State.current_year == datetime.now().year) &
                        (day == State.today),
                        "linear-gradient(145deg, #78aefb, #657fe8)",
                        rx.cond(State.selected_day == day,
                                "light-dark(rgba(93,139,226,0.20), rgba(117,158,255,0.22))",
                                "transparent")
                    )
                ),
                color=rx.cond(
                    day == "", "transparent",
                    rx.cond(
                        (State.current_month == datetime.now().month) &
                        (State.current_year == datetime.now().year) &
                        (day == State.today),
                        "#ffffff", "light-dark(#34415a, #e8edff)")
                ),
                border=rx.cond((day != "") & (State.selected_day != "") & (State.selected_day == day),
                               "1px solid light-dark(rgba(83,125,210,0.45), rgba(130,166,255,0.45))",
                               "1px solid transparent"),
                border_radius="15px", display="flex", align_items="center",
                justify_content="center", width="100%", height="clamp(54px, 7vh, 76px)",
                cursor=rx.cond(day == "", "default", "pointer"),
                on_click=State.select_day(day) if selectable else None,
            )
        ),
        columns="7", width="100%",
        grid_template_columns="repeat(7, minmax(0, 1fr))", gap="6px",
        align_content="center", justify_content="stretch",
        height="100%", min_height="0",
    )



def mini_calendar():
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return glass_card(
        rx.vstack(
            rx.hstack(
                rx.text(State.month_name + " " + State.current_year.to_string(),
                        font_weight="700", color="light-dark(#34415a, #eff3ff)"),
                rx.spacer(),
                rx.button(rx.icon(tag="chevron-left", size=14), on_click=State.prev_month,
                          size="1", variant="ghost"),
                rx.button(rx.icon(tag="chevron-right", size=14), on_click=State.next_month,
                          size="1", variant="ghost"),
                width="100%", align="center"),
            rx.grid(*[rx.text(d, text_align="center", font_size="10px",
                              color="light-dark(#8490a5, #9eabc7)") for d in weekdays],
                    columns="7", width="100%", grid_template_columns="repeat(7, minmax(0, 1fr))"),
            calendar_grid(State.calendar_days),
            spacing="2", width="100%"),
        padding="10px", width="100%",
    )


def workload_panel():
    # Загруженность считается по существующим демонстрационным задачам.
    counts = [0, 1, 0, 1, 0, 0, 0]
    day_labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return glass_card(
        rx.vstack(
            rx.text("ЗАГРУЖЕННОСТЬ НЕДЕЛИ", font_size="10px",
                    letter_spacing="1.4px", font_weight="700",
                    color="light-dark(#71809c, #aab7d5)"),
            rx.grid(*[
                rx.vstack(
                    rx.text(day_labels[i], font_size="11px",
                            color="light-dark(#71809c, #aab7d5)"),
                    rx.box(width="100%", height="26px", border_radius="9px",
                           background=["light-dark(rgba(112,151,239,0.10), rgba(112,151,239,0.12))",
                                       "light-dark(rgba(112,151,239,0.72), rgba(112,151,239,0.62))",
                                       "light-dark(rgba(112,151,239,0.10), rgba(112,151,239,0.12))",
                                       "light-dark(rgba(112,151,239,0.72), rgba(112,151,239,0.62))",
                                       "light-dark(rgba(112,151,239,0.10), rgba(112,151,239,0.12))",
                                       "light-dark(rgba(112,151,239,0.10), rgba(112,151,239,0.12))",
                                       "light-dark(rgba(112,151,239,0.10), rgba(112,151,239,0.12))"][i]),
                    rx.text(str(counts[i]), font_size="10px",
                            color="light-dark(#71809c, #aab7d5)"),
                    align="center", spacing="1")
                for i in range(7)],
                columns="7", width="100%", gap="5px"),
            spacing="2", width="100%"),
        padding="10px", width="100%",
    )


def chat_view():
    return rx.hstack(
        rx.vstack(
            rx.vstack(
                rx.text("ВАШ AI-АССИСТЕНТ", font_size="10px", letter_spacing="2px",
                        font_weight="700", color="light-dark(#71809c, #aab7d5)"),
                rx.heading("Добро пожаловать", size="6",
                           color="light-dark(#253047, #f3f6ff)"),
                rx.text("Общайтесь текстом или голосом — я рядом, чтобы помочь.",
                        color="light-dark(#68758d, #aab5cb)", font_size="14px"),
                spacing="1", align="start"),
            glass_card(
                rx.scroll_area(
                    rx.vstack(rx.foreach(State.messages, render_message),
                              width="100%", padding="12px", gap="10px"),
                    type="scroll", scrollbars="vertical",
                    style={"height": "100%", "minHeight": "0", "flex": "1", "overflowY": "auto"}),
                width="100%", flex="1", min_height="0", height="100%", padding="3px", style={"minHeight": 0}),
            rx.cond(
                State.is_recording,
                glass_card(
                    rx.hstack(
                        rx.hstack(
                            rx.box(width="7px", height="7px", border_radius="50%",
                                   background="#ff596d", animation="pulse 1s infinite"),
                            rx.text("Запись", font_size="12px", font_weight="700",
                                    color="light-dark(#d43c56, #ff8294)"), spacing="2"),
                        rx.spacer(),
                        rx.text("00:00", id="voice-recording-timer",
                                font_size="13px", font_weight="700",
                                font_family="monospace",
                                color="light-dark(#34415a, #f2f5ff)"),
                        rx.button("Отмена", on_click=State.cancel_recording,
                                  size="1", variant="ghost"),
                        width="100%", align="center"),
                    rx.hstack(*[
                        rx.box(id=f"voice-wave-{i}", width="3px", height="4px",
                               min_height="4px", background="linear-gradient(180deg, #9bb9ff, #6588e8)",
                               border_radius="full", transition="height 80ms linear")
                        for i in range(28)],
                        width="100%", height="34px", align="center",
                        justify="center", spacing="1"),
                    width="100%", padding="6px 10px", gap="3px"),
                rx.fragment()),
            glass_card(
                rx.form(
                    rx.hstack(
                        rx.text_area(
                            placeholder=rx.cond(State.is_recording, "Идёт запись голосового сообщения…",
                                                "Напишите сообщение или задайте вопрос…"),
                            value=State.user_input, on_change=State.set_user_input,
                            enter_key_submit=True, flex="1",
                            background="transparent !important", border="none !important",
                            box_shadow="none !important", outline="none !important",
                            color="light-dark(#253047, #f2f5ff)",
                            resize="none", rows="1", auto_height=False,
                            height="42px", max_height="88px", overflow_y="auto",
                            min_height="0", padding="10px 4px", key=State.input_key,
                            disabled=State.is_recording),
                        rx.button(rx.icon(tag=rx.cond(State.is_recording, "square", "mic"), size=18),
                                  type="button",
                                  on_click=rx.cond(State.is_recording, State.stop_recording, State.start_recording),
                                  background=rx.cond(State.is_recording, "rgba(255,80,100,0.16)",
                                                     "light-dark(rgba(103,143,235,0.13), rgba(123,158,255,0.16))"),
                                  color=rx.cond(State.is_recording, "#ff6478", "#82a6ff"),
                                  border_radius="14px", width="42px", height="42px"),
                        rx.button(rx.icon(tag="arrow-up", size=19), type="submit",
                                  disabled=State.is_recording,
                                  background="linear-gradient(145deg, #8eb5ff, #6e8bea)",
                                  color="#ffffff", border_radius="14px",
                                  width="42px", height="42px"),
                        width="100%", align="end", spacing="2"),
                    on_submit=State.send_message, width="100%"),
                width="100%", padding="6px 8px", style={"flexShrink": 0}),
            width="100%", height="100%", flex="1", min_height="0",
            style={"display": "flex", "flexDirection": "column", "minHeight": 0, "overflow": "hidden"},
            align="stretch", spacing="2"),
        rx.vstack(
            mini_calendar(),
            glass_card(
                rx.vstack(
                    rx.text("БЛИЖАЙШИЕ СОБЫТИЯ", font_size="10px",
                            letter_spacing="1.4px", font_weight="700",
                            color="light-dark(#71809c, #aab7d5)"),
                    rx.vstack(
                        rx.hstack(rx.icon(tag="users", color="#789df3"),
                                  rx.vstack(rx.text("Сегодня · 15:00", font_size="11px",
                                                    color="light-dark(#71809c, #aab7d5)"),
                                            rx.text("Встреча с командой", font_size="13px",
                                                    font_weight="600",
                                                    color="light-dark(#34415a, #eff3ff)"),
                                            spacing="0", align="start"),
                                  align="center", spacing="2"),
                        rx.divider(color="subtle"),
                        rx.hstack(rx.icon(tag="phone", color="#789df3"),
                                  rx.vstack(rx.text("Завтра · 10:00", font_size="11px",
                                                    color="light-dark(#71809c, #aab7d5)"),
                                            rx.text("Позвонить Ивану", font_size="13px",
                                                    font_weight="600",
                                                    color="light-dark(#34415a, #eff3ff)"),
                                            spacing="0", align="start"),
                                  align="center", spacing="2"),
                        width="100%", spacing="3"),
                    width="100%", spacing="3"),
                padding="11px", width="100%"),
            workload_panel(),
            width="290px", min_width="260px", height="100%",
            align="stretch", spacing="2"),
        width="100%", height="100%", align="stretch", spacing="3",
    )



def week_view():
    return glass_card(
        rx.vstack(
            rx.hstack(
                rx.button(rx.icon(tag="chevron-left", size=15), on_click=State.previous_week,
                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                          color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                          border_radius="10px", width="32px", height="32px"),
                rx.heading(State.week_range_label, size="4",
                           color="light-dark(#34415a, #eff3ff)"),
                rx.button(rx.icon(tag="chevron-right", size=15), on_click=State.next_week,
                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                          color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                          border_radius="10px", width="32px", height="32px"),
                rx.spacer(),
                rx.hstack(rx.icon(tag="clock", size=13, color="#7399ef"),
                          rx.text("Сейчас " + State.current_time_label, font_size="12px", font_weight="700",
                                  color="light-dark(#53617a, #d5def0)"),
                          background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                          border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                          border_radius="10px", padding="7px 10px", spacing="2"),
                rx.button("Сегодня", on_click=State.go_to_current_week,
                          background="linear-gradient(145deg, #8eb5ff, #6e8bea)",
                          color="#ffffff", border_radius="10px", padding="7px 11px"),
                width="100%", align="center"),
            rx.grid(
                rx.foreach(
                    State.week_days_data,
                    lambda day: rx.vstack(
                        rx.text(day["label"], font_size="10px",
                                color="light-dark(#8490a5, #9eabc7)"),
                        rx.text(day["date"], font_size="18px", font_weight="700",
                                color=rx.cond(day["is_today"], "#78aefb",
                                              "light-dark(#34415a, #eff3ff)")),
                        width="100%", align="center", spacing="0",
                        background=rx.cond(day["is_today"],
                            "light-dark(rgba(120,174,251,0.16), rgba(120,174,251,0.18))",
                            "transparent"),
                        padding="9px", border_radius="13px"),
                ),
                columns="7", width="100%",
                grid_template_columns="repeat(7, minmax(0, 1fr))", gap="4px"),
            rx.hstack(
              rx.vstack(
                *[rx.text(f"{hour:02d}:00", font_size="10px", line_height="1",
                          color="light-dark(#8490a5, #9eabc7)", height="72px",
                          width="42px", text_align="right", padding_top="0px")
                  for hour in range(7, 20, 2)],
                width="42px", min_width="42px", align="end", spacing="0",
                padding_top="4px"),
              rx.grid(
                rx.foreach(
                    State.week_days_data,
                    lambda day: rx.box(
                        rx.vstack(
                            rx.cond(
                                day["iso"] == State.week_days_data[0]["iso"],
                                rx.box(
                                    rx.vstack(
                                        rx.text("Встреча с командой", font_size="11px",
                                                font_weight="500"),
                                        rx.text("15:00", font_size="10px"),
                                        spacing="1"),
                                    background="rgba(112,151,239,0.28)",
                                    border="1px solid rgba(112,151,239,0.35)",
                                    border_radius="10px", padding="7px",
                                    margin_top="190px", width="100%"),
                                rx.fragment()),
                            rx.cond(
                                day["iso"] == State.week_days_data[1]["iso"],
                                rx.box(
                                    rx.vstack(
                                        rx.text("Позвонить Ивану", font_size="11px",
                                                font_weight="500"),
                                        rx.text("10:00", font_size="10px"),
                                        spacing="1"),
                                    background="rgba(89,190,170,0.25)",
                                    border="1px solid rgba(89,190,170,0.35)",
                                    border_radius="10px", padding="7px",
                                    margin_top="90px", width="100%"),
                                rx.fragment()),
                            width="100%", align="stretch", spacing="2"),
                        rx.cond(
                            day["is_today"],
                            rx.box(
                                rx.box(width="7px", height="7px", border_radius="50%",
                                       background="#3988f6", position="absolute",
                                       left="-3px", top="-3px"),
                                width="100%", height="2px",
                                background="#3988f6",
                                position="absolute", left="0", right="0",
                                top=State.current_time_top, z_index="5",
                                box_shadow="0 0 8px rgba(57,136,246,0.45)"),
                            rx.fragment()),
                        min_height="504px", height="504px", padding="4px", position="relative",
                        border_left="1px solid light-dark(rgba(80,100,140,0.12), rgba(255,255,255,0.08))",
                        background=rx.cond(day["is_today"],
                            "light-dark(rgba(120,174,251,0.045), rgba(120,174,251,0.055))",
                            "transparent"),
                    ),
                ),
                columns="7", width="100%",
                grid_template_columns="repeat(7, minmax(0, 1fr))", gap="0px"),
              width="100%", align="start", spacing="2"),
            rx.text("Шкала времени: 07:00–21:00 · синяя линия показывает текущее время. События пока демонстрационные: исходный проект не содержит хранилища или API событий.",
                    font_size="11px", color="light-dark(#8994a9, #98a6c3)"),
            width="100%", spacing="2"),
        padding="12px", width="100%", overflow_x="auto",
        style={"scrollbarWidth": "none", "msOverflowStyle": "none",
               "&::-webkit-scrollbar": {"display": "none", "width": "0px", "height": "0px"}})


def calendar_view():
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text("ПЛАНИРОВАНИЕ", font_size="10px", letter_spacing="2px",
                        font_weight="700", color="light-dark(#71809c, #aab7d5)"),
                rx.heading("Календарь", size="6", color="light-dark(#253047, #f3f6ff)"),
                rx.text("Ваше расписание в одном пространстве", font_size="14px",
                        color="light-dark(#68758d, #aab5cb)"),
                spacing="1", align="start"),
            rx.spacer(),
            rx.hstack(
                rx.button("Месяц", on_click=lambda: State.set_calendar_mode("month"),
                          background=rx.cond(State.calendar_mode == "month",
                              "linear-gradient(145deg, #8eb5ff, #6e8bea)",
                              "light-dark(rgba(226,233,246,0.55), rgba(255,255,255,0.05))"),
                          color=rx.cond(State.calendar_mode == "month", "#ffffff",
                              "light-dark(#53617a, #c4cee3)"),
                          border=rx.cond(State.calendar_mode == "month",
                              "1px solid rgba(255,255,255,0.28)",
                              "1px solid light-dark(rgba(255,255,255,0.55), rgba(255,255,255,0.08))"),
                          border_radius="11px", padding="7px 13px", box_shadow=rx.cond(State.calendar_mode == "month", "0 3px 12px rgba(85,120,200,0.22)", "none")),
                rx.button("Неделя", on_click=lambda: State.set_calendar_mode("week"),
                          background=rx.cond(State.calendar_mode == "week",
                              "linear-gradient(145deg, #8eb5ff, #6e8bea)",
                              "light-dark(rgba(226,233,246,0.55), rgba(255,255,255,0.05))"),
                          color=rx.cond(State.calendar_mode == "week", "#ffffff",
                              "light-dark(#53617a, #c4cee3)"),
                          border=rx.cond(State.calendar_mode == "week",
                              "1px solid rgba(255,255,255,0.28)",
                              "1px solid light-dark(rgba(255,255,255,0.55), rgba(255,255,255,0.08))"),
                          border_radius="11px", padding="7px 13px", box_shadow=rx.cond(State.calendar_mode == "week", "0 3px 12px rgba(85,120,200,0.22)", "none")),
                spacing="1"),
            width="100%", align="center", wrap="wrap"),
        rx.cond(
            State.calendar_mode == "month",
            rx.hstack(
                glass_card(
                    rx.vstack(
                        rx.hstack(
                            rx.button(rx.icon(tag="chevron-left", size=16), on_click=State.prev_month,
                                      background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                                      color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                                      border_radius="11px", width="34px", height="34px"),
                            rx.heading(State.month_name + " " + State.current_year.to_string(),
                                       size="5", color="light-dark(#34415a, #eff3ff)"),
                            rx.button(rx.icon(tag="chevron-right", size=16), on_click=State.next_month,
                                      background="light-dark(rgba(226,233,246,0.72), rgba(255,255,255,0.07))",
                                      color="light-dark(#53617a, #d5def0)", border="1px solid light-dark(rgba(255,255,255,0.7), rgba(255,255,255,0.1))",
                                      border_radius="11px", width="34px", height="34px"),
                            width="100%", justify="center", align="center"),
                        rx.grid(*[
                            rx.text(day, color="light-dark(#8490a5, #9eabc7)",
                                    font_size="12px", font_weight="700", text_align="center")
                            for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]],
                            columns="7", width="100%",
                            grid_template_columns="repeat(7, minmax(0, 1fr))", gap="6px"),
                        calendar_grid(State.calendar_days, selectable=True),
                        width="100%", spacing="2"),
                    width="58%", padding="18px", min_height="72vh", height="72vh"),
                glass_card(
                    rx.vstack(
                        rx.text("СЕГОДНЯ", font_size="10px", letter_spacing="1.5px",
                                font_weight="700", color="light-dark(#71809c, #aab7d5)"),
                        rx.heading("События дня", size="5",
                                   color="light-dark(#34415a, #eff3ff)"),
                        rx.text("15:00 · Встреча с командой", font_weight="400",
                                color="light-dark(#34415a, #eff3ff)"),
                        rx.text("10:00 · Позвонить Ивану — завтра",
                                color="light-dark(#68758d, #aab5cb)"),
                        rx.text("События ниже пока демонстрационные: в исходном проекте нет хранилища событий.",
                                font_size="11px", color="light-dark(#8994a9, #98a6c3)"),
                        align="start", width="100%", spacing="3"),
                    flex="1", padding="20px", min_height="72vh", height="72vh"),
                width="100%", align="stretch", spacing="3"),
            week_view()),
        width="100%", height="100%", flex="1", min_height="0",
        align="stretch", spacing="2")


def index() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Верхняя стеклянная панель и переключатель разделов
            glass_card(
                rx.hstack(
                    rx.hstack(
                        rx.box(rx.icon(tag="audio-waveform", size=21, color="#7399ef"),
                               background="light-dark(rgba(255,255,255,0.85), rgba(130,160,255,0.15))",
                               border="1px solid light-dark(rgba(255,255,255,0.9), rgba(255,255,255,0.16))",
                               border_radius="15px", padding="10px"),
                        rx.vstack(rx.text("AURA", font_size="15px", font_weight="800", letter_spacing="2px",
                                          color="light-dark(#2c3a55, #f2f5ff)"),
                                  rx.text("PERSONAL ASSISTANT", font_size="9px", letter_spacing="1.5px",
                                          color="light-dark(#8994a9, #98a6c3)"), spacing="0", align="start"),
                        spacing="3", align="center"),
                    rx.spacer(),
                    rx.hstack(nav_button("Ассистент", "message-circle", "chat"),
                              nav_button("Календарь", "calendar-days", "calendar"),
                              background="light-dark(rgba(225,232,245,0.58), rgba(10,15,28,0.28))",
                              border="1px solid light-dark(rgba(255,255,255,0.72), rgba(255,255,255,0.09))",
                              border_radius="19px", padding="4px", spacing="1"),
                    width="100%", align="center", wrap="wrap"),
                width="100%", padding="8px 12px"),
            rx.cond(State.active_view == "chat", chat_view(), calendar_view()),
            width="100%", height="100%", max_width="1180px", padding="12px",
            align="stretch", spacing="2", margin="0 auto",
        ),
        width="100%", height="100vh", overflow="hidden",
        background="radial-gradient(ellipse at 12% 8%, light-dark(rgba(160,195,255,0.42), rgba(71,101,171,0.30)), transparent 42%), radial-gradient(ellipse at 90% 88%, light-dark(rgba(202,222,255,0.65), rgba(85,74,145,0.28)), transparent 44%), light-dark(#e8eef8, #101522)",
        color="light-dark(#253047, #f2f5ff)",
        style={**style, "colorScheme": "light dark", "backgroundAttachment": "fixed"},
    )


# Фрагменты записи временно хранятся на диске backend-сервера.
_audio_dir_setting = Path(os.getenv("AUDIO_RECORDINGS_DIR", "recordings"))
AUDIO_DIR = (_audio_dir_setting if _audio_dir_setting.is_absolute()
             else Path(__file__).resolve().parent / _audio_dir_setting).resolve()
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

async def audio_start(recording_id: str):
    try:
        safe_id = str(uuid.UUID(recording_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recording id")
    temp_path = AUDIO_DIR / f".{safe_id}.part"
    temp_path.write_bytes(b"")
    return {"ok": True}

async def audio_chunk(recording_id: str, request: Request):
    try:
        safe_id = str(uuid.UUID(recording_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recording id")
    data = await request.body()
    if not data:
        return {"ok": True, "bytes": 0}
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio chunk too large")
    temp_path = AUDIO_DIR / f".{safe_id}.part"
    # Append creates the file if a start request was handled by another worker
    # or its empty-file creation raced with the first chunk.
    with temp_path.open("ab") as audio_file:
        audio_file.write(data)
    return {"ok": True, "bytes": len(data)}

async def audio_finish(recording_id: str):
    try:
        safe_id = str(uuid.UUID(recording_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recording id")
    temp_path = AUDIO_DIR / f".{safe_id}.part"
    if not temp_path.exists():
        raise HTTPException(status_code=404, detail="Recording session not found")
    if temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty recording")
    final_path = AUDIO_DIR / f"recording_{datetime.now():%Y%m%d_%H%M%S}_{safe_id[:8]}.webm"
    temp_path.replace(final_path)
    return {"ok": True, "path": final_path.as_posix(), "bytes": final_path.stat().st_size}

async def audio_cancel(recording_id: str):
    try:
        safe_id = str(uuid.UUID(recording_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid recording id")
    (AUDIO_DIR / f".{safe_id}.part").unlink(missing_ok=True)
    return {"ok": True}

# Reflex передаёт сюда ASGI-приложение Starlette. Используем add_route
# и небольшие адаптеры: Starlette передаёт параметры пути через Request.
async def _audio_route(request: Request, handler, needs_body: bool = False):
    try:
        recording_id = request.path_params["recording_id"]
        if needs_body:
            result = await handler(recording_id, request)
        else:
            result = await handler(recording_id)
        return JSONResponse(result)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

async def _audio_start_route(request: Request):
    return await _audio_route(request, audio_start)

async def _audio_chunk_route(request: Request):
    return await _audio_route(request, audio_chunk, needs_body=True)

async def _audio_finish_route(request: Request):
    return await _audio_route(request, audio_finish)

async def _audio_cancel_route(request: Request):
    return await _audio_route(request, audio_cancel)

def audio_api_transformer(api):
    api.add_route("/audio/start/{recording_id}", _audio_start_route, methods=["POST"])
    api.add_route("/audio/chunk/{recording_id}", _audio_chunk_route, methods=["POST"])
    api.add_route("/audio/finish/{recording_id}", _audio_finish_route, methods=["POST"])
    api.add_route("/audio/cancel/{recording_id}", _audio_cancel_route, methods=["DELETE"])
    return api


app = rx.App(api_transformer=audio_api_transformer)
app.add_page(index)
