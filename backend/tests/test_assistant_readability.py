from app.services.assistant_rag import SourceChunk, answer_from_sources


def test_fallback_goal_is_short_and_human_readable():
    answer = answer_from_sources(
        "ما الأهداف الحالية ونسبة التقدم؟",
        [
            SourceChunk(
                source_type="goal",
                source_id="g1",
                title="هدف · استخدام جمل من 4 كلمات",
                text=(
                    "الهدف: استخدام جمل من 4 كلمات\n"
                    "الحالة الحالية: completed\n"
                    "نسبة التقدم الحالية: 100%\n"
                    "آخر تحديث: لا توجد ملاحظة نصية"
                ),
            )
        ],
    )
    assert "100%" in answer
    assert "مكتمل" in answer
    assert "completed" not in answer
    assert len(answer) < 350


def test_fallback_followup_drops_synthetic_metadata():
    answer = answer_from_sources(
        "ما المتابعة القادمة؟",
        [
            SourceChunk(
                source_type="report",
                source_id="r1",
                title="تقرير معتمد · سمعيات",
                text=(
                    "إجراءات المتابعة: Audiology review in 3 months. | "
                    "Synthetic test document for Weam MVP upload testing only."
                ),
            )
        ],
    )
    assert "Audiology review in 3 months." in answer
    assert "Synthetic test document" not in answer
