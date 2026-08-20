from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.constants import CarePermission
from app.db.session import SessionLocal, get_db
from app.models.care_team import AccessAuditLog, CareTeamMembership
from app.models.chat import ChatMessage, Conversation, ConversationParticipant
from app.models.child import GuardianMembership
from app.models.user import User
from app.schemas.chat import (
    ChatMessagePublic,
    ConversationCreate,
    ConversationParticipantPublic,
    ConversationPublic,
    MessageCreate,
)
from app.services.access import membership_is_active, require_child_access
from app.services.security import decode_token

router = APIRouter(tags=["chat"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConversationSocketManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, conversation_id: str, websocket: WebSocket) -> None:
        self.connections[conversation_id].add(websocket)

    def disconnect(self, conversation_id: str, websocket: WebSocket) -> None:
        sockets = self.connections.get(conversation_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self.connections.pop(conversation_id, None)

    async def broadcast(self, conversation_id: str, payload: dict) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.connections.get(conversation_id, set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(conversation_id, websocket)


socket_manager = ConversationSocketManager()


def _audit(
    db: Session,
    *,
    child_id: str,
    actor_user_id: str,
    action: str,
    entity_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AccessAuditLog(
            child_id=child_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type="conversation",
            entity_id=entity_id,
            details=details or {},
        )
    )


def _conversation_query(conversation_id: str):
    return (
        select(Conversation)
        .options(selectinload(Conversation.participants))
        .where(Conversation.id == conversation_id)
    )


def _conversation_or_404(db: Session, conversation_id: str) -> Conversation:
    conversation = db.scalar(_conversation_query(conversation_id))
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _participant_user_ids(conversation: Conversation) -> set[str]:
    return {participant.user_id for participant in conversation.participants}


def _require_conversation_access(
    db: Session,
    conversation: Conversation,
    user: User,
):
    grant = require_child_access(
        db,
        conversation.child_id,
        user,
        CarePermission.MESSAGE_TEAM.value,
    )
    if user.id not in _participant_user_ids(conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return grant


def _active_team_user_ids(db: Session, child_id: str) -> set[str]:
    active: set[str] = set()

    guardians = db.scalars(
        select(GuardianMembership).where(
            GuardianMembership.child_id == child_id
        )
    ).all()
    for membership in guardians:
        if membership_is_active(
            membership.access_status,
            membership.expires_at,
        ):
            active.add(membership.guardian_user_id)

    providers = db.scalars(
        select(CareTeamMembership).where(
            CareTeamMembership.child_id == child_id
        )
    ).all()
    for membership in providers:
        if (
            membership_is_active(
                membership.access_status,
                membership.expires_at,
            )
            and CarePermission.MESSAGE_TEAM.value
            in (membership.permissions or [])
        ):
            active.add(membership.user_id)

    return active


def _role_label(db: Session, child_id: str, user_id: str) -> str | None:
    guardian = db.scalar(
        select(GuardianMembership).where(
            GuardianMembership.child_id == child_id,
            GuardianMembership.guardian_user_id == user_id,
        )
    )
    if guardian:
        return guardian.role_label or (
            "ولي أمر رئيسي"
            if guardian.guardian_type == "primary"
            else "ولي أمر"
        )

    provider = db.scalar(
        select(CareTeamMembership).where(
            CareTeamMembership.child_id == child_id,
            CareTeamMembership.user_id == user_id,
        )
    )
    return provider.role_label if provider else None


def _serialize_message(db: Session, message: ChatMessage) -> ChatMessagePublic:
    sender = db.get(User, message.sender_user_id)
    return ChatMessagePublic(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_user_id=message.sender_user_id,
        sender_name=sender.full_name if sender else "عضو فريق الرعاية",
        body=message.body,
        created_at=message.created_at,
    )


def _conversation_title(
    db: Session,
    conversation: Conversation,
    current_user_id: str,
) -> str:
    if conversation.title:
        return conversation.title

    people = []
    for participant in conversation.participants:
        if conversation.kind == "direct" and participant.user_id == current_user_id:
            continue
        user = db.get(User, participant.user_id)
        if user:
            people.append(user.full_name)

    if conversation.kind == "direct":
        return people[0] if people else "محادثة مباشرة"
    return " · ".join(people[:3]) or "مجموعة فريق الرعاية"


def _serialize_conversation(
    db: Session,
    conversation: Conversation,
    current_user_id: str,
) -> ConversationPublic:
    participants: list[ConversationParticipantPublic] = []
    for participant in conversation.participants:
        user = db.get(User, participant.user_id)
        if not user:
            continue
        participants.append(
            ConversationParticipantPublic(
                user_id=user.id,
                full_name=user.full_name,
                role_label=_role_label(
                    db,
                    conversation.child_id,
                    user.id,
                ),
            )
        )

    last = db.scalar(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )

    return ConversationPublic(
        id=conversation.id,
        child_id=conversation.child_id,
        kind=conversation.kind,
        title=_conversation_title(
            db,
            conversation,
            current_user_id,
        ),
        participants=participants,
        last_message=_serialize_message(db, last) if last else None,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get(
    "/children/{child_id}/conversations",
    response_model=list[ConversationPublic],
)
def list_conversations(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ConversationPublic]:
    require_child_access(
        db,
        child_id,
        user,
        CarePermission.MESSAGE_TEAM.value,
    )

    conversations = db.scalars(
        select(Conversation)
        .join(ConversationParticipant)
        .options(selectinload(Conversation.participants))
        .where(
            Conversation.child_id == child_id,
            ConversationParticipant.user_id == user.id,
        )
        .order_by(Conversation.updated_at.desc())
    ).unique().all()

    return [
        _serialize_conversation(db, conversation, user.id)
        for conversation in conversations
    ]


@router.post(
    "/children/{child_id}/conversations",
    response_model=ConversationPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    child_id: str,
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationPublic:
    require_child_access(
        db,
        child_id,
        user,
        CarePermission.MESSAGE_TEAM.value,
    )

    participant_ids = [
        participant_id
        for participant_id in payload.participant_user_ids
        if participant_id != user.id
    ]

    if payload.kind == "direct" and len(participant_ids) != 1:
        raise HTTPException(
            status_code=422,
            detail="Direct conversation requires exactly one other participant",
        )
    if payload.kind == "group" and len(participant_ids) < 1:
        raise HTTPException(
            status_code=422,
            detail="Group conversation requires at least one other participant",
        )

    allowed = _active_team_user_ids(db, child_id)
    if user.id not in allowed:
        allowed.add(user.id)
    unknown = [
        participant_id
        for participant_id in participant_ids
        if participant_id not in allowed
    ]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail="Conversation participants must be active care-team members with messaging access",
        )

    # Reuse an existing direct conversation for the same pair.
    if payload.kind == "direct":
        candidate_ids = {user.id, participant_ids[0]}
        existing = db.scalars(
            select(Conversation)
            .options(selectinload(Conversation.participants))
            .where(
                Conversation.child_id == child_id,
                Conversation.kind == "direct",
            )
        ).all()
        for conversation in existing:
            if _participant_user_ids(conversation) == candidate_ids:
                return _serialize_conversation(db, conversation, user.id)

    clean_title = (
        " ".join(payload.title.strip().split())
        if payload.title
        else None
    )
    conversation = Conversation(
        child_id=child_id,
        kind=payload.kind,
        title=clean_title,
        created_by_user_id=user.id,
    )
    db.add(conversation)
    db.flush()

    for participant_id in [user.id, *participant_ids]:
        db.add(
            ConversationParticipant(
                conversation_id=conversation.id,
                user_id=participant_id,
            )
        )

    _audit(
        db,
        child_id=child_id,
        actor_user_id=user.id,
        action="conversation_created",
        entity_id=conversation.id,
        details={
            "kind": payload.kind,
            "participant_count": len(participant_ids) + 1,
        },
    )
    db.commit()

    conversation = _conversation_or_404(db, conversation.id)
    return _serialize_conversation(db, conversation, user.id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[ChatMessagePublic],
)
def list_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChatMessagePublic]:
    conversation = _conversation_or_404(db, conversation_id)
    _require_conversation_access(db, conversation, user)

    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    ).all()
    rows.reverse()
    return [_serialize_message(db, message) for message in rows]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessagePublic,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatMessagePublic:
    conversation = _conversation_or_404(db, conversation_id)
    _require_conversation_access(db, conversation, user)

    message = ChatMessage(
        conversation_id=conversation.id,
        sender_user_id=user.id,
        body=payload.body,
    )
    conversation.updated_at = utcnow()
    db.add(message)
    db.add(conversation)
    db.commit()
    db.refresh(message)

    public = _serialize_message(db, message)
    await socket_manager.broadcast(
        conversation.id,
        {
            "type": "message",
            "message": public.model_dump(mode="json"),
        },
    )
    return public


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_socket(
    websocket: WebSocket,
    conversation_id: str,
) -> None:
    await websocket.accept()
    connected = False

    try:
        auth_payload = await websocket.receive_json()
        if (
            auth_payload.get("type") != "auth"
            or not auth_payload.get("token")
        ):
            await websocket.close(code=4401)
            return

        claims = decode_token(
            str(auth_payload["token"]),
            "access",
        )
        if not claims:
            await websocket.close(code=4401)
            return

        with SessionLocal() as db:
            user = db.get(User, claims["sub"])
            conversation = db.scalar(
                _conversation_query(conversation_id)
            )
            if not user or not conversation:
                await websocket.close(code=4404)
                return
            try:
                _require_conversation_access(
                    db,
                    conversation,
                    user,
                )
            except HTTPException:
                await websocket.close(code=4403)
                return

        await socket_manager.connect(conversation_id, websocket)
        connected = True
        await websocket.send_json({"type": "ready"})

        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if connected:
            socket_manager.disconnect(
                conversation_id,
                websocket,
            )
