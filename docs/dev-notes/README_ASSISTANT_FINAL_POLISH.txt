Weam AI Assistant final UI polish + chat deletion

Included:
- Compact assistant hero.
- Arabic product-facing labels (no Gemini/RAG jargon in the UI).
- Smaller safety footer inside assistant answers.
- Cleaner source cards; raw source excerpt is hidden behind "عرض مقتطف المصدر".
- Friendly conversation titles in the sidebar.
- Delete button for old assistant chats with confirmation.
- Backend DELETE endpoint with ownership/privacy checks and audit logging.
- Gemini prompt wording tightened around diagnosis attribution.
- No DB migration and no new dependency.

Important:
- Keep your real API keys only in backend/.env.
- Do not commit backend/.env.

After applying:
1) backend: .\.venv\Scripts\python.exe -m pytest -q
2) frontend: npm.cmd run typecheck
3) frontend: npm.cmd run build
4) manually test deleting active and inactive old chats.
