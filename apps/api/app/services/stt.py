"""Speech-to-text via smallest.ai Pulse (pre-recorded endpoint).

Docs: https://docs.smallest.ai/models/speech-to-text/quickstart
  POST https://api.smallest.ai/waves/v1/stt/?model=pulse&language={en|hi}
  body = raw audio bytes (Content-Type: application/octet-stream)
  -> {"status": "success", "transcription": "...", ...}
We use `pulse` (multilingual, incl. Hindi), NOT pulse-pro (English-only).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("speakfill.stt")

STT_URL = "https://api.smallest.ai/waves/v1/stt/"
MAX_AUDIO_BYTES = 2 * 1024 * 1024  # 2 MB ~ 30 s of Opus, per plan
ALLOWED_MIME = {
    "audio/webm", "audio/ogg", "audio/opus", "audio/mpeg", "audio/mp3",
    "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac",
}


class VoiceError(Exception):
    """Provider/voice failure. Routers translate this into a typed-fallback error shape."""


@dataclass
class TranscribeResult:
    transcript: str
    timed_ms: float
    language: str | None = None


# Test hook: tests set app.services.stt._stub_hook = lambda audio, mime, locale: "..."
_stub_hook = None


def transcribe(audio_bytes: bytes, mime: str, locale: str, timeout: float = 30.0) -> TranscribeResult:
    if settings.voice_provider == "stub":
        if _stub_hook is None:
            raise VoiceError("stub STT has no transcript hook (tests set stt._stub_hook)")
        t0 = time.perf_counter()
        text = _stub_hook(audio_bytes, mime, locale)
        return TranscribeResult(transcript=text, timed_ms=(time.perf_counter() - t0) * 1000)

    if not settings.smallest_api_key:
        raise VoiceError("missing SMALLEST_API_KEY — switch to typed input")

    t0 = time.perf_counter()
    try:
        r = httpx.post(
            STT_URL,
            params={"model": settings.smallest_stt_model, "language": locale},
            headers={"Authorization": f"Bearer {settings.smallest_api_key}"},
            content=audio_bytes,
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        raise VoiceError(f"STT request failed: {e}") from e
    timed_ms = (time.perf_counter() - t0) * 1000

    if r.status_code != 200:
        raise VoiceError(f"STT HTTP {r.status_code}: {r.text[:200]}")
    try:
        data = r.json()
    except ValueError:
        raise VoiceError(f"STT returned non-JSON: {r.text[:200]}")
    if data.get("status") != "success" or not data.get("transcription"):
        raise VoiceError(f"STT unsuccessful: {str(data)[:200]}")

    logger.info("stt ok lang=%s timed_ms=%.0f chars=%d", locale, timed_ms, len(data["transcription"]))
    return TranscribeResult(
        transcript=data["transcription"], timed_ms=timed_ms, language=data.get("language")
    )
