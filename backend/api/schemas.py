from datetime import date as DateType, time as TimeType

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="web", min_length=1, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)


class ChatResponse(BaseModel):
    reply: str


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


class EventResponse(BaseModel):
    id: int | None = None
    text: str
    date: DateType | None = None
    time: TimeType | None = None
    status: str | None = None
