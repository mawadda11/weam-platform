from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class VoiceNoteReview(BaseModel):
    review_status: Literal["approved", "rejected"]
    transcript: str = Field(min_length=1, max_length=20000)


class VoiceNotePublic(BaseModel):
    id: str
    child_id: str
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    duration_seconds: int | None
    transcription_status: Literal["not_started", "completed", "failed"]
    review_status: Literal["not_started", "draft", "approved", "rejected"]
    transcript_draft: str | None
    transcript_final: str | None
    transcript_language: str | None
    stt_provider: str | None
    stt_model: str | None
    error_message: str | None
    created_by_user_id: str
    created_by_name: str
    reviewed_by_user_id: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
