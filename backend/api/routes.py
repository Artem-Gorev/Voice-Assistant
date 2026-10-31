import asyncio
import io
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from scipy.io import wavfile

from backend.api.schemas import ChatRequest, ChatResponse, EventResponse, SpeakRequest

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Сообщение не должно быть пустым")
    try:
        reply = await asyncio.to_thread(
            request.app.state.runtime.chat,
            message,
            payload.session_id,
            payload.request_id,
        )
        return ChatResponse(reply=reply)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/events", response_model=list[EventResponse])
async def events(request: Request, event_date: date):
    try:
        result = await asyncio.to_thread(request.app.state.runtime.events, event_date)
        return [EventResponse(**event) for event in result]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Не удалось получить события") from exc


@router.post("/voice/transcribe")
async def transcribe_voice(request: Request):
    audio_bytes = await request.body()
    if not audio_bytes or len(audio_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Аудиозапись пустая или превышает 20 МБ")
    if request.headers.get("content-type", "").split(";")[0] not in {"audio/wav", "audio/x-wav"}:
        raise HTTPException(status_code=415, detail="Ожидается WAV-аудио")
    try:
        sample_rate, audio = wavfile.read(io.BytesIO(audio_bytes))
        if audio.ndim == 2:
            audio = audio.mean(axis=1).astype(audio.dtype)
        text = await asyncio.to_thread(
            request.app.state.runtime.transcribe_audio, audio, sample_rate
        )
        return {"text": text}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, EOFError) as exc:
        raise HTTPException(status_code=422, detail="Не удалось прочитать WAV-аудио") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/speech")
async def synthesize_speech(payload: SpeakRequest, request: Request):
    try:
        audio = await asyncio.to_thread(request.app.state.runtime.synthesize_speech, payload.text)
        return Response(content=audio, media_type="audio/wav")
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
