Weam M2 - FREE Local Speech-to-Text

This patch removes the paid OpenAI transcription dependency from the runtime
workflow and uses faster-whisper locally.

Cost:
- No API key.
- No per-minute API charge.
- The model is open source and runs locally.
- First run downloads the selected model once; later transcription is local.

Recommended local settings:
WEAM_STT_PROVIDER=local_whisper
WEAM_STT_MODEL=small
WEAM_STT_LANGUAGE=ar
WEAM_STT_DEVICE=cpu
WEAM_STT_COMPUTE_TYPE=int8

Install:
python -m pip install -r requirements.txt

Notes:
- "small" balances Arabic quality and CPU cost.
- If the laptop is slow, use WEAM_STT_MODEL=base.
- If language detection is desired, use WEAM_STT_LANGUAGE=auto.
- No database migration is needed.
- Remove WEAM_STT_API_KEY from .env; it is not used by local_whisper.
