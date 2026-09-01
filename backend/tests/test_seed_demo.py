from __future__ import annotations

from datetime import timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.center import Center
from app.models.center_match import CenterMatchRun
from app.models.child import Child, GuardianMembership
from app.models.follow_up import FollowUp
from app.models.goal import Goal
from app.models.report import Report
from app.models.user import User
from scripts.seed_demo import CHILD_BUILDERS, run_reset, run_seed


def _child_by_ref(db, ref: str) -> Child:
    child = db.scalar(select(Child).where(Child.external_ref == ref))
    assert child is not None, f"missing demo child {ref}"
    return child


def test_seed_demo_is_idempotent():
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        counts_first = db.scalar(select(Child).where(Child.external_ref.in_(CHILD_BUILDERS.keys())))
        assert counts_first is not None

        run_seed(db, rebuild=False)  # rerun: must not duplicate
        children = db.scalars(select(Child).where(Child.external_ref.in_(CHILD_BUILDERS.keys()))).all()
        assert len(children) == len(CHILD_BUILDERS)


def test_seed_demo_rebuild_replaces_cleanly():
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        lama = _child_by_ref(db, "demo-lama")
        lama.care_profile.summary = "تعديل مؤقت لاختبار rebuild"
        db.commit()

        run_seed(db, rebuild=True)
        children = db.scalars(select(Child).where(Child.external_ref.in_(CHILD_BUILDERS.keys()))).all()
        assert len(children) == len(CHILD_BUILDERS)
        lama_again = _child_by_ref(db, "demo-lama")
        assert lama_again.care_profile.summary != "تعديل مؤقت لاختبار rebuild"


def test_four_profiles_linked_to_one_guardian():
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        guardian = db.scalar(select(User).where(User.email == "guardian@weam.demo"))
        assert guardian is not None
        memberships = db.scalars(
            select(GuardianMembership).where(GuardianMembership.guardian_user_id == guardian.id)
        ).all()
        assert len(memberships) == len(CHILD_BUILDERS)


def test_permissions_differ_across_care_team():
    from app.models.care_team import CareTeamMembership

    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        slp = db.scalar(select(User).where(User.email == "slp@weam.demo"))
        lama = _child_by_ref(db, "demo-lama")
        rawan = _child_by_ref(db, "demo-rawan")

        on_lama = db.scalar(
            select(CareTeamMembership).where(
                CareTeamMembership.child_id == lama.id, CareTeamMembership.user_id == slp.id
            )
        )
        on_rawan = db.scalar(
            select(CareTeamMembership).where(
                CareTeamMembership.child_id == rawan.id, CareTeamMembership.user_id == slp.id
            )
        )
        assert on_lama is not None and on_rawan is not None
        assert set(on_rawan.permissions) < set(on_lama.permissions)


def test_reports_are_real_pdfs_and_access_restricted(client):
    from app.services.storage import LocalReportStorage

    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        lama = _child_by_ref(db, "demo-lama")
        report = db.scalar(select(Report).where(Report.child_id == lama.id))
        assert report is not None
        lama_id = lama.id
        storage_key = report.versions[0].storage_key

    path = LocalReportStorage().resolve(storage_key)
    assert path.read_bytes().startswith(b"%PDF")

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "outsider@example.com", "full_name": "شخص آخر", "password": "StrongPass123!", "role": "guardian"},
    )
    assert other.status_code == 201
    resp = client.get(
        f"/api/v1/children/{lama_id}/reports",
        headers={"Authorization": f"Bearer {other.json()['access_token']}"},
    )
    assert resp.status_code == 404


def test_goals_followups_present_for_every_child():
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        for ref in CHILD_BUILDERS:
            child = _child_by_ref(db, ref)
            goals = db.scalars(select(Goal).where(Goal.child_id == child.id)).all()
            followups = db.scalars(select(FollowUp).where(FollowUp.child_id == child.id)).all()
            assert len(goals) >= 2, ref
            assert len(followups) >= 1, ref


def test_center_matches_differ_across_children():
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        top_centers = set()
        for ref in CHILD_BUILDERS:
            child = _child_by_ref(db, ref)
            run = db.scalar(
                select(CenterMatchRun)
                .where(CenterMatchRun.child_id == child.id)
                .order_by(CenterMatchRun.created_at.desc())
            )
            assert run is not None, ref
            matches = run.result_json.get("matches") or []
            assert matches, f"no matches for {ref}"
            top_centers.add(matches[0]["center_id"])
        assert len(top_centers) > 1, "every child matched the same top center"


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def test_timeline_events_are_chronologically_coherent():
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        for ref in CHILD_BUILDERS:
            child = _child_by_ref(db, ref)
            reports = db.scalars(select(Report).where(Report.child_id == child.id)).all()
            for report in reports:
                assert _aware(report.created_at) >= _aware(child.created_at), ref


def test_reset_cannot_delete_non_demo_records(client):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "real.guardian@example.com", "full_name": "ولي أمر حقيقي", "password": "StrongPass123!", "role": "guardian"},
    )
    assert register.status_code == 201
    create_child = client.post(
        "/api/v1/children",
        json={"first_name": "طفل حقيقي", "conditions": [], "needs": [], "support_requirements": [], "services": []},
        headers={"Authorization": f"Bearer {register.json()['access_token']}"},
    )
    assert create_child.status_code in (200, 201), create_child.text
    real_child_id = create_child.json()["id"]

    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        run_reset(db)

        real_child = db.get(Child, real_child_id)
        assert real_child is not None
        real_user = db.scalar(select(User).where(User.email == "real.guardian@example.com"))
        assert real_user is not None

        remaining_demo_children = db.scalars(
            select(Child).where(Child.external_ref.in_(CHILD_BUILDERS.keys()))
        ).all()
        assert remaining_demo_children == []


def test_demo_seed_rejects_center_verification_side_effects_are_isolated():
    """Guards the deletion-order assumption in the architecture doc: demo users
    must never end up referenced by a non-cascading FK outside their own child
    subtree, or --reset would fail with a constraint violation."""
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        demo_centers = db.scalars(select(Center).where(Center.source_type == "synthetic_demo")).all()
        for center in demo_centers:
            assert center.verified_by_user_id is None


def test_seeded_data_actually_serializes_through_the_real_api(client):
    """DB-level checks alone missed a real bug: seeded rows can satisfy every
    SQLAlchemy/DB constraint and still make a FastAPI response_model raise a
    500 at serialization time (e.g. an invalid Literal value). This exercises
    every list endpoint a guardian's browser actually calls, for every seeded
    child, so that class of bug fails a test instead of only showing up live."""
    with SessionLocal() as db:
        run_seed(db, rebuild=False)
        child_ids = {
            ref: db.scalar(select(Child.id).where(Child.external_ref == ref))
            for ref in CHILD_BUILDERS
        }

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "guardian@weam.demo", "password": "WeamDemo123!"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    endpoints = [
        "reports",
        "goals",
        "follow-ups",
        "voice-notes",
        "conversations",
        "assistant/threads",
        "center-matches/latest",
        "care-team",
    ]
    for ref, child_id in child_ids.items():
        for endpoint in endpoints:
            response = client.get(f"/api/v1/children/{child_id}/{endpoint}", headers=headers)
            assert response.status_code == 200, f"{ref} /{endpoint} -> {response.status_code}: {response.text}"
