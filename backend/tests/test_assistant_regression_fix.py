from app.services.assistant_rag import SourceChunk, answer_from_sources, detect_intent


def test_followup_arabic_taa_marbuta_is_detected():
    assert detect_intent("ما المتابعة القادمة؟") == "follow_up"


def test_followup_fallback_filters_synthetic_metadata():
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


def test_fallback_keeps_non_diagnostic_safety_note():
    answer = answer_from_sources(
        "ما حالة تاليا؟",
        [
            SourceChunk(
                source_type="profile",
                source_id="p1",
                title="ملف تاليا",
                text="الحالات: ضعف سمع\nالاحتياجات: دعم التواصل",
            )
        ],
    )
    assert "لا يقدّم تشخيصًا طبيًا" in answer
