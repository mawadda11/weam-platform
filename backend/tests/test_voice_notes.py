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


def wav_bytes() -> bytes:
    # Minimal RIFF-like bytes are enough for storage signature validation.
    return b"RIFF" + (b"\x00" * 60)


def create_voice_note(client, auth, child):
    response = client.post(
        f"/api/v1/children/{child['id']}/voice-notes",
        headers=auth_header(auth),
        data={"title": "ملاحظة جلسة التخاطب", "duration_seconds": "12"},
        files={"file": ("note.wav", wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def invite_and_accept(client, guardian, provider, child, permissions):
    invitation = client.post(
        f"/api/v1/children/{child['id']}/care-team/invitations",
        headers=auth_header(guardian),
        json={
            "email": provider["user"]["email"],
            "target_role": "care_provider",
            "permissions": permissions,
        },
    )
    assert invitation.status_code == 201, invitation.text
    accepted = client.post(
        f"/api/v1/care-team/invitations/{invitation.json()['id']}/accept",
        headers=auth_header(provider),
    )
    assert accepted.status_code == 200, accepted.text


def test_guardian_can_upload_transcribe_edit_and_approve(client):
    guardian = register(client, "voice.guardian@example.com", "guardian")
    child = create_child(client, guardian)
    note = create_voice_note(client, guardian, child)

    transcribed = client.post(
        f"/api/v1/voice-notes/{note['id']}/transcribe",
        headers=auth_header(guardian),
    )
    assert transcribed.status_code == 200, transcribed.text
    assert transcribed.json()["transcription_status"] == "completed"
    assert transcribed.json()["review_status"] == "draft"
    assert "وضع التطوير المحلي" in transcribed.json()["transcript_draft"]

    reviewed = client.patch(
        f"/api/v1/voice-notes/{note['id']}/review",
        headers=auth_header(guardian),
        json={
            "review_status": "approved",
            "transcript": "اليوم استخدمت تاليا جملة من أربع كلمات بشكل واضح.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_status"] == "approved"
    assert reviewed.json()["transcript_final"].startswith("اليوم استخدمت")


def test_view_only_provider_sees_only_approved_transcript(client):
    guardian = register(client, "voice.guardian2@example.com", "guardian")
    provider = register(
        client,
        "voice.provider2@example.com",
        "care_provider",
        "تخاطب",
    )
    child = create_child(client, guardian)
    note = create_voice_note(client, guardian, child)
    client.post(
        f"/api/v1/voice-notes/{note['id']}/transcribe",
        headers=auth_header(guardian),
    )

    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_voice_notes"],
    )

    before = client.get(
        f"/api/v1/children/{child['id']}/voice-notes",
        headers=auth_header(provider),
    )
    assert before.status_code == 200
    assert before.json()[0]["transcript_draft"] is None
    assert before.json()[0]["transcript_final"] is None

    client.patch(
        f"/api/v1/voice-notes/{note['id']}/review",
        headers=auth_header(guardian),
        json={
            "review_status": "approved",
            "transcript": "تفريغ معتمد.",
        },
    )
    after = client.get(
        f"/api/v1/children/{child['id']}/voice-notes",
        headers=auth_header(provider),
    )
    assert after.status_code == 200
    assert after.json()[0]["transcript_final"] == "تفريغ معتمد."


def test_provider_without_create_permission_cannot_transcribe(client):
    guardian = register(client, "voice.guardian3@example.com", "guardian")
    provider = register(
        client,
        "voice.provider3@example.com",
        "care_provider",
        "سمعيات",
    )
    child = create_child(client, guardian)
    note = create_voice_note(client, guardian, child)

    invite_and_accept(
        client,
        guardian,
        provider,
        child,
        ["view_profile", "view_voice_notes"],
    )
    response = client.post(
        f"/api/v1/voice-notes/{note['id']}/transcribe",
        headers=auth_header(provider),
    )
    assert response.status_code == 403
