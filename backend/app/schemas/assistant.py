from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AssistantThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=180)


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=2000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Question is too short")
        return cleaned


class AssistantSourcePublic(BaseModel):
    index: int
    source_type: str
    source_id: str
    title: str
    snippet: str
    occurred_at: datetime | None = None


class AssistantMessagePublic(BaseModel):
    id: str
    role: str
    content: str
    sources: list[AssistantSourcePublic]
    created_at: datetime


class AssistantThreadPublic(BaseModel):
    id: str
    child_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: AssistantMessagePublic | None = None


class AssistantAnswer(BaseModel):
    thread: AssistantThreadPublic
    user_message: AssistantMessagePublic
    assistant_message: AssistantMessagePublic
