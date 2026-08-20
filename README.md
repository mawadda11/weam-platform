# Weam Platform

وئام منصة ذكية لتنسيق رحلة رعاية الأطفال ذوي الإعاقة، تجمع ولي الأمر وفريق الرعاية والمراكز في منظومة واحدة مع صلاحيات دقيقة، سجل رعاية موحد، ومكونات ذكاء اصطناعي مساندة.

## Current stage
Official initial scaffold for the MVP implementation.

## Stack
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + Python
- Database: PostgreSQL
- File storage: Object storage (Supabase Storage planned for MVP)
- AI: Provider-independent AI Gateway (planned)
- Realtime: WebSocket-compatible backend path (planned)

## Repository layout
- `frontend/` — responsive web app
- `backend/` — API and business logic
- `docs/` — architecture and local setup notes
- `.github/workflows/` — basic CI checks

## Local quick start
See `docs/LOCAL_SETUP.md`.

## MVP implementation order
1. Authentication
2. Child profile
3. Care team and permissions
4. Reports and AI extraction
5. Voice updates
6. Timeline and goals
7. AI assistant and RAG
8. Care Coordination Agent
9. Realtime communication
10. Care centers, matching, booking
11. Calls, notifications, admin

## Data policy for demo
Use synthetic/demo data only. Do not commit real child, medical, identity, API key, secret, or credential data.
