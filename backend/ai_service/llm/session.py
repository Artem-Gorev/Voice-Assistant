from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DialogSession:
    missing_field: str
    partial_data: dict[str, Any]
    last_reply_text: str | None = None
    updated_at: datetime = field(default_factory=datetime.now)


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, DialogSession] = {}

    def get(self, session_id: str) -> DialogSession | None:
        return self._sessions.get(session_id)

    def save(self, session_id: str, session: DialogSession) -> None:
        self._sessions[session_id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._sessions

    def __getitem__(self, session_id: str) -> DialogSession:
        return self._sessions[session_id]
