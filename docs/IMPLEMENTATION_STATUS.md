# Weam implementation status

## Implemented — Competition demo environment rebuild

Replaced the old 3-child, fields-only seed with a full four-child demonstration
environment (لمى، يوسف، روان، عمر), each with a complete journey: reports (real,
signature-valid synthetic PDFs), a reviewed/approved AI analysis, goals with
progress history, follow-ups, a voice note with transcription, a grounded
assistant conversation, an explainable center match computed by the real
matching algorithm, and guardian↔specialist chat. Design and rationale:
[`docs/SEED_DATA_ARCHITECTURE.md`](SEED_DATA_ARCHITECTURE.md).

- Idempotent, production-guarded, migration-aware (`scripts/seed_demo.py`,
  `--rebuild` / `--reset` flags). New migration `0017_demo_data_tags`.
- Six real, publicly-sourced centers (Riyadh/Jeddah) added via a separate,
  equally guarded script (`scripts/seed_real_centers.py`), tagged distinctly
  from synthetic demo centers and never auto-marked as Weam-verified.
- 19 new backend tests covering idempotency, rebuild, cross-child permission
  differences, report file integrity + access control, notification/timeline
  coherence, and that `--reset` cannot touch non-demo data.
- Known limitation: the four report PDFs are pre-generated static assets, so
  the calendar date printed inside each document is fixed at generation time
  while the app's own `Report.report_date` is computed relative to the seed
  run — the two are not automatically kept in sync.

## Implemented — M6–M8 (verification pending)

### M6 — Communication Upgrade
- Global messages inbox and unread count
- Per-conversation unread state and read receipts
- Validated private PDF/image attachments
- Permission-aware sharing of reports, goals, and follow-ups with direct item links
- Responsive mobile conversation flow and authenticated WebSocket updates
- Migration `0012_communication_upgrade`

### M7 — Center Accounts / Provider Experience
- Provider workspace with only explicitly authorized child files
- Center-owned profile and service management
- Center specialist create/update/remove API and responsive UI
- Guardian invitations for center accounts with granular, expiring permissions
- Center profile edits return verified entries to review
- Migration `0013_center_accounts`

### M8 — Admin Dashboard
- Secure CLI provisioning for the first admin; public admin registration is blocked
- Aggregate operational summary without clinical content
- Account and center verification/activation controls
- Verified-center gate for the public directory and center matching
- Dedicated administrative audit log without child clinical records
- Migration `0014_admin_governance`

### Verification
- Added backend tests for unread/read state, attachments, sharing permissions, center accounts, guardian-controlled center access, admin isolation, and center verification.
- Run migration, complete Backend tests, TypeScript typecheck, Frontend build, and responsive role-based UX review before closing M6–M8.

---

## Completed — M5: AI Center Matching

### Backend
- Child-scoped matching endpoint and latest-result endpoint
- Matching over authorized profile data, approved report analyses, and active goals
- Age, city, and in-person/remote constraints
- Explainable top-three ranking with source attribution
- Stored per-user matching runs and access audit records
- Gemini summary through the existing AI layer with a grounded local fallback
- Migration `0011_ai_center_matching`

### Frontend
- Arabic RTL center-matching page under each child profile
- Optional city and delivery preferences
- Clear reasons, authorized source labels, limitations, loading, empty, and error states
- Responsive cards and direct navigation to center details
- Safety wording that avoids medical endorsement or “best center” claims

### Verification
- Automated M5 backend tests cover ranking, permissions, source approval, age/city/mode constraints, latest results, and insufficient data.
- Backend, TypeScript, build, and responsive manual verification completed before M6–M8 work began.

---

## Completed — Feature 01: Authentication + Child Profile

### Backend
- Email/password registration and login
- JWT access + refresh tokens
- `GET /auth/me`
- Google Sign-In backend path (activates when a Google Client ID is configured)
- Roles: guardian, care provider, center, admin
- Care providers and centers start unverified
- PostgreSQL-ready SQLAlchemy models
- Alembic baseline migration
- Identity data separated from care-profile data
- Multiple children per guardian
- Multi-condition / multi-need child profile
- Guardian isolation: another guardian receives 404 for a child they do not own
- Synthetic demo seed script

### Frontend
- Arabic responsive landing page
- Register / login
- Role selection
- Google Sign-In UI path when configured
- Protected routes
- Guardian dashboard with multiple children
- New child flow
- Child profile detail page
- PWA baseline manifest/service worker

### Verification
- Backend automated tests: 9 passing
- Python compile check: passing
- Frontend build must be run on a machine where npm dependencies can be installed (package network access is unavailable in the build sandbox used to prepare this package).

