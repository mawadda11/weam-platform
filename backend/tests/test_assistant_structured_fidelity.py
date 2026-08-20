from app.services.assistant_generation import _ensure_structured_source_fidelity
from app.services.assistant_rag import SourceChunk


def test_need_question_preserves_exact_profile_term():
    sources = [
        SourceChunk(
            source_type="profile",
            source_id="child-1",
            title="ملف تاليا",
            text=(
                "الحالات: ضعف سمع\n"
                "الاحتياجات: دعم التواصل\n"
                "متطلبات الدعم: الجلوس بالقرب من المعلمة\n"
                "الخدمات الحالية: تخاطب"
            ),
        )
    ]

    result = _ensure_structured_source_fidelity(
        question="ما احتياجات تاليا الحالية؟",
        text=(
            "الخلاصة:\n"
            "• تحتاج تاليا إلى دعم في التواصل [1].\n\n"
            "هذا مساعد تنسيقي يعتمد على بيانات الملف ولا يقدّم تشخيصًا طبيًا "
            "أو يغيّر خطة علاجية."
        ),
        sources=sources,
    )

    assert "دعم التواصل" in result
    assert "الاحتياجات المسجلة" in result


def test_exact_profile_term_is_not_duplicated():
    sources = [
        SourceChunk(
            source_type="profile",
            source_id="child-1",
            title="ملف تاليا",
            text="الاحتياجات: دعم التواصل",
        )
    ]

    original = "الخلاصة:\n• الاحتياج الحالي هو دعم التواصل [1]."
    result = _ensure_structured_source_fidelity(
        question="ما الاحتياجات؟",
        text=original,
        sources=sources,
    )

    assert result == original


def test_unrelated_question_does_not_append_profile_need():
    sources = [
        SourceChunk(
            source_type="profile",
            source_id="child-1",
            title="ملف تاليا",
            text="الاحتياجات: دعم التواصل",
        )
    ]

    original = "الخلاصة:\n• لا توجد معلومات إضافية."
    result = _ensure_structured_source_fidelity(
        question="ما آخر تقرير؟",
        text=original,
        sources=sources,
    )

    assert result == original
