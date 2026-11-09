import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

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
