from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import get_db
from app.models.care_team import AccessAuditLog
from app.models.center import Center, CenterFavorite
from app.models.center_match import CenterMatchRun
from app.models.child import Child
from app.models.user import User
from app.schemas.center import CenterPublic
from app.schemas.center_matching import (
    CenterMatchEvidence,
    CenterMatchItem,
    CenterMatchRequest,
    CenterMatchResponse,
    CenterMatchSource,
)
from app.services.access import require_child_access
from app.services.assistant_rag import collect_authorized_sources
from app.services.center_matching import compute_center_matches

router = APIRouter(
    prefix="/children/{child_id}/center-matches",
    tags=["center-matching"],
)


def _load_child(db: Session, child_id: str) -> Child:
    child = db.scalar(
        select(Child)
        .options(joinedload(Child.identity), joinedload(Child.care_profile))
        .where(Child.id == child_id)
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child profile not found")
    return child


def _favorite_ids(db: Session, user_id: str) -> set[str]:
    return set(
        db.scalars(
            select(CenterFavorite.center_id).where(CenterFavorite.user_id == user_id)
        ).all()
    )


def _center_public(center: Center, favorite_ids: set[str]) -> CenterPublic:
    return CenterPublic(
        id=center.id,
        name=center.name,
        description=center.description,
        city=center.city,
        region=center.region,
        address=center.address,
        specialties=list(center.specialties or []),
        services=list(center.services or []),
        served_needs=list(center.served_needs or []),
        min_age_years=center.min_age_years,
        max_age_years=center.max_age_years,
        offers_in_person=center.offers_in_person,
        offers_remote=center.offers_remote,
        phone=center.phone,
        email=center.email,
        working_hours=center.working_hours,
        price_range=center.price_range,
        latitude=center.latitude,
        longitude=center.longitude,
        is_favorite=center.id in favorite_ids,
        source_type=center.source_type,
        last_reviewed_at=center.last_reviewed_at,
        created_at=center.created_at,
        updated_at=center.updated_at,
    )


def _serialize_run(db: Session, run: CenterMatchRun, user: User) -> CenterMatchResponse:
    result = dict(run.result_json or {})
    raw_matches = list(result.get("matches") or [])
    center_ids = [str(item.get("center_id")) for item in raw_matches if item.get("center_id")]
    centers = db.scalars(
        select(Center).where(
            Center.id.in_(center_ids),
            Center.is_active.is_(True),
            Center.verification_status == "verified",
        )
    ).all() if center_ids else []
    center_by_id = {center.id: center for center in centers}
    favorite_ids = _favorite_ids(db, user.id)

    matches: list[CenterMatchItem] = []
    for raw in raw_matches:
        center = center_by_id.get(str(raw.get("center_id")))
        if not center:
            continue
        sources = [CenterMatchSource(**item) for item in (raw.get("sources") or [])]
        matches.append(
            CenterMatchItem(
                rank=len(matches) + 1,
                match_level=raw.get("match_level") or "initial",
                center=_center_public(center, favorite_ids),
                reasons=list(raw.get("reasons") or []),
                matched_signals=list(raw.get("matched_signals") or []),
                sources=sources,
            )
        )

    criteria = dict(run.criteria_json or {})
    return CenterMatchResponse(
        id=run.id,
        child_id=run.child_id,
        child_name=str(result.get("child_name") or "الطفل"),
        child_age_years=result.get("child_age_years"),
        preferred_city=criteria.get("city"),
        delivery_mode=criteria.get("delivery_mode"),
        summary=str(result.get("summary") or ""),
        profile_signals=list(result.get("profile_signals") or []),
        evidence=CenterMatchEvidence(**(result.get("evidence") or {})),
        insufficient_data=bool(result.get("insufficient_data")),
        limitations=list(result.get("limitations") or []),
        safety_note=str(result.get("safety_note") or ""),
        matches=matches,
        created_at=run.created_at,
    )


@router.get("/latest", response_model=CenterMatchResponse)
def get_latest_center_match(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CenterMatchResponse:
    require_child_access(db, child_id, user, CarePermission.VIEW_PROFILE.value)
    run = db.scalar(
        select(CenterMatchRun)
        .where(
            CenterMatchRun.child_id == child_id,
            CenterMatchRun.requested_by_user_id == user.id,
        )
        .order_by(CenterMatchRun.created_at.desc())
    )
    if not run:
        raise HTTPException(status_code=404, detail="Center match not found")
    return _serialize_run(db, run, user)


@router.post("", response_model=CenterMatchResponse, status_code=status.HTTP_201_CREATED)
def create_center_match(
    child_id: str,
    payload: CenterMatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CenterMatchResponse:
    grant = require_child_access(db, child_id, user, CarePermission.VIEW_PROFILE.value)
    child = _load_child(db, child_id)
    sources = [
        source
        for source in collect_authorized_sources(
            db,
            child_id=child_id,
            user=user,
            grant=grant,
        )
        if source.source_type in {"profile", "report", "goal"}
    ]
    centers = list(
        db.scalars(
            select(Center)
            .where(
                Center.is_active.is_(True),
                Center.verification_status == "verified",
            )
            .order_by(Center.name.asc())
        ).all()
    )
    result = compute_center_matches(
        child=child,
        sources=sources,
        centers=centers,
        city=payload.city,
        delivery_mode=payload.delivery_mode,
    )
    run = CenterMatchRun(
        child_id=child_id,
        requested_by_user_id=user.id,
        provider=result.provider,
        model=result.model,
        criteria_json=payload.model_dump(),
        result_json=result.data,
    )
    db.add(run)
    db.flush()
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=user.id,
            action="center_match_generated",
            entity_type="center_match_run",
            entity_id=run.id,
            details={
                "city": payload.city,
                "delivery_mode": payload.delivery_mode,
                "center_ids": [item.get("center_id") for item in result.data.get("matches", [])],
                "source_counts": result.data.get("evidence", {}),
            },
        )
    )
    db.commit()
    db.refresh(run)
    return _serialize_run(db, run, user)
