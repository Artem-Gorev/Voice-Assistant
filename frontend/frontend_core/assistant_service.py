import base64
import logging
import re
import threading
from datetime import datetime, timedelta

import reflex as rx

from backend.audio.audio_handler import decode_audio_bytes
from backend.dal.datetime_utils import get_app_timezone
from backend.text_normalizer import normalize_text_for_speech

_assistant_instance = None
_assistant_lock = threading.RLock()
_assistant_logger = logging.getLogger("voice_assistant.frontend")
_assistant_ready = False
_assistant_startup_error: str | None = None


def _get_assistant():
    global _assistant_instance
    if _assistant_instance is None:
        from backend.voice_assistant import VoiceAssistant

        _assistant_instance = VoiceAssistant(
            logger=_assistant_logger,
            voice_input=True,
            speak=True,
        )
    return _assistant_instance


def _serialize_events(rows: list[dict]) -> list[dict]:
    app_timezone = get_app_timezone()
    values = []
    for row in rows:
        start = row.get("start_time")
        if not isinstance(start, datetime):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=app_timezone)
        local_start = start.astimezone(app_timezone)

        end = row.get("end_time")
        if isinstance(end, datetime):
            if end.tzinfo is None:
                end = end.replace(tzinfo=app_timezone)
            local_end = end.astimezone(app_timezone)
        else:
            local_end = local_start

        duration = max(30, int((local_end - local_start).total_seconds() // 60))
        start_minute = local_start.hour * 60 + local_start.minute
        top = max(0, min((start_minute - 7 * 60) * 0.7, 14 * 60 * 0.7 - 30))
        height = max(30, min(duration * 0.7, 14 * 60 * 0.7 - top))
        event_date = local_start.date()
        today = datetime.now(app_timezone).date()
        if event_date == today:
            date_label = f"Сегодня · {local_start:%H:%M}"
        elif event_date == today + timedelta(days=1):
            date_label = f"Завтра · {local_start:%H:%M}"
        else:
            date_label = f"{local_start:%d.%m} · {local_start:%H:%M}"

        status = str(row.get("status") or "pending")
        values.append({
            "id": str(row.get("id") or ""),
            "title": str(row.get("text") or "Событие"),
            "date": event_date.isoformat(),
            "time": local_start.strftime("%H:%M"),
            "date_label": date_label,
            "sort_key": local_start.isoformat(),
            "status": status,
            "active": status.lower() not in {"completed", "cancelled", "canceled"},
            "top": f"{top:.0f}px",
            "height": f"{height:.0f}px",
            "_top_px": top,
            "_height_px": height,
            "_start_minute": start_minute,
            "_end_minute": max(start_minute + 30, local_end.hour * 60 + local_end.minute),
        })
    values = sorted(values, key=lambda event: event["sort_key"])
    _assign_week_columns(values)
    return values


def _assign_week_columns(events: list[dict]) -> None:
    by_date: dict[str, list[dict]] = {}
    for event in events:
        event["week_left"] = "3px"
        event["week_right"] = "3px"
        by_date.setdefault(event["date"], []).append(event)

    for day_events in by_date.values():
        ordered = sorted(
            day_events,
            key=lambda item: (item["_top_px"], item["_start_minute"], item["_end_minute"]),
        )
        cluster: list[dict] = []
        cluster_end = -1.0
        for event in ordered:
            visual_end = event["_top_px"] + event["_height_px"] + 4
            if cluster and event["_top_px"] >= cluster_end:
                _layout_event_cluster(cluster)
                cluster = []
                cluster_end = -1.0
            cluster.append(event)
            cluster_end = max(cluster_end, visual_end)
        if cluster:
            _layout_event_cluster(cluster)


def _layout_event_cluster(events: list[dict]) -> None:
    lane_ends: list[float] = []
    for event in events:
        visual_start = event["_top_px"]
        visual_end = visual_start + event["_height_px"] + 4
        lane = next(
            (index for index, end_position in enumerate(lane_ends)
             if end_position <= visual_start),
            len(lane_ends),
        )
        if lane == len(lane_ends):
            lane_ends.append(visual_end)
        else:
            lane_ends[lane] = visual_end
        event["_week_lane"] = lane

    lane_count = max(1, len(lane_ends))
    for event in events:
        lane = event["_week_lane"]
        event["week_left"] = f"calc({lane * 100 / lane_count:.4f}% + 3px)"
        event["week_right"] = f"calc({(lane_count - lane - 1) * 100 / lane_count:.4f}% + 3px)"


def _read_calendar_events(assistant=None) -> list[dict]:
    instance = assistant or _get_assistant()
    return _serialize_events(instance._repository.get_all_events())


def _preload_assistant() -> list[dict]:
    global _assistant_ready, _assistant_startup_error
    with _assistant_lock:
        try:
            assistant = _get_assistant()
            assistant.preload_models()
            events = _read_calendar_events(assistant)
            _assistant_ready = True
            _assistant_startup_error = None
            return events
        except Exception as error:
            _assistant_ready = False
            _assistant_startup_error = str(error)
            _assistant_logger.exception("Не удалось подготовить ассистента при запуске")
            raise


def _require_assistant_ready():
    if not _assistant_ready:
        reason = _assistant_startup_error or "модели ещё загружаются"
        raise RuntimeError(f"Ассистент пока не готов: {reason}")


def _play_audio_script(audio_data: str):
    if not audio_data:
        return None
    script = (
        '(() => { if (!window.__voiceOutputEnabled) return; '
        'const C = window.AudioContext || window.webkitAudioContext; '
        'const context = window.__assistantAudioContext || new C(); '
        'window.__assistantAudioContext = context; '
        'fetch("data:audio/wav;base64,' + audio_data + '").then(r => r.arrayBuffer()) '
        '.then(data => context.resume().then(() => context.decodeAudioData(data))) '
        '.then(buffer => { if (!window.__voiceOutputEnabled) return; '
        'try { window.__assistantAudioSource?.stop(); } catch (_) {} '
        'const source = context.createBufferSource(); window.__assistantAudioSource = source; '
        'source.buffer = buffer; source.connect(context.destination); '
        'source.onended = () => { if (window.__assistantAudioSource === source) '
        'window.__assistantAudioSource = null; }; source.start(); }) '
        '.catch(error => console.error("Не удалось воспроизвести ответ:", error)); })()'
    )
    return rx.call_script(script)


def _process_text(text: str, session_id: str, voice_output: bool) -> tuple[str, str, list[dict]]:
    with _assistant_lock:
        _require_assistant_ready()
        assistant = _get_assistant()
        answer = assistant.run(text, text_output=False, session_id=session_id)
        audio_data = ""
        if voice_output:
            try:
                spoken_answer = _limit_spoken_answer(answer)
                audio_data = base64.b64encode(assistant.synthesize_response(spoken_answer)).decode("ascii")
            except Exception:
                _assistant_logger.exception("Не удалось озвучить ответ")
        events = _read_calendar_events(assistant)
        return answer, audio_data, events


def _process_audio(
    audio_bytes: bytes,
    session_id: str,
    voice_output: bool,
) -> tuple[str, str, str, list[dict]]:
    _assistant_logger.info("[VOICE]: Декодирование аудио (%d байт)", len(audio_bytes))
    samples = decode_audio_bytes(audio_bytes, sample_rate=8_000)
    with _assistant_lock:
        _require_assistant_ready()
        assistant = _get_assistant()
        _assistant_logger.info("[VOICE]: Начинаю распознавание STT (%d отсчётов)", len(samples))
        transcript = assistant.process_input(samples, sample_rate=8_000)
        _assistant_logger.info("[VOICE]: STT завершено, распознано %d символов", len(transcript))
        _assistant_logger.info("[VOICE]: Начинаю обработку запроса ассистентом")
        answer = assistant.run(transcript, text_output=False, session_id=session_id)
        _assistant_logger.info("[VOICE]: Обработка запроса завершена")
        audio_data = ""
        if voice_output:
            try:
                spoken_answer = _limit_spoken_answer(answer)
                audio_data = base64.b64encode(assistant.synthesize_response(spoken_answer)).decode("ascii")
            except Exception:
                _assistant_logger.exception("Не удалось озвучить ответ")
        events = _read_calendar_events(assistant)
    return transcript, answer, audio_data, events


def _limit_spoken_answer(answer: str, limit: int = 900) -> str:
    if len(normalize_text_for_speech(answer)) <= limit:
        return answer

    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    marker = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
    item_indexes = [index for index, line in enumerate(lines) if marker.match(line)]

    if item_indexes:
        intro = "\n".join(lines[:item_indexes[0]])
        groups = []
        for position, start in enumerate(item_indexes):
            end = item_indexes[position + 1] if position + 1 < len(item_indexes) else len(lines)
            groups.append("\n".join(lines[start:end]))
        chosen = intro if len(normalize_text_for_speech(intro)) <= limit else ""
        omitted = False
        for group in groups:
            candidate = "\n".join(part for part in (chosen, group) if part)
            if len(normalize_text_for_speech(candidate)) > limit:
                omitted = True
                break
            chosen = candidate
        if omitted and chosen:
            suffix = "Остальные планы можно посмотреть в чате."
            if len(normalize_text_for_speech(f"{chosen}\n{suffix}")) <= limit:
                chosen = f"{chosen}\n{suffix}"
        return chosen or "Список планов слишком длинный для озвучивания. Посмотрите его в чате."

    sentences = re.findall(r"[^.!?…]+(?:[.!?…]+|$)", " ".join(lines))
    chosen = ""
    omitted = False
    for sentence in sentences:
        candidate = f"{chosen} {sentence.strip()}".strip()
        if len(normalize_text_for_speech(candidate)) > limit:
            omitted = True
            break
        chosen = candidate
    if omitted and chosen:
        suffix = "Остальное можно посмотреть в чате."
        if len(normalize_text_for_speech(f"{chosen} {suffix}")) <= limit:
            chosen = f"{chosen} {suffix}"
    return chosen or "Ответ слишком длинный для озвучивания. Посмотрите его в чате."


def _assistant_is_ready() -> bool:
    return _assistant_ready
