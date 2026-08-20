from app.services.assistant_generation import _normalize_safety_note, SAFETY_NOTE


def test_normalizes_gemini_diagnostic_disclaimer():
    raw = (
        "الخلاصة:\n"
        "• تحتاج إلى متابعة مستمرة [1].\n\n"
        "تنبيه: هذه الإجابة لأغراض تنسيق الرعاية وليست تشخيصاً طبيًا."
    )
    result = _normalize_safety_note(raw)
    assert SAFETY_NOTE in result
    assert "تنبيه:" not in result
    assert result.count("تشخيص") == 1


def test_does_not_duplicate_standard_safety_note():
    raw = f"الخلاصة:\n• معلومة [1].\n\n{SAFETY_NOTE}"
    result = _normalize_safety_note(raw)
    assert result.count(SAFETY_NOTE) == 1
