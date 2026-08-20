from __future__ import annotations

import httpx
import pytest

from app.services import gemini_failover


def _response(status: int, body: dict | None = None, *, retry_after: str | None = None):
    request = httpx.Request("POST", "https://example.test")
    headers = {"Retry-After": retry_after} if retry_after else {}
    return httpx.Response(
        status,
        json=body or {"error": {"message": "test"}},
        headers=headers,
        request=request,
    )


def test_primary_gemini_36_is_used_when_available(monkeypatch):
    gemini_failover.reset_failover_state()
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return _response(200, {"candidates": []})

    monkeypatch.setattr(gemini_failover.httpx, "post", fake_post)

    result = gemini_failover.call_gemini_with_failover(
        api_key="test",
        primary_model="gemini-3.6-flash",
        body={"contents": []},
        timeout_seconds=5,
    )

    assert result.model == "gemini-3.6-flash"
    assert result.used_secondary is False
    assert len(calls) == 1


def test_429_on_36_falls_back_to_35(monkeypatch):
    gemini_failover.reset_failover_state()
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        if "gemini-3.6-flash" in url:
            return _response(429, retry_after="60")
        return _response(200, {"candidates": []})

    monkeypatch.setattr(gemini_failover.httpx, "post", fake_post)

    result = gemini_failover.call_gemini_with_failover(
        api_key="test",
        primary_model="gemini-3.6-flash",
        body={"contents": []},
        timeout_seconds=5,
    )

    assert result.model == "gemini-3.5-flash"
    assert result.used_secondary is True
    assert len(calls) == 2


def test_cooldown_temporarily_skips_36_then_returns_after_reset(monkeypatch):
    gemini_failover.reset_failover_state()
    calls = []

    def first_post(url, **kwargs):
        calls.append(url)
        if "gemini-3.6-flash" in url:
            return _response(429)
        return _response(200, {"candidates": []})

    monkeypatch.setattr(gemini_failover.httpx, "post", first_post)

    first = gemini_failover.call_gemini_with_failover(
        api_key="test",
        primary_model="gemini-3.6-flash",
        body={"contents": []},
        timeout_seconds=5,
    )
    assert first.model == "gemini-3.5-flash"

    calls.clear()
    second = gemini_failover.call_gemini_with_failover(
        api_key="test",
        primary_model="gemini-3.6-flash",
        body={"contents": []},
        timeout_seconds=5,
    )
    assert second.model == "gemini-3.5-flash"
    assert all("gemini-3.6-flash" not in url for url in calls)

    gemini_failover.reset_failover_state()
    calls.clear()

    def success_post(url, **kwargs):
        calls.append(url)
        return _response(200, {"candidates": []})

    monkeypatch.setattr(gemini_failover.httpx, "post", success_post)
    recovered = gemini_failover.call_gemini_with_failover(
        api_key="test",
        primary_model="gemini-3.6-flash",
        body={"contents": []},
        timeout_seconds=5,
    )
    assert recovered.model == "gemini-3.6-flash"


def test_both_gemini_models_unavailable_raises_for_local_caller(monkeypatch):
    gemini_failover.reset_failover_state()

    monkeypatch.setattr(
        gemini_failover.httpx,
        "post",
        lambda *args, **kwargs: _response(429),
    )

    with pytest.raises(gemini_failover.GeminiFailoverError):
        gemini_failover.call_gemini_with_failover(
            api_key="test",
            primary_model="gemini-3.6-flash",
            body={"contents": []},
            timeout_seconds=5,
        )
