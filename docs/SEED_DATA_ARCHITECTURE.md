# Seed data architecture — the four-child demonstration environment

This document is the design for replacing `backend/scripts/seed_demo.py` (currently
three bare children with a name and three list fields each — no reports, goals,
follow-ups, voice notes, chat, or assistant content) with a coherent, idempotent,
production-safe demonstration environment covering four full child journeys.

Status: **design, not yet implemented.** This is the plan to review before the
build starts.

## 1. Goals this design has to satisfy

Restated from the product requirements, because they drive every decision below:

- Four complete child journeys (لمى، يوسف، روان، عمر), each touching every major
  product surface, demonstrably *connected* rather than parallel unrelated records.
- Idempotent (rerun = no duplicates), deterministic, transactional, Postgres-compatible,
  tested.
- Never uses `Base.metadata.create_all()`; refuses to run unless Alembic is at head.
- Can create a fresh demo, can safely extend an older/incomplete one, and can be
  reset through a narrowly-scoped command that can never touch non-demo data.
- Rejects running in production without an explicit override.
- Dates stay coherent no matter when the script is actually run.
- No fabricated real-world facts (this only concerns the *fictional* demo content —
  the six real researched centers are handled by the separate, already-shipped
  `seed_real_centers.py` and are explicitly out of scope here).

## 2. The core problem: idempotency at what granularity?

The naive approach — check whether each individual report/goal/message already
exists before inserting it — would need a stable natural key on every one of
~15 leaf tables. That's a lot of migration surface for marginal benefit, and it
invites subtle drift (half-updated rows) between runs.

**Decision: idempotency is enforced at the child (and user) level, not the leaf-record
level.** Concretely:

- `Child` gets a new nullable, unique-when-set column: `external_ref` (e.g. `"demo-lama"`).
- Before building a child's journey, the script checks `select(Child).where(Child.external_ref == ref)`.
  - **Not found** → build the full subtree for that child from scratch.
  - **Found** → skip entirely by default (this alone satisfies "rerunning doesn't
    duplicate records").
- An explicit `--rebuild` flag changes "found" behavior to: delete that child (cascades
  away its entire subtree — see §5) and rebuild it fresh. This is how an older/incomplete
  demo gets safely brought up to date: not a field-by-field diff, but a clean,
  deterministic rebuild scoped to exactly the demo children, which is safe *because*
  they're cleanly tagged and cascade-deletable.
- Guardian/specialist/center-rep `User` rows are matched by their fixed demo email
  addresses (already unique at the DB level — no new column needed).
- Fictional demo `Center` rows reuse the `source_type` column already added for the
  real-center work: `source_type="synthetic_demo"` (vs. `"public_research"` for the
  real ones). No new column needed there either.

This is simpler, more testable, and avoids adding natural-key columns to Report,
Goal, FollowUp, VoiceNote, ChatMessage, AssistantThread, etc.

## 3. Demo tagging — the "explicit safe mechanism"

Two new nullable, indexed columns, added in one focused migration:

- `users.demo_batch: str | None`
- `children.external_ref: str | None` (unique when set) — doubles as both the
  idempotency key (§2) and the tag used for scoped deletion (§5).

Both default to `None` for every non-demo row (including everything a real
guardian creates through the product). A single constant,
`DEMO_BATCH = "weam-demo-2026"`, is stamped onto every demo `User` and every
demo `Child.external_ref` is prefixed `demo-*`. If the demo content is ever
redesigned wholesale later, bumping `DEMO_BATCH` retires the old rows cleanly
without touching the new ones.

Centers reuse `source_type` as their own tag (no new column, see §2).

## 4. Reference-date handling

The script captures one `SEED_NOW = datetime.now(timezone.utc)` at start (injectable
in tests so assertions aren't wall-clock-dependent). Every seeded date is an
*offset* from `SEED_NOW`, never a literal calendar date:

- Reports: dated 30–60 days in the past (varies per child so the timeline reads
  naturally, not four identical dates).
- Goals: `start_date` 20–40 days ago; a mix of `target_date`s — one per child
  landing within the next 7 days ("approaching target"), the rest further out.
- Follow-ups: deliberately spread across the states the requirements ask for —
  one due today, one due within 3 days, one completed a few days ago, one
  slightly overdue is *avoided* (a permanently-overdue item is exactly what the
  brief says to avoid) — "near-due" and "due today" are used instead of anything
  that ages into "overdue" on a delayed rerun.
- Notifications: timestamps within the last 3–5 days, mixed read/unread.
- Chat messages: a short exchange dated within the last few days, last message
  unread by the guardian.

This satisfies "dates remain useful whenever the seed is rerun" — running the
script next month produces the same *shape* of demo, just shifted forward.

## 5. Deletion safety (for `--rebuild` and `--reset`)

Checked directly against the models: every FK from a child-scoped table
(`reports`, `goals`, `follow_ups`, `voice_notes`, `chat` tables, `assistant`
tables, `center_match_runs`, `care_team_memberships`, `guardian_memberships`)
to `children.id` already has `ondelete="CASCADE"`. **Deleting a `Child` row
cleanly removes its entire subtree in one statement — no orphans.**

Most FKs *to* `users.id` (e.g. `report.uploaded_by_user_id`, `chat.sender_id`,
`goal.assigned_to_user_id`) do **not** cascade. This fixes the required
deletion order:

1. Delete demo `Child` rows first (`WHERE external_ref LIKE 'demo-%'` scoped to
   the current `DEMO_BATCH`) — this cascades away everything that references
   demo users via those non-cascading FKs.
2. Delete demo `User` rows second (`WHERE demo_batch = :batch`) — safe now that
   step 1 removed the rows that pointed at them.
3. Delete demo `Center` rows (`WHERE source_type = 'synthetic_demo'`) — never
   touches the real researched centers, which carry `source_type='public_research'`.

**Operating constraint this design relies on:** demo users must never be used to
verify another user or a center, and must never generate an `AdminAuditLog` row
(those are the two remaining non-cascading references to `users.id` that
wouldn't be cleaned up by step 1). The demo journeys never call admin actions,
so this holds by construction — worth a one-line regression test rather than
just an assumption (see §8).

`--reset` is step 1–3 with no rebuild step after — a narrowly-scoped delete-only
command, always scoped by `demo_batch`/`external_ref`/`source_type`, which
structurally *cannot* reach a non-demo row because those columns are `NULL` /
`"synthetic_demo"`-only on demo data.

## 6. Production safety

Mirrors the pattern already shipped in `seed_real_centers.py`: refuses to run
if `WEAM_ENVIRONMENT=production` unless `WEAM_ALLOW_DEMO_SEED=true` is set
explicitly. Unlike the real-center script (where running in production is the
eventual normal case), demo seeding in production should be rare and deliberate
— e.g. a pre-exhibition refresh of a staging-like environment — so the override
is named separately and documented as such.

Both scripts share one `_assert_migrations_at_head()` helper — currently
duplicated logic in `seed_real_centers.py` will move to a new
`backend/app/scripts/_seed_shared.py` module so it isn't copy-pasted a third time.

## 7. File layout

```
backend/scripts/
  seed_demo.py                  # thin CLI: --rebuild / --reset / (default) flags
  seed_real_centers.py          # existing, unchanged
  demo_data/
    __init__.py
    shared.py                   # DEMO_BATCH, SEED_NOW plumbing, guardian/specialist/center pool
    lama.py                     # build_lama(db, ctx) -> full journey
    youssef.py                  # build_youssef(db, ctx)
    rawan.py                    # build_rawan(db, ctx)
    omar.py                     # build_omar(db, ctx)
    assets/
      lama_hearing_report.pdf       # real, valid PDF bytes — signature-checked by
      youssef_mobility_report.pdf   # LocalReportStorage.save_upload() just like a
      rawan_learning_report.pdf     # real upload, so seeded reports open exactly
      omar_early_intervention.pdf   # the way an uploaded one does
      demo_voice_sample.(wav|mp3)   # one shared or per-child short audio sample
```

Each `demo_data/<child>.py` module is self-contained and independently reviewable
— this keeps any single file from becoming an unreadable 1500-line script, and
means a future contributor extending "Omar" doesn't have to read Lama's file.

`ctx` is a small dataclass threaded through every builder: the shared
guardian(s), the specialist pool, the demo centers, `SEED_NOW`, and the storage
helper — created once in `seed_demo.py` and passed down, so specialists can be
*reused* across children where the spec calls for it (§9) without recreating
them per file.

### Why real PDF bytes, not placeholder text files

`LocalReportStorage.save_upload()` validates the actual file signature (`%PDF`
magic bytes for PDFs) before accepting an upload — the same code path a real
guardian's browser upload goes through. Seeding a fake `.pdf` that's actually a
text file would either bypass that validation (wrong — the seed data should
prove the real path works) or get rejected. The four report PDFs are generated
once, offline, as small valid PDF documents (clean Arabic layout, each opening
with an explicit **"مستند توضيحي لأغراض العرض التجريبي فقط"** disclaimer per the
product requirement) and committed as static assets. The seed script wraps each
one in an `UploadFile`-compatible object and calls the *real* `save_upload()` —
so seeded reports are provably openable through the app's normal authorized
download path, not a shortcut around it.

## 8. Guardian / specialist pool (reuse, not duplication)

- **One primary guardian** (`ولي الأمر التجريبي`, fixed demo email) owns all
  four children — this is a deliberate choice, not an oversight: "multiple child
  profiles under one guardian" is a named core capability, and one guardian
  juggling four different journeys is the strongest demonstration of it. One
  **secondary guardian** is added on exactly one child (Youssef) to demonstrate
  the primary/secondary guardian-type distinction without repeating it four times.
- **Four specialist accounts**, one per required discipline, each anchored to
  the child whose story needs them, per the spec:
  - Speech & language specialist → Lama's care team (hearing/communication story).
  - Physical/rehabilitation specialist → Youssef's care team (mobility story).
  - Educational specialist → Rawan's care team (learning-support story).
  - Occupational therapist → Omar's care team (early intervention/sensory story).
- **Reuse, not duplication where realistic:** the speech & language specialist
  is *also* granted a limited, view-only membership on Rawan's care team (a
  specialist legitimately following a second child with narrower permissions)
  — this is the one deliberate cross-child reuse, giving the demo a concrete
  example of "the same person, different permission scope per child" without
  contriving reuse everywhere.
- **One center representative** account, tied to one fictional demo center
  (`source_type="synthetic_demo"`), distinct from the six real researched ones.
- **Care-team invitation history**, spread across children rather than repeated
  four times identically: one `CareInvitation` left `pending` (Omar — the OT
  invited but not yet accepted), the rest `accepted`; one membership carries a
  fixed `expires_at` a few weeks out (Rawan's educational specialist — a
  time-limited engagement), the rest open-ended; permission sets deliberately
  differ per membership (e.g. the SLP's view-only slot on Rawan has only
  `view_profile`/`view_reports`, nowhere near her full permission set on Lama)
  so "different permission combinations" is genuinely visible, not four copies
  of the same grant.

## 9. Per-child entity checklist

Each of the four `demo_data/<child>.py` builders creates, in dependency order:

1. `Child` + `ChildIdentity` + `CareProfile` (identity/care separation preserved).
2. `GuardianMembership` (primary; + secondary for Youssef only).
3. `CareTeamMembership`(s) + `CareInvitation` history (see §8).
4. `Report` + `ReportVersion` + the real PDF asset via `save_upload()`.
5. `ReportAIAnalysis` — seeded as an **already-reviewed/approved** draft (labeled
   as such, evidence/limitations populated, sourced from the report's own
   content) so the demo shows the *outcome* of human review without pretending
   a live Gemini call happened during seeding — the product requirement is
   explicit that pre-seeded analysis must never be presented as if generated
   live. A separate, documented path (existing `WEAM_AI_PROVIDER=gemini` +
   report-analysis endpoint) is how someone demos a *live* run during judging.
6. Two-plus `Goal`s with `GoalUpdate` history — mixed status per child (active,
   recently updated, one completed where it strengthens the story, one nearing
   its target date), always tied back to something concrete: the report, a
   family priority, or a specialist note — never an administrative task
   ("follow up with school" is a `FollowUp`, not a goal).
7. `FollowUp`s tied to the report/goal, timed per §4.
8. `VoiceNote` + transcription — short, non-clinical family observation,
   connected to a goal or follow-up, transcription clearly reviewable/editable
   (matches the "no unreviewed transcription becomes a trusted fact" rule).
9. `AssistantThread` + `AssistantMessage`(s) — a realistic coordination question
   *specific to that child* (no copy-pasted Q&A across children), answer
   grounded only in that child's authorized sources, explicitly stating any gap.
10. `CenterMatchRun` (persisted, explainable, top-3) — computed against each
    child's actual recorded needs/age/city so the four results are genuinely
    different, not the same list four times; plus one `CenterFavorite`.
11. `Conversation` + participants + a short, natural `ChatMessage` exchange
    between guardian and the assigned specialist, with a reference to a
    shared report/goal where permissions allow, unread state on at least one
    child's thread.
12. `NotificationReceipt`s generated from the above events (not fabricated
    separately) — read/unread mixed across the four children so the
    notification center as a whole (not per-child) shows the required balance:
    one near-due, one due-today, one completed, one unread message, one
    invitation.

Timeline itself is **not a stored table** (confirmed: no `Timeline` model
exists; `routes/timeline.py` composes it from the tables above) — so there is
nothing separate to seed for it. It will be correct automatically as long as
every entity's `created_at`/event date is coherent per §4, which is worth an
explicit assertion in tests (§10) rather than an unstated assumption.

## 10. Testing plan

New `backend/tests/test_seed_demo.py`:

- `test_seed_demo_is_idempotent` — run the seed function twice, assert row
  counts are identical after the second run (not doubled).
- `test_seed_demo_rebuild_replaces_cleanly` — seed, mutate a fact, `--rebuild`,
  assert the mutation is gone and counts match a fresh seed exactly.
- `test_four_profiles_linked_to_one_guardian` — all four `external_ref`s
  resolve to children owned by the same guardian email.
- `test_permissions_differ_across_care_team` — assert the SLP's permission set
  on Rawan is a strict subset of her permission set on Lama.
- `test_reports_are_real_pdfs_and_access_restricted` — the stored file opens
  and starts with `%PDF`; a guardian of a *different* demo child gets 404 on it.
- `test_goals_followups_notifications_present_for_every_child` — non-empty,
  per-child.
- `test_center_matches_differ_across_children` — the four `CenterMatchRun`
  results are not identical (different top center, or different reasons).
- `test_timeline_events_are_chronologically_coherent` — for each child, every
  event's timestamp is ≥ the child's `created_at`.
- `test_reset_cannot_delete_non_demo_records` — create an ordinary (non-tagged)
  user + child through the normal API flow, run `--reset`, assert both still
  exist and the demo rows are gone.
- `test_demo_seed_rejected_in_production_without_override` — same pattern as
  the existing `test_production_guard_*` tests.

## 11. What this design deliberately leaves out (next steps, not silently dropped)

- The **admin review workflow** for real centers (mark stale / deactivate /
  record source) — flagged as pending in the previous update, unaffected by
  this design.
- A **separate API-level QA script** (`qa_invitation_flow.py`) that exercises
  invite → accept through real HTTP calls against a running server, for manual
  QA rather than the DB-level seed itself — small, but scoped as its own
  follow-up so it doesn't bloat this change.
- The **demo-mode "بيانات تجريبية لأغراض العرض" banner** and any non-production
  role-switcher UI are frontend work, sequenced with the visual redesign pass
  rather than here.

## 12. Open judgment calls worth a second look before I build this

1. **Audio asset**: a single shared short demo voice-note sample (re-used per
   child with different surrounding text) vs. four distinct recordings. I'm
   planning one well-made shared sample plus per-child transcription text,
   per the brief's explicit allowance ("two especially strong examples across
   the four journeys" is acceptable) — flag if four unique recordings matter
   to you.
2. **Migration count**: this adds exactly one migration (`users.demo_batch`,
   `children.external_ref`) — no other schema changes are needed given the
   reuse decisions in §2–3.
