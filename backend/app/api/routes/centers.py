from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.center import Center, CenterFavorite
from app.models.center_account import CenterSpecialist
from app.models.user import User
from app.schemas.center import CenterFilterOptions, CenterPublic

router = APIRouter(prefix="/centers", tags=["centers"])

AGE_GROUPS: dict[str, tuple[int, int | None]] = {
    "0-5": (0, 5),
    "6-12": (6, 12),
    "13-18": (13, 18),
    "18+": (18, None),
}


def _normalize(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _center_or_404(db: Session, center_id: str) -> Center:
    center = db.get(Center, center_id)
    if not center or not center.is_active or center.verification_status != "verified":
        raise HTTPException(status_code=404, detail="Center not found")
    return center


def _favorite_center_ids(db: Session, user_id: str) -> set[str]:
    return set(
        db.scalars(
            select(CenterFavorite.center_id).where(CenterFavorite.user_id == user_id)
        ).all()
    )


def _serialize(
    center: Center,
    favorite_ids: set[str],
    specialists: list[CenterSpecialist] | None = None,
) -> CenterPublic:
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
        specialists=list(specialists or []),
        is_favorite=center.id in favorite_ids,
        source_type=center.source_type,
        last_reviewed_at=center.last_reviewed_at,
        created_at=center.created_at,
        updated_at=center.updated_at,
    )


def _has_value(values: list[str] | None, requested: str) -> bool:
    normalized = _normalize(requested)
    return any(_normalize(item) == normalized for item in values or [])


def _matches_age_group(center: Center, age_group: str) -> bool:
    requested_min, requested_max = AGE_GROUPS[age_group]
    center_min = center.min_age_years if center.min_age_years is not None else 0
    center_max = center.max_age_years
    if requested_max is not None and center_min > requested_max:
        return False
    if center_max is not None and center_max < requested_min:
        return False
    return True


@router.get("/filter-options", response_model=CenterFilterOptions)
def get_center_filter_options(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CenterFilterOptions:
    centers = db.scalars(
        select(Center).where(
            Center.is_active.is_(True),
            Center.verification_status == "verified",
        )
    ).all()
    return CenterFilterOptions(
        cities=sorted({center.city for center in centers}),
        specialties=sorted(
            {item for center in centers for item in (center.specialties or [])}
        ),
        services=sorted(
            {item for center in centers for item in (center.services or [])}
        ),
    )


@router.get("", response_model=list[CenterPublic])
def list_centers(
    q: str | None = Query(default=None, max_length=120),
    city: str | None = Query(default=None, max_length=100),
    specialty: str | None = Query(default=None, max_length=120),
    service: str | None = Query(default=None, max_length=160),
    age_group: Literal["0-5", "6-12", "13-18", "18+"] | None = None,
    delivery_mode: Literal["in_person", "remote", "both"] | None = None,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CenterPublic]:
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
    favorite_ids = _favorite_center_ids(db, user.id)

    if q and (query := _normalize(q)):
        centers = [
            center
            for center in centers
            if query
            in _normalize(
                " ".join(
                    [
                        center.name,
                        center.description,
                        center.city,
                        center.region or "",
                        center.address,
                        *(center.specialties or []),
                        *(center.services or []),
                        *(center.served_needs or []),
                    ]
                )
            )
        ]
    if city:
        centers = [center for center in centers if _normalize(center.city) == _normalize(city)]
    if specialty:
        centers = [
            center for center in centers if _has_value(center.specialties, specialty)
        ]
    if service:
        centers = [center for center in centers if _has_value(center.services, service)]
    if age_group:
        centers = [
            center for center in centers if _matches_age_group(center, age_group)
        ]
    if delivery_mode == "in_person":
        centers = [center for center in centers if center.offers_in_person]
    elif delivery_mode == "remote":
        centers = [center for center in centers if center.offers_remote]
    elif delivery_mode == "both":
        centers = [
            center for center in centers
            if center.offers_in_person and center.offers_remote
        ]
    if favorites_only:
        centers = [center for center in centers if center.id in favorite_ids]

    centers.sort(key=lambda center: (center.id not in favorite_ids, center.name))
    return [_serialize(center, favorite_ids) for center in centers]


@router.get("/{center_id}", response_model=CenterPublic)
def get_center(
    center_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CenterPublic:
    center = _center_or_404(db, center_id)
    specialists = list(
        db.scalars(
            select(CenterSpecialist)
            .where(
                CenterSpecialist.center_id == center.id,
                CenterSpecialist.is_active.is_(True),
            )
            .order_by(CenterSpecialist.full_name.asc())
        ).all()
    )
    return _serialize(center, _favorite_center_ids(db, user.id), specialists)


@router.put("/{center_id}/favorite", response_model=CenterPublic)
def add_center_favorite(
    center_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CenterPublic:
    center = _center_or_404(db, center_id)
    existing = db.scalar(
        select(CenterFavorite).where(
            CenterFavorite.user_id == user.id,
            CenterFavorite.center_id == center.id,
        )
    )
    if not existing:
        db.add(CenterFavorite(user_id=user.id, center_id=center.id))
        try:
            db.commit()
        except IntegrityError:
            # A repeated concurrent request remains idempotent.
            db.rollback()
    return _serialize(center, {center.id})


@router.delete("/{center_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_center_favorite(
    center_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    center = _center_or_404(db, center_id)
    favorite = db.scalar(
        select(CenterFavorite).where(
            CenterFavorite.user_id == user.id,
            CenterFavorite.center_id == center.id,
        )
    )
    if favorite:
        db.delete(favorite)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
