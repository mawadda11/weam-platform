from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ConversationCreate(BaseModel):
    kind: Literal["direct", "group"]
    title: str | None = Field(default=None, max_length=180)
    participant_user_ids: list[str] = Field(min_length=1, max_length=30)

    @field_validator("participant_user_ids")
    @classmethod
    def unique_participants(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result


class ConversationParticipantPublic(BaseModel):
    user_id: str
    full_name: str
    role_label: str | None = None


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty")
        return cleaned


class ChatMessagePublic(BaseModel):
    id: str
    conversation_id: str
    sender_user_id: str
    sender_name: str
    body: str
    created_at: datetime


class ConversationPublic(BaseModel):
    id: str
    child_id: str
    kind: Literal["direct", "group"]
    title: str
    participants: list[ConversationParticipantPublic]
    last_message: ChatMessagePublic | None
    created_at: datetime
    updated_at: datetime
