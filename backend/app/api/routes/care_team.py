from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.constants import (
    AccessStatus,
    CarePermission,
    GuardianType,
    InvitationStatus,
    UserRole,
)
from app.db.session import get_db
from app.models.care_team import AccessAuditLog, CareInvitation, CareTeamMembership, utcnow
from app.models.child import Child, GuardianMembership
from app.models.user import User
from app.schemas.care_team import (
    AuditLogPublic,
    CareTeamOverview,
    InvitationCreate,
    InvitationPublic,
    MemberPublic,
    MembershipUpdate,
)
from app.services.access import membership_is_active, require_child_access

router = APIRouter(tags=["care-team"])

DEFAULT_PROVIDER_PERMISSIONS = [
    CarePermission.VIEW_PROFILE.value,
    CarePermission.VIEW_CARE_TEAM.value,
    CarePermission.VIEW_REPORTS.value,
    CarePermission.UPLOAD_REPORTS.value,
    CarePermission.VIEW_GOALS.value,
    CarePermission.MANAGE_GOALS.value,
    CarePermission.VIEW_TIMELINE.value,
    CarePermission.MESSAGE_TEAM.value,
]
DEFAULT_SECONDARY_GUARDIAN_PERMISSIONS = [
    CarePermission.VIEW_PROFILE.value,
    CarePermission.VIEW_CARE_TEAM.value,
    CarePermission.VIEW_REPORTS.value,
    CarePermission.VIEW_GOALS.value,
    CarePermission.VIEW_TIMELINE.value,
    CarePermission.MESSAGE_TEAM.value,
]


def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )


def _child_name(db: Session, child_id: str) -> str:
    child = db.get(Child, child_id)
    if not child or not child.identity:
        return "ملف طفل"
    return child.identity.preferred_name or child.identity.first_name


def _serialize_invitation(db: Session, invitation: CareInvitation) -> InvitationPublic:
    return InvitationPublic(
        id=invitation.id,
        child_id=invitation.child_id,
        child_name=_child_name(db, invitation.child_id),
        email=invitation.email,
        target_role=invitation.target_role,
        role_label=invitation.role_label,
        permissions=list(invitation.permissions or []),
        status=invitation.status,
        access_expires_at=invitation.access_expires_at,
        invitation_expires_at=invitation.invitation_expires_at,
        created_at=invitation.created_at,
    )


def _serialize_guardian(db: Session, membership: GuardianMembership) -> MemberPublic | None:
    user = db.get(User, membership.guardian_user_id)
    if not user:
        return None
    return MemberPublic(
        membership_id=membership.id,
        membership_kind="guardian",
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        account_role=user.role,
        role_label=membership.role_label or (
            "ولي أمر رئيسي" if membership.guardian_type == GuardianType.PRIMARY.value else "ولي أمر"
        ),
        verification_status=user.verification_status,
        guardian_type=membership.guardian_type,
        permissions=list(membership.permissions or []),
        access_status=membership.access_status,
        expires_at=membership.expires_at,
        is_primary_guardian=membership.guardian_type == GuardianType.PRIMARY.value,
    )


def _serialize_member(db: Session, membership: CareTeamMembership) -> MemberPublic | None:
    user = db.get(User, membership.user_id)
    if not user:
        return None
    return MemberPublic(
        membership_id=membership.id,
        membership_kind="care_provider",
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        account_role=user.role,
        role_label=membership.role_label or user.provider_specialty,
        verification_status=user.verification_status,
        guardian_type=None,
        permissions=list(membership.permissions or []),
        access_status=membership.access_status,
        expires_at=membership.expires_at,
        is_primary_guardian=False,
    )


@router.get("/children/{child_id}/care-team", response_model=CareTeamOverview)
def care_team_overview(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CareTeamOverview:
    grant = require_child_access(db, child_id, user, CarePermission.VIEW_CARE_TEAM.value)

    guardians = db.scalars(
        select(GuardianMembership)
        .where(GuardianMembership.child_id == child_id)
        .order_by(GuardianMembership.created_at.asc())
    ).all()
    care_members = db.scalars(
        select(CareTeamMembership)
        .where(CareTeamMembership.child_id == child_id)
        .order_by(CareTeamMembership.created_at.asc())
    ).all()

    members: list[MemberPublic] = []
    for membership in guardians:
        if grant.is_primary_guardian or membership_is_active(membership.access_status, membership.expires_at):
            item = _serialize_guardian(db, membership)
            if item:
                members.append(item)
    for membership in care_members:
        if grant.is_primary_guardian or membership_is_active(membership.access_status, membership.expires_at):
            item = _serialize_member(db, membership)
            if item:
                members.append(item)

    pending: list[InvitationPublic] = []
    if grant.allows(CarePermission.MANAGE_CARE_TEAM.value):
        invitations = db.scalars(
            select(CareInvitation)
            .where(
                CareInvitation.child_id == child_id,
                CareInvitation.status == InvitationStatus.PENDING.value,
            )
            .order_by(CareInvitation.created_at.desc())
        ).all()
        pending = [_serialize_invitation(db, invitation) for invitation in invitations]

    return CareTeamOverview(child_id=child_id, members=members, pending_invitations=pending)


@router.post(
    "/children/{child_id}/care-team/invitations",
    response_model=InvitationPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    child_id: str,
    payload: InvitationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InvitationPublic:
    require_child_access(db, child_id, user, CarePermission.MANAGE_CARE_TEAM.value)
    if payload.target_role not in {UserRole.GUARDIAN, UserRole.CARE_PROVIDER}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only guardians and care providers can join a child's care team",
        )

    email = str(payload.email).lower().strip()
    if email == user.email.lower():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have access")

    existing_pending = db.scalar(
        select(CareInvitation).where(
            CareInvitation.child_id == child_id,
            CareInvitation.email == email,
            CareInvitation.status == InvitationStatus.PENDING.value,
        )
    )
    if existing_pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pending invitation already exists")

    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
        if payload.target_role == UserRole.GUARDIAN:
            existing_access = db.scalar(
                select(GuardianMembership).where(
                    GuardianMembership.child_id == child_id,
                    GuardianMembership.guardian_user_id == existing_user.id,
                )
            )
        else:
            existing_access = db.scalar(
                select(CareTeamMembership).where(
                    CareTeamMembership.child_id == child_id,
                    CareTeamMembership.user_id == existing_user.id,
                )
            )
        if existing_access and membership_is_active(existing_access.access_status, existing_access.expires_at):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has access")

    permissions = payload.permissions or (
        DEFAULT_SECONDARY_GUARDIAN_PERMISSIONS
        if payload.target_role == UserRole.GUARDIAN
        else DEFAULT_PROVIDER_PERMISSIONS
    )
    now = utcnow()
    invitation = CareInvitation(
        child_id=child_id,
        invited_by_user_id=user.id,
        email=email,
        target_role=payload.target_role.value,
        role_label=payload.role_label.strip() if payload.role_label else None,
        permissions=permissions,
        access_expires_at=now + timedelta(days=payload.access_days) if payload.access_days else None,
        invitation_expires_at=now + timedelta(days=7),
    )
    db.add(invitation)
    db.flush()
    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="invitation_created",
        entity_type="care_invitation",
        entity_id=invitation.id,
        details={"email": email, "target_role": invitation.target_role},
    )
    db.commit()
    db.refresh(invitation)
    return _serialize_invitation(db, invitation)


@router.get("/care-team/invitations/mine", response_model=list[InvitationPublic])
def my_invitations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[InvitationPublic]:
    now = utcnow()
    invitations = db.scalars(
        select(CareInvitation)
        .where(
            CareInvitation.email == user.email.lower(),
            CareInvitation.status == InvitationStatus.PENDING.value,
        )
        .order_by(CareInvitation.created_at.desc())
    ).all()
    return [
        _serialize_invitation(db, invitation)
        for invitation in invitations
        if invitation.invitation_expires_at.replace(tzinfo=invitation.invitation_expires_at.tzinfo or now.tzinfo) > now
    ]


def _load_invitation_for_user(db: Session, invitation_id: str, user: User) -> CareInvitation:
    invitation = db.get(CareInvitation, invitation_id)
    if not invitation or invitation.email.lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation is no longer pending")
    now = utcnow()
    expiry = invitation.invitation_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=now.tzinfo)
    if expiry <= now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invitation has expired")
    if invitation.target_role != user.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation does not match this account type")
    return invitation


@router.post("/care-team/invitations/{invitation_id}/accept", response_model=MemberPublic)
def accept_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberPublic:
    invitation = _load_invitation_for_user(db, invitation_id, user)
    now = utcnow()

    if invitation.target_role == UserRole.GUARDIAN.value:
        membership = db.scalar(
            select(GuardianMembership).where(
                GuardianMembership.child_id == invitation.child_id,
                GuardianMembership.guardian_user_id == user.id,
            )
        )
        if not membership:
            membership = GuardianMembership(
                child_id=invitation.child_id,
                guardian_user_id=user.id,
                guardian_type=GuardianType.SECONDARY.value,
            )
            db.add(membership)
        membership.role_label = invitation.role_label or "ولي أمر ثانوي"
        membership.permissions = list(invitation.permissions or [])
        membership.access_status = AccessStatus.ACTIVE.value
        membership.accepted_at = now
        membership.expires_at = invitation.access_expires_at
        membership.revoked_at = None
        db.flush()
        member_public = _serialize_guardian(db, membership)
    else:
        membership = db.scalar(
            select(CareTeamMembership).where(
                CareTeamMembership.child_id == invitation.child_id,
                CareTeamMembership.user_id == user.id,
            )
        )
        if not membership:
            membership = CareTeamMembership(
                child_id=invitation.child_id,
                user_id=user.id,
                invited_by_user_id=invitation.invited_by_user_id,
            )
            db.add(membership)
        membership.role_label = invitation.role_label or user.provider_specialty
        membership.permissions = list(invitation.permissions or [])
        membership.access_status = AccessStatus.ACTIVE.value
        membership.accepted_at = now
        membership.expires_at = invitation.access_expires_at
        membership.revoked_at = None
        db.flush()
        member_public = _serialize_member(db, membership)

    invitation.status = InvitationStatus.ACCEPTED.value
    invitation.responded_at = now
    _audit(
        db,
        child_id=invitation.child_id,
        actor_user_id=user.id,
        action="invitation_accepted",
        entity_type="care_invitation",
        entity_id=invitation.id,
        details={"target_role": invitation.target_role},
    )
    db.commit()
    if member_public is None:
        raise HTTPException(status_code=500, detail="Unable to create membership")
    return member_public


@router.post("/care-team/invitations/{invitation_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invitation(
    invitation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    invitation = _load_invitation_for_user(db, invitation_id, user)
    invitation.status = InvitationStatus.DECLINED.value
    invitation.responded_at = utcnow()
    _audit(
        db,
        child_id=invitation.child_id,
        actor_user_id=user.id,
        action="invitation_declined",
        entity_type="care_invitation",
        entity_id=invitation.id,
    )
    db.commit()


def _find_editable_membership(db: Session, child_id: str, membership_id: str):
    guardian = db.get(GuardianMembership, membership_id)
    if guardian and guardian.child_id == child_id:
        if guardian.guardian_type == GuardianType.PRIMARY.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary guardian access cannot be changed here")
        return guardian, "guardian"
    member = db.get(CareTeamMembership, membership_id)
    if member and member.child_id == child_id:
        return member, "care_provider"
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Care team member not found")


@router.patch("/children/{child_id}/care-team/members/{membership_id}", response_model=MemberPublic)
def update_member_access(
    child_id: str,
    membership_id: str,
    payload: MembershipUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemberPublic:
    require_child_access(db, child_id, user, CarePermission.MANAGE_PERMISSIONS.value)
    membership, kind = _find_editable_membership(db, child_id, membership_id)
    membership.permissions = list(payload.permissions)
    membership.expires_at = utcnow() + timedelta(days=payload.access_days) if payload.access_days else None
    membership.access_status = AccessStatus.ACTIVE.value
    membership.revoked_at = None
    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="permissions_updated",
        entity_type="care_membership",
        entity_id=membership_id,
        details={"permissions": membership.permissions, "access_days": payload.access_days},
    )
    db.commit()
    item = _serialize_guardian(db, membership) if kind == "guardian" else _serialize_member(db, membership)
    if item is None:
        raise HTTPException(status_code=500, detail="Unable to load membership")
    return item


@router.delete("/children/{child_id}/care-team/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_member_access(
    child_id: str,
    membership_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    require_child_access(db, child_id, user, CarePermission.MANAGE_PERMISSIONS.value)
    membership, _ = _find_editable_membership(db, child_id, membership_id)
    membership.access_status = AccessStatus.REVOKED.value
    membership.revoked_at = utcnow()
    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="access_revoked",
        entity_type="care_membership",
        entity_id=membership_id,
    )
    db.commit()


@router.get("/children/{child_id}/care-team/audit", response_model=list[AuditLogPublic])
def access_audit_log(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditLogPublic]:
    require_child_access(db, child_id, user, CarePermission.MANAGE_PERMISSIONS.value)
    logs = db.scalars(
        select(AccessAuditLog)
        .where(AccessAuditLog.child_id == child_id)
        .order_by(AccessAuditLog.created_at.desc())
        .limit(100)
    ).all()
    return [
        AuditLogPublic(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details=dict(log.details or {}),
            created_at=log.created_at,
        )
        for log in logs
    ]
