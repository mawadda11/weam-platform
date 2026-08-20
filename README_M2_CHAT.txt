Weam Milestone 2 - Feature 3: Communication Hub

Adds:
- One-to-one child care-team conversations.
- Group conversations.
- PostgreSQL message history.
- WebSocket live delivery using FastAPI only (no Firebase / paid service).
- Existing message_team permission enforced.
- Non-participants cannot read a conversation.
- Only active care-team members with messaging access can be added.

Apply after voice/STT branch is merged into main.

Migration:
python -m alembic upgrade head
Expected head: 0007_chat

No paid services and no new Python/npm dependencies.
