"""HTTP client for the assistant backend."""

import os

import httpx


def _base_url() -> str:
    return os.getenv("ASSISTANT_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")


async def send_message(message: str, session_id: str, request_id: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{_base_url()}/chat",
            json={"message": message, "session_id": session_id, "request_id": request_id},
        )
        response.raise_for_status()
        return response.json()["reply"]


async def get_events(event_date: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{_base_url()}/events", params={"event_date": event_date}
        )
        response.raise_for_status()
        return response.json()
