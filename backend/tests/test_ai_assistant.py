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
            "support_requirements": ["الجلوس بالقرب من المعلمة"],
            "services": ["تخاطب"],
            "summary": "تحتاج إلى متابعة مشتركة بين الأسرة وفريق الرعاية.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_assistant_answers_from_authorized_profile_sources(client):
    guardian = register(client, "assistant.guardian@example.com", "guardian")
    child = create_child(client, guardian)

    thread = client.post(
        f"/api/v1/children/{child['id']}/assistant/threads",
        headers=auth_header(guardian),
        json={},
    )
    assert thread.status_code == 201, thread.text

    answer = client.post(
        f"/api/v1/assistant/threads/{thread.json()['id']}/ask",
        headers=auth_header(guardian),
        json={"question": "ما احتياجات تاليا الحالية؟"},
    )
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    assert "دعم التواصل" in payload["assistant_message"]["content"]
    assert payload["assistant_message"]["sources"]
    assert payload["assistant_message"]["sources"][0]["source_type"] == "profile"


def test_assistant_thread_is_private_to_creator(client):
    guardian = register(client, "assistant.owner@example.com", "guardian")
    child = create_child(client, guardian)

    provider = register(
        client,
        "assistant.provider@example.com",
        "care_provider",
        "تخاطب",
    )
    invitation = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={
            "email": provider["user"]["email"],
            "target_role": "care_provider",
            "permissions": ["view_profile", "message_team"],
        },
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/api/v1/care-team/invitations/{invitation.json()['id']}/accept",
        headers=auth_header(provider),
    )
    assert accepted.status_code == 200

    thread = client.post(
        f"/api/v1/children/{child['id']}/assistant/threads",
        headers=auth_header(guardian),
        json={},
    ).json()

    blocked = client.get(
        f"/api/v1/assistant/threads/{thread['id']}/messages",
        headers=auth_header(provider),
    )
    assert blocked.status_code == 404


def test_assistant_does_not_claim_diagnosis(client):
    guardian = register(client, "assistant.safety@example.com", "guardian")
    child = create_child(client, guardian)
    thread = client.post(
        f"/api/v1/children/{child['id']}/assistant/threads",
        headers=auth_header(guardian),
        json={},
    ).json()

    answer = client.post(
        f"/api/v1/assistant/threads/{thread['id']}/ask",
        headers=auth_header(guardian),
        json={"question": "ما حالة تاليا؟"},
    )
    assert answer.status_code == 200
    assert "لا يقدّم تشخيصًا طبيًا" in answer.json()["assistant_message"]["content"]
