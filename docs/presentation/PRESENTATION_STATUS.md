# Presentation status

`WEAM_SUBMISSION_DRAFT.pptx` in this folder is a **working draft**, not the
final submission — it still has bracket placeholders on the slides that
genuinely depend on facts only the team has. This file tracks exactly what's
done, what's pending, and the one verification gap worth knowing about.

## Confirmed done (bracket-free, content-complete)

- **Slide 5 — Who we serve**: Lama's persona (age, context, a day today,
  needs, barriers, alternatives), grounded in the real seeded demo profile.
  The "what success feels like" field is deliberately **not** phrased as a
  verbatim interview quote — there is no real interview to quote.
- **Slide 6 — Our solution**: one-paragraph description + three capability
  cards (unified record, guardian-controlled access, explainable AI). The
  product-image placeholder still needs a real screenshot inserted.
- **Slide 7 — How it works**: the five-step flow rewritten to describe
  Weam's actual architecture (input → hosted model with local deterministic
  fallback → access-filtered processing → labeled draft output → human
  review), not the template's generic sensor/robotics flow.
- **Slide 10 — Results**: replaced the blank canvas with six real, verified
  numbers from this development cycle — 111/111 backend tests, 18/18
  migrations verified on real Postgres, 0 horizontal-overflow issues across 5
  viewport sizes, 5.18:1 worst-case contrast, 4 complete child journeys, 6
  real researched centers. Every number traces to something actually run
  this session, not an estimate.
- **Slide 13 — Safety, reliability, accessibility**: four bullets each under
  Safety / Reliability / Accessibility & ethics, all drawn from real,
  verified work (identity/care separation, draft-until-approved AI, the auth
  hardening, the Postgres verification, the contrast/keyboard/reduced-motion
  pass). Also fixed the template's own "SECTION 11" label to read
  "SECTION 11 · SAFETY" for consistency with the other section slides.

## Still blocked on facts only the team has

| Slide | What's missing |
|---|---|
| 2 (Submission details) | Project name formatting, team name, project number |
| 3 (Team snapshot) | One-line pitch confirmation, track rationale sentence, category, 2–5 team members' names/roles |
| 4 (Problem, 30%) | A real, cited Saudi-context statistic — do not fill with an invented number |
| 8 (What makes it different) | The comparison table needs real, verified competitor information, not a guess |
| 9 (Prototype and demo, 10%) | Demo video URL, repo URL, live build URL, TRL self-assessment |
| 11 (Expected impact, 30%) | Output/outcome/impact figures and a baseline→target — genuine business/product decisions, not engineering output |
| 12 (Sustainability, 10%) | Who pays, revenue model, cost per unit, path to break-even |
| 14 (Closing) | The one closing sentence (reuse in the demo video and judge script too), team lead contact |

Track = **Everyday Life**, Category = **Individuals** are already applied
where the template asks for them directly.

## One real verification gap

**LibreOffice isn't installed in this environment**, so the deck could not be
rendered to images for the pixel-level visual QA the presentation skill
normally requires (checking for text overflow, clipped boxes, misalignment).
What *was* verified:
- Structural/schema validation (`validate.py --original`) — passed clean.
- Every inserted text block was sized conservatively against its shape's
  actual EMU dimensions, matching font sizes already used elsewhere in the
  template for similarly-sized boxes.
- `markitdown` extraction confirms all intended bracket placeholders are gone
  from slides 5/6/7/10/13, and only the genuinely fact-blocked slides still
  have theirs.

**Before submission: open the actual `.pptx` in real PowerPoint (or Google
Slides) and eyeball slides 5, 10, and 13 specifically** — those have the
most added text density (the persona's narrow columns, the six-stat grid, and
the three bullet lists) and are the ones most likely to need a font-size nudge
if something wraps further than expected. This is the one QA step in the
whole engineering pass this session that was asserted from careful estimation
rather than actually observed.
