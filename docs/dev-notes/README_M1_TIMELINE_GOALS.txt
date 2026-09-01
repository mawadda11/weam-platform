Weam Milestone 1 - Timeline + Goals

This patch is intended to be applied AFTER the Reports feature (0003_reports).

Backend:
- Goal + GoalUpdate models
- Alembic 0004_goals_timeline
- Goal create/view/metadata/progress endpoints
- Permission enforcement: view_goals / manage_goals / view_timeline
- Goal owner must be an active care-team member
- Unified timeline combining child profile, care-team audit events, report events and goal updates

Frontend:
- Goals page
- Unified Timeline page
- Child profile + Dashboard shortcuts
- Responsive prototype-aligned styling

Expected test total after applying on the reports branch: 23 tests.
