from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import get_db
from app.models.care_team import AccessAuditLog
from app.models.user import User
from app.models.voice_note import VoiceNote
from app.schemas.voice_note import VoiceNotePublic, VoiceNoteReview
from app.services.access import require_child_access
from app.services.speech_to_text import SpeechToTextError, transcribe_audio
from app.services.storage import LocalVoiceStorage, StorageValidationError

router = APIRouter(tags=["voice-notes"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    note_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="voice_note",
            entity_id=note_id,
            details=details or {},
        )
    )


def _note_or_404(db: Session, note_id: str) -> VoiceNote:
    note = db.get(VoiceNote, note_id)
    if not note or note.is_archived:
        raise HTTPException(status_code=404, detail="Voice note not found")
    return note


def _can_manage(grant) -> bool:
    return grant.is_primary_guardian or grant.allows(
        CarePermission.CREATE_VOICE_NOTES.value
    )


def _serialize(
    db: Session,
    note: VoiceNote,
    *,
    can_manage: bool,
) -> VoiceNotePublic:
    creator = db.get(User, note.created_by_user_id)
    reviewer = db.get(User, note.reviewed_by_user_id) if note.reviewed_by_user_id else None

    # Draft text is intentionally hidden from view-only members. They only
    # receive the transcript after human approval.
    draft = note.transcript_draft if can_manage else None
    final = note.transcript_final if note.review_status == "approved" else None

    return VoiceNotePublic(
        id=note.id,
        child_id=note.child_id,
        title=note.title,
        original_filename=note.original_filename,
        content_type=note.content_type,
        size_bytes=note.size_bytes,
        duration_seconds=note.duration_seconds,
        transcription_status=note.transcription_status,
        review_status=note.review_status,
        transcript_draft=draft,
        transcript_final=final,
        transcript_language=note.transcript_language,
        stt_provider=note.stt_provider,
        stt_model=note.stt_model,
        error_message=note.error_message if can_manage else None,
        created_by_user_id=note.created_by_user_id,
        created_by_name=creator.full_name if creator else "مستخدم وئام",
        reviewed_by_user_id=note.reviewed_by_user_id,
        reviewed_by_name=reviewer.full_name if reviewer else None,
        reviewed_at=note.reviewed_at,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get(
    "/children/{child_id}/voice-notes",
    response_model=list[VoiceNotePublic],
)
def list_voice_notes(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[VoiceNotePublic]:
    grant = require_child_access(
        db, child_id, user, CarePermission.VIEW_VOICE_NOTES.value
    )
    notes = db.scalars(
        select(VoiceNote)
        .where(
            VoiceNote.child_id == child_id,
            VoiceNote.is_archived.is_(False),
        )
        .order_by(VoiceNote.created_at.desc())
    ).all()
    return [_serialize(db, note, can_manage=_can_manage(grant)) for note in notes]


@router.post(
    "/children/{child_id}/voice-notes",
    response_model=VoiceNotePublic,
    status_code=status.HTTP_201_CREATED,
)
def create_voice_note(
    child_id: str,
    title: str = Form(..., min_length=1, max_length=180),
    duration_seconds: int | None = Form(default=None, ge=0, le=60 * 60),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VoiceNotePublic:
    grant = require_child_access(
        db, child_id, user, CarePermission.CREATE_VOICE_NOTES.value
    )

    clean_title = " ".join(title.strip().split())
    if not clean_title:
        raise HTTPException(status_code=422, detail="Voice note title is required")

    note_id = str(uuid.uuid4())
    storage = LocalVoiceStorage()
    try:
        stored = storage.save_upload(
            file,
            child_id=child_id,
            voice_note_id=note_id,
        )
    except StorageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    note = VoiceNote(
        id=note_id,
        child_id=child_id,
        title=clean_title,
        original_filename=(file.filename or "voice-note").strip()[:255] or "voice-note",
        content_type=stored.content_type,
        storage_key=stored.key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        duration_seconds=duration_seconds,
        created_by_user_id=user.id,
    )
    db.add(note)
    db.flush()
    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="voice_note_created",
        note_id=note.id,
        details={"title": note.title},
    )
    db.commit()
    db.refresh(note)
    return _serialize(db, note, can_manage=_can_manage(grant))


@router.get("/voice-notes/{note_id}/audio")
def download_voice_note(
    note_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    note = _note_or_404(db, note_id)
    require_child_access(
        db, note.child_id, user, CarePermission.VIEW_VOICE_NOTES.value
    )
    try:
        path = LocalVoiceStorage().resolve(note.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Audio file not found") from exc
    return FileResponse(
        path,
        media_type=note.content_type,
        filename=note.original_filename,
    )


@router.post(
    "/voice-notes/{note_id}/transcribe",
    response_model=VoiceNotePublic,
)
def transcribe_voice_note(
    note_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VoiceNotePublic:
    note = _note_or_404(db, note_id)
    grant = require_child_access(
        db, note.child_id, user, CarePermission.CREATE_VOICE_NOTES.value
    )
    try:
        path = LocalVoiceStorage().resolve(note.storage_key)
        result = transcribe_audio(path=path, title=note.title)
        note.transcription_status = "completed"
        note.review_status = "draft"
        note.transcript_draft = result.transcript
        note.transcript_final = None
        note.transcript_language = result.language
        note.stt_provider = result.provider
        note.stt_model = result.model
        note.error_message = None
    except (FileNotFoundError, SpeechToTextError) as exc:
        note.transcription_status = "failed"
        note.review_status = "not_started"
        note.error_message = str(exc)

    db.add(note)
    db.flush()
    _audit(
        db,
        child_id=note.child_id,
        actor_user_id=user.id,
        action="voice_note_transcribed",
        note_id=note.id,
        details={
            "provider": note.stt_provider,
            "status": note.transcription_status,
        },
    )
    db.commit()
    db.refresh(note)
    return _serialize(db, note, can_manage=_can_manage(grant))


@router.patch(
    "/voice-notes/{note_id}/review",
    response_model=VoiceNotePublic,
)
def review_voice_note(
    note_id: str,
    payload: VoiceNoteReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VoiceNotePublic:
    note = _note_or_404(db, note_id)
    grant = require_child_access(
        db, note.child_id, user, CarePermission.CREATE_VOICE_NOTES.value
    )
    if note.transcription_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voice note must be transcribed before review",
        )

    clean = payload.transcript.strip()
    note.transcript_draft = clean
    note.review_status = payload.review_status
    note.reviewed_by_user_id = user.id
    note.reviewed_at = utcnow()
    note.transcript_final = clean if payload.review_status == "approved" else None

    db.add(note)
    db.flush()
    _audit(
        db,
        child_id=note.child_id,
        actor_user_id=user.id,
        action="voice_note_reviewed",
        note_id=note.id,
        details={"review_status": note.review_status},
    )
    db.commit()
    db.refresh(note)
    return _serialize(db, note, can_manage=_can_manage(grant))


@router.delete(
    "/voice-notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def archive_voice_note(
    note_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    note = _note_or_404(db, note_id)
    require_child_access(
        db, note.child_id, user, CarePermission.CREATE_VOICE_NOTES.value
    )
    note.is_archived = True
    _audit(
        db,
        child_id=note.child_id,
        actor_user_id=user.id,
        action="voice_note_archived",
        note_id=note.id,
    )
    db.commit()
