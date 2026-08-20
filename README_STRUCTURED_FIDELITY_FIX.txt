Weam assistant structured-source fidelity fix

Why:
Gemini can correctly understand a structured care-profile value but paraphrase
its wording (e.g. "دعم التواصل" -> "دعم في التواصل"). For structured fields,
the exact stored term should remain visible.

This fix:
- Keeps Gemini synthesis.
- Keeps Gemini 3.6 -> 3.5 -> Local failover.
- Preserves exact profile values when the question specifically asks about:
  needs, support requirements, current services, or conditions.
- Does not hard-code any child's value.
- Avoids adding duplicate exact terms.
- Adds regression tests.
- No migration, no new dependency.

Run:
  cd backend
  .\.venv\Scripts\python.exe -m pytest -q
