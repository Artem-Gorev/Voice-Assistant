import asyncio
import calendar
import json
import uuid
from datetime import date, datetime, timedelta

import reflex as rx
from reflex.config import get_config

from .assistant_service import (
    _assistant_is_ready,
    _assistant_logger,
    _play_audio_script,
    _preload_assistant,
    _process_text,
    _read_calendar_events,
)

class State(rx.State):

    messages: list[dict] = []
    calendar_events: list[dict] = []
    voice_output: bool = False
    models_ready: bool = False
    startup_status: str = "Загружаю модели ассистента..."

    user_input: str = ""

    input_key: int = 0

    selected_day: str = ""

    is_recording: bool = False
    is_processing: bool = False

    current_month: int = datetime.now().month

    current_year: int = datetime.now().year

    modal_month: int = datetime.now().month

    modal_year: int = datetime.now().year
    full_month: int = datetime.now().month
    full_year: int = datetime.now().year

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

        return (days + [""] * 42)[:42]

    @rx.var
    def full_month_name(self) -> str:
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль",
                  "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        return months[self.full_month - 1]

    @rx.var
    def full_calendar_days(self) -> list[str]:
        cal = calendar.monthcalendar(self.full_year, self.full_month)
        days = ["" if day == 0 else str(day) for week in cal for day in week]
        return (days + [""] * 42)[:42]

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

        return (days + [""] * 42)[:42]

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

    def full_prev_month(self):
        if self.full_month == 1:
            self.full_month, self.full_year = 12, self.full_year - 1
        else:
            self.full_month -= 1
        self.selected_day = ""

    def full_next_month(self):
        if self.full_month == 12:
            self.full_month, self.full_year = 1, self.full_year + 1
        else:
            self.full_month += 1
        self.selected_day = ""

    def select_day(self, day: str):

        if day:

            self.selected_day = day

    def set_user_input(self, val: str):

        self.user_input = val

    @rx.event(background=True)
    async def initialize_app(self):
        async with self:
            self.models_ready = False
            self.calendar_events = []
            self.messages = []
            self.startup_status = "Загружаю модели ассистента..."
        try:
            events = await asyncio.to_thread(_preload_assistant)
        except Exception as error:
            events = []
            status = f"Не удалось запустить ассистента: {error}"
        else:
            status = ""
        async with self:
            self.calendar_events = events
            self.models_ready = _assistant_is_ready()
            self.startup_status = status

    def toggle_voice_output(self):
        self.voice_output = not self.voice_output
        enabled = "true" if self.voice_output else "false"
        script = f"window.__voiceOutputEnabled = {enabled};"
        if self.voice_output:
            script += "const C=window.AudioContext||window.webkitAudioContext; " \
                      "window.__assistantAudioContext=window.__assistantAudioContext||new C(); " \
                      "window.__assistantAudioContext.resume();"
        return rx.call_script(script)

    @rx.event(background=True)
    async def send_message(self):
        async with self:
            text = self.user_input.strip()
            if not text or self.is_processing:
                return
            self.is_processing = True
            session_id = self.router.session.client_token or str(uuid.uuid4())
            voice_output = self.voice_output
            self.messages = self.messages + [{"role": "user", "text": text}]
            self.user_input = ""
            self.input_key += 1

        try:
            answer, audio_data, events = await asyncio.to_thread(
                _process_text, text, session_id, voice_output
            )
        except Exception as error:
            answer, audio_data, events = f"Не удалось обработать запрос: {error}", "", None

        async with self:
            self.is_processing = False
            self.messages = self.messages + [{"role": "ai", "text": answer}]
            if events is not None:
                self.calendar_events = events

        if audio_data:
            return _play_audio_script(audio_data)

    def start_recording(self):

        return rx.call_script("""
            (async () => {
                if (window.__voiceStarting || window.__voiceRecorder) return false;
                window.__voiceStarting = true;

                let stream = null;
                let recordingId = null;
                let audioApiBase = null;

                try {
                    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                        throw new Error("Для доступа к микрофону откройте приложение через HTTPS или localhost.");
                    }
                    if (!window.MediaRecorder) {
                        throw new Error("Этот браузер не поддерживает запись аудио.");
                    }

                    stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                    const location = window.location;
                    const backendUrl = new URL("__REFLEX_API_URL__");
                    const localFrontend = ["localhost", "127.0.0.1", "0.0.0.0"].includes(location.hostname);
                    if (["localhost", "127.0.0.1", "0.0.0.0"].includes(backendUrl.hostname)) {
                        backendUrl.hostname = location.hostname;
                    }
                    const defaultAudioApiBase = localFrontend ? backendUrl.origin : location.origin;
                    audioApiBase = window.__AUDIO_API_BASE || defaultAudioApiBase;
                    window.__voiceAudioApiBase = audioApiBase;
                    window.__voiceClientToken = window.sessionStorage.getItem("token") || "";

                    const makeId = () => {
                        if (window.crypto && typeof window.crypto.randomUUID === "function") {
                            return window.crypto.randomUUID();
                        }
                        const bytes = new Uint8Array(16);
                        window.crypto.getRandomValues(bytes);
                        bytes[6] = (bytes[6] & 0x0f) | 0x40;
                        bytes[8] = (bytes[8] & 0x3f) | 0x80;
                        return Array.from(bytes, (b, i) =>
                            ([4, 6, 8, 10].includes(i) ? "-" : "") + b.toString(16).padStart(2, "0")
                        ).join("");
                    };
                    recordingId = makeId();

                    const init = await fetch(audioApiBase + "/audio/start/" + recordingId, {
                        method: "POST",
                        headers: {
                            "Accept": "application/json",
                            "X-Reflex-Client-Token": window.__voiceClientToken || ""
                        }
                    });
                    if (!init.ok) {
                        const detail = await init.text().catch(() => "");
                        throw new Error("Сервер не смог начать запись (HTTP " + init.status + "): " + detail);
                    }

                    const mimeCandidates = [
                        "audio/webm;codecs=opus",
                        "audio/webm",
                        "audio/ogg;codecs=opus",
                        "audio/mp4"
                    ];
                    const mimeType = mimeCandidates.find(type =>
                        MediaRecorder.isTypeSupported(type)
                    );
                    const recorder = mimeType
                        ? new MediaRecorder(stream, { mimeType })
                        : new MediaRecorder(stream);

                    window.__voiceStream = stream;
                    window.__voiceRecordingId = recordingId;
                    window.__voiceUploadQueue = Promise.resolve();
                    window.__voiceUploadError = null;
                    window.__voiceStartedAt = Date.now();
                    window.__voiceRecorder = recorder;
                    window.__voiceRecorderError = null;
                    recorder.onerror = (event) => {
                        const err = event && event.error;
                        window.__voiceRecorderError =
                            (err && err.message) || "Браузер прервал запись аудио.";
                        console.error("MediaRecorder error:", event);
                    };
                    stream.getAudioTracks().forEach(track => {
                        track.addEventListener("ended", () => {
                            if (window.__voiceRecorder === recorder &&
                                recorder.state !== "inactive") {
                                window.__voiceRecorderError =
                                    "Доступ к микрофону был прерван браузером или системой.";
                            }
                        });
                    });

                    recorder.ondataavailable = (event) => {
                        if (!event.data || !event.data.size) return;
                        window.__voiceUploadQueue = window.__voiceUploadQueue.then(async () => {
                            if (window.__voiceUploadError) return;
                            const response = await fetch(
                                window.__voiceAudioApiBase + "/audio/chunk/" + recordingId,
                                {
                                    method: "POST",
                                    headers: { "Content-Type": "application/octet-stream" },
                                    body: event.data
                                }
                            );
                            if (!response.ok) {
                                const detail = await response.text().catch(() => "");
                                throw new Error("Не удалось передать фрагмент аудио (HTTP " +
                                    response.status + "): " + detail);
                            }
                        }).catch(error => {
                            window.__voiceUploadError = error.message || String(error);
                            console.error("Audio chunk upload failed:", error);
                        });
                    };

                    try {
                        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                        if (AudioContextClass) {
                            window.__voiceAudioContext = new AudioContextClass();
                            window.__voiceAnalyser = window.__voiceAudioContext.createAnalyser();
                            window.__voiceAnalyser.fftSize = 256;
                            window.__voiceAnalyser.smoothingTimeConstant = 0.84;
                            window.__voiceAnalyser.minDecibels = -88;
                            window.__voiceAnalyser.maxDecibels = -24;
                            window.__voiceAudioContext.createMediaStreamSource(stream)
                                .connect(window.__voiceAnalyser);
                            window.__voiceFrequencyData =
                                new Uint8Array(window.__voiceAnalyser.frequencyBinCount);
                            window.__voiceWaveHeights = new Array(36).fill(3);
                        }
                    } catch (visualError) {
                        console.warn("Audio visualization unavailable:", visualError);
                        window.__voiceAnalyser = null;
                    }

                    window.__voiceTimer = setInterval(() => {
                        const seconds = Math.floor((Date.now() - window.__voiceStartedAt) / 1000);
                        const timer = document.getElementById("voice-recording-timer");
                        if (timer) timer.textContent =
                            String(Math.floor(seconds / 60)).padStart(2, "0") + ":" +
                            String(seconds % 60).padStart(2, "0");
                    }, 250);

                    const animateWave = () => {
                        if (!window.__voiceAnalyser || !window.__voiceFrequencyData) return;
                        window.__voiceAnalyser.getByteFrequencyData(window.__voiceFrequencyData);
                        const barCount = 36;
                        const highestVoiceBin = Math.min(36, window.__voiceFrequencyData.length - 1);
                        for (let i = 0; i < barCount; i++) {
                            const bar = document.getElementById("voice-wave-" + i);
                            if (!bar) continue;
                            const position = i / (barCount - 1);
                            const bin = Math.max(1, Math.round(
                                1 + Math.pow(position, 1.4) * (highestVoiceBin - 1)
                            ));
                            const energy = (window.__voiceFrequencyData[bin] || 0) / 255;
                            const target = 3 + Math.pow(energy, 0.72) * 22;
                            const previous = window.__voiceWaveHeights[i] || 3;
                            const easing = target > previous ? 0.3 : 0.14;
                            const height = previous + (target - previous) * easing;
                            window.__voiceWaveHeights[i] = height;
                            bar.style.height = height + "px";
                        }
                        window.__voiceAnimationFrame = requestAnimationFrame(animateWave);
                    };
                    if (window.__voiceAnalyser) animateWave();

                    recorder.start(5000);
                    return true;
                } catch (error) {
                    console.error("Не удалось начать запись:", error);
                    alert("Не удалось начать запись: " + (error.message || error));

                    if (recordingId && audioApiBase) {
                        fetch(audioApiBase + "/audio/cancel/" + recordingId, {
                            method: "DELETE"
                        }).catch(() => {});
                    }
                    if (stream) stream.getTracks().forEach(track => track.stop());
                    if (window.__voiceAudioContext) {
                        try { await window.__voiceAudioContext.close(); } catch (_) {}
                    }
                    window.__voiceStream = null;
                    window.__voiceAudioContext = null;
                    window.__voiceAnalyser = null;
                    window.__voiceRecorder = null;
                    window.__voiceRecordingId = null;
                    return false;
                } finally {
                    window.__voiceStarting = false;
                }
            })()
        """.replace("__REFLEX_API_URL__", get_config().api_url), callback=State.handle_recording_started)

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

                    for (let i = 0; i < 36; i++) {

                        const bar = document.getElementById("voice-wave-" + i);

                        if (bar) bar.style.height = "4px";

                    }

                }

                return true;

            })()

        """)

    def stop_recording(self):

        self.is_recording = False
        self.is_processing = True

        return rx.call_script("""
            (async () => {
                const recorder = window.__voiceRecorder;
                const recordingId = window.__voiceRecordingId;
                let saved = null;

                if (!recorder || !recordingId || recorder.state === "inactive") {
                    window.__voiceStarting = false;
                    window.__voiceRecorder = null;
                    window.__voiceRecordingId = null;
                    window.__voiceStream?.getTracks().forEach(track => track.stop());
                    return JSON.stringify({ok: false, error:
                        "Запись была прервана браузером. Нажмите на микрофон, чтобы начать новую."});
                }

                if (window.__voiceTimer) clearInterval(window.__voiceTimer);
                if (window.__voiceAnimationFrame) cancelAnimationFrame(window.__voiceAnimationFrame);

                try {
                    if (recorder.state !== "inactive") {
                        await new Promise(resolve => {
                            recorder.addEventListener("stop", resolve, { once: true });
                            recorder.stop();
                        });
                    }

                    await (window.__voiceUploadQueue || Promise.resolve());
                    if (window.__voiceRecorderError) {
                        throw new Error(window.__voiceRecorderError);
                    }
                    if (window.__voiceUploadError) {
                        throw new Error("Не все фрагменты дошли до сервера: " +
                            window.__voiceUploadError);
                    }

                    const response = await fetch(
                        window.__voiceAudioApiBase + "/audio/finish/" + recordingId,
                        {
                            method: "POST",
                            headers: {
                                "Accept": "application/json",
                                "X-Reflex-Client-Token": window.__voiceClientToken || "",
                                "X-Voice-Output": window.__voiceOutputEnabled ? "true" : "false"
                            }
                        }
                    );
                    if (!response.ok) {
                        const detail = await response.text().catch(() => "");
                        throw new Error("Не удалось обработать аудио (HTTP " +
                            response.status + "): " + detail);
                    }
                    saved = await response.json();
                    return JSON.stringify(saved);
                } catch (error) {
                    return JSON.stringify({ok: false, error: error?.message || String(error)});
                } finally {
                    if (!saved && recordingId && window.__voiceAudioApiBase) {
                        fetch(window.__voiceAudioApiBase + "/audio/cancel/" + recordingId, {
                            method: "DELETE"
                        }).catch(() => {});
                    }
                    if (window.__voiceStream) {
                        window.__voiceStream.getTracks().forEach(track => track.stop());
                    }
                    if (window.__voiceAudioContext) {
                        try { await window.__voiceAudioContext.close(); } catch (_) {}
                    }
                    window.__voiceStream = null;
                    window.__voiceAudioContext = null;
                    window.__voiceAnalyser = null;
                    window.__voiceRecorder = null;
                    window.__voiceRecordingId = null;
                    window.__voiceUploadQueue = Promise.resolve();
                    window.__voiceUploadError = null;
                    for (let i = 0; i < 36; i++) {
                        const bar = document.getElementById("voice-wave-" + i);
                        if (bar) bar.style.height = "4px";
                    }
                }
            })()
        """, callback=State.handle_chunked_audio_saved)

    def handle_chunked_audio_saved(self, result: str):
        self.is_processing = False
        try:
            payload = json.loads(result) if isinstance(result, str) else result
        except (TypeError, json.JSONDecodeError):
            payload = {}

        if not isinstance(payload, dict) or not payload.get("ok"):
            message = payload.get("error", "Не удалось обработать голосовое сообщение.") if isinstance(payload, dict) else str(result)
            self.messages = self.messages + [{"role": "ai", "text": message}]
            return

        self.messages = self.messages + [
            {"role": "user", "text": payload.get("transcript") or "🎙️ [Голосовое сообщение]"},
            {"role": "ai", "text": payload.get("response") or "Ассистент не вернул ответ."},
        ]
        if isinstance(payload.get("events"), list):
            self.calendar_events = payload["events"]
        if payload.get("audio_data"):
            return _play_audio_script(payload["audio_data"])

    def set_calendar_mode(self, mode: str):
        if self.calendar_mode != mode:
            self.week_offset = 0
            today = date.today()
            self.full_month, self.full_year = today.month, today.year
        self.calendar_mode = mode

    def previous_week(self):

        self.week_offset -= 1

    def next_week(self):

        self.week_offset += 1

    def go_to_current_week(self):
        today = date.today()
        self.week_offset = 0
        self.full_month = today.month
        self.full_year = today.year
        self.selected_date_iso = today.isoformat()
        self.selected_day = str(today.day)

    @rx.var
    def week_days_data(self) -> list[dict]:
        today = date.today()
        monday = today - timedelta(days=today.weekday()) + timedelta(days=self.week_offset * 7)
        names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        result = []
        for index, name in enumerate(names):
            day = monday + timedelta(days=index)
            day_events = [event for event in self.calendar_events if event.get("date") == day.isoformat()]
            result.append({
                "label": name,
                "date": day.strftime("%d"),
                "iso": day.isoformat(),
                "is_today": day == today,
                "full": day.strftime("%d.%m.%Y"),
                "count": sum(1 for event in day_events if event.get("active", True)),
            })
        return result

    @rx.var

    def week_range_label(self) -> str:

        today = date.today()

        monday = today - timedelta(days=today.weekday()) + timedelta(days=self.week_offset * 7)

        sunday = monday + timedelta(days=6)

        return f"{monday:%d.%m} — {sunday:%d.%m.%Y}"

    active_view: str = "chat"

    calendar_mode: str = "month"

    week_offset: int = 0

    selected_date_iso: str = date.today().isoformat()

    @rx.var
    def selected_date_label(self) -> str:
        try:
            chosen = date.fromisoformat(self.selected_date_iso)
        except (TypeError, ValueError):
            chosen = date.today()
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return f"{chosen.day} {months[chosen.month - 1]} {chosen.year}"

    @rx.var
    def selected_day_events(self) -> list[str]:
        return [
            f"{event.get('time', '')} · {event.get('title', 'Событие')}"
            for event in self.calendar_events
            if event.get("date") == self.selected_date_iso
        ]

    @rx.var
    def current_month_event_days(self) -> list[str]:
        prefix = f"{self.current_year:04d}-{self.current_month:02d}-"
        return sorted({str(int(event["date"][8:10])) for event in self.calendar_events
                       if event.get("date", "").startswith(prefix)})

    @rx.var
    def full_month_event_days(self) -> list[str]:
        prefix = f"{self.full_year:04d}-{self.full_month:02d}-"
        return sorted({str(int(event["date"][8:10])) for event in self.calendar_events
                       if event.get("date", "").startswith(prefix)})

    @rx.var
    def upcoming_events(self) -> list[dict]:
        now = datetime.now().astimezone()
        upcoming = []
        for event in self.calendar_events:
            if not event.get("active", True):
                continue
            try:
                event_start = datetime.fromisoformat(event["sort_key"])
            except (KeyError, TypeError, ValueError):
                continue
            if event_start >= now:
                upcoming.append(event)
        return upcoming[:3]

    def select_calendar_day(self, day: str):
        if not day:
            return
        try:
            chosen = date(self.full_year, self.full_month, int(day))
        except (TypeError, ValueError):
            return
        self.selected_day = str(chosen.day)
        self.selected_date_iso = chosen.isoformat()

    def show_chat(self):
        today = date.today()
        self.current_month, self.current_year = today.month, today.year
        self.modal_month, self.modal_year = today.month, today.year
        self.today = str(today.day)
        self.selected_day = ""
        self.selected_date_iso = today.isoformat()
        self.week_offset = 0
        self.active_view = "chat"

    def show_calendar(self):
        today = date.today()
        self.full_month, self.full_year = today.month, today.year
        self.week_offset = 0
        self.selected_date_iso = today.isoformat()
        self.selected_day = str(today.day)
        self.active_view = "calendar"
