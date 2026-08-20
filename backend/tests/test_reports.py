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


def create_child(client, guardian_auth):
    response = client.post(
        "/api/v1/children",
        headers=auth_header(guardian_auth),
        json={
            "first_name": "ريم",
            "conditions": ["احتياج تواصلي"],
            "needs": ["دعم التواصل"],
            "support_requirements": [],
            "services": ["تخاطب"],
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
            "role_label": "أخصائي",
            "permissions": permissions,
        },
    )
    assert invite.status_code == 201, invite.text
    accepted = client.post(
        f"/api/v1/care-team/invitations/{invite.json()['id']}/accept",
        headers=auth_header(provider),
    )
    assert accepted.status_code == 200, accepted.text
    return accepted.json()


def pdf_bytes(label: bytes = b"v1") -> bytes:
    return b"%PDF-1.4\n% Weam test\n" + label + b"\n%%EOF"


def create_report(client, guardian, child, **overrides):
    data = {
        "title": "تقرير السمعيات",
        "report_type": "سمعيات",
        "report_date": "2026-08-20",
        "source_label": "مركز وئام",
        "notes": "النسخة الأولى",
        "visibility": "care_team",
        "allowed_user_ids_json": "[]",
    }
    data.update(overrides.pop("data", {}))
    files = overrides.pop(
        "files",
        {"file": ("report.pdf", pdf_bytes(), "application/pdf")},
    )
    response = client.post(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(guardian),
        data=data,
        files=files,
    )
    return response


def test_guardian_can_upload_list_download_and_version_report(client):
    guardian = register(client, "report.guardian@example.com", "guardian")
    child = create_child(client, guardian)

    created = create_report(client, guardian, child)
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["title"] == "تقرير السمعيات"
    assert len(report["versions"]) == 1
    assert report["versions"][0]["version_number"] == 1

    listed = client.get(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(guardian),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [report["id"]]

    second = client.post(
        f"/api/v1/reports/{report['id']}/versions",
        headers=auth_header(guardian),
        data={"notes": "تحديث بعد المتابعة"},
        files={"file": ("report-v2.pdf", pdf_bytes(b"v2"), "application/pdf")},
    )
    assert second.status_code == 201, second.text
    assert [item["version_number"] for item in second.json()["versions"]] == [2, 1]

    latest = second.json()["versions"][0]
    download = client.get(
        f"/api/v1/reports/{report['id']}/versions/{latest['id']}/download",
        headers=auth_header(guardian),
    )
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")


def test_provider_with_view_reports_but_without_upload_cannot_upload(client):
    guardian = register(client, "report.guardian2@example.com", "guardian")
    provider = register(client, "report.provider2@example.com", "care_provider", "تخاطب")
    child = create_child(client, guardian)
    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_reports"],
    )

    forbidden = create_report(client, provider, child)
    assert forbidden.status_code == 403


def test_provider_with_upload_permission_can_add_team_report(client):
    guardian = register(client, "report.guardian3@example.com", "guardian")
    provider = register(client, "report.provider3@example.com", "care_provider", "علاج وظيفي")
    child = create_child(client, guardian)
    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_reports", "upload_reports"],
    )

    created = create_report(
        client,
        provider,
        child,
        data={"title": "تقرير العلاج الوظيفي", "report_type": "علاج وظيفي"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["created_by_user_id"] == provider["user"]["id"]


def test_restricted_report_only_visible_to_selected_team_member(client):
    guardian = register(client, "report.guardian4@example.com", "guardian")
    provider_a = register(client, "report.provider.a@example.com", "care_provider", "تخاطب")
    provider_b = register(client, "report.provider.b@example.com", "care_provider", "سمعيات")
    child = create_child(client, guardian)
    permissions = ["view_profile", "view_reports"]
    invite_and_accept(client, guardian, provider_a, child, permissions)
    invite_and_accept(client, guardian, provider_b, child, permissions)

    created = create_report(
        client,
        guardian,
        child,
        data={
            "visibility": "restricted",
            "allowed_user_ids_json": f'["{provider_a["user"]["id"]}"]',
        },
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]

    list_a = client.get(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(provider_a),
    )
    assert list_a.status_code == 200
    assert [item["id"] for item in list_a.json()] == [report_id]

    list_b = client.get(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(provider_b),
    )
    assert list_b.status_code == 200
    assert list_b.json() == []

    hidden_detail = client.get(
        f"/api/v1/reports/{report_id}",
        headers=auth_header(provider_b),
    )
    assert hidden_detail.status_code == 404


def test_invalid_file_content_is_rejected_without_report_record(client):
    guardian = register(client, "report.guardian5@example.com", "guardian")
    child = create_child(client, guardian)

    invalid = create_report(
        client,
        guardian,
        child,
        files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")},
    )
    assert invalid.status_code == 415

    listed = client.get(
        f"/api/v1/children/{child['id']}/reports",
        headers=auth_header(guardian),
    )
    assert listed.status_code == 200
    assert listed.json() == []
