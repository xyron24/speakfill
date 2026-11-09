import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import Job, Session as SessionRow
from app.services.photo import MAX_PHOTO_BYTES, PhotoError, normalize_image, run_extraction, uploads_dir

router = APIRouter(prefix="/api", tags=["photo"])


@router.post("/sessions/{session_id}/photo", status_code=202)
async def upload_photo(
    session_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    db: DBSession = Depends(get_db),
):
    s = db.get(SessionRow, session_id)
    if s is None:
        raise HTTPException(404, f"unknown session: {session_id}")
    if s.status in ("done", "abandoned", "review"):
        raise HTTPException(409, f"session is {s.status} (photo pre-fill needs an active session)")

    form = await request.form()
    upload = form.get("photo")
    if upload is None:
        raise HTTPException(422, "multipart needs a 'photo' file")
    data: bytes = await upload.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(400, f"photo too large (>{MAX_PHOTO_BYTES} bytes)")
    mime = (upload.content_type or "").split(";")[0].strip()
    if not mime.startswith("image/"):
        raise HTTPException(400, f"unsupported upload type: {mime or 'unknown'} (send an image)")

    # Validate + normalize BEFORE persisting anything (400s leave no trace).
    try:
        clean = normalize_image(data)
    except PhotoError as e:
        raise HTTPException(400, str(e))

    job_id = uuid.uuid4()
    (uploads_dir() / f"{job_id}.png").write_bytes(clean)
    db.add(Job(id=job_id, session_id=s.id, kind="photo_extract", status="queued"))
    db.commit()
    background.add_task(run_extraction, job_id)
    return {"job_id": str(job_id), "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID, db: DBSession = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, f"unknown job: {job_id}")
    return {
        "job_id": str(job.id),
        "session_id": str(job.session_id),
        "kind": job.kind,
        "status": job.status,
        "result": job.result,
        "error": job.error,
    }
