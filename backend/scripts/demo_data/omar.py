"""Omar (عمر) — early-intervention / sensory-regulation journey."""
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
    upload_report_pdf,
    upload_voice_wav,
)

EXTERNAL_REF = "demo-omar"


def build(ctx: SeedContext) -> Child:
    db = ctx.db
    now = ctx.now
    guardian = ctx.guardian
    ot = ctx.specialists["ot"]

    child = Child(created_by_user_id=guardian.id, external_ref=EXTERNAL_REF,
                  created_at=days_ago(now, 21), updated_at=now)
    child.identity = ChildIdentity(first_name="عمر", birth_date=date(2024, 5, 20), gender="male")
    child.care_profile = CareProfile(
        conditions=["تأخر نمائي"],
        needs=["تنظيم حسي", "إرشاد الأسرة", "تدخل مبكر"],
        support_requirements=["استراتيجيات دعم الروتين اليومي في المنزل"],
        services=["تدخل مبكر", "علاج وظيفي"],
        summary="طفل يستفيد من تدخل مبكر منتظم ودعم لتنظيمه الحسي، مع إرشاد الأسرة حول الروتين اليومي.",
    )
    db.add(child)
    db.flush()

    db.add(GuardianMembership(child=child, guardian_user_id=guardian.id, guardian_type=GuardianType.PRIMARY.value,
                               accepted_at=days_ago(now, 20), created_at=days_ago(now, 20)))

    invitation_created = days_ago(now, 18)
    db.add(CareInvitation(
        child_id=child.id, invited_by_user_id=guardian.id, email=ot.email, target_role="care_provider",
        role_label="أخصائية علاج وظيفي",
        permissions=["view_profile", "view_care_team", "view_reports", "upload_reports", "view_goals",
                     "manage_goals", "view_timeline", "view_voice_notes", "create_voice_notes", "message_team"],
        status=InvitationStatus.ACCEPTED.value, invitation_expires_at=days_from_now(invitation_created, 14),
        created_at=invitation_created, responded_at=days_ago(now, 17),
    ))
    db.add(CareTeamMembership(
        child_id=child.id, user_id=ot.id, invited_by_user_id=guardian.id, role_label="أخصائية علاج وظيفي",
        permissions=["view_profile", "view_care_team", "view_reports", "upload_reports", "view_goals",
                     "manage_goals", "view_timeline", "view_voice_notes", "create_voice_notes", "message_team"],
        access_status=AccessStatus.ACTIVE.value, accepted_at=days_ago(now, 17), created_at=days_ago(now, 17),
    ))

    # A second, still-pending invitation — demonstrates invitation history beyond
    # "accepted", without leaving Omar without an active care-team member (the OT above).
    db.add(CareInvitation(
        child_id=child.id, invited_by_user_id=guardian.id, email="followup.slp2@weam.demo",
        target_role="care_provider", role_label="متابعة نطق مبكرة",
        permissions=["view_profile", "view_reports"],
        status=InvitationStatus.PENDING.value, invitation_expires_at=days_from_now(now, 10),
        created_at=days_ago(now, 2),
    ))
    db.flush()

    report_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    report_created = days_ago(now, 15)
    stored = upload_report_pdf(ctx, child_id=child.id, report_id=report_id, version_id=version_id,
                                asset_filename="omar_early_intervention_report.pdf")
    db.add(Report(id=report_id, child_id=child.id, title="تقرير تدخل مبكر وعلاج وظيفي", report_type="تدخل مبكر",
                   report_date=date_days_ago(now, 15), source_label="مركز براعم للتدخل المبكر (تجريبي)",
                   visibility="care_team", created_by_user_id=ot.id, created_at=report_created, updated_at=report_created))
    db.add(ReportVersion(id=version_id, report_id=report_id, version_number=1,
                          original_filename="omar_early_intervention_report.pdf", content_type=stored.content_type,
                          storage_key=stored.key, size_bytes=stored.size_bytes, sha256=stored.sha256,
                          uploaded_by_user_id=ot.id, created_at=report_created))
    add_audit_log(db, child_id=child.id, actor_user_id=ot.id, action="report_uploaded",
                   entity_type="report", entity_id=report_id, created_at=report_created,
                   details={"version": 1, "visibility": "care_team", "report_type": "تدخل مبكر"})

    follow_up_actions = ["مراجعة خطة التدخل المبكر خلال شهر", "جلسة إرشاد أسري إضافية عند الحاجة"]
    db.add(ReportAIAnalysis(
        child_id=child.id, report_id=report_id, report_version_id=version_id,
        provider="seeded_demo", model="weam-demo-v1", analysis_status="completed", review_status="approved",
        result_json={
            "summary": "استجابة حسية متفاوتة للأصوات المرتفعة، مع تفاعل إيجابي مع الأنشطة الحسية الموجهة خلال الجلسات.",
            "key_findings": ["استجابة حسية متفاوتة للأصوات المرتفعة في البيئة المنزلية.",
                              "تفاعل إيجابي مع الأنشطة الحسية الموجهة خلال الجلسات.",
                              "حاجة إلى دعم إضافي أثناء الانتقال بين الأنشطة."],
            "needs": ["تنظيم حسي أثناء الأنشطة اليومية", "إرشاد الأسرة حول استراتيجيات دعم الروتين"],
            "recommendations": ["استخدام إشارات انتقالية بين الأنشطة", "متابعة جلسات الإرشاد الأسري"],
            "follow_up_actions": follow_up_actions,
            "goal_mentions": ["التنظيم الحسي أثناء الأنشطة اليومية"],
            "source_language": "ar",
            "evidence": ["تفاعل إيجابي مع الأنشطة الحسية الموجهة خلال الجلسات."],
            "limitations": ["هذا تحليل تجريبي مُعدّ مسبقًا لأغراض العرض، وليس نتيجة تحليل حي — راجعيه قبل الاعتماد عليه."],
            "safety_note": "هذا تلخيص مساعد وليس تشخيصًا أو خطة علاجية بديلة عن المختص.",
        },
        created_by_user_id=guardian.id, reviewed_by_user_id=ot.id, reviewed_at=days_ago(now, 14),
        created_at=days_ago(now, 14), updated_at=days_ago(now, 14),
    ))

    for i, action_text in enumerate(follow_up_actions):
        due = date_days_from_now(now, 30) if i == 0 else date_days_from_now(now, 45)
        db.add(FollowUp(child_id=child.id, title=action_text, note=action_text, due_date=due, status="open",
                         source_type="report_ai", source_id=follow_up_source_id(report_id, action_text),
                         source_label="تقرير معتمد · تقرير تدخل مبكر وعلاج وظيفي",
                         created_by_user_id=ot.id, created_at=days_ago(now, 14)))

    goal1 = Goal(child_id=child.id, title="تحسين التنظيم الحسي أثناء الأنشطة اليومية",
                 description="بناء استجابة أكثر استقرارًا للأصوات والمثيرات الحسية اليومية.",
                 category="حسي", status="new", progress_percent=5,
                 start_date=date_days_ago(now, 10), target_date=date_days_from_now(now, 50),
                 assigned_to_user_id=ot.id, created_by_user_id=ot.id, created_at=days_ago(now, 10))
    db.add(goal1)
    db.flush()
    add_audit_log(db, child_id=child.id, actor_user_id=ot.id, action="goal_created",
                   entity_type="goal", entity_id=goal1.id, created_at=days_ago(now, 10),
                   details={"title": goal1.title, "assigned_to_user_id": ot.id})

    goal2 = Goal(child_id=child.id, title="دعم استقرار الروتين اليومي في المنزل",
                 description="تقليل الاضطراب أثناء الانتقال بين الأنشطة اليومية.",
                 category="سلوكي", status="in_progress", progress_percent=15,
                 start_date=date_days_ago(now, 6), target_date=date_days_from_now(now, 55),
                 assigned_to_user_id=ot.id, created_by_user_id=guardian.id, created_at=days_ago(now, 6))
    db.add(goal2)
    db.flush()
    db.add(GoalUpdate(goal_id=goal2.id, actor_user_id=ot.id, note="بداية تحسّن مع استخدام إشارات الانتقال.",
                       progress_percent=15, status="in_progress", created_at=days_ago(now, 1)))

    voice_note_id = str(uuid.uuid4())
    voice_stored = upload_voice_wav(ctx, child_id=child.id, voice_note_id=voice_note_id)
    db.add(VoiceNote(id=voice_note_id, child_id=child.id, title="ملاحظة من الأم أثناء وقت اللعب",
                      original_filename="demo_voice_sample.wav", content_type=voice_stored.content_type,
                      storage_key=voice_stored.key, size_bytes=voice_stored.size_bytes, sha256=voice_stored.sha256,
                      duration_seconds=2, transcription_status="completed", review_status="approved",
                      transcript_draft="عمر انزعج شوي من صوت الخلاط بس هدى بسرعة أكثر من قبل.",
                      transcript_final="عمر انزعج قليلاً من صوت الخلاط في المطبخ، لكنه هدأ بسرعة أكبر من المعتاد.",
                      transcript_language="ar", stt_provider="seeded_demo", stt_model="weam-demo-v1",
                      created_by_user_id=guardian.id, reviewed_by_user_id=guardian.id,
                      reviewed_at=days_ago(now, 2), created_at=days_ago(now, 2), updated_at=days_ago(now, 2)))

    thread = AssistantThread(child_id=child.id, created_by_user_id=guardian.id, title="متابعة التدخل المبكر",
                              created_at=now, updated_at=now)
    db.add(thread)
    db.flush()
    db.add(AssistantMessage(thread_id=thread.id, role="user", content="متى موعد مراجعة خطة التدخل المبكر؟",
                             sources_json=[], created_at=now))
    db.add(AssistantMessage(
        thread_id=thread.id, role="assistant",
        content=("بحسب تقرير التدخل المبكر الأخير، يُنصح بمراجعة خطة التدخل المبكر خلال شهر من تاريخ التقرير. "
                  "لا تتوفر معلومات إضافية عن موعد محدد بعد ذلك ضمن السجلات المصرّح لك بالاطلاع عليها."),
        sources_json=[{"index": 1, "source_type": "report", "source_id": report_id,
                        "title": "تقرير تدخل مبكر وعلاج وظيفي",
                        "snippet": "مراجعة خطة التدخل المبكر خلال شهر.",
                        "occurred_at": days_ago(now, 15).isoformat()}],
        created_at=now,
    ))

    grant = ctx.guardian_grant()
    sources = [s for s in collect_authorized_sources(db, child_id=child.id, user=guardian, grant=grant)
               if s.source_type in {"profile", "report", "goal"}]
    centers = list(db.scalars(select(Center).where(Center.is_active.is_(True), Center.verification_status == "verified")).all())
    result = compute_center_matches(child=child, sources=sources, centers=centers, city="جدة", delivery_mode="in_person")
    run = CenterMatchRun(child_id=child.id, requested_by_user_id=guardian.id, provider=result.provider,
                          model=result.model, criteria_json={"city": "جدة", "delivery_mode": "in_person"},
                          result_json=result.data, created_at=days_ago(now, 1))
    db.add(run)
    db.flush()

    conversation = Conversation(child_id=child.id, kind="direct", created_by_user_id=guardian.id,
                                 created_at=days_ago(now, 1), updated_at=now)
    db.add(conversation)
    db.flush()
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=guardian.id, joined_at=days_ago(now, 1)))
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=ot.id, joined_at=days_ago(now, 1)))
    msg1 = ChatMessage(conversation_id=conversation.id, sender_user_id=ot.id,
                        body="جربي معه إشارة بسيطة قبل الانتقال من نشاط لثاني، وأخبريني كيف كان تجاوبه.",
                        created_at=now)
    db.add(msg1)
    db.flush()
    db.add(MessageReadReceipt(message_id=msg1.id, user_id=ot.id, read_at=now))
    # Deliberately unread by the guardian — the most recently arrived message in the demo.

    return child
