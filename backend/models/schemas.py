from datetime import date, datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CreateEventData(BaseModel):
    title: str = Field(min_length=1)
    start_time: str = Field(description="Strict ISO 8601 format (YYYY-MM-DDTHH:MM:SS)")
    end_time: Optional[str] = Field(default=None, description="Strict ISO 8601 format (YYYY-MM-DDTHH:MM:SS)")
    category: Optional[str] = "Другое"
    description: Optional[str] = None

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
    def validate_end_time(cls, v: Optional[str]) -> Optional[str]:
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
    date: str = Field(description="Format YYYY-MM-DD")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except Exception as e:
            raise ValueError(f"date must be in valid format (YYYY-MM-DD): {e}")
        return v


class SearchEventsData(BaseModel):
    query: str = Field(min_length=1)
    date_from: Optional[str] = None
    date_to: Optional[str] = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("query cannot be empty or whitespace only")
        return cleaned


class ClarifyData(BaseModel):
    missing_field: str = Field(description="Name of the missing field, e.g., 'start_time'")
    partial_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LLMResponseSchema(BaseModel):
    action: Literal["create_event", "list_events", "search_events", "clarify", "chat"]
    data: Dict[str, Any]
    reply_text: Optional[str] = None

    @model_validator(mode="after")
    def validate_action_data(self) -> "LLMResponseSchema":
        action_map = {
            "create_event": CreateEventData,
            "list_events": ListEventsData,
            "search_events": SearchEventsData,
            "clarify": ClarifyData,
        }
        schema_cls = action_map.get(self.action)
        if schema_cls:
            self.data = schema_cls.model_validate(self.data).model_dump()
        elif self.action == "chat":
            if not isinstance(self.data, dict):
                self.data = {}
        return self
