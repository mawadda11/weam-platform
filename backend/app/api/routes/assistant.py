from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import get_db
from app.models.assistant import AssistantMessage, AssistantThread
from app.models.care_team import AccessAuditLog
from app.models.user import User
from app.schemas.assistant import (
    AssistantAnswer,
    AssistantMessagePublic,
    AssistantQuestion,
    AssistantSourcePublic,
    AssistantThreadCreate,
    AssistantThreadPublic,
)
from app.services.access import require_child_access
from app.services.assistant_generation import generate_grounded_answer
from app.services.assistant_rag import (
    collect_authorized_sources,
    retrieve,
)

router = APIRouter(tags=["ai-assistant"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)



def _friendly_thread_title(question: str) -> str:
    """Generate short, readable Arabic labels for the conversation sidebar."""
    value = " ".join(question.strip().split())
    normalized = (
        value.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
    )

    if any(term in normalized for term in ("لخص", "ملخص", "اخر المعلومات", "الوضع")):
        return "ملخص ملف الطفل"
    if any(term in normalized for term in ("هدف", "اهداف", "التقدم", "نسبه التقدم")):
        return "الأهداف والتقدم"
    if any(term in normalized for term in ("تقرير", "تقارير", "النتائج")):
        return "آخر التقارير"
    if any(term in normalized for term in ("صوت", "ملاحظه صوتيه", "ملاحظات صوتيه")):
        return "الملاحظات الصوتية"
    if any(term in normalized for term in ("متابعه", "القادمه", "التالي", "موعد")):
        return "المتابعة القادمة"
    if any(term in normalized for term in ("احتياج", "احتياجات", "يحتاج")):
        return "الاحتياجات الحالية"

    return value[:42] + ("…" if len(value) > 42 else "")



def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    thread_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="assistant_thread",
            entity_id=thread_id,
            details=details or {},
        )
    )


def _thread_or_404(db: Session, thread_id: str) -> AssistantThread:
    thread = db.scalar(
        select(AssistantThread)
        .options(selectinload(AssistantThread.messages))
        .where(AssistantThread.id == thread_id)
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    return thread


def _serialize_message(message: AssistantMessage) -> AssistantMessagePublic:
    sources = [
        AssistantSourcePublic.model_validate(source)
        for source in (message.sources_json or [])
    ]
    return AssistantMessagePublic(
        id=message.id,
        role=message.role,
        content=message.content,
        sources=sources,
        created_at=message.created_at,
    )


def _serialize_thread(thread: AssistantThread) -> AssistantThreadPublic:
    last = thread.messages[-1] if thread.messages else None
    return AssistantThreadPublic(
        id=thread.id,
        child_id=thread.child_id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_message=_serialize_message(last) if last else None,
    )


@router.get(
    "/children/{child_id}/assistant/threads",
    response_model=list[AssistantThreadPublic],
)
def list_threads(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AssistantThreadPublic]:
    require_child_access(
        db,
        child_id,
        user,
        CarePermission.VIEW_PROFILE.value,
    )
    threads = db.scalars(
        select(AssistantThread)
        .options(selectinload(AssistantThread.messages))
        .where(
            AssistantThread.child_id == child_id,
            AssistantThread.created_by_user_id == user.id,
        )
        .order_by(AssistantThread.updated_at.desc())
    ).unique().all()
    return [_serialize_thread(thread) for thread in threads]


@router.post(
    "/children/{child_id}/assistant/threads",
    response_model=AssistantThreadPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_thread(
    child_id: str,
    payload: AssistantThreadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssistantThreadPublic:
    require_child_access(
        db,
        child_id,
        user,
        CarePermission.VIEW_PROFILE.value,
    )
    title = (
        " ".join(payload.title.strip().split())
        if payload.title
        else "محادثة جديدة مع مساعد وئام"
    )
    thread = AssistantThread(
        child_id=child_id,
        created_by_user_id=user.id,
        title=title,
    )
    db.add(thread)
    db.flush()
    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="assistant_thread_created",
        thread_id=thread.id,
    )
    db.commit()
    db.refresh(thread)
    return _serialize_thread(thread)


@router.get(
    "/assistant/threads/{thread_id}/messages",
    response_model=list[AssistantMessagePublic],
)
def list_messages(
    thread_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AssistantMessagePublic]:
    thread = _thread_or_404(db, thread_id)
    if thread.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Assistant thread not found")
    require_child_access(
        db,
        thread.child_id,
        user,
        CarePermission.VIEW_PROFILE.value,
    )
    return [_serialize_message(message) for message in thread.messages]


@router.delete(
    "/assistant/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    thread = _thread_or_404(db, thread_id)
    if thread.created_by_user_id != user.id:
        # Keep private thread existence hidden from other users.
        raise HTTPException(status_code=404, detail="Assistant thread not found")

    require_child_access(
        db,
        thread.child_id,
        user,
        CarePermission.VIEW_PROFILE.value,
    )

    child_id = thread.child_id
    title = thread.title
    message_count = len(thread.messages)

    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="assistant_thread_deleted",
        thread_id=thread.id,
        details={
            "title": title,
            "message_count": message_count,
        },
    )
    db.delete(thread)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/assistant/threads/{thread_id}/ask",
    response_model=AssistantAnswer,
)
def ask_assistant(
    thread_id: str,
    payload: AssistantQuestion,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AssistantAnswer:
    thread = _thread_or_404(db, thread_id)
    if thread.created_by_user_id != user.id:
        raise HTTPException(status_code=404, detail="Assistant thread not found")

    grant = require_child_access(
        db,
        thread.child_id,
        user,
        CarePermission.VIEW_PROFILE.value,
    )

    user_message = AssistantMessage(
        thread_id=thread.id,
        role="user",
        content=payload.question,
        sources_json=[],
    )
    db.add(user_message)
    db.flush()

    chunks = collect_authorized_sources(
        db,
        child_id=thread.child_id,
        user=user,
        grant=grant,
    )
    matched = retrieve(payload.question, chunks, limit=5)

    source_payload = [
        {
            "index": index,
            "source_type": source.source_type,
            "source_id": source.source_id,
            "title": source.title,
            "snippet": (
                source.text
                if len(source.text) <= 450
                else source.text[:447].rstrip() + "..."
            ),
            "occurred_at": (
                source.occurred_at.isoformat()
                if source.occurred_at
                else None
            ),
        }
        for index, source in enumerate(matched, start=1)
    ]
    generated = generate_grounded_answer(
        question=payload.question,
        sources=matched,
    )

    assistant_message = AssistantMessage(
        thread_id=thread.id,
        role="assistant",
        content=generated.text,
        sources_json=source_payload,
    )
    thread.updated_at = utcnow()
    if len(thread.messages) == 0 and thread.title == "محادثة جديدة مع مساعد وئام":
        thread.title = _friendly_thread_title(payload.question)

    db.add(assistant_message)
    db.add(thread)
    _audit(
        db,
        child_id=thread.child_id,
        actor_user_id=user.id,
        action="assistant_question_answered",
        thread_id=thread.id,
        details={
            "source_count": len(source_payload),
            "provider": generated.provider,
            "model": generated.model,
            "used_fallback": generated.used_fallback,
        },
    )
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    thread = _thread_or_404(db, thread.id)

    return AssistantAnswer(
        thread=_serialize_thread(thread),
        user_message=_serialize_message(user_message),
        assistant_message=_serialize_message(assistant_message),
    )
