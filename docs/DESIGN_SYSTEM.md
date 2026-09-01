# Weam design system

Approved palette: **Option A — Blue-Violet + Teal** (see prior audit/approval in
project history). This document is the reference; implementation lives in
`frontend/src/styles/global.css` (base tokens, shared with `WeamLogo` and the
public/auth screens) and `frontend/src/styles/m9-polish.css` (the `--m9-*`
tokens most authenticated pages actually consume).

## Color roles

| Role | Hex | Used for |
|---|---|---|
| Primary | `#4338CA` | Brand wordmark, primary buttons, active top-level nav, links, kickers, focus rings on primary actions |
| Primary bright | `#6D5BD0` | Gradients and large fills only — not small text on white (contrast) |
| Primary soft | `#EEECFB` | Active-state backgrounds, badges, AI-assisted content cards |
| Secondary (teal) | `#0F8A82` | Secondary actions, in-page tabs, calm/neutral positive surfaces, human-authored (non-AI) content |
| Teal soft | `#E5F5F3` | Secondary badges, quick-stat tiles |
| Accent (gold) | `#E8A33D` | Sparing use only — "next action" nudges, highlights. Never large fills. |
| Background | `#F7F7FB` | App background |
| Surface | `#FFFFFF` | Cards |
| Text (ink) | `#221F3B` | Body text, headings |
| Text muted | `#635E7A` | Secondary text |
| Success | `#1E8E5A` | |
| Warning | `#B9770E` | |
| Error | `#C23B4B` | |

## The AI-assisted signal

Blue-violet (primary) is deliberately reused as a **trust signal**, not just a
brand color: any AI-assisted, human-reviewable surface — draft report
analysis, Weam Assistant replies, center-match reasons — gets a
primary-tinted card border/background (`--m9-primary-soft`) and, where space
allows, a small "draft — needs review" style label. Secondary teal marks
human-authored content (specialist notes, care-team activity) by contrast.
This is a semantic distinction, not decoration: color alone never carries the
meaning (labels/icons always accompany it), but the recurring pairing helps a
user learn "violet-tinted = generated, please review" over repeated use.

## The harmony motif

"وئام" (harmony/togetherness) is expressed as a restrained set of soft
converging paths — a small circle (the child) with 2–3 gently curved lines
reaching it from different directions (guardian, specialist, center), each
line in a different palette color at low opacity, ending in small circular
nodes. No puzzle pieces, no literal disability iconography. Implemented as
`WeamConnector` (`frontend/src/components/WeamConnector.tsx`), an inline SVG
used as: (1) a subtle background texture on the landing hero and auth visual
panel, (2) a small mark near "current journey" / "next step" banners.

## Typography

Arabic-first. `Tajawal` (Google Fonts, open-source, SIL license) loaded for
Arabic text with the existing system stack (`Segoe UI, Tahoma, Arial`) as
fallback so a blocked font request never breaks layout.

## Other tokens

- Radius: 12–16px small controls, 20–28px cards/heroes, 999px pills — unchanged
  from the existing scale, which was already good.
- Shadows: re-tinted toward the primary/ink family (`rgba(67,56,202,.08–.14)`)
  instead of the old teal tint, kept equally soft.
- Motion: existing transitions kept; anything decorative-only (spinners,
  pulses) must be wrapped in `@media (prefers-reduced-motion: no-preference)`.

## What changed vs. what didn't

This pass retheme's the shared token layer and the highest-traffic surfaces
(wordmark, primary buttons, top-level nav, dashboard/child-profile heroes,
auth screens). Feature-specific CSS files (reports, goals, centers, admin,
etc.) inherit the new tokens automatically wherever they already reference
`var(--m9-*)` / `var(--teal)` etc. — which is most of them, since the app
already centralized color through these two files. Anything that still reads
visually "off-brand" after this pass is a targeted follow-up, not a sign the
approach didn't work.
