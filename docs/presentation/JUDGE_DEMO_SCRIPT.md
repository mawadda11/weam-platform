# Mentor / judge live demonstration script

Three depths, so whoever's at the table can match the time a judge actually
has — most will only give you the 20-second version unprompted.

**Before any demo**: confirm the environment is seeded and clean
(`python -m scripts.seed_demo --rebuild` if it's been used for testing since
the last reset), and have the demo credentials sheet ready but never displayed
on screen (see the booth checklist). Log in as `guardian@weam.demo` before the
judge sits down — don't make them wait through a login screen.

---

## 20-second version (the elevator pitch)

> "أسرة الطفل ذي الإعاقة تتعامل مع تقارير ومختصين ومراكز متفرقة — كل جهة على
> حدة. وئام تجمعها في سجل رعاية واحد، بصلاحيات يتحكم بها ولي الأمر، ومساعد
> ذكي يلخّص ويربط بدون أن يشخّص."

Say it once, from memory, without looking at the screen. If the judge's eyes
go to the laptop after this sentence, move to the 2-minute version.

## 2-minute walkthrough

Goal: show the unified record, permissions, and one AI-assisted moment — not
every feature.

1. **(20s)** Dashboard with the four-child switcher already open. "هذا حساب
   ولي أمر واحد يتابع أربعة أطفال بقصص مختلفة." Click into Lama.
2. **(25s)** Child profile hero + the four shortcut cards. "كل شيء عن لمى في
   مكان واحد — التقارير، الأهداف، فريق الرعاية، المتابعات."
3. **(30s)** Open the hearing report → click "تحليل التقرير". Point at the
   "مراجعة بشرية قبل الاعتماد" badge before scrolling to content. "أي تحليل
   من الذكاء الاصطناعي يبقى مسودة حتى يعتمده إنسان — دايمًا."
4. **(25s)** Care Team page for Lama. "ولي الأمر يحدد بالضبط من يشوف ماذا —
   ومتى تنتهي صلاحيته." Point at an expiring/limited permission if one is
   visible without extra clicks.
5. **(20s)** Center matching results for Lama. "التوصية موضحة الأسباب دائمًا،
   وما تقول أبدًا إن مركز هو الأفضل طبيًا."

Close with: "هذا نموذج أولي شغّال بالكامل — مو مجرد تصميم."

## 5-minute walkthrough (the full journey)

Follow the exact story the product is built around — this is deliberately
the same sequence as the demo video, so a judge who watched the video and then
sees the live demo recognizes it instead of getting a second, different demo.

1. **Guardian → child record** (30s): dashboard, child switcher, Lama's
   profile. Mention the identity/care-profile separation in one sentence if
   asked "how is privacy handled" — don't volunteer it unprompted, it slows
   the pace.
2. **Report → draft analysis → human review** (60s): upload is already seeded,
   so open the existing report, show the PDF opens (click "تنزيل" briefly),
   then the AI analysis page. Explicitly say the word "مسودة" and point at
   the review-status badge. This is the single most safety-relevant moment in
   the whole demo — do not rush it.
3. **Follow-up appears → notification** (30s): jump to Notifications, point at
   the due-today follow-up card tied to that same report.
4. **Weam Assistant** (45s): open Lama's assistant thread, read the seeded
   question aloud, then read the answer's first sentence aloud and point at
   the citation. If a judge asks a live question, type one in — the local
   deterministic fallback still grounds correctly answers even without a live
   external AI call (see Q&A doc, "what if the AI service is down").
5. **Suitable center + reasons** (45s): center matching page, point at the
   ranked list and the "الأسباب" text for the top result, then favorite it.
6. **Communication with the specialist** (40s): Communication Hub, show the
   thread with the SLP, point at the shared-goal message bubble specifically
   ("هذا مو مجرد شات — هو مرتبط مباشرة بهدف لمى").
7. **Close** (30s): "هذا كامل الرحلة — من تقرير لمركز مناسب لتواصل مباشر مع
   المختص، كل شيء مترابط وتحت تحكم الأسرة." State the closing line here too
   (same sentence as the video's end card and the deck's last slide).

### If there's time left / a technically-curious judge
- Show the responsive layout by resizing the browser or switching to a phone,
  on the *same* dashboard they just saw on desktop — don't re-explain the
  product, just prove "same site, both devices."
- Show the admin center-review screen only if asked how the real-center data
  is governed — it's not part of the core story and can make the demo feel
  administrative if shown unprompted.

## Recovery moves (things that can go wrong)
- **Live build unreachable / Wi-Fi down**: switch immediately to the offline
  screen recording (see booth checklist) — say "خلينا نشوف تسجيل سريع للتجربة
  الحية" and keep talking over it. Don't apologize more than once.
- **A judge asks to see a real child's data**: state plainly that all data in
  the demo is synthetic and no real child information exists in the system in
  this environment — this is a one-sentence answer, not a diversion.
- **A judge pushes on "is this AI diagnosing"**: point at the badge again and
  say the boundary out loud: "الذكاء الاصطناعي يلخّص ويربط، ما يشخّص ولا
  يوصي بعلاج — القرار دايمًا للمختص."
