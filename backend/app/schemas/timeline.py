from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TimelineEventPublic(BaseModel):
    id: str
    event_type: str
    title: str
    description: str | None
    actor_user_id: str | None
    actor_name: str | None
    occurred_at: datetime
    data: dict
