Weam Gemini output completion fix

- Keeps gemini-3.6-flash.
- Sets thinkingLevel=low for RAG summarization (faster and sufficient for this task).
- Raises maxOutputTokens from 700 to 2000 to avoid clipped answers/citations.

No migration and no new dependencies.
