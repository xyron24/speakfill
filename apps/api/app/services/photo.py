"""Photo pre-fill: validate -> normalize (EXIF-strip) -> vision extract -> map to schema.

Runs as a FastAPI BackgroundTask so the upload returns 202 immediately; the
client polls GET /api/jobs/{id}. Failures land on the job row, never as 500s.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Answer, Job, Session, TemplateField
from app.services.llm import VisionError, get_adapter

logger = logging.getLogger("speakfill.photo")

MAX_PHOTO_BYTES = 8 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


class PhotoError(Exception):
    """Invalid upload (client's fault -> 400, nothing persisted)."""


def uploads_dir() -> Path:
    d = Path(settings.data_dir) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def normalize_image(data: bytes) -> bytes:
    """Validate + EXIF-transpose + re-encode as metadata-free PNG."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise PhotoError(f"not a readable image: {e}") from e
    if (img.format or "").upper() not in ALLOWED_FORMATS:
        raise PhotoError(f"unsupported image format: {img.format} (use PNG/JPEG/WebP)")
    img = ImageOps.exif_transpose(img).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # fresh encode => no EXIF / metadata survives
    return buf.getvalue()


def _readable(field: TemplateField, value, language: str) -> str:
    if value is None:
        return ""
    if field.ftype == "choice" and field.options:
        for o in field.options:
            if o.get("key") == value:
                return o.get(language) or o.get("en") or str(value)
    if isinstance(value, dict):
        v, scale = value.get("value"), value.get("scale")
        return f"{v:g} ({'percent' if scale == 'percent' else 'CGPA'})" if v is not None else ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def run_extraction(job_id: uuid.UUID) -> None:
    """Background worker: extract, map to schema, recompute next field. Own DB session."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        db.commit()

        session = db.get(Session, job.session_id)
        fields = list(
            db.execute(
                select(TemplateField)
                .where(TemplateField.template_id == session.template_id)
                .order_by(TemplateField.ord)
            )
            .scalars()
            .all()
        )
        schema = [
            {"key": f.field_key, "type": f.ftype,
             "options": [o["key"] for o in f.options] if f.options else None}
            for f in fields
        ]
        raw = (uploads_dir() / f"{job_id}.png").read_bytes()
        result = get_adapter().extract_fields(raw, schema)

        by_key = {f.field_key: f for f in fields}
        already_confirmed = {
            r.field_key
            for r in db.execute(
                select(Answer).where(Answer.session_id == session.id, Answer.confirmed.is_(True))
            )
            .scalars()
            .all()
        }
        mapped, unknown = [], []
        for vf in result.fields:
            field = by_key.get(vf.key)
            if field is None or vf.key == "UNKNOWN":
                unknown.append({"value": vf.value, "confidence": vf.confidence})
                continue
            if field.field_key in already_confirmed:
                continue  # never overwrite a human-confirmed value with a photo guess
            db.add(
                Answer(
                    session_id=session.id,
                    field_key=field.field_key,
                    attempt=1,
                    transcript=None,
                    extracted={"value": vf.value, "readable": _readable(field, vf.value, session.language),
                               "needs_clarify": False, "clarify_reason": None},
                    confidence=vf.confidence,
                    source="photo",
                    confirmed=False,
                    created_at=datetime.now(timezone.utc),
                )
            )
            mapped.append({"key": vf.key, "value": vf.value, "confidence": vf.confidence})

        # Next state = first required field still lacking a confirmed answer.
        # Photo values are unconfirmed, so the interview starts at field 1 and
        # the user voice-confirms each pre-filled value in order.
        remaining = [f for f in fields if f.required and f.field_key not in already_confirmed]
        if remaining:
            session.current_ord = remaining[0].ord
        else:
            session.status = "review"
        session.updated_at = datetime.now(timezone.utc)

        job.status = "done"
        job.result = {"fields": mapped, "unknown": unknown, "next_ord": session.current_ord}
        db.commit()
        logger.info("photo job %s done: %d mapped, %d unknown", job_id, len(mapped), len(unknown))
    except (VisionError, OSError) as e:
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = "failed"
            job.error = str(e)[:500]
            db.commit()
        logger.warning("photo job %s failed: %s", job_id, e)
    finally:
        db.close()
