"""Lama (لمى) — hearing-support journey. See docs/SEED_DATA_ARCHITECTURE.md."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from app.core.constants import AccessStatus, GuardianType, InvitationStatus
from app.models.care_team import CareInvitation, CareTeamMembership
from app.models.center import Center, CenterFavorite
from app.models.chat import ChatMessage, Conversation, ConversationParticipant, MessageReadReceipt
from app.models.child import CareProfile, Child, ChildIdentity, GuardianMembership
from app.models.center_match import CenterMatchRun
from app.models.follow_up import FollowUp
from app.models.goal import Goal, GoalUpdate
from app.models.report import Report, ReportVersion
from app.models.report_ai import ReportAIAnalysis
from app.models.assistant import AssistantMessage, AssistantThread
from app.models.voice_note import VoiceNote
from app.services.assistant_rag import collect_authorized_sources
from app.services.center_matching import compute_center_matches
from app.services.follow_up_notifications import follow_up_source_id

from .shared import (
    SeedContext,
    add_audit_log,
    date_days_ago,
    date_days_from_now,
    days_ago,
    days_from_now,
    ensure_favorite,
    mark_read,
    upload_report_pdf,
    upload_voice_wav,
)

EXTERNAL_REF = "demo-lama"


def build(ctx: SeedContext) -> Child:
    db = ctx.db
    now = ctx.now
    guardian = ctx.guardian
    slp = ctx.specialists["slp"]

    child = Child(created_by_user_id=guardian.id, external_ref=EXTERNAL_REF,
                  created_at=days_ago(now, 61), updated_at=days_ago(now, 1))
    child.identity = ChildIdentity(
        first_name="لمى",
        birth_date=date(2023, 9, 15),
        gender="female",
    )
    child.care_profile = CareProfile(
        conditions=["ضعف سمع"],
        needs=["دعم التواصل", "متابعة سمعية", "تنسيق المتابعات"],
        support_requirements=["إرشادات مكتوبة واضحة للأسرة", "مشاركة الملاحظات بين الأسرة وفريق الرعاية"],
        services=["سمعيات", "نطق وتخاطب"],
        summary="طفلة تحتاج متابعة سمعية منتظمة ودعم تواصل، مع تنسيق قريب بين الأسرة وأخصائية النطق والتخاطب.",
    )
    db.add(child)
    db.flush()

    db.add(
        GuardianMembership(
            child=child,
            guardian_user_id=guardian.id,
            guardian_type=GuardianType.PRIMARY.value,
            accepted_at=days_ago(now, 60),
            created_at=days_ago(now, 60),
        )
    )

    invitation_created = days_ago(now, 52)
    db.add(
        CareInvitation(
            child_id=child.id,
            invited_by_user_id=guardian.id,
            email=slp.email,
            target_role="care_provider",
            role_label="أخصائية نطق وتخاطب",
            permissions=[
                "view_profile", "view_care_team", "view_reports", "upload_reports",
                "view_goals", "manage_goals", "view_timeline",
                "view_voice_notes", "create_voice_notes", "message_team",
            ],
            status=InvitationStatus.ACCEPTED.value,
            invitation_expires_at=days_from_now(invitation_created, 14),
            created_at=invitation_created,
            responded_at=days_ago(now, 51),
        )
    )
    db.add(
        CareTeamMembership(
            child_id=child.id,
            user_id=slp.id,
            invited_by_user_id=guardian.id,
            role_label="أخصائية نطق وتخاطب",
            permissions=[
                "view_profile", "view_care_team", "view_reports", "upload_reports",
                "view_goals", "manage_goals", "view_timeline",
                "view_voice_notes", "create_voice_notes", "message_team",
            ],
            access_status=AccessStatus.ACTIVE.value,
            accepted_at=days_ago(now, 51),
            created_at=days_ago(now, 51),
        )
    )
    db.flush()

    # --- Report + version + PDF asset --------------------------------------
    report_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    report_created = days_ago(now, 45)
    stored = upload_report_pdf(
        ctx, child_id=child.id, report_id=report_id, version_id=version_id,
        asset_filename="lama_hearing_report.pdf",
    )
    db.add(
        Report(
            id=report_id,
            child_id=child.id,
            title="تقرير سمعيات ونطق وتخاطب",
            report_type="سمعيات",
            report_date=date_days_ago(now, 45),
            source_label="مركز نبض للسمعيات والتخاطب (تجريبي)",
            visibility="care_team",
            created_by_user_id=slp.id,
            created_at=report_created,
            updated_at=report_created,
        )
    )
    db.add(
        ReportVersion(
            id=version_id,
            report_id=report_id,
            version_number=1,
            original_filename="lama_hearing_report.pdf",
            content_type=stored.content_type,
            storage_key=stored.key,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            uploaded_by_user_id=slp.id,
            created_at=report_created,
        )
    )
    audit = add_audit_log(
        db, child_id=child.id, actor_user_id=slp.id, action="report_uploaded",
        entity_type="report", entity_id=report_id, created_at=report_created,
        details={"version": 1, "visibility": "care_team", "report_type": "سمعيات"},
    )
    mark_read(db, user_id=guardian.id, event_key=f"audit:{audit.id}")  # already seen in the demo story

    follow_up_actions = [
        "مراجعة السمعيات خلال 3 أشهر",
        "متابعة جلسات النطق الأسبوعية دون انقطاع",
    ]
    db.add(
        ReportAIAnalysis(
            child_id=child.id,
            report_id=report_id,
            report_version_id=version_id,
            provider="seeded_demo",
            model="weam-demo-v1",
            analysis_status="completed",
            review_status="approved",
            result_json={
                "summary": "التقرير يوثّق استخدامًا منتظمًا للمعين السمعي مع تحسّن في نطق المقاطع البسيطة، ويشير إلى صعوبة نسبية في متابعة الأصوات المتعددة داخل الصف.",
                "key_findings": [
                    "استخدام معين سمعي منتظم مع استجابة جيدة في البيئة الهادئة.",
                    "صعوبة نسبية في متابعة الأصوات المتعددة داخل الصف الدراسي.",
                    "تحسّن ملحوظ في نطق المقاطع الصوتية البسيطة.",
                ],
                "needs": ["دعم التواصل بين المنزل والمدرسة", "متابعة سمعية دورية"],
                "recommendations": ["ضبط إعدادات المعين السمعي دوريًا", "تنسيق مواعيد المتابعة مع الأسرة"],
                "follow_up_actions": follow_up_actions,
                "goal_mentions": ["توسيع المفردات", "الفهم السمعي داخل الصف"],
                "source_language": "ar",
                "evidence": [
                    "استخدام معين سمعي بشكل منتظم مع استجابة جيدة في البيئة الهادئة.",
                    "تحسّن ملحوظ في نطق المقاطع الصوتية البسيطة خلال الجلسات الأخيرة.",
                ],
                "limitations": [
                    "هذا تحليل تجريبي مُعدّ مسبقًا لأغراض العرض، وليس نتيجة تحليل حي — راجعي محتواه كما تُراجعين أي تحليل فعلي قبل الاعتماد عليه.",
                ],
                "safety_note": "هذا تلخيص مساعد وليس تشخيصًا أو خطة علاجية بديلة عن المختص.",
            },
            created_by_user_id=guardian.id,
            reviewed_by_user_id=slp.id,
            reviewed_at=days_ago(now, 44),
            created_at=days_ago(now, 44),
            updated_at=days_ago(now, 44),
        )
    )

    for i, action_text in enumerate(follow_up_actions):
        source_id = follow_up_source_id(report_id, action_text)
        due = date_days_from_now(now, 0) if i == 0 else date_days_from_now(now, 10)
        db.add(
            FollowUp(
                child_id=child.id,
                title=action_text,
                note=action_text,
                due_date=due,
                status="open",
                source_type="report_ai",
                source_id=source_id,
                source_label=f"تقرير معتمد · تقرير سمعيات ونطق وتخاطب",
                created_by_user_id=slp.id,
                created_at=days_ago(now, 44),
            )
        )

    # --- Goals ---------------------------------------------------------------
    goal1 = Goal(
        child_id=child.id,
        title="توسيع المفردات المستخدمة يوميًا",
        description="زيادة عدد الكلمات التي تستخدمها لمى بشكل مستقل في المواقف اليومية.",
        category="تواصل",
        status="in_progress",
        progress_percent=55,
        start_date=date_days_ago(now, 40),
        target_date=date_days_from_now(now, 30),
        assigned_to_user_id=slp.id,
        created_by_user_id=slp.id,
        created_at=days_ago(now, 40),
    )
    db.add(goal1)
    db.flush()
    db.add(GoalUpdate(goal_id=goal1.id, actor_user_id=slp.id, note="تحسّن ملحوظ في المفردات المستخدمة في الجلسات.",
                       progress_percent=55, status="in_progress", created_at=days_ago(now, 10)))
    audit_goal1 = add_audit_log(
        db, child_id=child.id, actor_user_id=slp.id, action="goal_created",
        entity_type="goal", entity_id=goal1.id, created_at=days_ago(now, 40),
        details={"title": goal1.title, "assigned_to_user_id": slp.id},
    )
    mark_read(db, user_id=guardian.id, event_key=f"audit:{audit_goal1.id}")

    goal2 = Goal(
        child_id=child.id,
        title="تحسين الفهم السمعي داخل الصف الدراسي",
        description="متابعة قدرة لمى على تمييز الأصوات المتعددة داخل بيئة الصف.",
        category="متابعة سمعية",
        status="in_progress",
        progress_percent=40,
        start_date=date_days_ago(now, 20),
        target_date=date_days_from_now(now, 5),
        assigned_to_user_id=slp.id,
        created_by_user_id=slp.id,
        created_at=days_ago(now, 20),
    )
    db.add(goal2)
    db.flush()
    add_audit_log(
        db, child_id=child.id, actor_user_id=slp.id, action="goal_progress_updated",
        entity_type="goal", entity_id=goal2.id, created_at=days_ago(now, 3),
        details={"progress_percent": 40, "status": "in_progress"},
    )  # left unread on purpose — a "new" update the guardian hasn't opened yet

    goal3 = Goal(
        child_id=child.id,
        title="التعرّف على المعين السمعي وارتدائه بشكل مستقل",
        description="هدف سابق تحقق بالكامل خلال المرحلة الأولى من المتابعة.",
        category="استقلالية",
        status="completed",
        progress_percent=100,
        start_date=date_days_ago(now, 90),
        target_date=date_days_ago(now, 30),
        assigned_to_user_id=slp.id,
        created_by_user_id=guardian.id,
        created_at=days_ago(now, 90),
    )
    db.add(goal3)
    db.flush()
    db.add(GoalUpdate(goal_id=goal3.id, actor_user_id=slp.id, note="تم تحقيق الهدف بالكامل.",
                       progress_percent=100, status="completed", created_at=days_ago(now, 30)))

    # --- Voice note ------------------------------------------------------------
    voice_note_id = str(uuid.uuid4())
    voice_stored = upload_voice_wav(ctx, child_id=child.id, voice_note_id=voice_note_id)
    db.add(
        VoiceNote(
            id=voice_note_id,
            child_id=child.id,
            title="ملاحظة صوتية من الأم بعد جلسة نطق",
            original_filename="demo_voice_sample.wav",
            content_type=voice_stored.content_type,
            storage_key=voice_stored.key,
            size_bytes=voice_stored.size_bytes,
            sha256=voice_stored.sha256,
            duration_seconds=2,
            transcription_status="completed",
            review_status="approved",
            transcript_draft="لمى صارت تردد كلمات جديدة بعد جلسة اليوم وفرحانة توريها لنا.",
            transcript_final="لمى بدأت تردد كلمات جديدة بعد جلسة اليوم، وكانت متحمسة لعرضها علينا في المنزل.",
            transcript_language="ar",
            stt_provider="seeded_demo",
            stt_model="weam-demo-v1",
            created_by_user_id=guardian.id,
            reviewed_by_user_id=guardian.id,
            reviewed_at=days_ago(now, 6),
            created_at=days_ago(now, 6),
            updated_at=days_ago(now, 6),
        )
    )

    # --- Assistant thread --------------------------------------------------
    thread = AssistantThread(child_id=child.id, created_by_user_id=guardian.id, title="متابعة السمعيات",
                              created_at=days_ago(now, 2), updated_at=days_ago(now, 2))
    db.add(thread)
    db.flush()
    db.add(AssistantMessage(thread_id=thread.id, role="user",
                             content="هل في تحديث على متابعة السمعيات الأخيرة؟",
                             sources_json=[], created_at=days_ago(now, 2)))
    db.add(
        AssistantMessage(
            thread_id=thread.id,
            role="assistant",
            content=(
                "بحسب تقرير السمعيات الأخير، يُنصح بمراجعة السمعيات خلال 3 أشهر ومتابعة جلسات النطق الأسبوعية "
                "دون انقطاع. لا تتوفر معلومات إضافية بعد هذا التقرير ضمن السجلات المصرّح لك بالاطلاع عليها — "
                "يمكنك التواصل مع أخصائية النطق والتخاطب للاستفسار عن أي تحديثات لاحقة."
            ),
            sources_json=[
                {
                    "index": 1,
                    "source_type": "report",
                    "source_id": report_id,
                    "title": "تقرير سمعيات ونطق وتخاطب",
                    "snippet": "يُنصح بمراجعة السمعيات خلال 3 أشهر ومتابعة جلسات النطق الأسبوعية دون انقطاع.",
                    "occurred_at": days_ago(now, 45).isoformat(),
                }
            ],
            created_at=days_ago(now, 2),
        )
    )

    # --- Center matching (real algorithm) -----------------------------------
    grant = ctx.guardian_grant()
    sources = [
        s for s in collect_authorized_sources(db, child_id=child.id, user=guardian, grant=grant)
        if s.source_type in {"profile", "report", "goal"}
    ]
    centers = list(
        db.scalars(
            select(Center).where(Center.is_active.is_(True), Center.verification_status == "verified")
        ).all()
    )
    result = compute_center_matches(child=child, sources=sources, centers=centers, city="الرياض", delivery_mode="in_person")
    run = CenterMatchRun(
        child_id=child.id,
        requested_by_user_id=guardian.id,
        provider=result.provider,
        model=result.model,
        criteria_json={"city": "الرياض", "delivery_mode": "in_person"},
        result_json=result.data,
        created_at=days_ago(now, 5),
    )
    db.add(run)
    db.flush()
    top_matches = result.data.get("matches") or []
    if top_matches:
        ensure_favorite(db, user_id=guardian.id, center_id=top_matches[0]["center_id"], created_at=days_ago(now, 4))

    # --- Conversation / chat -------------------------------------------------
    conversation = Conversation(child_id=child.id, kind="direct", created_by_user_id=guardian.id,
                                 created_at=days_ago(now, 3), updated_at=days_ago(now, 1))
    db.add(conversation)
    db.flush()
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=guardian.id, joined_at=days_ago(now, 3)))
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=slp.id, joined_at=days_ago(now, 3)))

    msg1 = ChatMessage(conversation_id=conversation.id, sender_user_id=guardian.id,
                        body="هل نحتاج تعديل موعد جلسة الأسبوع الجاي؟", created_at=days_ago(now, 3))
    db.add(msg1)
    db.flush()
    db.add(MessageReadReceipt(message_id=msg1.id, user_id=guardian.id, read_at=days_ago(now, 3)))
    db.add(MessageReadReceipt(message_id=msg1.id, user_id=slp.id, read_at=days_ago(now, 3)))

    msg2 = ChatMessage(
        conversation_id=conversation.id, sender_user_id=slp.id,
        body="ما فيه داعي، بس حبيت أشاركك هدف المفردات — تقدر تشوفينه في ملف لمى.",
        message_type="shared", shared_entity_type="goal", shared_entity_id=goal1.id,
        shared_entity_title=goal1.title, created_at=days_ago(now, 1),
    )
    db.add(msg2)
    db.flush()
    db.add(MessageReadReceipt(message_id=msg2.id, user_id=slp.id, read_at=days_ago(now, 1)))
    db.add(MessageReadReceipt(message_id=msg2.id, user_id=guardian.id, read_at=days_ago(now, 1)))

    return child
