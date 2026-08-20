Weam Gemini automatic failover + report AI polish

Policy implemented:
1. Gemini 3.6 Flash is always the primary model.
2. On quota/rate-limit/transient failure it temporarily enters cooldown.
3. Requests automatically fall back to Gemini 3.5 Flash.
4. If both Gemini models are unavailable:
   - AI Assistant uses existing local grounded RAG fallback.
   - Report Analysis uses local deterministic extraction fallback.
5. After cooldown, the system automatically tries Gemini 3.6 again.
6. Repeated transient failures increase cooldown from 60s up to 15 minutes.

Also:
- Assistant delete button now uses a real trash-can SVG.
- Report AI output is connected to the same Gemini API key.
- Report result shows friendly model labels.
- Local fallback banner is accurate instead of saying Gemini is not connected.
- Evidence is collapsed by default to reduce visual clutter.
- Gemini report extraction returns Arabic structured content; evidence may stay in source language.
- No migration and no new dependency.

Keep these values in backend/.env:
WEAM_AI_PROVIDER=gemini
WEAM_AI_API_KEY=<your existing key>
WEAM_AI_MODEL=gemini-3.6-flash

WEAM_ASSISTANT_PROVIDER=gemini
WEAM_ASSISTANT_MODEL=gemini-3.6-flash

The secondary model is intentionally fixed to gemini-3.5-flash in the failover service.

Testing:
backend:
  .\.venv\Scripts\python.exe -m pytest -q

frontend:
  npm.cmd run typecheck
  npm.cmd run build

Manual:
- Normal request should record model gemini-3.6-flash.
- The application will automatically use 3.5/local only when needed.
- Never commit backend/.env or API keys.
