from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import get_db
from app.models.follow_up import FollowUp
from app.models.report import Report
from app.models.report_ai import ReportAIAnalysis
from app.models.user import User
from app.schemas.follow_up import (
    FollowUpCreate,
    FollowUpFromAnalysisCreate,
    FollowUpPublic,
    FollowUpSuggestionPublic,
    FollowUpUpdate,
)
from app.services.access import require_child_access
from app.services.follow_up_notifications import (
    can_manage_follow_ups,
    can_view_follow_ups,
    extract_iso_date,
    follow_up_display_status,
    follow_up_source_id,
    sync_approved_followups_for_child,
    utcnow,
)

router = APIRouter(tags=["follow-ups"])


def _follow_up_or_404(db: Session, follow_up_id: str) -> FollowUp:
    item = db.get(FollowUp, follow_up_id)
    if not item:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return item


def _require_view(db: Session, child_id: str, user: User):
    grant = require_child_access(db, child_id, user)
    if not can_view_follow_ups(grant):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return grant


def _require_manage(db: Session, child_id: str, user: User):
    grant = require_child_access(db, child_id, user)
    if not can_manage_follow_ups(grant):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return grant


def _serialize(db: Session, item: FollowUp) -> FollowUpPublic:
    creator = db.get(User, item.created_by_user_id)
    completer = db.get(User, item.completed_by_user_id) if item.completed_by_user_id else None
    return FollowUpPublic(
        id=item.id,
        child_id=item.child_id,
        title=item.title,
        note=item.note,
        due_date=item.due_date,
        status=item.status,
        display_status=follow_up_display_status(item),
        source_type=item.source_type,
        source_id=item.source_id,
        source_label=item.source_label,
        created_by_user_id=item.created_by_user_id,
        created_by_name=creator.full_name if creator else "مستخدم وئام",
        completed_by_user_id=item.completed_by_user_id,
        completed_by_name=completer.full_name if completer else None,
        completed_at=item.completed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _report_visible(report: Report, user: User, grant) -> bool:
    if grant.is_primary_guardian or report.visibility == "care_team":
        return True
    return user.id in (report.allowed_user_ids or [])


@router.get(
    "/children/{child_id}/follow-ups",
    response_model=list[FollowUpPublic],
)
def list_follow_ups(
    child_id: str,
    item_status: str = Query(default="all", alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FollowUpPublic]:
    _require_view(db, child_id, user)
    if item_status not in {"all", "open", "completed"}:
        raise HTTPException(status_code=422, detail="Invalid status")

    statement = (
        select(FollowUp)
        .where(FollowUp.child_id == child_id)
        .order_by(FollowUp.due_date.asc().nullslast(), FollowUp.created_at.desc())
    )
    if item_status != "all":
        statement = statement.where(FollowUp.status == item_status)
    return [_serialize(db, item) for item in db.scalars(statement).all()]


@router.post(
    "/children/{child_id}/follow-ups",
    response_model=FollowUpPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_follow_up(
    child_id: str,
    payload: FollowUpCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FollowUpPublic:
    _require_manage(db, child_id, user)
    item = FollowUp(
        child_id=child_id,
        title=payload.title,
        note=payload.note,
        due_date=payload.due_date,
        status="open",
        source_type="manual",
        created_by_user_id=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(db, item)


@router.patch("/follow-ups/{follow_up_id}", response_model=FollowUpPublic)
def update_follow_up(
    follow_up_id: str,
    payload: FollowUpUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FollowUpPublic:
    item = _follow_up_or_404(db, follow_up_id)
    _require_manage(db, item.child_id, user)
    values = payload.model_dump(exclude_unset=True)
    for field in {"title", "note", "due_date"} & values.keys():
        setattr(item, field, values[field])
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(db, item)


@router.post("/follow-ups/{follow_up_id}/complete", response_model=FollowUpPublic)
def complete_follow_up(
    follow_up_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FollowUpPublic:
    item = _follow_up_or_404(db, follow_up_id)
    _require_manage(db, item.child_id, user)
    if item.status != "completed":
        item.status = "completed"
        item.completed_by_user_id = user.id
        item.completed_at = utcnow()
        db.add(item)
        db.commit()
        db.refresh(item)
    return _serialize(db, item)


@router.post("/follow-ups/{follow_up_id}/reopen", response_model=FollowUpPublic)
def reopen_follow_up(
    follow_up_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FollowUpPublic:
    item = _follow_up_or_404(db, follow_up_id)
    _require_manage(db, item.child_id, user)
    item.status = "open"
    item.completed_by_user_id = None
    item.completed_at = None
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(db, item)


@router.delete("/follow-ups/{follow_up_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_follow_up(
    follow_up_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    item = _follow_up_or_404(db, follow_up_id)
    _require_manage(db, item.child_id, user)
    db.delete(item)
    db.commit()


@router.post("/children/{child_id}/follow-ups/sync-approved-analyses")
def sync_approved_analysis_followups(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    grant = _require_manage(db, child_id, user)
    if not (
        grant.is_primary_guardian
        or grant.allows(CarePermission.VIEW_REPORTS.value)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permission")

    created = sync_approved_followups_for_child(
        db,
        child_id=child_id,
        created_by_user_id=user.id,
    )
    db.commit()
    return {"created": created}


@router.get(
    "/children/{child_id}/follow-up-suggestions",
    response_model=list[FollowUpSuggestionPublic],
)
def follow_up_suggestions(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FollowUpSuggestionPublic]:
    grant = _require_view(db, child_id, user)
    if not (
        grant.is_primary_guardian
        or grant.allows(CarePermission.VIEW_REPORTS.value)
    ):
        return []

    analyses = db.scalars(
        select(ReportAIAnalysis)
        .where(
            ReportAIAnalysis.child_id == child_id,
            ReportAIAnalysis.analysis_status == "completed",
            ReportAIAnalysis.review_status == "approved",
        )
        .order_by(ReportAIAnalysis.reviewed_at.desc().nullslast(), ReportAIAnalysis.created_at.desc())
    ).all()

    seen_reports: set[str] = set()
    suggestions: list[FollowUpSuggestionPublic] = []
    for analysis in analyses:
        if analysis.report_id in seen_reports:
            continue
        report = db.get(Report, analysis.report_id)
        if not report or report.is_archived or not _report_visible(report, user, grant):
            continue
        seen_reports.add(analysis.report_id)
        actions = (analysis.result_json or {}).get("follow_up_actions") or []
        if not isinstance(actions, list):
            continue
        for index, action in enumerate(actions):
            if not isinstance(action, str) or not action.strip():
                continue
            source_id = follow_up_source_id(report.id, " ".join(action.strip().split()))
            existing = db.scalar(
                select(FollowUp.id).where(
                    FollowUp.child_id == child_id,
                    FollowUp.source_type == "report_ai",
                    FollowUp.source_id == source_id,
                )
            )
            suggestions.append(
                FollowUpSuggestionPublic(
                    analysis_id=analysis.id,
                    report_id=report.id,
                    report_title=report.title,
                    action_index=index,
                    action_text=" ".join(action.strip().split()),
                    extracted_due_date=extract_iso_date(action),
                    already_added=existing is not None,
                )
            )
    return suggestions[:20]


@router.post(
    "/report-ai-analyses/{analysis_id}/follow-ups",
    response_model=FollowUpPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_follow_up_from_analysis(
    analysis_id: str,
    payload: FollowUpFromAnalysisCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FollowUpPublic:
    analysis = db.get(ReportAIAnalysis, analysis_id)
    if not analysis or analysis.review_status != "approved" or analysis.analysis_status != "completed":
        raise HTTPException(status_code=404, detail="Approved analysis not found")

    grant = _require_manage(db, analysis.child_id, user)
    if not (
        grant.is_primary_guardian
        or grant.allows(CarePermission.VIEW_REPORTS.value)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permission")

    report = db.get(Report, analysis.report_id)
    if not report or not _report_visible(report, user, grant):
        raise HTTPException(status_code=404, detail="Report not found")

    actions = (analysis.result_json or {}).get("follow_up_actions") or []
    if not isinstance(actions, list) or payload.action_index >= len(actions):
        raise HTTPException(status_code=422, detail="Follow-up action not found")
    action = actions[payload.action_index]
    if not isinstance(action, str) or not action.strip():
        raise HTTPException(status_code=422, detail="Follow-up action not found")

    clean_action = " ".join(action.strip().split())
    source_id = follow_up_source_id(report.id, clean_action)
    duplicate = db.scalar(
        select(FollowUp).where(
            FollowUp.child_id == analysis.child_id,
            FollowUp.source_type == "report_ai",
            FollowUp.source_id == source_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Follow-up already added")

    due_date = payload.due_date or extract_iso_date(clean_action)
    title = (
        " ".join(payload.title.strip().split())
        if payload.title and payload.title.strip()
        else clean_action[:177] + ("..." if len(clean_action) > 177 else "")
    )
    item = FollowUp(
        child_id=analysis.child_id,
        title=title,
        note=payload.note or clean_action,
        due_date=due_date,
        status="open",
        source_type="report_ai",
        source_id=source_id,
        source_label=f"تقرير معتمد · {report.title}",
        created_by_user_id=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(db, item)
