from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReportAIAnalysisCreate(BaseModel):
    report_version_id: str | None = Field(default=None, max_length=36)


class ReportAIAnalysisReview(BaseModel):
    review_status: Literal["approved", "rejected"]
    edited_result: dict | None = None


class ReportAIAnalysisPublic(BaseModel):
    id: str
    child_id: str
    report_id: str
    report_version_id: str
    report_version_number: int
    provider: str
    model: str
    analysis_status: Literal["completed", "failed"]
    review_status: Literal["draft", "approved", "rejected"]
    result: dict
    error_message: str | None
    created_by_user_id: str
    created_by_name: str
    reviewed_by_user_id: str | None
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
