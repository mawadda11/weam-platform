from io import BytesIO

from pypdf import PdfWriter


def register(client, email: str, role: str, specialty: str | None = None):
    payload = {
        "email": email,
        "full_name": email.split("@")[0],
        "password": "StrongPass123!",
        "role": role,
    }
    if specialty:
        payload["provider_specialty"] = specialty
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


def create_report(client, guardian, child):
    response = client.post(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(guardian),
        data={
            "title": "تقرير متابعة سمعيات",
            "report_type": "سمعيات",
            "source_label": "مركز تجريبي",
            "visibility": "care_team",
        },
        files={
            "file": (
                "audiology.pdf",
                simple_pdf(),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def invite_and_accept(client, guardian, provider, child, permissions):
    invite = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={
            "email": provider["user"]["email"],
            "target_role": "care_provider",
            "permissions": permissions,
        },
    )
    assert invite.status_code == 201, invite.text
    accepted = client.post(
        f"/api/v1/care-team/invitations/{invite.json()['id']}/accept",
        headers=auth_header(provider),
    )
    assert accepted.status_code == 200, accepted.text


def test_guardian_can_generate_and_review_ai_analysis(client):
    guardian = register(client, "ai.guardian@example.com", "guardian")
    child = create_child(client, guardian)
    report = create_report(client, guardian, child)

    created = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
        json={},
    )
    assert created.status_code == 201, created.text
    analysis = created.json()
    assert analysis["analysis_status"] == "completed"
    assert analysis["review_status"] == "draft"
    assert analysis["provider"] == "mock"
    assert "summary" in analysis["result"]

    approved = client.patch(
        f"/api/v1/report-ai-analyses/{analysis['id']}/review",
        headers=auth_header(guardian),
        json={
            "review_status": "approved",
            "edited_result": {
                "summary": "ملخص راجعه ولي الأمر واعتمده."
            },
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["result"]["summary"] == "ملخص راجعه ولي الأمر واعتمده."


def test_ai_analysis_history_is_preserved(client):
    guardian = register(client, "ai.history@example.com", "guardian")
    child = create_child(client, guardian)
    report = create_report(client, guardian, child)

    first = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
        json={},
    )
    second = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
        json={},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    listed = client.get(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert listed.json()[0]["id"] == second.json()["id"]


def test_view_only_provider_can_see_analysis_but_cannot_generate(client):
    guardian = register(client, "ai.guardian2@example.com", "guardian")
    provider = register(
        client,
        "ai.provider2@example.com",
        "care_provider",
        "سمعيات",
    )
    child = create_child(client, guardian)
    report = create_report(client, guardian, child)
    created = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(guardian),
        json={},
    )
    assert created.status_code == 201

    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_reports"],
    )

    visible = client.get(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(provider),
    )
    assert visible.status_code == 200
    assert len(visible.json()) == 1

    forbidden = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(provider),
        json={},
    )
    assert forbidden.status_code == 403


def test_provider_with_upload_permission_can_generate_analysis(client):
    guardian = register(client, "ai.guardian3@example.com", "guardian")
    provider = register(
        client,
        "ai.provider3@example.com",
        "care_provider",
        "تخاطب",
    )
    child = create_child(client, guardian)
    report = create_report(client, guardian, child)

    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_reports", "upload_reports"],
    )

    created = client.post(
        f"/api/v1/reports/{report['id']}/ai-analyses",
        headers=auth_header(provider),
        json={},
    )
    assert created.status_code == 201, created.text
    assert created.json()["created_by_user_id"] == provider["user"]["id"]
