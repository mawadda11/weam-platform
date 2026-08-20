from types import SimpleNamespace

from app.services import assistant_generation
from app.services.assistant_rag import SourceChunk
from app.services.gemini_failover import reset_failover_state


def test_legacy_assistant_httpx_monkeypatch_still_intercepts_gemini(monkeypatch):
    reset_failover_state()

    settings = SimpleNamespace(
        assistant_api_key="test-key",
        ai_api_key=None,
        assistant_model="gemini-3.6-flash",
        assistant_timeout_seconds=30,
    )
    monkeypatch.setattr(assistant_generation, "get_settings", lambda: settings)

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "الاستجابة السمعية مستقرة [1]."}]
                        }
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(assistant_generation.httpx, "post", fake_post)

    result = assistant_generation.generate_with_gemini(
        question="ما أهم النتائج؟",
        sources=[
            SourceChunk(
                source_type="report",
                source_id="r1",
                title="تقرير سمعيات",
                text="Hearing response was stable.",
            )
        ],
    )

    assert "gemini-3.6-flash" in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert result.provider == "gemini"
    assert result.model == "gemini-3.6-flash"
    assert "[1]" in result.text
