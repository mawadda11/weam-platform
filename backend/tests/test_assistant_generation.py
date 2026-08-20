from types import SimpleNamespace

from app.services import assistant_generation
from app.services.assistant_rag import SourceChunk


def test_gemini_generation_uses_only_provided_sources(monkeypatch):
    settings = SimpleNamespace(
        assistant_api_key="test-key",
        ai_api_key=None,
        assistant_model="gemini-2.5-flash",
        assistant_timeout_seconds=30,
    )
    monkeypatch.setattr(
        assistant_generation,
        "get_settings",
        lambda: settings,
    )

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "الاستجابة السمعية مستقرة [1]."
                                }
                            ]
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

    prompt = captured["json"]["contents"][0]["parts"][0]["text"]
    assert "Hearing response was stable." in prompt
    assert "اعتمادًا حصريًا" in prompt
    assert result.provider == "gemini"
    assert "[1]" in result.text
    assert captured["headers"]["x-goog-api-key"] == "test-key"


def test_gemini_failure_falls_back_locally(monkeypatch):
    settings = SimpleNamespace(
        assistant_provider="gemini",
        assistant_api_key="test-key",
        ai_api_key=None,
        assistant_model="gemini-2.5-flash",
        assistant_timeout_seconds=30,
    )
    monkeypatch.setattr(
        assistant_generation,
        "get_settings",
        lambda: settings,
    )

    def fail(**kwargs):
        raise RuntimeError("quota")

    monkeypatch.setattr(
        assistant_generation,
        "generate_with_gemini",
        fail,
    )

    result = assistant_generation.generate_grounded_answer(
        question="ما الهدف الحالي؟",
        sources=[
            SourceChunk(
                source_type="goal",
                source_id="g1",
                title="هدف التخاطب",
                text="الهدف: استخدام جمل من 4 كلمات. الحالة الحالية: completed. نسبة التقدم الحالية: 100%.",
            )
        ],
    )

    assert result.provider == "local_grounded_retrieval"
    assert result.used_fallback is True
    assert "100%" in result.text
