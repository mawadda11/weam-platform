from app.core.constants import UserRole, VerificationStatus
from app.db.session import SessionLocal
from app.models.user import User
from app.services.security import hash_password


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


def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def create_admin(client):
    with SessionLocal() as db:
        item = User(
            email="admin@example.com",
            full_name="إدارة وئام",
            password_hash=hash_password("StrongPass123!"),
            role=UserRole.ADMIN.value,
            verification_status=VerificationStatus.VERIFIED.value,
            auth_provider="password",
        )
        db.add(item)
        db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    return response.json()


def test_public_registration_cannot_create_admin(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fake-admin@example.com",
            "full_name": "مدير غير مصرح",
            "password": "StrongPass123!",
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_admin_reviews_accounts_without_clinical_records(client):
    guardian = register(client, "admin.guardian@example.com")
    provider = register(client, "admin.provider@example.com", "care_provider")
    admin = create_admin(client)

    assert client.get("/api/v1/admin/summary", headers=headers(guardian)).status_code == 403
    summary = client.get("/api/v1/admin/summary", headers=headers(admin))
    assert summary.status_code == 200
    assert summary.json()["users_total"] == 3
    assert "reports" not in summary.json()

    reviewed = client.patch(
        f"/api/v1/admin/users/{provider['user']['id']}",
        headers=headers(admin),
        json={
            "verification_status": "verified",
            "verification_note": "تمت مراجعة بيانات الحساب التجريبي.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["verification_status"] == "verified"

    audit = client.get("/api/v1/admin/audit", headers=headers(admin))
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "user_reviewed"
    assert "child_id" not in audit.json()[0]


def test_admin_verifies_center_before_it_appears_in_directory(client):
    center_auth = register(client, "admin.center@example.com", "center")
    created = client.post(
        "/api/v1/provider/center",
        headers=headers(center_auth),
        json={
            "name": "مركز مراجعة تجريبي",
            "description": "ملف مركز تجريبي مخصص لاختبار دورة الاعتماد.",
            "city": "الرياض",
            "address": "عنوان تجريبي",
            "specialties": ["النطق والتخاطب"],
            "services": ["جلسات تخاطب"],
            "served_needs": ["دعم التواصل"],
            "offers_in_person": True,
            "offers_remote": False,
            "phone": "+966 50 000 0800",
            "working_hours": "الأحد–الخميس، 8 ص–5 م",
        },
    )
    assert created.status_code == 201, created.text
    center_id = created.json()["id"]
    specialist = client.post(
        "/api/v1/provider/center/specialists",
        headers=headers(center_auth),
        json={
            "full_name": "أ. سارة التجريبية",
            "professional_title": "أخصائية تخاطب",
            "specialty": "النطق والتخاطب",
        },
    )
    assert specialist.status_code == 201, specialist.text
    guardian = register(client, "directory.guardian@example.com")
    before = client.get("/api/v1/centers", headers=headers(guardian))
    assert all(item["id"] != center_id for item in before.json())

    admin = create_admin(client)
    reviewed = client.patch(
        f"/api/v1/admin/centers/{center_id}",
        headers=headers(admin),
        json={"verification_status": "verified", "verification_note": "تم الاعتماد."},
    )
    assert reviewed.status_code == 200, reviewed.text
    after = client.get("/api/v1/centers", headers=headers(guardian))
    assert any(item["id"] == center_id for item in after.json())
    detail = client.get(f"/api/v1/centers/{center_id}", headers=headers(guardian))
    assert detail.json()["specialists"][0]["full_name"] == "أ. سارة التجريبية"


def test_admin_can_review_center_sources_without_verifying(client):
    """Refreshing/recording public source info must not, by itself, verify a
    center -- the two are deliberately separate actions in the admin API."""
    center_auth = register(client, "source.center@example.com", "center")
    created = client.post(
        "/api/v1/provider/center",
        headers=headers(center_auth),
        json={
            "name": "مركز مصدر عام تجريبي",
            "description": "ملف مركز تجريبي لاختبار مراجعة المصدر.",
            "city": "جدة",
            "address": "عنوان تجريبي",
            "specialties": ["دعم تعليمي"],
            "services": ["جلسات دعم"],
            "served_needs": ["دعم تعليمي"],
            "offers_in_person": True,
            "offers_remote": False,
            "phone": "+966 50 000 0900",
            "working_hours": "الأحد–الخميس، 8 ص–5 م",
        },
    )
    assert created.status_code == 201, created.text
    center_id = created.json()["id"]

    admin = create_admin(client)
    before = client.get("/api/v1/admin/centers", headers=headers(admin))
    before_item = next(item for item in before.json() if item["id"] == center_id)
    assert before_item["last_reviewed_at"] is None
    assert before_item["verification_status"] == "unverified"

    reviewed = client.patch(
        f"/api/v1/admin/centers/{center_id}",
        headers=headers(admin),
        json={"source_urls": ["https://example.org/center"], "mark_reviewed": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["source_urls"] == ["https://example.org/center"]
    assert reviewed.json()["last_reviewed_at"] is not None
    # A source review alone must not verify the center.
    assert reviewed.json()["verification_status"] == "unverified"

    audit = client.get("/api/v1/admin/audit", headers=headers(admin))
    assert audit.json()[0]["action"] == "center_reviewed"
