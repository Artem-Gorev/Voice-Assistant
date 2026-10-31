import asyncio
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .assistant_service import _process_audio

_audio_dir_setting = Path(
    os.getenv("AUDIO_RECORDINGS_DIR", str(Path(tempfile.gettempdir()) / "aura_recordings"))
)
AUDIO_DIR = _audio_dir_setting.expanduser().resolve()
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

    with temp_path.open("ab") as audio_file:

        audio_file.write(data)

    return {"ok": True, "bytes": len(data)}


async def audio_finish(recording_id: str, request: Request):

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
    session_id = request.headers.get("X-Reflex-Client-Token", "voice")[:128] or "voice"
    voice_output = request.headers.get("X-Voice-Output", "false").lower() == "true"
    try:
        transcript, answer, audio_data, events = await asyncio.to_thread(
            _process_audio,
            final_path.read_bytes(),
            session_id,
            voice_output,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "path": final_path.as_posix(),
            "bytes": final_path.stat().st_size,
        }

    return {
        "ok": True,
        "path": final_path.as_posix(),
        "bytes": final_path.stat().st_size,
        "transcript": transcript,
        "response": answer,
        "audio_data": audio_data,
        "events": events,
    }


async def audio_cancel(recording_id: str):

    try:

        safe_id = str(uuid.UUID(recording_id))

    except ValueError:

        raise HTTPException(status_code=400, detail="Invalid recording id")

    (AUDIO_DIR / f".{safe_id}.part").unlink(missing_ok=True)

    return {"ok": True}


async def _audio_route(
    request: Request,
    handler,
    needs_body: bool = False,
    needs_request: bool = False,
):

    try:

        recording_id = request.path_params["recording_id"]

        if needs_request:
            result = await handler(recording_id, request)
        elif needs_body:
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

    return await _audio_route(request, audio_finish, needs_request=True)


async def _audio_cancel_route(request: Request):

    return await _audio_route(request, audio_cancel)


def audio_api_transformer(api):

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("AUDIO_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if allowed_origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Accept", "X-Reflex-Client-Token", "X-Voice-Output"],
        )
    else:
        api.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
            allow_methods=["POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Accept", "X-Reflex-Client-Token", "X-Voice-Output"],
        )

    api.add_route("/audio/start/{recording_id}", _audio_start_route, methods=["POST"])

    api.add_route("/audio/chunk/{recording_id}", _audio_chunk_route, methods=["POST"])

    api.add_route("/audio/finish/{recording_id}", _audio_finish_route, methods=["POST"])

    api.add_route("/audio/cancel/{recording_id}", _audio_cancel_route, methods=["DELETE"])

    return api
