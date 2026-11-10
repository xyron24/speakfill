import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import TemplateField
from app.services.stt import VoiceError
from app.services.tts import speak

router = APIRouter(prefix="/api", tags=["audio"])

# Cache-only serving: strict shape, no user text is ever proxied (prevents API abuse).
_AUDIO_RE = re.compile(r"^[a-f0-9]{64}\.wav$")


@router.get("/audio/{name}")
def get_audio(name: str):
    if not _AUDIO_RE.match(name):
        raise HTTPException(404, "unknown audio")
    path = Path(settings.data_dir) / "audio_cache" / name
    if not path.exists():
        raise HTTPException(404, "unknown audio")
    return FileResponse(
        path,
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/audio/prompt/{template_id}/{ord}")
def prompt_audio(template_id: str, ord: int, language: str = Query("en"), db: DBSession = Depends(get_db)):
    """Spoken ask+hint for one field (ask autoplay, replay, demo mode). Cached like all TTS."""
    if language not in ("en", "hi"):
        raise HTTPException(422, "language must be 'en' or 'hi'")
    field = (
        db.execute(
            select(TemplateField).where(
                TemplateField.template_id == template_id, TemplateField.ord == ord
            )
        )
        .scalars()
        .first()
    )
    if field is None:
        raise HTTPException(404, f"unknown field {template_id}#{ord}")
    prompts = field.prompts.get(language) or field.prompts.get("en", {})
    text = f"{prompts.get('ask', '')} {prompts.get('hint', '')}".strip()
    try:
        return {"audio_url": speak(text, language), "text": text}
    except VoiceError as e:
        raise HTTPException(502, {"message": str(e), "fallback": "typed"})
