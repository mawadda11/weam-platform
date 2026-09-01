# Likely judge/mentor questions and accurate answers

Grouped by theme. Every answer here reflects what was actually built and
verified this session — not aspiration. Where something is a genuine
limitation, the answer says so; a confident wrong answer costs more credibility
than an honest "not yet, and here's why that's the right call for a prototype."

## Product & impact

**"Why does this need AI at all — couldn't a guardian just keep folders?"**
The problem isn't storage, it's fragmentation across *people*: reports live
with specialists, goals live in someone's head, follow-ups live in a WhatsApp
thread. AI's job here is narrow — summarize a report into a reviewable draft,
answer a grounded question from authorized sources, and explain a center
match. Every one of those stays a draft or an explanation, never a decision.

**"Why hearing loss as the demo scenario? Is this really only for hearing
impairment?"**
Hearing loss is one of four full demo journeys — the seed data includes a
mobility case (Youssef), a learning-support case (Rawan), and an early-
intervention/sensory case (Omar), each with a different care team, different
permission structure, and different center-matching result. The `CareProfile`
model itself never encodes a diagnosis type; conditions/needs/services are
free-form tags precisely so the product doesn't assume one condition.

**"What's the actual evidence this helps anyone?"**
Be direct: there is no user study yet. What exists is a working prototype
with a coherent, testable demonstration environment and engineering QA
evidence (test coverage, accessibility/contrast checks, verified access
control) — that's Feasibility/Prototype evidence, not Impact evidence. [Fill
in with any real interview notes the team has; do not imply a study happened
if it didn't.]

## AI behavior and safety boundaries

**"What happens if the AI hallucinates a fact into a report analysis?"**
The analysis is stored with `review_status="draft"` and a human (a care-team
member with the right permission) must explicitly approve it before it can
generate a follow-up. The UI never hides this — the draft badge and a
"مراجعة بشرية قبل الاعتماد" (human review before approval) label are shown
directly on the analysis card, not buried in a tooltip.

**"Can the assistant answer from a report the user isn't allowed to see?"**
No — `collect_authorized_sources()` filters strictly by the caller's actual
`AccessGrant` before any text reaches the generation step; there's no path
where a broader context gets built and then filtered after the fact. This was
specifically verified: a care-team member with a narrower permission slot on
one child (view-only) gets a real 403 on endpoints outside that scope, not a
silently-filtered response.

**"What model are you using, and what if it's down during judging?"**
[State the real provider only if the team wants to disclose it to judges —
it's not shown in the product UI by design, but is fair to discuss verbally.]
If the external call fails or times out, both report analysis and the
assistant fall back to a **local, deterministic** path — regex/keyword-based
extraction for reports, a grounded template-based answer for the assistant —
so the demo does not go blank if connectivity drops. This is the actual
`WEAM_AI_PROVIDER=mock` / failover code path, not a hypothetical.

**"How do you stop someone from prompt-injecting through an uploaded PDF?"**
Extracted report text is treated as data to summarize, never as instructions
— the extraction prompt/logic doesn't grant the document authority to alter
the assistant's behavior or safety rules. [If the team wants a stronger claim
here, this is a good area for an explicit adversarial test before submission
rather than an unqualified assertion.]

**"Why not a fully autonomous care-coordination agent?"**
That was explicitly scoped out. An agent that acts on a child's care record
without a human in the loop is a different risk profile than a tool that
drafts and explains. Every AI output that touches the record — analysis,
follow-ups, matches — has a human approval step by construction, not by
policy alone.

## Privacy, consent, and security

**"How is a child's identity separated from their medical/care data?"**
At the schema level: `ChildIdentity` (name, DOB, gender) and `CareProfile`
(conditions, needs, services) are separate tables, not separate views over
one table. A center never sees identity data before a guardian grants access
to a specific child.

**"What does a guardian actually control?"**
Per care-team member, per child: which permissions (view reports, upload
reports, manage goals, message the team, etc.), an optional expiry date, and
revocation at any time. This was demonstrated live in the seed data — the
same specialist has a full permission set on one child and a two-permission,
view-only slot on another.

**"What happens to a specialist's contributed data if access is revoked?"**
The specialist's past contributions (reports, goals, messages) stay in the
child's record — revocation stops future access, it doesn't retroactively
erase clinical history the family may still need. [Confirm this is the
answer the team wants to give; it's a real product decision worth stating
deliberately rather than improvising live.]

**"Is this actually secure, or just a demo?"**
Concretely: Argon2 password hashing, JWT access/refresh tokens with real
server-side refresh-token rotation and revocation (not just short expiry),
login lockout after repeated failures, and a startup guard that refuses to
boot in production with a default secret or a non-Postgres database. These
were added and tested this cycle, not inherited — 111 backend tests pass,
including dedicated tests for the lockout and rotation behavior.

**"Did you test this against a real database, or just SQLite?"**
Both, deliberately, because they disagree in ways that matter: all 18
migrations were run from empty against real PostgreSQL, and doing so caught a
real bug (a column too narrow for a genuine multi-number phone listing) that
87 SQLite-backed tests had no way to catch, since SQLite doesn't enforce
column length. Fixed and re-verified on Postgres.

## Centers & matching

**"Are these real centers or fake ones?"**
Both, clearly separated. The demo's matching results mostly use fictional,
clearly-labeled demo centers so the four child journeys can show different
results reliably. Six *real* centers in Riyadh and Jeddah were researched
from each center's own official website (never scraped from Google Maps,
never using a paid Places API) and added with a source URL and review date —
but they are marked "unverified" until an administrator formally reviews
them, which is a deliberately separate step from "we found a public website."

**"Couldn't a center's ranking be gamed or biased?"**
Ranking is deterministic, computed from recorded needs/age/city/delivery
preference against each center's own recorded specialties/services — not
from any generative text, and not from ratings or popularity. The generative
layer only writes the *summary sentence*; it cannot alter which centers rank
or why, and a filter blocks generated text containing phrases like "أفضل
مركز" (best center) before it ever reaches a user.

## Architecture & scale

**"Why FastAPI/React instead of [X]?"**
[Team's own reasoning — not something to improvise from outside knowledge.]

**"Does the real-time chat scale past one server?"**
Not yet — it's an in-memory WebSocket implementation on a single process,
which is fine for a prototype and a live demo but a documented limitation for
production. The honest answer is "single-process today, Redis pub/sub (or
equivalent) is the known next step," not a claim it already scales.

**"Why isn't there a native mobile app?"**
Deliberately out of scope — one responsive site serves both, verified at five
viewport sizes (360px through 1440px) with zero horizontal-overflow issues
found in this pass, plus a baseline PWA manifest/service worker already in
place.

**"Is the interface accessible?"**
Keyboard focus is visible everywhere (not just default browser styling),
`prefers-reduced-motion` is respected, and the current color system was
checked against real WCAG contrast math — every text/background pairing in
the retheme clears AA, worst case 5.18:1. Screen-reader state announcement on
custom toggle controls is a known partial gap (documented, one instance fixed
this session, several others identified and not yet addressed).

## Sustainability & business model

**"Who pays for this?"** / **"What's the cost per user?"** / **"What's the
path to break-even?"**
[Genuinely open — these are business decisions for the team, not engineering
answers. Do not answer with an invented number in the room; say the model is
still being defined and describe the *options* under consideration if the
team has discussed any (family-pay, institutional/B2B via centers or
insurers, grant-funded pilot), rather than presenting a guess as a decision.]

## If asked to compare to a specific existing product
Do not improvise a comparison to a named competitor from general knowledge —
verify what it actually does first, or defer: "We'd want to give you an
accurate comparison rather than guess at what [product] currently does."
