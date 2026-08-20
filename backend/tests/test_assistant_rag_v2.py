from app.services.assistant_rag import SourceChunk, detect_intent, retrieve


def test_voice_question_filters_non_voice_sources():
    sources = [
        SourceChunk("voice", "v1", "ملاحظة صوتية", "جلسة تخاطب جديدة"),
        SourceChunk("goal", "g1", "هدف التخاطب", "التقدم 80%"),
        SourceChunk("report", "r1", "تقرير", "نتيجة سمعيات"),
    ]
    result = retrieve(
        "هل توجد ملاحظة صوتية معتمدة فيها تحديث مهم؟",
        sources,
        limit=5,
    )
    assert result
    assert all(item.source_type == "voice" for item in result)


def test_summary_prefers_source_diversity():
    sources = [
        SourceChunk("report", "r1", "تقرير 1", "نتيجة مهمة"),
        SourceChunk("report", "r2", "تقرير 2", "نتيجة أخرى"),
        SourceChunk("goal", "g1", "هدف", "التقدم 70%"),
        SourceChunk("voice", "v1", "صوت", "جلسة اليوم"),
        SourceChunk("profile", "p1", "ملف", "احتياج دعم تواصل"),
    ]
    result = retrieve(
        "لخص لي أهم المعلومات في ملف الطفل",
        sources,
        limit=4,
    )
    assert {item.source_type for item in result} == {
        "profile",
        "report",
        "goal",
        "voice",
    }


def test_intent_detection():
    assert detect_intent("ما الأهداف الحالية؟") == "goals"
    assert detect_intent("ما أهم النتائج في آخر تقرير؟") == "reports"
    assert detect_intent("ما المتابعة القادمة؟") == "follow_up"
