Weam AI Assistant readability polish

Apply on top of RAG v2 + Gemini patch.

Changes:
- Formats assistant replies as readable headings + bullet lists.
- Stops rendering the whole answer as one dense paragraph.
- Makes local fallback concise instead of dumping raw retrieved chunks.
- Translates common goal statuses in fallback.
- Removes synthetic test metadata from follow-up fallback.
- Gemini prompt now targets 2-4 concise points (~90 words).
- Sources remain collapsed by default.

No migration. No new dependencies.
