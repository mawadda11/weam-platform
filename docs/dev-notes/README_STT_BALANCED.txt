Weam free STT balanced patch

Goals:
- Better Arabic/English accuracy: large-v3-turbo.
- Lower latency: batched inference and beam size 1.
- Still 100% local/free.
- Automatic fallback to small if the larger model cannot load.

Recommended backend .env:
WEAM_STT_PROVIDER=local_whisper
WEAM_STT_MODEL=large-v3-turbo
WEAM_STT_FALLBACK_MODEL=small
WEAM_STT_LANGUAGE=auto
WEAM_STT_DEVICE=cpu
WEAM_STT_COMPUTE_TYPE=int8
WEAM_STT_BATCH_SIZE=4
WEAM_STT_BEAM_SIZE=1
WEAM_STT_VAD_MIN_SILENCE_MS=500

No migration.
No new package beyond faster-whisper.
The first use of large-v3-turbo downloads the model once and is slower.
Subsequent transcriptions reuse the loaded model in the backend process.
