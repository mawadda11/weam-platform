from datetime import date, timedelta


def register_guardian(client, email="parent@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "ولي أمر تجريبي",
            "password": "StrongPass123!",
            "role": "guardian",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_login_refresh_and_me(client):
    payload = register_guardian(client)
    assert payload["user"]["verification_status"] == "verified"
    assert payload["access_token"]
    assert payload["refresh_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["role"] == "guardian"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "PARENT@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 200

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


def test_duplicate_email_and_bad_password_are_rejected(client):
    register_guardian(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "parent@example.com",
            "full_name": "Duplicate",
            "password": "StrongPass123!",
            "role": "guardian",
        },
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "parent@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401


def test_care_provider_requires_specialty_and_starts_unverified(client):
    missing = client.post(
        "/api/v1/auth/register",
        json={
            "email": "specialist@example.com",
            "full_name": "أخصائية",
            "password": "StrongPass123!",
            "role": "care_provider",
        },
    )
    assert missing.status_code == 422

    created = client.post(
        "/api/v1/auth/register",
        json={
            "email": "specialist@example.com",
            "full_name": "أخصائية",
            "password": "StrongPass123!",
            "role": "care_provider",
            "provider_specialty": "تخاطب",
        },
    )
    assert created.status_code == 201
    assert created.json()["user"]["verification_status"] == "unverified"


def test_google_endpoint_reports_not_configured(client):
    response = client.post(
        "/api/v1/auth/google",
        json={"credential": "x" * 30, "role": "guardian"},
    )
    assert response.status_code == 503


def test_guardian_can_create_multiple_children_with_different_needs(client):
    token = register_guardian(client)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/v1/children",
        headers=headers,
        json={
            "first_name": "طفل أ",
            "gender": "female",
            "conditions": ["ضعف سمع"],
            "needs": ["دعم التواصل"],
            "support_requirements": ["تعليمات مرئية"],
            "services": ["تخاطب", "سمعيات"],
            "summary": "بيانات تجريبية فقط",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/children",
        headers=headers,
        json={
            "first_name": "طفل ب",
            "conditions": ["اضطراب طيف التوحد"],
            "needs": ["روتين واضح"],
            "services": ["علاج وظيفي"],
        },
    )
    assert second.status_code == 201, second.text

    children = client.get("/api/v1/children", headers=headers)
    assert children.status_code == 200
    assert len(children.json()) == 2
    assert children.json()[0]["guardian_type"] == "primary"


def test_child_profile_is_private_to_its_guardian(client):
    first = register_guardian(client, "first@example.com")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    child = client.post(
        "/api/v1/children",
        headers=first_headers,
        json={"first_name": "طفل خاص", "conditions": ["احتياج تجريبي"]},
    ).json()

    second = register_guardian(client, "second@example.com")
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    response = client.get(f"/api/v1/children/{child['id']}", headers=second_headers)
    assert response.status_code == 404


def test_only_guardian_can_create_child(client):
    provider = client.post(
        "/api/v1/auth/register",
        json={
            "email": "provider@example.com",
            "full_name": "مقدم رعاية",
            "password": "StrongPass123!",
            "role": "care_provider",
            "provider_specialty": "علاج وظيفي",
        },
    ).json()
    response = client.post(
        "/api/v1/children",
        headers={"Authorization": f"Bearer {provider['access_token']}"},
        json={"first_name": "غير مسموح"},
    )
    assert response.status_code == 403


def test_child_can_be_updated_and_future_birth_date_is_rejected(client):
    guardian = register_guardian(client)
    headers = {"Authorization": f"Bearer {guardian['access_token']}"}
    child = client.post(
        "/api/v1/children",
        headers=headers,
        json={"first_name": "طفل", "needs": ["دعم تواصل"]},
    ).json()

    updated = client.patch(
        f"/api/v1/children/{child['id']}",
        headers=headers,
        json={"needs": ["دعم تواصل", "  دعم تواصل  ", "تنظيم حسي"]},
    )
    assert updated.status_code == 200
    assert updated.json()["needs"] == ["دعم تواصل", "تنظيم حسي"]

    invalid = client.post(
        "/api/v1/children",
        headers=headers,
        json={
            "first_name": "مستقبل",
            "birth_date": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert invalid.status_code == 422
