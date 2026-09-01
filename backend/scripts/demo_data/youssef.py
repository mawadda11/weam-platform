"""Youssef (يوسف) — mobility/physical-accessibility journey."""
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
    mark_read,
    upload_report_pdf,
    upload_voice_wav,
)

EXTERNAL_REF = "demo-youssef"


def build(ctx: SeedContext) -> Child:
    db = ctx.db
    now = ctx.now
    guardian = ctx.guardian
    secondary_guardian = ctx.secondary_guardian
    pt = ctx.specialists["pt"]

    child = Child(created_by_user_id=guardian.id, external_ref=EXTERNAL_REF,
                  created_at=days_ago(now, 71), updated_at=days_ago(now, 1))
    child.identity = ChildIdentity(first_name="يوسف", birth_date=date(2018, 3, 4), gender="male")
    child.care_profile = CareProfile(
        conditions=["احتياج حركي"],
        needs=["دعم حركي", "تسهيل الوصول داخل المدرسة", "تنسيق بين الأسرة والمدرسة وفريق التأهيل"],
        support_requirements=["تنسيق مع إدارة المدرسة حول إمكانية الوصول"],
        services=["علاج طبيعي", "دعم حركي"],
        summary="طفل يحتاج دعمًا حركيًا منتظمًا وتنسيقًا بين الأسرة والمدرسة وفريق التأهيل.",
    )
    db.add(child)
    db.flush()

    db.add(GuardianMembership(child=child, guardian_user_id=guardian.id, guardian_type=GuardianType.PRIMARY.value,
                               accepted_at=days_ago(now, 70), created_at=days_ago(now, 70)))
    db.add(GuardianMembership(child=child, guardian_user_id=secondary_guardian.id, guardian_type=GuardianType.SECONDARY.value,
                               permissions=["view_profile", "view_care_team", "view_reports", "view_goals", "view_timeline", "message_team"],
                               accepted_at=days_ago(now, 65), created_at=days_ago(now, 65)))

    invitation_created = days_ago(now, 38)
    db.add(CareInvitation(
        child_id=child.id, invited_by_user_id=guardian.id, email=pt.email, target_role="care_provider",
        role_label="أخصائي علاج طبيعي",
        permissions=["view_profile", "view_care_team", "view_reports", "upload_reports", "view_goals",
                     "manage_goals", "view_timeline", "message_team"],
        status=InvitationStatus.ACCEPTED.value, invitation_expires_at=days_from_now(invitation_created, 14),
        created_at=invitation_created, responded_at=days_ago(now, 37),
    ))
    db.add(CareTeamMembership(
        child_id=child.id, user_id=pt.id, invited_by_user_id=guardian.id, role_label="أخصائي علاج طبيعي",
        permissions=["view_profile", "view_care_team", "view_reports", "upload_reports", "view_goals",
                     "manage_goals", "view_timeline", "message_team"],
        access_status=AccessStatus.ACTIVE.value, accepted_at=days_ago(now, 37), created_at=days_ago(now, 37),
    ))
    db.flush()

    report_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    report_created = days_ago(now, 30)
    stored = upload_report_pdf(ctx, child_id=child.id, report_id=report_id, version_id=version_id,
                                asset_filename="youssef_mobility_report.pdf")
    db.add(Report(id=report_id, child_id=child.id, title="تقرير علاج طبيعي ودعم حركي", report_type="علاج طبيعي",
                   report_date=date_days_ago(now, 30), source_label="مركز مسار للتأهيل الحركي (تجريبي)",
                   visibility="care_team", created_by_user_id=pt.id, created_at=report_created, updated_at=report_created))
    db.add(ReportVersion(id=version_id, report_id=report_id, version_number=1,
                          original_filename="youssef_mobility_report.pdf", content_type=stored.content_type,
                          storage_key=stored.key, size_bytes=stored.size_bytes, sha256=stored.sha256,
                          uploaded_by_user_id=pt.id, created_at=report_created))
    add_audit_log(db, child_id=child.id, actor_user_id=pt.id, action="report_uploaded",
                   entity_type="report", entity_id=report_id, created_at=report_created,
                   details={"version": 1, "visibility": "care_team", "report_type": "علاج طبيعي"})
    # left unread — a "new report" notification the guardian hasn't opened yet

    follow_up_actions = ["مراجعة الأخصائي الحركي خلال أسبوعين", "التواصل مع إدارة المدرسة بخصوص تسهيلات الوصول"]
    db.add(ReportAIAnalysis(
        child_id=child.id, report_id=report_id, report_version_id=version_id,
        provider="seeded_demo", model="weam-demo-v1", analysis_status="completed", review_status="approved",
        result_json={
            "summary": "تحسّن تدريجي في ثبات التوازن أثناء المشي، مع الحاجة إلى دعم إضافي عند استخدام الدرج داخل المدرسة.",
            "key_findings": ["تحسّن تدريجي في ثبات التوازن أثناء المشي لمسافات قصيرة.",
                              "الحاجة إلى دعم إضافي عند استخدام الدرج داخل المدرسة.",
                              "تجاوب جيد مع برنامج التمارين المنزلي."],
            "needs": ["دعم حركي منتظم", "تنسيق بين الأسرة والمدرسة وفريق التأهيل"],
            "recommendations": ["متابعة برنامج التمارين المنزلي", "تنسيق تسهيلات الوصول مع المدرسة"],
            "follow_up_actions": follow_up_actions,
            "goal_mentions": ["الثبات أثناء المشي", "تسهيل الوصول داخل المدرسة"],
            "source_language": "ar",
            "evidence": ["تحسّن تدريجي في ثبات التوازن أثناء المشي لمسافات قصيرة.",
                         "تجاوب جيد مع برنامج التمارين المنزلي الموصى به."],
            "limitations": ["هذا تحليل تجريبي مُعدّ مسبقًا لأغراض العرض، وليس نتيجة تحليل حي — راجعيه قبل الاعتماد عليه."],
            "safety_note": "هذا تلخيص مساعد وليس تشخيصًا أو خطة علاجية بديلة عن المختص.",
        },
        created_by_user_id=guardian.id, reviewed_by_user_id=pt.id, reviewed_at=days_ago(now, 29),
        created_at=days_ago(now, 29), updated_at=days_ago(now, 29),
    ))

    for i, action_text in enumerate(follow_up_actions):
        due = date_days_from_now(now, 2) if i == 0 else date_days_from_now(now, 21)
        db.add(FollowUp(child_id=child.id, title=action_text, note=action_text, due_date=due, status="open",
                         source_type="report_ai", source_id=follow_up_source_id(report_id, action_text),
                         source_label="تقرير معتمد · تقرير علاج طبيعي ودعم حركي",
                         created_by_user_id=pt.id, created_at=days_ago(now, 29)))

    goal1 = Goal(child_id=child.id, title="تحسين الثبات أثناء المشي في المساحات المفتوحة",
                 description="زيادة المسافة التي يمشيها يوسف بثبات دون مساعدة.",
                 category="حركي", status="in_progress", progress_percent=45,
                 start_date=date_days_ago(now, 28), target_date=date_days_from_now(now, 35),
                 assigned_to_user_id=pt.id, created_by_user_id=pt.id, created_at=days_ago(now, 28))
    db.add(goal1)
    db.flush()
    db.add(GoalUpdate(goal_id=goal1.id, actor_user_id=pt.id, note="زيادة ملحوظة في مسافة المشي الثابت.",
                       progress_percent=45, status="in_progress", created_at=days_ago(now, 8)))

    goal2 = Goal(child_id=child.id, title="استخدام الدرج المدرسي بأمان وبدعم محدود",
                 description="هدف يتابعه الأخصائي بالتنسيق مع المدرسة.",
                 category="استقلالية", status="new", progress_percent=10,
                 start_date=date_days_ago(now, 5), target_date=date_days_from_now(now, 60),
                 assigned_to_user_id=pt.id, created_by_user_id=guardian.id, created_at=days_ago(now, 5))
    db.add(goal2)
    db.flush()
    add_audit_log(db, child_id=child.id, actor_user_id=guardian.id, action="goal_created",
                   entity_type="goal", entity_id=goal2.id, created_at=days_ago(now, 5),
                   details={"title": goal2.title, "assigned_to_user_id": pt.id})

    voice_note_id = str(uuid.uuid4())
    voice_stored = upload_voice_wav(ctx, child_id=child.id, voice_note_id=voice_note_id)
    db.add(VoiceNote(id=voice_note_id, child_id=child.id, title="ملاحظة من الأب بعد نشاط في الحديقة",
                      original_filename="demo_voice_sample.wav", content_type=voice_stored.content_type,
                      storage_key=voice_stored.key, size_bytes=voice_stored.size_bytes, sha256=voice_stored.sha256,
                      duration_seconds=2, transcription_status="completed", review_status="approved",
                      transcript_draft="يوسف مشى مسافة أطول اليوم في الحديقة وما احتاج مساعدة كثيرة.",
                      transcript_final="يوسف مشى اليوم مسافة أطول من المعتاد في الحديقة، واحتاج مساعدة أقل من قبل.",
                      transcript_language="ar", stt_provider="seeded_demo", stt_model="weam-demo-v1",
                      created_by_user_id=secondary_guardian.id, reviewed_by_user_id=guardian.id,
                      reviewed_at=days_ago(now, 4), created_at=days_ago(now, 4), updated_at=days_ago(now, 4)))

    thread = AssistantThread(child_id=child.id, created_by_user_id=guardian.id, title="متابعة الدعم الحركي",
                              created_at=days_ago(now, 1), updated_at=days_ago(now, 1))
    db.add(thread)
    db.flush()
    db.add(AssistantMessage(thread_id=thread.id, role="user", content="وش آخر توصية بخصوص الدرج بالمدرسة؟",
                             sources_json=[], created_at=days_ago(now, 1)))
    db.add(AssistantMessage(
        thread_id=thread.id, role="assistant",
        content=("بحسب تقرير العلاج الطبيعي، يوصى بالتواصل مع إدارة المدرسة بخصوص تسهيلات الوصول عند استخدام "
                 "الدرج. لا تتوفر تفاصيل إضافية عن ترتيبات المدرسة نفسها ضمن السجلات المصرّح لك بالاطلاع عليها."),
        sources_json=[{"index": 1, "source_type": "report", "source_id": report_id,
                        "title": "تقرير علاج طبيعي ودعم حركي",
                        "snippet": "التواصل مع إدارة المدرسة بخصوص تسهيلات الوصول.",
                        "occurred_at": days_ago(now, 30).isoformat()}],
        created_at=days_ago(now, 1),
    ))

    grant = ctx.guardian_grant()
    sources = [s for s in collect_authorized_sources(db, child_id=child.id, user=guardian, grant=grant)
               if s.source_type in {"profile", "report", "goal"}]
    centers = list(db.scalars(select(Center).where(Center.is_active.is_(True), Center.verification_status == "verified")).all())
    result = compute_center_matches(child=child, sources=sources, centers=centers, city="الرياض", delivery_mode="in_person")
    run = CenterMatchRun(child_id=child.id, requested_by_user_id=guardian.id, provider=result.provider,
                          model=result.model, criteria_json={"city": "الرياض", "delivery_mode": "in_person"},
                          result_json=result.data, created_at=days_ago(now, 6))
    db.add(run)
    db.flush()
    top_matches = result.data.get("matches") or []
    if top_matches:
        ensure_favorite(db, user_id=guardian.id, center_id=top_matches[0]["center_id"], created_at=days_ago(now, 5))

    conversation = Conversation(child_id=child.id, kind="direct", created_by_user_id=guardian.id,
                                 created_at=days_ago(now, 2), updated_at=days_ago(now, 2))
    db.add(conversation)
    db.flush()
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=guardian.id, joined_at=days_ago(now, 2)))
    db.add(ConversationParticipant(conversation_id=conversation.id, user_id=pt.id, joined_at=days_ago(now, 2)))
    msg1 = ChatMessage(conversation_id=conversation.id, sender_user_id=pt.id,
                        body="لاحظت تحسن بسيط اليوم في ثبات مشيه، بس خلنا نكمل البرنامج المنزلي.",
                        created_at=days_ago(now, 2))
    db.add(msg1)
    db.flush()
    db.add(MessageReadReceipt(message_id=msg1.id, user_id=pt.id, read_at=days_ago(now, 2)))
    # Deliberately NOT marked read by the guardian — demonstrates unread state.

    return child
