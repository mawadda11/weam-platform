# Demo video — script and shot list

Target length: **2:30–2:50** (fits the "2–3 minutes" requirement with margin for
editing). Narration is written in Arabic (the product's own language); screen
directions are in English for crew clarity. **Requires Arabic captions burned
in or as subtitles, per the submission rules** — do not rely on voice alone.

Every screen shown must be the real, seeded demo environment (`guardian@weam.demo`),
not a mockup. Record at 1440×900 or larger, then crop/letterbox for the final
export — do not record at a cramped mobile width and scale up.

Before recording: confirm the exact final repo/live-build/video URLs are ready
to type on-screen if the script calls for it (see beat 10), and reset the demo
database to a clean state (`python -m scripts.seed_demo --rebuild`) so nothing
looks half-finished from earlier testing.

---

## Beat-by-beat

| # | Time | Screen / action | Narration (Arabic) | Notes |
|---|---|---|---|---|
| 1 | 0:00–0:12 | Landing page (`/`), slow push-in on hero, then the `WeamConnector` background motif | "رحلة كل طفل موزّعة بين تقارير وأخصائيين ومراكز مختلفة. وئام تجمعها في مكان واحد — بصلاحيات يتحكم بها ولي الأمر." | Let the harmony-motif lines be visible; this is the one shot that sells the visual identity before any UI clutter. |
| 2 | 0:12–0:22 | Login → guardian dashboard, child switcher visible with all 4 children | "منى ولية أمر لمى، طفلة تحتاج متابعة سمعية منتظمة." | Cut on the child-switcher tap so the "multiple children, one guardian" capability registers without narrating it explicitly. |
| 3 | 0:22–0:34 | Lama's child profile hero → click into Reports | "هذا هو ملف لمى — التقارير والأهداف والمتابعات وفريق الرعاية، كلها في مكان واحد." | Single continuous scroll/click, no jump cuts, to read as "one connected record." |
| 4 | 0:34–0:50 | Open the seeded hearing report → click "تحليل التقرير" → show the analysis with the "مراجعة بشرية قبل الاعتماد" badge and the violet-tinted summary card | "وئام يحلل التقرير ويستخرج أهم المعلومات — كمسودة تحتاج مراجعة بشرية دائمًا قبل اعتمادها." | **Do not skip the "draft, needs review" badge** — it's the single clearest safety cue in the product and directly supports the Safety criterion. |
| 5 | 0:50–1:00 | Scroll to the approved analysis state / an existing approved goal tied to the report | "بعد المراجعة، تتحول التوصيات إلى أهداف ومتابعات فعلية." | Show goal1 ("توسيع المفردات") with its real progress bar. |
| 6 | 1:00–1:10 | Notifications page, the "متابعة اليوم" (due-today) item | "وئام يذكّر الأسرة بالخطوة التالية، لا يتركها تبحث عنها." | This is the one card that should read as urgent-but-calm, not alarming. |
| 7 | 1:10–1:28 | Weam Assistant thread for Lama, show the question + the grounded, source-cited answer | "مساعد وئام يجيب من بيانات لمى المصرّح بها فقط، ويذكر متى لا تتوفر معلومة — بدون تشخيص." | Let the citation chip for the report be visible on screen for at least 1.5s — it's evidence, not decoration. |
| 8 | 1:28–1:46 | Center matching page for Lama → the ranked results with visible reasons | "عند البحث عن مركز مناسب، تشرح وئام سبب كل توصية — بدون أي وصف طبي أو حكم على الجودة." | Zoom on the "الأسباب" (reasons) list for one card so it's legible, not just a flash of UI. |
| 9 | 1:46–1:58 | Save a center to favorites → cut to Communication Hub, the SLP's reply referencing the shared goal | "وتتواصل الأسرة مباشرة مع الأخصائية المصرّح لها، وتشارك التحديثات المهمة معها." | Shows the `message_type="shared"` goal-reference bubble — a distinctive, real feature, not a generic chat screenshot. |
| 10 | 1:58–2:10 | Quick montage: mobile viewport (375px) of the same dashboard + child profile, 2–3 fast cuts | "وئام تعمل بنفس الكفاءة على الجوال والحاسوب — من موقع واحد." | This is the only place a phone-width shot belongs; don't intersperse mobile shots earlier, it breaks the visual rhythm. |
| 11 | 2:10–2:24 | Cut to black or wordmark card | "وئام — بيانات تجريبية بالكامل في هذا العرض." + logo | **Mandatory**: the synthetic-data disclaimer must appear on screen, not just be assumed. |
| 12 | 2:24–2:40 | End card: wordmark, one-line pitch, [repo / live build / contact — fill in once URLs are confirmed] | closing line — see "Missing" below | Keep on screen ≥5s; judges pause video here to note links. |

**Total: ~2:40**, leaves room to trim to fit a hard 2:30 or 3:00 cutoff depending on final rules confirmation.

## Missing before this can be finalized
- The exact **closing line** the team wants judges to remember (the template's own slide 14 asks for this too — reuse the same sentence in both places for consistency).
- **Repo / live build / contact** for the end card (from the facts list already requested).
- Confirm whether the mentor/judge audience needs **English captions** in addition to Arabic, or Arabic-only is acceptable (affects post-production time).

## Shot list summary (for whoever's operating the recording)
1. Landing page hero (static, 3s hold + slow push-in)
2. Login → dashboard (real keystrokes, not a cut)
3. Child switcher tap → Lama profile
4. Reports list → open report → AI analysis page (scroll, don't cut mid-read)
5. Approved goal card
6. Notifications page, due-today card
7. Assistant thread with citation visible
8. Center matching results, reasons visible
9. Favorite tap → Communication Hub → shared-goal message
10. Three quick mobile-width cuts (dashboard, child profile, notifications)
11. Disclaimer card
12. End card
