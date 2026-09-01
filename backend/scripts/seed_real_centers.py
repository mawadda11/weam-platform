"""Idempotently seed real, publicly-sourced centers (Riyadh & Jeddah) into the directory.

Every fact below was read directly from the center's own official website on
2026-09-01 (see `source_urls` on each row). Nothing here is inferred: fields the
source did not state (working hours, exact age range, etc.) are left empty or
carry an explicit "not published" note rather than a guess.

This is deliberately a SEPARATE script from `seed_demo.py`: real centers are
reference data that should persist across demo resets, not synthetic data that
gets wiped. It is safe to re-run — rows are upserted by (name, city).

Two centers surfaced during research were deliberately excluded from this batch
even though the initial review marked them "include":
  * Riyadh Specialized Rehabilitation Center — a direct fetch of the site found
    no itemized services/specialties, and the male branch is stated to serve
    ages 12+ only, which is hard to reconcile with confident inclusion in a
    directory meant to also serve young children. Held back pending a manual
    look rather than seeded on thin/ambiguous data.
  * The five "include-with-caveats" candidates from the original research table
    are not in this script at all — their own sites blocked automated access,
    so no field values could be directly verified.

Usage (from backend/):
    .venv\\Scripts\\python.exe -m scripts.seed_real_centers
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.center import Center
from scripts._seed_shared import assert_migrations_at_head

REVIEWED_AT = datetime(2026, 9, 1, tzinfo=timezone.utc)

REAL_CENTERS: list[dict] = [
    {
        "name": "مراكز الأوائل للرعاية والتأهيل",
        "city": "الرياض",
        "region": "منطقة الرياض",
        "address": "تقاطع طريق عثمان بن عفان مع طريق الملك عبدالله، الرياض",
        "phone": "0535242200",
        "email": "info@alaweal.org",
        "working_hours": "الأحد – الخميس | صباحي 7:30ص–12:30م | مسائي 3:00م–8:00م",
        "services": ["تدخل مبكر", "تأهيل توحد", "علاج نفسي وسلوكي", "تأهيل نطق ولغة", "علاج وظيفي وحسي", "أنشطة ترفيهية واجتماعية"],
        "specialties": ["إعاقة ذهنية", "اضطراب طيف التوحد", "متلازمة داون", "صعوبات تعلم", "فرط حركة وتشتت انتباه", "تأخر نمو"],
        "served_needs": ["دعم النمو", "دعم سلوكي", "دعم النطق واللغة", "دعم حسي"],
        "min_age_years": 2,
        "max_age_years": None,
        "offers_in_person": True,
        "offers_remote": True,
        "description": (
            "مركز رعاية وتأهيل خاص في الرياض. يذكر الموقع الرسمي إتاحة جلسات فيديو عن بعد "
            "للعائلات البعيدة، إلى جانب الخدمات الحضورية."
        ),
        "source_urls": ["https://awael.sa/"],
    },
    {
        "name": "مركز العباقرة للرعاية النهارية",
        "city": "الرياض",
        "region": "منطقة الرياض",
        "address": "الرياض – حي الشرفية",
        "phone": "0556511765 / 0118102496",
        "email": "abaqera2023@gmail.com",
        "working_hours": "الأحد – الخميس | قسم الإناث 7:00–1:00 | قسم الذكور 3:00–8:00",
        "services": ["علاج طبيعي", "علاج نطق ولغة", "علاج وظيفي", "خدمات نفسية وسلوكية", "خدمات اجتماعية", "رعاية طبية"],
        "specialties": ["متلازمة داون", "اضطراب طيف التوحد", "إعاقة ذهنية", "إعاقة حركية", "فرط حركة وتشتت انتباه", "ضعف سمع"],
        "served_needs": ["دعم حركي", "دعم النطق واللغة", "دعم سلوكي", "متابعة سمعية"],
        "min_age_years": 2,
        "max_age_years": 45,
        "offers_in_person": True,
        "offers_remote": False,
        "description": (
            "مركز رعاية نهارية بقسمين منفصلين للذكور والإناث في حي الشرفية بالرياض. "
            "يذكر الموقع الرسمي ترخيصًا رقم 150 لقسم الإناث ورقم 2349 لقسم الذكور، "
            "وشهادة أيزو 9001:2015. يخدم فئات عمرية من 2 إلى 45 سنة."
        ),
        "source_urls": ["https://abaqeracenter.com/"],
    },
    {
        "name": "مركز بداية لتأهيل اضطرابات التواصل",
        "city": "الرياض",
        "region": "منطقة الرياض",
        "address": "حي النرجس، الرياض",
        "phone": "00966538626901",
        "email": "info@bedayacenter.sa",
        "working_hours": "غير معلن على الموقع الرسمي — يُنصح بالتواصل للتأكد.",
        "services": ["علاج اضطرابات النطق", "علاج اللغة", "علاج النطق عند الأطفال", "علاج اضطرابات البلع والصوت", "خدمات مساندة للتواصل (وظيفي وسلوكي ونفسي وأكاديمي)"],
        "specialties": ["تأتأة", "عسر التلفظ", "تأخر لغوي", "اضطرابات اللغة التعبيرية والاستقبالية"],
        "served_needs": ["دعم النطق واللغة", "دعم التواصل"],
        "min_age_years": None,
        "max_age_years": None,
        "offers_in_person": True,
        "offers_remote": False,
        "description": "مركز متخصص في اضطرابات التواصل والنطق واللغة في حي النرجس بالرياض، يخدم الأطفال والبالغين.",
        "source_urls": ["https://bedayacenter.sa/"],
    },
    {
        "name": "مركز تأهيل ورعاية الأطفال ذوي الإعاقة بشمال جدة",
        "city": "جدة",
        "region": "منطقة مكة المكرمة",
        "address": "حي الفروسية، شمال جدة",
        "phone": "920006222",
        "email": "info@dca.org.sa",
        "working_hours": "غير معلن على الموقع الرسمي — يُنصح بالتواصل للتأكد.",
        "services": ["عيادات تأهيلية وتعليمية شاملة"],
        "specialties": [],
        "served_needs": [],
        "min_age_years": None,
        "max_age_years": None,
        "offers_in_person": True,
        "offers_remote": False,
        "description": (
            "مركز تابع لجمعية الأطفال ذوي الإعاقة (دي سي ايه) في شمال جدة، مخصص للأطفال حصرًا "
            "بحسب ما نُشر (طاقة استيعابية معلنة 500 طفل). لا تتوفر تفاصيل عامة عن الفئات "
            "العمرية أو التخصصات الدقيقة على المصدر المتاح."
        ),
        "source_urls": ["https://store.dca.org.sa/p/72507"],
    },
    {
        "name": "الجمعية الأولى للتوحد بمنطقة مكة المكرمة",
        "city": "جدة",
        "region": "منطقة مكة المكرمة",
        "address": "جدة - حي الشاطئ",
        "phone": "0561868244",
        "email": None,
        "working_hours": "غير معلن على الموقع الرسمي — يُنصح بالتواصل للتأكد.",
        "services": ["برامج تعليمية", "برامج تدريب أسري", "استشارات أسرية", "برامج رياضية لأطفال التوحد", "برامج تأهيل مهني لشباب التوحد"],
        "specialties": ["اضطراب طيف التوحد"],
        "served_needs": ["دعم سلوكي", "دعم أسري"],
        "min_age_years": None,
        "max_age_years": None,
        "offers_in_person": True,
        "offers_remote": False,
        "description": "جمعية متخصصة في التوحد بحي الشاطئ في جدة، تقدم برامج للأطفال والشباب على السواء.",
        "source_urls": ["https://www.jacenter.sa/"],
    },
    {
        "name": "Badghish Rehabilitation and Healthcare (BRHC)",
        "city": "جدة",
        "region": "منطقة مكة المكرمة",
        "address": "Ibrahim Aljaffali, Jeddah, Saudi Arabia",
        "phone": "+966 54 911 2030 / +966 55 110 6350 / 920001604 (toll-free)",
        "email": "info@brhc.com.sa",
        "working_hours": "غير معلن على الموقع الرسمي — يُنصح بالتواصل للتأكد.",
        "services": [
            "Occupational Therapy", "Psychology", "Speech and Hearing therapy",
            "Paediatric Rehabilitation", "Neuro Rehabilitation", "Women's Health",
            "Spine Care", "Cardio Rehabilitation", "Orthopaedic Rehabilitation",
        ],
        "specialties": [
            "Cerebral palsy", "Nerve plexus injury", "Brain strokes", "Spinal injuries",
            "Hemiplegia", "Quadriplegia", "Neck/back pain", "Herniated disc",
        ],
        "served_needs": ["دعم حركي", "متابعة سمعية", "دعم النطق واللغة"],
        "min_age_years": None,
        "max_age_years": None,
        "offers_in_person": True,
        "offers_remote": False,
        "description": (
            "Badghish Rehabilitation and Healthcare (BRHC) — مركز تأهيل في جدة. الاسم "
            "المنشور رسميًا باللغة الإنجليزية فقط على الموقع الذي تم الاطلاع عليه؛ يقدم "
            "من ضمن خدماته تأهيلاً للأطفال (Paediatric Rehabilitation) إلى جانب خدمات "
            "للبالغين. يذكر الموقع قبول شركات تأمين (Bupa, Gulf, ISDB, Med) دون تفاصيل تغطية."
        ),
        "source_urls": ["https://brhc.com.sa/"],
    },
]


def seed_real_centers(db: Session, *, check_migrations: bool = True) -> dict[str, int]:
    if check_migrations:
        assert_migrations_at_head()

    created = 0
    updated = 0
    for entry in REAL_CENTERS:
        existing = db.scalar(
            select(Center).where(Center.name == entry["name"], Center.city == entry["city"])
        )
        if existing is None:
            db.add(
                Center(
                    name=entry["name"],
                    description=entry["description"],
                    city=entry["city"],
                    region=entry["region"],
                    address=entry["address"],
                    specialties=entry["specialties"],
                    services=entry["services"],
                    served_needs=entry["served_needs"],
                    min_age_years=entry["min_age_years"],
                    max_age_years=entry["max_age_years"],
                    offers_in_person=entry["offers_in_person"],
                    offers_remote=entry["offers_remote"],
                    phone=entry["phone"],
                    email=entry["email"],
                    working_hours=entry["working_hours"],
                    source_type="public_research",
                    source_urls=entry["source_urls"],
                    last_reviewed_at=REVIEWED_AT,
                    data_confidence="high",
                )
            )
            created += 1
        else:
            existing.description = entry["description"]
            existing.region = entry["region"]
            existing.address = entry["address"]
            existing.specialties = entry["specialties"]
            existing.services = entry["services"]
            existing.served_needs = entry["served_needs"]
            existing.min_age_years = entry["min_age_years"]
            existing.max_age_years = entry["max_age_years"]
            existing.offers_in_person = entry["offers_in_person"]
            existing.offers_remote = entry["offers_remote"]
            existing.phone = entry["phone"]
            existing.email = entry["email"]
            existing.working_hours = entry["working_hours"]
            existing.source_type = "public_research"
            existing.source_urls = entry["source_urls"]
            existing.last_reviewed_at = REVIEWED_AT
            existing.data_confidence = "high"
            updated += 1

    db.commit()
    return {"created": created, "updated": updated, "total": len(REAL_CENTERS)}


def main() -> None:
    settings = get_settings()
    if settings.environment == "production" and os.environ.get("WEAM_ALLOW_REAL_CENTER_SEED") != "true":
        raise SystemExit(
            "Refusing to seed real centers in production without explicit override. "
            "Set WEAM_ALLOW_REAL_CENTER_SEED=true if this is intentional."
        )

    with SessionLocal() as db:
        result = seed_real_centers(db)

    print(f"Real centers: {result['created']} created, {result['updated']} updated (of {result['total']} total).")


if __name__ == "__main__":
    main()
