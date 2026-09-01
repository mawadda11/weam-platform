"""Rawan (روان) — educational-support journey."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from app.core.constants import AccessStatus, GuardianType, InvitationStatus
from app.models.assistant import AssistantMessage, AssistantThread
from app.models.care_team import CareInvitation, CareTeamMembership
from app.models.center import Center, CenterFavorite
from app.models.center_match import CenterMatchRun
from app.models.chat import ChatMessage, Conversation, ConversationParticipant, MessageReadReceipt
from app.models.child import CareProfile, Child, ChildIdentity, GuardianMembership
from app.models.follow_up import FollowUp
from app.models.goal import Goal, GoalUpdate
from app.models.report import Report, ReportVersion
from app.models.report_ai import ReportAIAnalysis
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
    upload_report_pdf,
    upload_voice_wav,
)

EXTERNAL_REF = "demo-rawan"


def build(ctx: SeedContext) -> Child:
    db = ctx.db
    now = ctx.now
    guardian = ctx.guardian
    edu = ctx.specialists["edu"]
    slp = ctx.specialists["slp"]  # reused here with a narrower, view-only slot

    child = Child(created_by_user_id=guardian.id, external_ref=EXTERNAL_REF,
                  created_at=days_ago(now, 56), updated_at=days_ago(now, 1))
    child.identity = ChildIdentity(first_name="روان", birth_date=date(2016, 11, 2), gender="female")
    child.care_profile = CareProfile(
        conditions=["صعوبات تعلم"],
        needs=["دعم تعليمي", "روتين منظم", "تواصل بين الأسرة والمختصين"],
        support_requirements=["جدول يومي منظم بصريًا", "تقسيم المهام إلى خطوات واضحة"],
        services=["دعم تعليمي", "تربية خاصة"],
        summary="طفلة تحتاج دعمًا تعليميًا فرديًا وروتينًا يوميًا واضحًا، مع تواصل منتظم بين الأسرة والمدرسة.",
    )
    db.add(child)
    db.flush()

    db.add(GuardianMembership(child=child, guardian_user_id=guardian.id, guardian_type=GuardianType.PRIMARY.value,
                               accepted_at=days_ago(now, 55), created_at=days_ago(now, 55)))

    # Educational specialist — a time-limited engagement (expires a few weeks out).
    invitation_created = days_ago(now, 33)
    db.add(CareInvitation(
        child_id=child.id, invited_by_user_id=guardian.id, email=edu.email, target_role="care_provider",
        role_label="أخصائية تربية خاصة",
        permissions=["view_profile", "view_care_team", "view_reports", "upload_reports", "view_goals",
                     "manage_goals", "view_timeline", "message_team"],
        status=InvitationStatus.ACCEPTED.value, invitation_expires_at=days_from_now(invitation_created, 14),
        created_at=invitation_created, responded_at=days_ago(now, 32),
    ))
    db.add(CareTeamMembership(
        child_id=child.id, user_id=edu.id, invited_by_user_id=guardian.id, role_label="أخصائية تربية خاصة",
        permissions=["view_profile", "view_care_team", "view_reports", "upload_reports", "view_goals",
                     "manage_goals", "view_timeline", "message_team"],
        access_status=AccessStatus.ACTIVE.value, accepted_at=days_ago(now, 32), created_at=days_ago(now, 32),
        expires_at=days_from_now(now, 21),
    ))

    # SLP reused here with a narrow, view-only slot — a concrete "different permission
    # combination for the same person" example (full permissions on Lama, minimal here).
    db.add(CareTeamMembership(
        child_id=child.id, user_id=slp.id, invited_by_user_id=guardian.id, role_label="متابعة تواصل (اطلاع)",
        permissions=["view_profile", "view_reports"],
        access_status=AccessStatus.ACTIVE.value, accepted_at=days_ago(now, 10), created_at=days_ago(now, 10),
    ))
    db.flush()

    report_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    report_created = days_ago(now, 25)
    stored = upload_report_pdf(ctx, child_id=child.id, report_id=report_id, version_id=version_id,
                                asset_filename="rawan_learning_report.pdf")
    db.add(Report(id=report_id, child_id=child.id, title="تقرير دعم تعليمي", report_type="دعم تعليمي",
                   report_date=date_days_ago(now, 25), source_label="مركز رواق للدعم التعليمي (تجريبي)",
                   visibility="care_team", created_by_user_id=edu.id, created_at=report_created, updated_at=report_created))
    db.add(ReportVersion(id=version_id, report_id=report_id, version_number=1,
                          original_filename="rawan_learning_report.pdf", content_type=stored.content_type,
                          storage_key=stored.key, size_bytes=stored.size_bytes, sha256=stored.sha256,
                          uploaded_by_user_id=edu.id, created_at=report_created))
    add_audit_log(db, child_id=child.id, actor_user_id=edu.id, action="report_uploaded",
                   entity_type="report", entity_id=report_id, created_at=report_created,
                   details={"version": 1, "visibility": "care_team", "report_type": "دعم تعليمي"})

    follow_up_actions = ["اجتماع متابعة مع المعلمة خلال أسبوعين", "تحديث خطة الدعم التعليمي الفردية"]
    db.add(ReportAIAnalysis(
        child_id=child.id, report_id=report_id, report_version_id=version_id,
        provider="seeded_demo", model="weam-demo-v1", analysis_status="completed", review_status="approved",
        result_json={
            "summary": "تركيز جيد خلال المهام القصيرة المقسّمة إلى خطوات واضحة، مع صعوبة في الحفاظ على التركيز لفترات أطول.",
            "key_findings": ["تركيز جيد خلال المهام القصيرة المقسّمة إلى خطوات واضحة.",
                              "صعوبة في الحفاظ على التركيز عند طول مدة المهمة الواحدة.",
                              "استجابة إيجابية لجدول يومي منظم بصريًا."],
            "needs": ["دعم تعليمي فردي منظم", "روتين يومي واضح ومتسق"],
            "recommendations": ["تقسيم المهام إلى خطوات أقصر", "استخدام جدول بصري يومي"],
            "follow_up_actions": follow_up_actions,
            "goal_mentions": ["التركيز أثناء المهام الصفية", "دعم القراءة"],
            "source_language": "ar",
            "evidence": ["تركيز جيد خلال المهام القصيرة المقسّمة إلى خطوات واضحة.",
                         "استجابة إيجابية لجدول يومي منظم بصريًا."],
            "limitations": ["هذا تحليل تجريبي مُعدّ مسبقًا لأغراض العرض، وليس نتيجة تحليل حي — راجعيه قبل الاعتماد عليه."],
            "safety_note": "هذا تلخيص مساعد وليس تشخيصًا أو خطة علاجية بديلة عن المختص.",
        },
        created_by_user_id=guardian.id, reviewed_by_user_id=edu.id, reviewed_at=days_ago(now, 24),
        created_at=days_ago(now, 24), updated_at=days_ago(now, 24),
    ))

    # One completed follow-up (demonstrates history), one open.
    completed_text, open_text = follow_up_actions[0], follow_up_actions[1]
    db.add(FollowUp(child_id=child.id, title=completed_text, note=completed_text,
                     due_date=date_days_ago(now, 5), status="completed",
                     source_type="report_ai", source_id=follow_up_source_id(report_id, completed_text),
                     source_label="تقرير معتمد · تقرير دعم تعليمي", created_by_user_id=edu.id,
                     completed_by_user_id=guardian.id, completed_at=days_ago(now, 4), created_at=days_ago(now, 24)))
    db.add(FollowUp(child_id=child.id, title=open_text, note=open_text, due_date=date_days_from_now(now, 15),
                     status="open", source_type="report_ai", source_id=follow_up_source_id(report_id, open_text),
                     source_label="تقرير معتمد · تقرير دعم تعليمي", created_by_user_id=edu.id, created_at=days_ago(now, 24)))

    goal1 = Goal(child_id=child.id, title="تحسين التركيز أثناء المهام الصفية",
                 description="زيادة مدة التركيز المستمر أثناء أداء المهام الصفية القصيرة.",
                 category="تعليمي", status="in_progress", progress_percent=35,
                 start_date=date_days_ago(now, 22), target_date=date_days_from_now(now, 40),
                 assigned_to_user_id=edu.id, created_by_user_id=edu.id, created_at=days_ago(now, 22))
    db.add(goal1)
    db.flush()
    db.add(GoalUpdate(goal_id=goal1.id, actor_user_id=edu.id, note="تحسّن بسيط بعد استخدام الجدول البصري.",
                       progress_percent=35, status="in_progress", created_at=days_ago(now, 2)))
    add_audit_log(db, child_id=child.id, actor_user_id=edu.id, action="goal_progress_updated",
                   entity_type="goal", entity_id=goal1.id, created_at=days_ago(now, 2),
                   details={"progress_percent": 35, "status": "in_progress"})

    goal2 = Goal(child_id=child.id, title="دعم مهارات القراءة الأساسية",
                 description="بناء مهارات القراءة تدريجيًا وفق خطة الدعم الفردية.",
                 category="تعليمي", status="in_progress", progress_percent=20,
                 start_date=date_days_ago(now, 15), target_date=date_days_from_now(now, 75),
                 assigned_to_user_id=edu.id, created_by_user_id=edu.id, created_at=days_ago(now, 15))
    db.add(goal2)

    voice_note_id = str(uuid.uuid4())
    voice_stored = upload_voice_wav(ctx, child_id=child.id, voice_note_id=voice_note_id)
    db.add(VoiceNote(id=voice_note_id, child_id=child.id, title="ملاحظة من الأم بعد الواجب المدرسي",
                      original_filename="demo_voice_sample.wav", content_type=voice_stored.content_type,
                      storage_key=voice_stored.key, size_bytes=voice_stored.size_bytes, sha256=voice_stored.sha256,
                      duration_seconds=2, transcription_status="completed", review_status="approved",
                      transcript_draft="روان خلصت الواجب اليوم بمساعدة بسيطة بس، أحسن من الأسبوع اللي فات.",
                      transcript_final="روان أنهت واجبها المدرسي اليوم بمساعدة أقل مقارنة بالأسبوع الماضي.",
                      transcript_language="ar", stt_provider="seeded_demo", stt_model="weam-demo-v1",
                      created_by_user_id=guardian.id, reviewed_by_user_id=guardian.id,
                      reviewed_at=days_ago(now, 3), created_at=days_ago(now, 3), updated_at=days_ago(now, 3)))

    thread = AssistantThread(child_id=child.id, created_by_user_id=guardian.id, title="متابعة الدعم التعليمي",
                              created_at=days_ago(now, 1), updated_at=days_ago(now, 1))
    db.add(thread)
    db.flush()
    db.add(AssistantMessage(thread_id=thread.id, role="user", content="هل عندنا خطة محدثة لدعم القراءة؟",
                             sources_json=[], created_at=days_ago(now, 1)))
    db.add(AssistantMessage(
        thread_id=thread.id, role="assistant",
        content=("يوجد هدف نشط لدعم مهارات القراءة الأساسية ضمن خطة الدعم الفردية. تفاصيل الخطة الكاملة "
                 "غير متوفرة كملف منفصل ضمن السجلات المصرّح لك بالاطلاع عليها — يمكنك سؤال أخصائية التربية الخاصة."),
        sources_json=[{"index": 1, "source_type": "goal", "source_id": goal2.id,
                        "title": "دعم مهارات القراءة الأساسية",
                        "snippet": "بناء مهارات القراءة تدريجيًا وفق خطة الدعم الفردية.",
                        "occurred_at": days_ago(now, 15).isoformat()}],
        created_at=days_ago(now, 1),
    ))

    grant = ctx.guardian_grant()
    sources = [s for s in collect_authorized_sources(db, child_id=child.id, user=guardian, grant=grant)
               if s.source_type in {"profile", "report", "goal"}]
    centers = list(db.scalars(select(Center).where(Center.is_active.is_(True), Center.verification_status == "verified")).all())
    result = compute_center_matches(child=child, sources=sources, centers=centers, city="جدة", delivery_mode="in_person")
    run = CenterMatchRun(child_id=child.id, requested_by_user_id=guardian.id, provider=result.provider,
                          model=result.model, criteria_json={"city": "جدة", "delivery_mode": "in_person"},
                          result_json=result.data, created_at=days_ago(now, 7))
    db.add(run)
    db.flush()
    top_matches = result.data.get("matches") or []
    if top_matches:
        ensure_favorite(db, user_id=guardian.id, center_id=top_matches[0]["center_id"], created_at=days_ago(now, 6))

    conversation = Conversation(child_id=child.id, kind="direct", created_by_user_id=guardian.id,
                                 created_at=days_ago(now, 4), updated_at=days_ago(now, 4))
    db.add(conversation)
    db.flush()
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=guardian.id, joined_at=days_ago(now, 4)))
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=edu.id, joined_at=days_ago(now, 4)))
    msg1 = ChatMessage(conversation_id=conversation.id, sender_user_id=guardian.id,
                        body="تحطين لنا وقت هالأسبوع لمناقشة خطة الدعم؟", created_at=days_ago(now, 4))
    db.add(msg1)
    db.flush()
    db.add(MessageReadReceipt(message_id=msg1.id, user_id=guardian.id, read_at=days_ago(now, 4)))
    msg2 = ChatMessage(conversation_id=conversation.id, sender_user_id=edu.id,
                        body="أكيد، بنراجعها بعد اجتماع المتابعة مع المعلمة إن شاء الله.", created_at=days_ago(now, 4))
    db.add(msg2)
    db.flush()
    db.add(MessageReadReceipt(message_id=msg2.id, user_id=edu.id, read_at=days_ago(now, 4)))
    db.add(MessageReadReceipt(message_id=msg2.id, user_id=guardian.id, read_at=days_ago(now, 4)))

    return child
