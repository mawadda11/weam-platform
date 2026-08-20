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


def invite_and_accept(client, guardian, provider, child):
    invitation = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={
            "email": provider["user"]["email"],
            "target_role": "care_provider",
            "permissions": [
                "view_profile",
                "view_care_team",
                "message_team",
            ],
        },
    )
    assert invitation.status_code == 201, invitation.text
    accepted = client.post(
        f"/api/v1/care-team/invitations/{invitation.json()['id']}/accept",
        headers=auth_header(provider),
    )
    assert accepted.status_code == 200, accepted.text


def test_direct_conversation_and_messages(client):
    guardian = register(client, "chat.guardian@example.com", "guardian")
    provider = register(
        client,
        "chat.provider@example.com",
        "care_provider",
        "تخاطب",
    )
    child = create_child(client, guardian)
    invite_and_accept(client, guardian, provider, child)

    created = client.post(
        f"/api/v1/children/{child['id']}/conversations",
        headers=auth_header(guardian),
        json={
            "kind": "direct",
            "participant_user_ids": [provider["user"]["id"]],
        },
    )
    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["kind"] == "direct"
    assert len(conversation["participants"]) == 2

    sent = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        headers=auth_header(provider),
        json={"body": "تمت مراجعة هدف هذا الأسبوع."},
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["sender_user_id"] == provider["user"]["id"]

    messages = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages",
        headers=auth_header(guardian),
    )
    assert messages.status_code == 200
    assert messages.json()[0]["body"] == "تمت مراجعة هدف هذا الأسبوع."


def test_group_only_accepts_active_team_members(client):
    guardian = register(client, "group.guardian@example.com", "guardian")
    stranger = register(client, "group.stranger@example.com", "care_provider", "سمعيات")
    child = create_child(client, guardian)

    response = client.post(
        f"/api/v1/children/{child['id']}/conversations",
        headers=auth_header(guardian),
        json={
            "kind": "group",
            "title": "فريق تاليا",
            "participant_user_ids": [stranger["user"]["id"]],
        },
    )
    assert response.status_code == 422


def test_non_participant_cannot_read_conversation(client):
    guardian = register(client, "private.guardian@example.com", "guardian")
    provider_a = register(client, "private.a@example.com", "care_provider", "تخاطب")
    provider_b = register(client, "private.b@example.com", "care_provider", "سمعيات")
    child = create_child(client, guardian)
    invite_and_accept(client, guardian, provider_a, child)
    invite_and_accept(client, guardian, provider_b, child)

    created = client.post(
        f"/api/v1/children/{child['id']}/conversations",
        headers=auth_header(guardian),
        json={
            "kind": "direct",
            "participant_user_ids": [provider_a["user"]["id"]],
        },
    )
    conversation_id = created.json()["id"]

    forbidden = client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=auth_header(provider_b),
    )
    assert forbidden.status_code == 404
