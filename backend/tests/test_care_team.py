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
            "first_name": "تاليا",
            "conditions": ["ضعف سمع"],
            "needs": ["دعم التواصل"],
            "support_requirements": [],
            "services": ["تخاطب"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_guardian_invites_provider_and_provider_gets_child_access(client):
    guardian = register(client, "guardian@example.com", "guardian")
    provider = register(client, "provider@example.com", "care_provider", "أخصائي تخاطب")
    child = create_child(client, guardian)

    invite = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={
            "email": "provider@example.com",
            "target_role": "care_provider",
            "role_label": "أخصائي التخاطب",
            "permissions": ["view_profile", "view_care_team", "view_reports"],
            "access_days": 90,
        },
    )
    assert invite.status_code == 201, invite.text

    mine = client.get("/api/v1/care-team/invitations/mine", headers=auth_header(provider))
    assert mine.status_code == 200
    assert len(mine.json()) == 1

    accepted = client.post(
        f"/api/v1/care-team/invitations/{invite.json()['id']}/accept",
        headers=auth_header(provider),
    )
    assert accepted.status_code == 200, accepted.text

    children = client.get("/api/v1/children", headers=auth_header(provider))
    assert children.status_code == 200
    assert [item["id"] for item in children.json()] == [child["id"]]
    assert children.json()[0]["access_role"] == "care_provider"


def test_provider_without_manage_permission_cannot_invite(client):
    guardian = register(client, "guardian2@example.com", "guardian")
    provider = register(client, "provider2@example.com", "care_provider", "علاج وظيفي")
    child = create_child(client, guardian)

    invite = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={
            "email": "provider2@example.com",
            "target_role": "care_provider",
            "permissions": ["view_profile", "view_care_team"],
        },
    ).json()
    client.post(
        f"/api/v1/care-team/invitations/{invite['id']}/accept",
        headers=auth_header(provider),
    )

    forbidden = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(provider),
        json={"email": "someone@example.com", "target_role": "care_provider"},
    )
    assert forbidden.status_code == 403


def test_guardian_can_revoke_provider_access(client):
    guardian = register(client, "guardian3@example.com", "guardian")
    provider = register(client, "provider3@example.com", "care_provider", "سمعيات")
    child = create_child(client, guardian)

    invite = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={"email": "provider3@example.com", "target_role": "care_provider"},
    ).json()
    member = client.post(
        f"/api/v1/care-team/invitations/{invite['id']}/accept",
        headers=auth_header(provider),
    ).json()

    revoked = client.delete(
        f"/api/v1/children/{child['id']}/care-team/members/{member['membership_id']}",
        headers=auth_header(guardian),
    )
    assert revoked.status_code == 204

    children = client.get("/api/v1/children", headers=auth_header(provider))
    assert children.status_code == 200
    assert children.json() == []


def test_secondary_guardian_invitation_is_supported(client):
    primary = register(client, "primary@example.com", "guardian")
    secondary = register(client, "secondary@example.com", "guardian")
    child = create_child(client, primary)

    invite = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(primary),
        json={
            "email": "secondary@example.com",
            "target_role": "guardian",
            "role_label": "والد",
            "permissions": ["view_profile", "view_care_team"],
        },
    ).json()
    accepted = client.post(
        f"/api/v1/care-team/invitations/{invite['id']}/accept",
        headers=auth_header(secondary),
    )
    assert accepted.status_code == 200
    assert accepted.json()["guardian_type"] == "secondary"

    child_response = client.get(f"/api/v1/children/{child['id']}", headers=auth_header(secondary))
    assert child_response.status_code == 200
    assert child_response.json()["guardian_type"] == "secondary"
