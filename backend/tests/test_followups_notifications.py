from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from pypdf import PdfWriter

from app.services.follow_up_notifications import (
    local_today,
    resolve_follow_up_due_date,
)


def register(client, email: str, role: str = "guardian"):
    payload = {
        "email": email,
        "full_name": email.split("@")[0],
        "password": "StrongPass123!",
        "role": role,
    }
    if role == "care_provider":
        payload["provider_specialty"] = "تخاطب"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def create_child(client, guardian):
    response = client.post(
        "/api/v1/children",
        headers=auth_header(guardian),
        json={
            "first_name": "تاليا",
            "conditions": ["ضعف سمع"],
            "needs": ["دعم التواصل"],
            "support_requirements": [],
            "services": ["تخاطب"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def simple_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def create_report(client, guardian, child, report_date: str | None = "2026-08-20"):
    data = {
        "title": "تقرير متابعة سمعيات",
        "report_type": "سمعيات",
        "source_label": "مركز تجريبي",
        "visibility": "care_team",
    }
    if report_date:
        data["report_date"] = report_date
    response = client.post(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(guardian),
        data=data,
        files={"file": ("audiology.pdf", simple_pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_relative_followup_date_uses_report_date():
    assert resolve_follow_up_due_date(
        "مراجعة السمعيات خلال 3 أشهر",
        report_date=date(2026, 8, 20),
    ) == date(2026, 11, 20)

    assert resolve_follow_up_due_date(
        "المراجعة بعد ثلاثة أشهر",
        report_date=date(2026, 8, 31),
    ) == date(2026, 11, 30)

    assert resolve_follow_up_due_date(
        "مراجعة لاحقة",
        report_date=date(2026, 8, 20),
    ) is None


def test_guardian_can_create_complete_and_reopen_follow_up(client):
    guardian = register(client, "followup.guardian@example.com")
    child = create_child(client, guardian)

    created = client.post(
        f"/api/v1/children/{child['id']}/follow-ups",
        headers=auth_header(guardian),
        json={
            "title": "مراجعة السمعيات",
            "due_date": (local_today() + timedelta(days=2)).isoformat(),
            "note": "متابعة تجريبية",
        },
    )
    assert created.status_code == 201, created.text
    follow_up = created.json()
    assert follow_up["status"] == "open"
    assert follow_up["display_status"] == "upcoming"

    completed = client.post(
        f"/api/v1/follow-ups/{follow_up['id']}/complete",
        headers=auth_header(guardian),
    )
    assert completed.status_code == 200
    assert completed.json()["display_status"] == "completed"

    reopened = client.post(
        f"/api/v1/follow-ups/{follow_up['id']}/reopen",
        headers=auth_header(guardian),
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"


def test_approved_report_analysis_auto_creates_followups(client):
    guardian = register(client, "auto.followup@example.com")
    child = create_child(client, guardian)
    report = create_report(client, guardian, child, "2026-08-20")

    analysis = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
        json={},
    )
    assert analysis.status_code == 201, analysis.text

    approved = client.patch(
        f"/api/v1/report-ai-analyses/{analysis.json()['id']}/review",
        headers=auth_header(guardian),
        json={
            "review_status": "approved",
            "edited_result": {
                "follow_up_actions": [
                    "مراجعة السمعيات خلال 3 أشهر",
                    "مشاركة ملاحظات التقدم مع فريق الرعاية",
                ]
            },
        },
    )
    assert approved.status_code == 200, approved.text

    listed = client.get(
        f"/api/v1/children/{child['id']}/follow-ups",
        headers=auth_header(guardian),
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) == 2
    assert all(item["source_type"] == "report_ai" for item in items)

    dated = next(item for item in items if "السمعيات" in item["title"])
    assert dated["due_date"] == "2026-11-20"

    undated = next(item for item in items if "مشاركة" in item["title"])
    assert undated["due_date"] is None


def test_sync_endpoint_backfills_old_approved_analysis_without_duplicates(client):
    guardian = register(client, "sync.followup@example.com")
    child = create_child(client, guardian)
    report = create_report(client, guardian, child)

    analysis = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
        json={},
    )
    assert analysis.status_code == 201

    approved = client.patch(
        f"/api/v1/report-ai-analyses/{analysis.json()['id']}/review",
        headers=auth_header(guardian),
        json={
            "review_status": "approved",
            "edited_result": {
                "follow_up_actions": ["مراجعة السمعيات بتاريخ 2026-11-30"]
            },
        },
    )
    assert approved.status_code == 200

    first_sync = client.post(
        f"/api/v1/children/{child['id']}/follow-ups/sync-approved-analyses",
        headers=auth_header(guardian),
    )
    second_sync = client.post(
        f"/api/v1/children/{child['id']}/follow-ups/sync-approved-analyses",
        headers=auth_header(guardian),
    )
    assert first_sync.status_code == 200
    assert second_sync.status_code == 200
    assert first_sync.json()["created"] == 0
    assert second_sync.json()["created"] == 0

    listed = client.get(
        f"/api/v1/children/{child['id']}/follow-ups",
        headers=auth_header(guardian),
    )
    assert len(listed.json()) == 1


def test_due_follow_up_creates_readable_notification(client):
    guardian = register(client, "notify.guardian@example.com")
    child = create_child(client, guardian)

    created = client.post(
        f"/api/v1/children/{child['id']}/follow-ups",
        headers=auth_header(guardian),
        json={
            "title": "متابعة اليوم",
            "due_date": local_today().isoformat(),
        },
    )
    assert created.status_code == 201

    notifications = client.get(
        "/api/v1/notifications",
        headers=auth_header(guardian),
    )
    assert notifications.status_code == 200, notifications.text
    due = next(
        item for item in notifications.json()
        if item["notification_type"] == "follow_up"
    )
    assert due["is_read"] is False

    marked = client.post(
        "/api/v1/notifications/read",
        headers=auth_header(guardian),
        json={"event_keys": [due["event_key"]]},
    )
    assert marked.status_code == 200

    notifications = client.get(
        "/api/v1/notifications",
        headers=auth_header(guardian),
    )
    due_after = next(
        item for item in notifications.json()
        if item["event_key"] == due["event_key"]
    )
    assert due_after["is_read"] is True


def test_goal_target_date_creates_automatic_deadline_notification(client):
    guardian = register(client, "goal.deadline@example.com")
    child = create_child(client, guardian)
    target = local_today() + timedelta(days=2)

    goal = client.post(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(guardian),
        json={
            "title": "استخدام جمل من 4 كلمات",
            "target_date": target.isoformat(),
        },
    )
    assert goal.status_code == 201, goal.text

    notifications = client.get(
        "/api/v1/notifications",
        headers=auth_header(guardian),
    )
    assert notifications.status_code == 200, notifications.text
    assert any(
        item["notification_type"] == "goal_deadline"
        and item["entity_id"] == goal.json()["id"]
        for item in notifications.json()
    )


def test_completed_follow_up_appears_in_timeline(client):
    guardian = register(client, "timeline.followup@example.com")
    child = create_child(client, guardian)
    follow_up = client.post(
        f"/api/v1/children/{child['id']}/follow-ups",
        headers=auth_header(guardian),
        json={"title": "متابعة تخاطب", "due_date": local_today().isoformat()},
    ).json()

    client.post(
        f"/api/v1/follow-ups/{follow_up['id']}/complete",
        headers=auth_header(guardian),
    )

    timeline = client.get(
        f"/api/v1/children/{child['id']}/timeline?types=follow_up",
        headers=auth_header(guardian),
    )
    assert timeline.status_code == 200, timeline.text
    titles = [item["title"] for item in timeline.json()]
    assert any("متابعة جديدة" in title for title in titles)
    assert any("تم إنجاز متابعة" in title for title in titles)
