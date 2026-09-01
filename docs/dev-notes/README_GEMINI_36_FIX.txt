Weam Gemini 3.6 Flash compatibility fix

Reason:
- Gemini 2.5 Flash is no longer available to new users.
- Gemini 3.6 Flash is the stable replacement.
- Sampling parameter `temperature` is deprecated for Gemini 3.6 Flash, so it is removed.

Update backend/.env manually:
WEAM_ASSISTANT_MODEL=gemini-3.6-flash
WEAM_AI_MODEL=gemini-3.6-flash

Keep your API key only in backend/.env. Do not commit it.
No migration. No new dependencies.
