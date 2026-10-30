from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class CreateEventData(BaseModel):
    title: str = Field(min_length=1)
    start_time: str = Field(description="Strict ISO 8601 format (YYYY-MM-DDTHH:MM:SS)")
    end_time: str | None = Field(default=None, description="Strict ISO 8601 format (YYYY-MM-DDTHH:MM:SS)")
    category: str | None = "Другое"
    description: str | None = None
    recurrence: Literal["daily", "weekly", "monthly"] | None = None
    recurrence_count: int | None = Field(default=None, ge=2, le=52)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("title cannot be empty or whitespace only")
        return cleaned

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except Exception as e:
            raise ValueError(f"start_time must be in valid ISO 8601 format: {e}")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                datetime.fromisoformat(v)
            except Exception as e:
                raise ValueError(f"end_time must be in valid ISO 8601 format: {e}")
        return v

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateEventData":
        if self.end_time:
            start_dt = datetime.fromisoformat(self.start_time)
            end_dt = datetime.fromisoformat(self.end_time)
            if end_dt <= start_dt:
                raise ValueError("end_time must be chronologically after start_time")
        return self


class ListEventsData(BaseModel):
    date: str | None = Field(default=None, description="Single day in YYYY-MM-DD format")
    date_from: str | None = Field(default=None, description="Range start in YYYY-MM-DD format")
    date_to: str | None = Field(default=None, description="Range end in YYYY-MM-DD format")
    time_from: str | None = Field(default=None, description="Optional time range start (HH:MM)")
    time_to: str | None = Field(default=None, description="Optional time range end (HH:MM)")

    @field_validator("date", "date_from", "date_to")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except ValueError as error:
            raise ValueError(f"date must be in valid format (YYYY-MM-DD): {error}") from error
        return v

    @field_validator("time_from", "time_to")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as error:
            raise ValueError("time must be in HH:MM format") from error
        return value

    @model_validator(mode="after")
    def validate_date_selector(self) -> "ListEventsData":
        if self.date is not None:
            if self.date_from is not None or self.date_to is not None:
                raise ValueError("Use either date or the date_from/date_to range")
            return self

        if self.date_from is None or self.date_to is None:
            raise ValueError("Provide date or both date_from and date_to")
        if date.fromisoformat(self.date_from) > date.fromisoformat(self.date_to):
            raise ValueError("date_from must be on or before date_to")
        return self


class SearchEventsData(BaseModel):
    query: str = Field(min_length=1)
    date_from: str | None = None
    date_to: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("query cannot be empty or whitespace only")
        return cleaned


class ClarifyData(BaseModel):
    missing_field: str = Field(description="Name of the missing field, e.g., 'start_time'")
    partial_data: dict[str, Any] | None = Field(default_factory=dict)


class EventChangeData(BaseModel):
    query: str | None = None
    event_id: int | None = None
    new_start_time: datetime | None = None
    new_date: date | None = None
    new_time: str | None = None
    new_title: str | None = None
    target_date: date | None = None
    target_time: str | None = None
    scope: Literal["one", "series", "all"] = "one"


class EventTargetData(BaseModel):
    query: str | None = None
    event_id: int | None = None
    target_date: date | None = None
    target_time: str | None = None
    scope: Literal["one", "series", "all"] = "one"


class LLMResult(BaseModel):
    action: Literal["create_event", "list_events", "search_events", "update_event", "delete_event", "complete_event", "clarify", "chat"]
    data: dict[str, Any]
    reply_text: str | None = None

    @model_validator(mode="after")
    def validate_action_data(self) -> "LLMResult":
        action_map = {
            "create_event": CreateEventData,
            "list_events": ListEventsData,
            "search_events": SearchEventsData,
            "update_event": EventChangeData,
            "delete_event": EventTargetData,
            "complete_event": EventTargetData,
            "clarify": ClarifyData,
        }
        schema_cls = action_map.get(self.action)
        if schema_cls:
            self.data = schema_cls.model_validate(self.data).model_dump()
        elif self.action == "chat":
            if not isinstance(self.data, dict):
                self.data = {}
        return self


LLMResponseSchema = LLMResult
