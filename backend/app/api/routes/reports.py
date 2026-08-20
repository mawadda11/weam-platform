from __future__ import annotations

import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.constants import CarePermission, GuardianType
from app.db.session import get_db
from app.models.care_team import AccessAuditLog, CareTeamMembership
from app.models.child import GuardianMembership
from app.models.report import Report, ReportVersion
from app.models.user import User
from app.schemas.report import ReportMetadataUpdate, ReportPublic, ReportVersionPublic
from app.services.access import membership_is_active, require_child_access
from app.services.storage import LocalReportStorage, StorageValidationError

router = APIRouter(tags=["reports"])


def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    report_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="report",
            entity_id=report_id,
            details=details or {},
        )
    )


def _report_query(report_id: str):
    # Refresh objects already present in the SQLAlchemy identity map so a newly
    # committed report version is included immediately in the response.
    return (
        select(Report)
        .options(selectinload(Report.versions))
        .execution_options(populate_existing=True)
        .where(Report.id == report_id)
    )


def _report_or_404(db: Session, report_id: str) -> Report:
    report = db.scalar(_report_query(report_id))
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _can_manage_report(grant) -> bool:
    return grant.is_primary_guardian or grant.allows(CarePermission.MANAGE_PERMISSIONS.value)


def _ensure_report_visible(db: Session, report: Report, user: User):
    grant = require_child_access(db, report.child_id, user, CarePermission.VIEW_REPORTS.value)
    if grant.is_primary_guardian or report.visibility == "care_team":
        return grant
    if user.id in (report.allowed_user_ids or []):
        return grant
    # Do not leak restricted report existence to team members who cannot see it.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


def _active_team_user_ids(db: Session, child_id: str) -> set[str]:
    allowed: set[str] = set()
    guardians = db.scalars(
        select(GuardianMembership).where(GuardianMembership.child_id == child_id)
    ).all()
    for membership in guardians:
        if membership_is_active(membership.access_status, membership.expires_at):
            allowed.add(membership.guardian_user_id)

    providers = db.scalars(
        select(CareTeamMembership).where(CareTeamMembership.child_id == child_id)
    ).all()
    for membership in providers:
        if membership_is_active(membership.access_status, membership.expires_at):
            allowed.add(membership.user_id)
    return allowed


def _parse_allowed_user_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="allowed_user_ids_json must be valid JSON",
        ) from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="allowed_user_ids_json must be a list of user IDs",
        )
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _validate_restricted_users(db: Session, child_id: str, user_ids: list[str]) -> None:
    active_ids = _active_team_user_ids(db, child_id)
    unknown = [user_id for user_id in user_ids if user_id not in active_ids]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Restricted report access can only include active care-team members",
        )


def _serialize_version(db: Session, version: ReportVersion) -> ReportVersionPublic:
    uploader = db.get(User, version.uploaded_by_user_id)
    return ReportVersionPublic(
        id=version.id,
        version_number=version.version_number,
        original_filename=version.original_filename,
        content_type=version.content_type,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
        notes=version.notes,
        uploaded_by_user_id=version.uploaded_by_user_id,
        uploaded_by_name=uploader.full_name if uploader else "مستخدم وئام",
        created_at=version.created_at,
    )


def _serialize_report(db: Session, report: Report) -> ReportPublic:
    creator = db.get(User, report.created_by_user_id)
    versions = sorted(report.versions, key=lambda item: item.version_number, reverse=True)
    return ReportPublic(
        id=report.id,
        child_id=report.child_id,
        title=report.title,
        report_type=report.report_type,
        report_date=report.report_date,
        source_label=report.source_label,
        visibility=report.visibility,
        allowed_user_ids=list(report.allowed_user_ids or []),
        created_by_user_id=report.created_by_user_id,
        created_by_name=creator.full_name if creator else "مستخدم وئام",
        is_archived=report.is_archived,
        created_at=report.created_at,
        updated_at=report.updated_at,
        versions=[_serialize_version(db, version) for version in versions],
    )


@router.get("/children/{child_id}/reports", response_model=list[ReportPublic])
def list_reports(
    child_id: str,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReportPublic]:
    grant = require_child_access(db, child_id, user, CarePermission.VIEW_REPORTS.value)
    query = (
        select(Report)
        .options(selectinload(Report.versions))
        .where(Report.child_id == child_id)
        .order_by(Report.report_date.desc().nullslast(), Report.created_at.desc())
    )
    if not include_archived:
        query = query.where(Report.is_archived.is_(False))

    reports = db.scalars(query).unique().all()
    visible: list[Report] = []
    for report in reports:
        if grant.is_primary_guardian or report.visibility == "care_team" or user.id in (report.allowed_user_ids or []):
            visible.append(report)
    return [_serialize_report(db, report) for report in visible]


@router.post(
    "/children/{child_id}/reports",
    response_model=ReportPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    child_id: str,
    title: str = Form(..., min_length=1, max_length=220),
    report_type: str = Form(..., min_length=1, max_length=80),
    report_date: date | None = Form(default=None),
    source_label: str | None = Form(default=None, max_length=180),
    notes: str | None = Form(default=None, max_length=3000),
    visibility: str = Form(default="care_team"),
    allowed_user_ids_json: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportPublic:
    grant = require_child_access(db, child_id, user, CarePermission.UPLOAD_REPORTS.value)
    if visibility not in {"care_team", "restricted"}:
        raise HTTPException(status_code=422, detail="Invalid report visibility")

    allowed_user_ids = _parse_allowed_user_ids(allowed_user_ids_json)
    if visibility == "restricted":
        if not _can_manage_report(grant):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
        _validate_restricted_users(db, child_id, allowed_user_ids)
    else:
        allowed_user_ids = []

    report_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    storage = LocalReportStorage()
    try:
        stored = storage.save_upload(
            file,
            child_id=child_id,
            report_id=report_id,
            version_id=version_id,
        )
    except StorageValidationError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    clean_title = " ".join(title.strip().split())
    clean_type = " ".join(report_type.strip().split())
    if not clean_title or not clean_type:
        storage.delete(stored.key)
        raise HTTPException(status_code=422, detail="Title and report type are required")

    report = Report(
        id=report_id,
        child_id=child_id,
        title=clean_title,
        report_type=clean_type,
        report_date=report_date,
        source_label=(" ".join(source_label.strip().split()) or None) if source_label else None,
        visibility=visibility,
        allowed_user_ids=allowed_user_ids,
        created_by_user_id=user.id,
    )
    version = ReportVersion(
        id=version_id,
        report=report,
        version_number=1,
        original_filename=(file.filename or "report").strip()[:255] or "report",
        content_type=stored.content_type,
        storage_key=stored.key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        notes=notes.strip() if notes else None,
        uploaded_by_user_id=user.id,
    )
    try:
        db.add(report)
        db.add(version)
        db.flush()
        _audit(
            db,
            child_id=child_id,
            actor_user_id=user.id,
            action="report_uploaded",
            report_id=report.id,
            details={"version": 1, "visibility": visibility, "report_type": clean_type},
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored.key)
        raise

    created = _report_or_404(db, report.id)
    return _serialize_report(db, created)


@router.get("/reports/{report_id}", response_model=ReportPublic)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportPublic:
    report = _report_or_404(db, report_id)
    _ensure_report_visible(db, report, user)
    return _serialize_report(db, report)


@router.post("/reports/{report_id}/versions", response_model=ReportPublic, status_code=201)
def add_report_version(
    report_id: str,
    notes: str | None = Form(default=None, max_length=3000),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportPublic:
    report = _report_or_404(db, report_id)
    _ensure_report_visible(db, report, user)
    require_child_access(db, report.child_id, user, CarePermission.UPLOAD_REPORTS.value)
    if report.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived report cannot receive new versions")

    current_number = db.scalar(
        select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id == report.id)
    ) or 0
    next_number = current_number + 1
    version_id = str(uuid.uuid4())
    storage = LocalReportStorage()
    try:
        stored = storage.save_upload(
            file,
            child_id=report.child_id,
            report_id=report.id,
            version_id=version_id,
        )
    except StorageValidationError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    version = ReportVersion(
        id=version_id,
        report_id=report.id,
        version_number=next_number,
        original_filename=(file.filename or "report").strip()[:255] or "report",
        content_type=stored.content_type,
        storage_key=stored.key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        notes=notes.strip() if notes else None,
        uploaded_by_user_id=user.id,
    )
    try:
        db.add(version)
        db.flush()
        _audit(
            db,
            child_id=report.child_id,
            actor_user_id=user.id,
            action="report_version_uploaded",
            report_id=report.id,
            details={"version": next_number},
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored.key)
        raise

    updated = _report_or_404(db, report.id)
    return _serialize_report(db, updated)


@router.get("/reports/{report_id}/versions/{version_id}/download")
def download_report_version(
    report_id: str,
    version_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report = _report_or_404(db, report_id)
    _ensure_report_visible(db, report, user)
    version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.id == version_id,
            ReportVersion.report_id == report.id,
        )
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report version not found")

    try:
        path = LocalReportStorage().resolve(version.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Stored report file is unavailable") from exc

    _audit(
        db,
        child_id=report.child_id,
        actor_user_id=user.id,
        action="report_downloaded",
        report_id=report.id,
        details={"version": version.version_number},
    )
    db.commit()
    return FileResponse(
        path=path,
        media_type=version.content_type,
        filename=version.original_filename,
    )


@router.patch("/reports/{report_id}", response_model=ReportPublic)
def update_report_metadata(
    report_id: str,
    payload: ReportMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReportPublic:
    report = _report_or_404(db, report_id)
    grant = _ensure_report_visible(db, report, user)
    if not _can_manage_report(grant):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")

    values = payload.model_dump(exclude_unset=True)
    target_visibility = values.get("visibility", report.visibility)
    target_allowed = values.get("allowed_user_ids", list(report.allowed_user_ids or []))
    if target_visibility == "restricted":
        _validate_restricted_users(db, report.child_id, target_allowed)
    else:
        target_allowed = []

    for field in {"title", "report_type", "report_date", "source_label"} & values.keys():
        setattr(report, field, values[field])
    report.visibility = target_visibility
    report.allowed_user_ids = target_allowed

    _audit(
        db,
        child_id=report.child_id,
        actor_user_id=user.id,
        action="report_metadata_updated",
        report_id=report.id,
        details={"visibility": report.visibility},
    )
    db.add(report)
    db.commit()
    updated = _report_or_404(db, report.id)
    return _serialize_report(db, updated)


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_report(
    report_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    report = _report_or_404(db, report_id)
    grant = _ensure_report_visible(db, report, user)
    if not _can_manage_report(grant):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permission")
    report.is_archived = True
    _audit(
        db,
        child_id=report.child_id,
        actor_user_id=user.id,
        action="report_archived",
        report_id=report.id,
    )
    db.add(report)
    db.commit()
