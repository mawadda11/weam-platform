Weam M2 - Real Speech-to-Text integration

This patch upgrades the existing Voice Notes workflow from mock transcription
to an optional real OpenAI transcription adapter while keeping the provider
boundary intact.

Recommended model:
  gpt-4o-mini-transcribe

Server-side environment:
  WEAM_STT_PROVIDER=openai
  WEAM_STT_API_KEY=<your OpenAI API key>
  WEAM_STT_MODEL=gpt-4o-mini-transcribe
  WEAM_STT_LANGUAGE=ar
  WEAM_STT_TIMEOUT_SECONDS=90

Important:
- Never put the API key in frontend/.env or VITE_* variables.
- Keep the key only in backend/.env / server environment.
- Use synthetic/test audio during development.
- Existing mock mode still works by setting WEAM_STT_PROVIDER=mock.
- No database migration is needed for this patch.
- httpx is already part of the backend requirements.
