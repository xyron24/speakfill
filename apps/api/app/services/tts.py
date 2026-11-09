"""Text-to-speech via smallest.ai Lightning, cache-first.

Docs: https://docs.smallest.ai/models/getting-started
  POST https://api.smallest.ai/waves/v1/tts
  {"text", "voice_id", "model": "lightning_v3.1_pro", "sample_rate": 24000, "output_format": "wav"}
Cache key = sha256(locale | voice | text). Static prompts are pre-generated at
deploy (scripts/pregen_prompts.py); dynamic read-backs cache on first use.
"""

from __future__ import annotations

import hashlib
import io
import logging
import wave
from pathlib import Path

import httpx

from app.config import settings
from app.services.stt import VoiceError

logger = logging.getLogger("speakfill.tts")

TTS_URL = "https://api.smallest.ai/waves/v1/tts"

# Counts real syntheses (stub placeholder writes + live API calls). Tests assert
# cache behavior through this; pregen reports hits/misses itself.
_synth_calls: list[str] = []


def cache_dir() -> Path:
    d = Path(settings.data_dir) / "audio_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(text: str, locale: str, voice: str) -> str:
    return hashlib.sha256(f"{locale}|{voice}|{text}".encode("utf-8")).hexdigest()


def voice_for(locale: str) -> str:
    return settings.smallest_voice_hi if locale == "hi" else settings.smallest_voice_en


def speak(text: str, locale: str, voice: str | None = None) -> str:
    """Return the public URL path for this text's audio, synthesizing on cache miss."""
    voice = voice or voice_for(locale)
    filename = f"{cache_key(text, locale, voice)}.wav"
    path = cache_dir() / filename
    if not path.exists():
        path.write_bytes(_synthesize(text, locale, voice))
    return f"/api/audio/{filename}"


def _synthesize(text: str, locale: str, voice: str) -> bytes:
    _synth_calls.append(text)
    if settings.voice_provider == "stub":
        return _silence_wav(seconds=0.5)
    if not settings.smallest_api_key:
        raise VoiceError("missing SMALLEST_API_KEY — voice readout unavailable")
    try:
        r = httpx.post(
            TTS_URL,
            headers={
                "Authorization": f"Bearer {settings.smallest_api_key}",
                "Accept": "audio/wav",
            },
            json={
                "text": text,
                "voice_id": voice,
                "model": settings.smallest_tts_model,
                "sample_rate": 24000,
                "output_format": "wav",
            },
            timeout=30.0,
        )
    except httpx.HTTPError as e:
        raise VoiceError(f"TTS request failed: {e}") from e
    if r.status_code != 200 or not r.content.startswith(b"RIFF"):
        raise VoiceError(f"TTS unsuccessful (HTTP {r.status_code}): {r.text[:200]}")
    logger.info("tts ok lang=%s voice=%s chars=%d bytes=%d", locale, voice, len(text), len(r.content))
    return r.content


def _silence_wav(seconds: float = 0.5, sample_rate: int = 24000) -> bytes:
    """Minimal valid WAV (silence) so stub mode still serves playable audio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00" * int(sample_rate * seconds) * 2)
    return buf.getvalue()
