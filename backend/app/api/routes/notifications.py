from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.follow_up import NotificationPublic, NotificationReadRequest
from app.services.follow_up_notifications import (
    collect_notification_events,
    mark_event_keys_read,
    read_event_keys,
)

router = APIRouter(tags=["notifications"])


def _public_events(db: Session, user: User) -> list[NotificationPublic]:
    events = collect_notification_events(db, user=user)
    read = read_event_keys(db, user_id=user.id)
    return [
        NotificationPublic(
            event_key=item.event_key,
            notification_type=item.notification_type,
            title=item.title,
            body=item.body,
            child_id=item.child_id,
            entity_type=item.entity_type,
            entity_id=item.entity_id,
            occurred_at=item.occurred_at,
            is_read=item.event_key in read,
            url=item.url,
        )
        for item in events
    ]


@router.get("/notifications", response_model=list[NotificationPublic])
def list_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NotificationPublic]:
    return _public_events(db, user)


@router.get("/notifications/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    items = _public_events(db, user)
    return {"count": sum(1 for item in items if not item.is_read)}


@router.post("/notifications/read")
def mark_read(
    payload: NotificationReadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    mark_event_keys_read(db, user_id=user.id, event_keys=payload.event_keys)
    db.commit()
    return {"marked": len(payload.event_keys)}


@router.post("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    keys = [item.event_key for item in collect_notification_events(db, user=user)]
    mark_event_keys_read(db, user_id=user.id, event_keys=keys)
    db.commit()
    return {"marked": len(keys)}
