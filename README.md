# Weam Platform | وئام

وئام منصة ذكية لتنسيق رحلة رعاية الأطفال ذوي الإعاقة والاحتياجات المختلفة، تجمع ولي الأمر وفريق الرعاية والمراكز في منظومة واحدة مع سجل رعاية موحد وصلاحيات دقيقة وذكاء اصطناعي مساند.

## Current implementation
**MVP Feature 01 complete: Authentication + Child Profile**

Implemented now:
- Responsive React + TypeScript UI
- FastAPI backend
- PostgreSQL-ready data layer + Alembic
- Email/password authentication
- JWT access + refresh
- Google Sign-In integration path (requires client ID configuration)
- Roles: guardian / care provider / center / admin
- Multiple child profiles under one guardian
- Separated `ChildIdentity` and `CareProfile`
- Condition-agnostic care model: conditions, needs, support requirements, services
- Protected child access
- Synthetic demo seed
- PWA baseline

## Stack
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Python
- Database: PostgreSQL
- Migrations: Alembic
- Authentication: Argon2 + JWT; optional Google Identity
- File storage: Object storage planned for reports/audio
- AI: provider-independent AI Gateway planned
- Realtime: WebSocket-compatible layer planned

## Repository layout
- `frontend/` — responsive web/PWA
- `backend/` — API, models, auth, migrations, tests
- `docs/` — architecture, local setup, branching, implementation status
- `.github/workflows/` — CI

## Local setup
See [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md).

## MVP order
1. ✅ Authentication + Child Profile
2. Care Team + Permissions
3. Reports + AI Extraction
4. Voice Updates
5. Timeline + Goals
6. AI Assistant + RAG
7. Care Coordination Agent
8. Realtime Communication
9. Centers + Matching + Booking
10. Calls + Notifications + Admin

## Product rules
- Supports multiple conditions and support needs from the start.
- Hearing impairment is a demo/use-case, not a product limitation.
- Guardian consent and least-privilege access apply to AI and future agent tools too.
- Competition/demo environments use synthetic data only.
