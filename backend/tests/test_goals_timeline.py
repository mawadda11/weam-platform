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


def invite_and_accept(
    client,
    guardian,
    provider,
    child,
    permissions,
):
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


def test_guardian_can_create_goal_add_progress_and_view_timeline(client):
    guardian = register(client, "goal.guardian@example.com", "guardian")
    child = create_child(client, guardian)

    created = client.post(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(guardian),
        json={
            "title": "زيادة استخدام الجمل",
            "description": "استخدام جمل من 4 كلمات في مواقف يومية.",
            "category": "تخاطب",
            "start_date": "2026-08-20",
            "target_date": "2026-09-20",
            "assigned_to_user_id": guardian["user"]["id"],
        },
    )
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["status"] == "new"
    assert goal["progress_percent"] == 0

    updated = client.post(
        f"/api/v1/goals/{goal['id']}/updates",
        headers=auth_header(guardian),
        json={
            "note": "بدأنا التمرين المنزلي.",
            "progress_percent": 35,
            "status": "in_progress",
        },
    )
    assert updated.status_code == 201, updated.text
    assert updated.json()["progress_percent"] == 35
    assert updated.json()["status"] == "in_progress"
    assert updated.json()["updates"][0]["note"] == "بدأنا التمرين المنزلي."

    timeline = client.get(
        f"/api/v1/children/{child['id']}/timeline",
        headers=auth_header(guardian),
    )
    assert timeline.status_code == 200, timeline.text
    kinds = [item["event_type"] for item in timeline.json()]
    assert "profile" in kinds
    assert "goal" in kinds


def test_completed_goal_is_always_100_percent(client):
    guardian = register(client, "goal.completed@example.com", "guardian")
    child = create_child(client, guardian)
    created = client.post(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(guardian),
        json={"title": "هدف مكتمل"},
    ).json()

    response = client.post(
        f"/api/v1/goals/{created['id']}/updates",
        headers=auth_header(guardian),
        json={
            "progress_percent": 15,
            "status": "completed",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["progress_percent"] == 100
    assert response.json()["status"] == "completed"

    timeline = client.get(
        f"/api/v1/children/{child['id']}/timeline?types=goal",
        headers=auth_header(guardian),
    )
    assert timeline.status_code == 200
    descriptions = [item["description"] for item in timeline.json() if item["description"]]
    assert any("الحالة مكتمل" in item for item in descriptions)


def test_view_only_provider_can_see_goals_but_cannot_manage(client):
    guardian = register(client, "goal.guardian2@example.com", "guardian")
    provider = register(
        client,
        "goal.provider2@example.com",
        "care_provider",
        "تخاطب",
    )
    child = create_child(client, guardian)
    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_goals", "view_timeline"],
    )

    created = client.post(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(guardian),
        json={"title": "هدف مشترك"},
    )
    assert created.status_code == 201
    goal_id = created.json()["id"]

    visible = client.get(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(provider),
    )
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [goal_id]

    forbidden = client.post(
        f"/api/v1/goals/{goal_id}/updates",
        headers=auth_header(provider),
        json={"progress_percent": 20},
    )
    assert forbidden.status_code == 403


def test_provider_with_manage_goals_can_create_and_update(client):
    guardian = register(client, "goal.guardian3@example.com", "guardian")
    provider = register(
        client,
        "goal.provider3@example.com",
        "care_provider",
        "علاج وظيفي",
    )
    child = create_child(client, guardian)
    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        [
            "view_profile",
            "view_goals",
            "manage_goals",
            "view_timeline",
        ],
    )

    created = client.post(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(provider),
        json={
            "title": "الاستقلال في ارتداء الحذاء",
            "assigned_to_user_id": provider["user"]["id"],
        },
    )
    assert created.status_code == 201, created.text

    done = client.post(
        f"/api/v1/goals/{created.json()['id']}/updates",
        headers=auth_header(provider),
        json={
            "note": "تم إتقان المهارة.",
            "status": "completed",
        },
    )
    assert done.status_code == 201, done.text
    assert done.json()["progress_percent"] == 100
    assert done.json()["status"] == "completed"


def test_provider_without_timeline_permission_is_forbidden(client):
    guardian = register(client, "goal.guardian4@example.com", "guardian")
    provider = register(
        client,
        "goal.provider4@example.com",
        "care_provider",
        "سمعيات",
    )
    child = create_child(client, guardian)
    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_goals"],
    )

    response = client.get(
        f"/api/v1/children/{child['id']}/timeline",
        headers=auth_header(provider),
    )
    assert response.status_code == 403


def test_goal_owner_must_be_active_care_team_member(client):
    guardian = register(client, "goal.guardian5@example.com", "guardian")
    outsider = register(
        client,
        "goal.outsider5@example.com",
        "care_provider",
        "سلوك",
    )
    child = create_child(client, guardian)

    response = client.post(
        f"/api/v1/children/{child['id']}/goals",
        headers=auth_header(guardian),
        json={
            "title": "هدف غير صالح",
            "assigned_to_user_id": outsider["user"]["id"],
        },
    )
    assert response.status_code == 422
