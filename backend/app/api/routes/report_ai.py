from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import get_db
from app.models.care_team import AccessAuditLog
from app.models.report import Report, ReportVersion
from app.models.report_ai import ReportAIAnalysis
from app.models.user import User
from app.schemas.report_ai import (
    ReportAIAnalysisCreate,
    ReportAIAnalysisPublic,
    ReportAIAnalysisReview,
)
from app.services.access import require_child_access
from app.services.ai_reports import AIReportError, analyze_report_file
from app.services.follow_up_notifications import can_manage_follow_ups, sync_analysis_followups
from app.services.storage import LocalReportStorage

router = APIRouter(tags=["report-ai"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    analysis_id: str,
    report_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="report_ai_analysis",
            entity_id=analysis_id,
            details={"report_id": report_id, **(details or {})},
        )
    )


def _report_query(report_id: str):
    return (
        select(Report)
        .options(selectinload(Report.versions))
        .where(Report.id == report_id)
    )


def _report_or_404(db: Session, report_id: str) -> Report:
    report = db.scalar(_report_query(report_id))
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def _visible_grant(db: Session, report: Report, user: User):
    grant = require_child_access(
        db,
        report.child_id,
        user,
        CarePermission.VIEW_REPORTS.value,
    )
    if grant.is_primary_guardian or report.visibility == "care_team":
        return grant
    if user.id in (report.allowed_user_ids or []):
        return grant
    raise HTTPException(status_code=404, detail="Report not found")


def _version_or_404(
    report: Report,
    version_id: str | None,
) -> ReportVersion:
    versions = sorted(
        list(report.versions or []),
        key=lambda item: item.version_number,
        reverse=True,
    )
    if not versions:
        raise HTTPException(status_code=404, detail="Report version not found")
    if not version_id:
        return versions[0]
    for version in versions:
        if version.id == version_id:
            return version
    raise HTTPException(status_code=404, detail="Report version not found")


def _analysis_or_404(db: Session, analysis_id: str) -> ReportAIAnalysis:
    analysis = db.get(ReportAIAnalysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="AI analysis not found")
    return analysis


def _serialize(
    db: Session,
    analysis: ReportAIAnalysis,
) -> ReportAIAnalysisPublic:
    creator = db.get(User, analysis.created_by_user_id)
    reviewer = (
        db.get(User, analysis.reviewed_by_user_id)
        if analysis.reviewed_by_user_id
        else None
    )
    version = db.get(ReportVersion, analysis.report_version_id)
    return ReportAIAnalysisPublic(
        id=analysis.id,
        child_id=analysis.child_id,
        report_id=analysis.report_id,
        report_version_id=analysis.report_version_id,
        report_version_number=version.version_number if version else 0,
        provider=analysis.provider,
        model=analysis.model,
        analysis_status=analysis.analysis_status,
        review_status=analysis.review_status,
        result=dict(analysis.result_json or {}),
        error_message=analysis.error_message,
        created_by_user_id=analysis.created_by_user_id,
        created_by_name=creator.full_name if creator else "مستخدم وئام",
        reviewed_by_user_id=analysis.reviewed_by_user_id,
        reviewed_by_name=reviewer.full_name if reviewer else None,
        reviewed_at=analysis.reviewed_at,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.get(
    "/reports/{report_id}/ai-analyses",
    response_model=list[ReportAIAnalysisPublic],
)
def list_report_ai_analyses(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReportAIAnalysisPublic]:
    report = _report_or_404(db, report_id)
    _visible_grant(db, report, user)
    analyses = db.scalars(
        select(ReportAIAnalysis)
        .where(ReportAIAnalysis.report_id == report.id)
        .order_by(ReportAIAnalysis.created_at.desc())
    ).all()
    return [_serialize(db, item) for item in analyses]


@router.post(
    "/reports/{report_id}/ai-analyses",
    response_model=ReportAIAnalysisPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_report_ai_analysis(
    report_id: str,
    payload: ReportAIAnalysisCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportAIAnalysisPublic:
    report = _report_or_404(db, report_id)
    _visible_grant(db, report, user)
    require_child_access(
        db,
        report.child_id,
        user,
        CarePermission.UPLOAD_REPORTS.value,
    )
    if report.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived report cannot receive new AI analyses",
        )

    version = _version_or_404(report, payload.report_version_id)

    analysis = ReportAIAnalysis(
        child_id=report.child_id,
        report_id=report.id,
        report_version_id=version.id,
        provider="pending",
        model="pending",
        analysis_status="completed",
        review_status="draft",
        result_json={},
        created_by_user_id=user.id,
    )

    try:
        path = LocalReportStorage().resolve(version.storage_key)
        result = analyze_report_file(
            path=path,
            content_type=version.content_type,
            report_title=report.title,
            report_type=report.report_type,
            source_label=report.source_label,
        )
        analysis.provider = result.provider
        analysis.model = result.model
        analysis.result_json = result.data
        analysis.analysis_status = "completed"
    except (AIReportError, FileNotFoundError) as exc:
        analysis.provider = "failed"
        analysis.model = "unavailable"
        analysis.analysis_status = "failed"
        analysis.error_message = str(exc)
        analysis.result_json = {
            "summary": "",
            "key_findings": [],
            "needs": [],
            "recommendations": [],
            "follow_up_actions": [],
            "goal_mentions": [],
            "source_language": "unknown",
            "evidence": [],
            "limitations": [str(exc)],
            "safety_note": "لم يكتمل التحليل، ولم يتم اعتماد أي نتيجة.",
        }

    db.add(analysis)
    db.flush()
    _audit(
        db,
        child_id=report.child_id,
        actor_user_id=user.id,
        action="report_ai_analysis_created",
        analysis_id=analysis.id,
        report_id=report.id,
        details={
            "version": version.version_number,
            "provider": analysis.provider,
            "status": analysis.analysis_status,
        },
    )
    db.commit()
    db.refresh(analysis)
    return _serialize(db, analysis)


@router.patch(
    "/report-ai-analyses/{analysis_id}/review",
    response_model=ReportAIAnalysisPublic,
)
def review_report_ai_analysis(
    analysis_id: str,
    payload: ReportAIAnalysisReview,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportAIAnalysisPublic:
    analysis = _analysis_or_404(db, analysis_id)
    report = _report_or_404(db, analysis.report_id)
    _visible_grant(db, report, user)
    review_grant = require_child_access(
        db,
        report.child_id,
        user,
        CarePermission.UPLOAD_REPORTS.value,
    )

    if analysis.analysis_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed AI analysis cannot be approved",
        )

    if payload.edited_result is not None:
        merged = dict(analysis.result_json or {})
        for key in {
            "summary",
            "key_findings",
            "needs",
            "recommendations",
            "follow_up_actions",
            "goal_mentions",
            "source_language",
            "evidence",
            "limitations",
            "safety_note",
        }:
            if key in payload.edited_result:
                merged[key] = payload.edited_result[key]
        analysis.result_json = merged

    analysis.review_status = payload.review_status
    analysis.reviewed_by_user_id = user.id
    analysis.reviewed_at = utcnow()

    created_followups = 0
    if analysis.review_status == "approved" and can_manage_follow_ups(review_grant):
        db.flush()
        created_followups = sync_analysis_followups(
            db,
            analysis=analysis,
            report=report,
            created_by_user_id=user.id,
        )

    _audit(
        db,
        child_id=report.child_id,
        actor_user_id=user.id,
        action="report_ai_analysis_reviewed",
        analysis_id=analysis.id,
        report_id=report.id,
        details={
            "review_status": analysis.review_status,
            "automatic_followups_created": created_followups,
        },
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return _serialize(db, analysis)
