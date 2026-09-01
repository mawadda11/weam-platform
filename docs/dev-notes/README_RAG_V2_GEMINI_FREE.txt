Weam RAG v2 + Gemini Free Tier

Apply this patch on top of the existing M2 AI Assistant branch BEFORE pushing it.

What changed
------------
1. Local permission-aware retrieval remains the source of truth.
2. Gemini 2.5 Flash is used only to synthesize the selected authorized chunks.
3. If Gemini is unavailable, rate-limited, quota-limited, or missing a key,
   Weam automatically falls back to the local grounded answer.
4. Retrieval is intent-aware:
   - voice questions -> voice sources only
   - goal questions -> goal sources only
   - report questions -> report sources only
   - summary -> diverse profile/report/goal/voice sources
5. One real source = one citation card. Report findings are no longer five
   separate cards.
6. Source details are collapsed by default in the UI.
7. Gemini is instructed to answer in the user's language, summarize instead
   of copy, deduplicate, and prefer current/latest state.

backend/.env
------------
Add:

WEAM_ASSISTANT_PROVIDER=gemini
WEAM_ASSISTANT_API_KEY=PASTE_YOUR_GOOGLE_AI_STUDIO_KEY_HERE
WEAM_ASSISTANT_MODEL=gemini-2.5-flash
WEAM_ASSISTANT_TIMEOUT_SECONDS=45
WEAM_ASSISTANT_SOURCE_LIMIT=5

You may also leave WEAM_ASSISTANT_API_KEY empty: the feature will still work
with the local fallback.

Important privacy note
----------------------
Use Gemini Free Tier with synthetic/demo data only during MVP development.
Google states Free Tier content may be used to improve its products.
Do not send real child health/care data to the Free Tier.

No new Python/npm dependency. No database migration.
