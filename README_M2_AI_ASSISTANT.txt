Weam M2 - Feature 4: Grounded AI Assistant (RAG-style, free/local)

This implementation is intentionally local-first and free:
- No paid API.
- No external child-data transfer.
- Retrieves only from data the current user is authorized to view.
- Uses approved report analyses only.
- Uses approved voice transcripts only.
- Uses goals/profile data when the user has those permissions.
- Every answer includes explicit source cards.
- Assistant threads are private per user.
- It does not diagnose or change treatment plans.

The current answer generator is deterministic grounded retrieval, not a general
LLM. This is deliberate for the MVP: it produces auditable answers and creates
the exact retrieval/source layer needed by the next Care Coordination Agent.
A local LLM can be layered on top later without changing the data-permission
or source pipeline.

Migration:
python -m alembic upgrade head
Expected head: 0008_ai_assistant

No new dependencies and no paid services.
