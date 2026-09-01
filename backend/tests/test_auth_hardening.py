from app.core.config import Settings, assert_production_ready


def _register(client, email="lock@example.com"):
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


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_account_locks_after_repeated_failed_logins(client):
    _register(client, "lock@example.com")

    for _ in range(5):
        response = _login(client, "lock@example.com", "wrong-password")
        assert response.status_code == 401

    locked = _login(client, "lock@example.com", "wrong-password")
    assert locked.status_code == 429

    # Even the correct password is rejected while locked.
    still_locked = _login(client, "lock@example.com", "StrongPass123!")
    assert still_locked.status_code == 429


def test_successful_login_resets_failed_attempt_counter(client):
    _register(client, "reset@example.com")

    for _ in range(3):
        assert _login(client, "reset@example.com", "wrong-password").status_code == 401

    ok = _login(client, "reset@example.com", "StrongPass123!")
    assert ok.status_code == 200

    # Counter was reset, so three more failures should not lock the account.
    for _ in range(3):
        assert _login(client, "reset@example.com", "wrong-password").status_code == 401
    assert _login(client, "reset@example.com", "StrongPass123!").status_code == 200


def test_refresh_token_is_single_use_and_rotates(client):
    payload = _register(client, "rotate@example.com")
    original_refresh = payload["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]
    assert new_refresh != original_refresh

    # The original refresh token was single-use; replaying it must fail.
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": original_refresh})
    assert replay.status_code == 401

    # The newly rotated token still works.
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert second.status_code == 200


def test_logout_revokes_refresh_token(client):
    payload = _register(client, "logout@example.com")
    refresh_token = payload["refresh_token"]

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401

    # Logging out an already-revoked (or bogus) token must not error or leak state.
    again = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert again.status_code == 204


def _settings(**overrides) -> Settings:
    base = dict(
        environment="production",
        jwt_secret="a" * 40,
        create_tables_on_startup=False,
        database_url="postgresql+psycopg://weam:weam@localhost:5432/weam",
    )
    base.update(overrides)
    return Settings(**base)


def test_production_guard_allows_safe_configuration():
    assert_production_ready(_settings())  # must not raise


def test_production_guard_rejects_default_jwt_secret():
    try:
        assert_production_ready(_settings(jwt_secret="replace-me-locally"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "JWT_SECRET" in str(exc)


def test_production_guard_rejects_create_tables_on_startup():
    try:
        assert_production_ready(_settings(create_tables_on_startup=True))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "CREATE_TABLES_ON_STARTUP" in str(exc)


def test_production_guard_rejects_non_postgres_database():
    try:
        assert_production_ready(_settings(database_url="sqlite:///demo.db"))
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)


def test_production_guard_ignores_non_production_environment():
    assert_production_ready(_settings(environment="development", jwt_secret="replace-me-locally"))
