Weam Milestone 1 - Increment 1
Care Team + Invitations + Permissions

Includes:
- Primary/secondary guardian access
- Care provider invitations and acceptance/decline
- Permission selection before invitation
- Time-limited or ongoing access
- Permission updates and access revocation
- Access audit log API
- Care provider child access after approval
- Responsive prototype-aligned Care Team UI
- Invitation inbox UI
- Backend tests

After extracting into the repository root:
1) backend: python -m alembic upgrade head
2) backend: python -m pytest -q
3) frontend: npm run typecheck
4) frontend: npm run build
