Weam Milestone 2 - Feature 2: Voice Notes + Speech-to-Text

Apply after M2 AI Report Analysis is merged.

Adds:
- Browser microphone recording with MediaRecorder.
- Upload WebM/WAV/MP3/M4A audio.
- Secure child-scoped audio storage.
- Provider-independent STT service boundary.
- Local mock transcription to test the complete workflow without pretending it recognized the audio.
- Human review/edit/approve/reject before transcript is considered approved.
- View-only members never see an unreviewed draft transcript.
- New permissions: view_voice_notes and create_voice_notes.

Important for the first UI test:
- Primary guardian automatically bypasses child permission checks, so test father1 first.
- Existing care providers do NOT automatically gain the two new voice permissions.
  Grant them later through Care Team permission UI after the small permission-list polish,
  or via API during developer testing.
- No new pip package is required.
- Run Alembic to 0006_voice_notes.
- Set WEAM_STT_PROVIDER=mock for local testing.

This patch intentionally tests the workflow first. A real STT provider adapter is the next integration step after UI approval.
