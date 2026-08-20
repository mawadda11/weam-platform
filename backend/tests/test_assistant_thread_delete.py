def register(client, email: str, role: str = "guardian"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": email.split("@")[0],
            "password": "StrongPass123!",
            "role": role,
        },
    )
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
            "summary": "تحتاج إلى متابعة مشتركة.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_can_delete_assistant_thread(client):
    guardian = register(client, "assistant.delete.owner@example.com")
    child = create_child(client, guardian)

    created = client.post(
        f"/api/v1/children/{child['id']}/assistant/threads",
        headers=auth_header(guardian),
        json={},
    )
    assert created.status_code == 201, created.text
    thread_id = created.json()["id"]

    deleted = client.delete(
        f"/api/v1/assistant/threads/{thread_id}",
        headers=auth_header(guardian),
    )
    assert deleted.status_code == 204, deleted.text

    missing = client.get(
        f"/api/v1/assistant/threads/{thread_id}/messages",
        headers=auth_header(guardian),
    )
    assert missing.status_code == 404

    threads = client.get(
        f"/api/v1/children/{child['id']}/assistant/threads",
        headers=auth_header(guardian),
    )
    assert threads.status_code == 200
    assert all(item["id"] != thread_id for item in threads.json())


def test_other_user_cannot_delete_private_assistant_thread(client):
    guardian = register(client, "assistant.delete.private@example.com")
    other = register(client, "assistant.delete.other@example.com")
    child = create_child(client, guardian)

    thread = client.post(
        f"/api/v1/children/{child['id']}/assistant/threads",
        headers=auth_header(guardian),
        json={},
    ).json()

    blocked = client.delete(
        f"/api/v1/assistant/threads/{thread['id']}",
        headers=auth_header(other),
    )
    assert blocked.status_code == 404
