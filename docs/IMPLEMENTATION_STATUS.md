# Weam implementation status

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

## Next feature
Care Team + Invitations + Consent + Permissions + Access Expiration/Revoke.
