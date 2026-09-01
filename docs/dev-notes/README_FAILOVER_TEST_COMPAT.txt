Weam Gemini failover test compatibility fix

Fixes:
- Keeps the new Gemini 3.6 -> Gemini 3.5 -> Local failover unchanged.
- Restores `assistant_generation.httpx` so the existing assistant-generation
  tests can monkeypatch HTTP calls exactly as before.
- The shared failover service now accepts an optional HTTP post function.
- Report AI continues to use the shared default HTTP client.
- No DB migration and no new dependency.

Run:
  cd backend
  .\.venv\Scripts\python.exe -m pytest -q
