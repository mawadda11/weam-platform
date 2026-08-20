from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

SECONDARY_MODEL = "gemini-3.5-flash"
BASE_COOLDOWN_SECONDS = 60
MAX_COOLDOWN_SECONDS = 15 * 60
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class GeminiCallResult:
    payload: dict
    model: str
    used_secondary: bool


class GeminiFailoverError(RuntimeError):
    pass


@dataclass
class _ModelState:
    failures: int = 0
    cooldown_until: float = 0.0


_states: dict[str, _ModelState] = {}
_lock = threading.Lock()


def _state(model: str) -> _ModelState:
    with _lock:
        return _states.setdefault(model, _ModelState())


def _available(model: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _lock:
        state = _states.setdefault(model, _ModelState())
        return state.cooldown_until <= now


def _retry_after_seconds(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        return None


def _register_failure(model: str, response: httpx.Response | None = None) -> None:
    retry_after = _retry_after_seconds(response) if response is not None else None
    now = time.monotonic()
    with _lock:
        state = _states.setdefault(model, _ModelState())
        state.failures += 1
        exponential = BASE_COOLDOWN_SECONDS * (2 ** min(state.failures - 1, 4))
        cooldown = min(MAX_COOLDOWN_SECONDS, max(retry_after or 0, exponential))
        state.cooldown_until = now + cooldown
        logger.warning(
            "Gemini model %s entered cooldown for %ss after transient failure #%s",
            model,
            cooldown,
            state.failures,
        )


def _register_success(model: str) -> None:
    with _lock:
        state = _states.setdefault(model, _ModelState())
        state.failures = 0
        state.cooldown_until = 0.0


def reset_failover_state() -> None:
    """Test/development helper. Runtime recovers automatically after cooldown."""
    with _lock:
        _states.clear()


def call_gemini_with_failover(
    *,
    api_key: str,
    primary_model: str,
    body: dict,
    timeout_seconds: int,
    post_func=None,
) -> GeminiCallResult:
    primary = (primary_model or "").strip() or "gemini-3.6-flash"
    if primary == "gemini-2.5-flash":
        # Backwards-compatible protection for old .env/config defaults.
        primary = "gemini-3.6-flash"

    models = [primary]
    if SECONDARY_MODEL not in models:
        models.append(SECONDARY_MODEL)

    errors: list[str] = []
    attempted = 0
    post = post_func or httpx.post

    for index, model in enumerate(models):
        if not _available(model):
            errors.append(f"{model}: cooldown")
            continue

        attempted += 1
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent"
        )

        try:
            response = post(
                endpoint,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                json=body,
                timeout=timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            _register_failure(model)
            errors.append(f"{model}: {type(exc).__name__}")
            continue

        if response.status_code < 400:
            _register_success(model)
            return GeminiCallResult(
                payload=response.json(),
                model=model,
                used_secondary=(index > 0),
            )

        excerpt = response.text[:350].replace("\n", " ")
        errors.append(f"{model}: HTTP {response.status_code} {excerpt}")

        if response.status_code in TRANSIENT_STATUS_CODES:
            _register_failure(model, response)
        else:
            # 400/401/403/404 are not quota cooldowns, but a second stable
            # model may still recover from a model-specific incompatibility.
            logger.warning(
                "Gemini model %s rejected request with HTTP %s; trying fallback",
                model,
                response.status_code,
            )

    if attempted == 0:
        reason = "all Gemini models are temporarily cooling down"
    else:
        reason = "; ".join(errors)

    raise GeminiFailoverError(
        "Gemini primary and secondary models are unavailable: " + reason
    )
