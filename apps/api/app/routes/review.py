import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import Session as SessionRow, Submission
from app.services.pdf import pdfs_dir, render_pdf
from app.services.review import answers_hash, build_review, confirmed_values, existing_submission
from app.services.stt import VoiceError
from app.services.tts import speak

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/sessions/{session_id}/review")
def get_review(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    s = db.get(SessionRow, session_id)
    if s is None:
        raise HTTPException(404, f"unknown session: {session_id}")
    review = build_review(db, s)
    try:
        review["readback_audio_url"] = speak(review["readback_script"], s.language)
    except VoiceError as e:
        review["readback_audio_url"] = None
        review["audio_error"] = str(e)
    review["can_export"] = s.status == "review" and not review["blocked"]
    return review


def _share_text(language: str, template_name: str, pdf_url: str) -> str:
    if language == "hi":
        return (
            f"मैंने अभी SpeakFill से बोलकर अपना {template_name} भरा — "
            f"बोलो। पुष्टि करो। हो गया। {pdf_url}"
        )
    return (
        f"I just completed my {template_name} by voice with SpeakFill — "
        f"Speak. Confirm. Done. {pdf_url}"
    )


@router.post("/sessions/{session_id}/export", status_code=201)
def export_session(session_id: uuid.UUID, db: DBSession = Depends(get_db)):
    s = db.get(SessionRow, session_id)
    if s is None:
        raise HTTPException(404, f"unknown session: {session_id}")
    if s.status == "active":
        raise HTTPException(409, "finish the interview first (session is still active)")

    review = build_review(db, s)
    if review["blocked"]:
        raise HTTPException(422, {"message": "form cannot be exported", "reasons": review["block_reasons"]})

    new_hash = answers_hash(confirmed_values(db, s.id))
    pdf_url_base = settings.app_base_url.rstrip("/")

    existing = existing_submission(db, s.id)
    if existing is not None and existing.answers_hash == new_hash:
        pdf_url = f"{pdf_url_base}/api/submissions/{existing.id}.pdf"
        return {
            "submission_id": str(existing.id),
            "pdf_url": pdf_url,
            "share_text": _share_text(
                s.language, review["template"]["name"].get(s.language, s.template_id), pdf_url
            ),
        }

    # New or changed answers: replace any stale submission.
    if existing is not None:
        old = pdfs_dir() / f"{existing.id}.pdf"
        if old.exists():
            old.unlink()
        db.delete(existing)
        db.flush()

    now = datetime.now(timezone.utc)
    sub = Submission(session_id=s.id, pdf_path="", answers_hash=new_hash, completed_at=now)
    db.add(sub)
    db.flush()  # assign sub.id before rendering
    consent_ts = now.strftime("%Y-%m-%d %H:%M UTC")
    path = render_pdf(sub.id, review, now, consent_ts)
    sub.pdf_path = str(path)
    s.status = "done"
    s.updated_at = now
    db.commit()

    pdf_url = f"{pdf_url_base}/api/submissions/{sub.id}.pdf"
    return {
        "submission_id": str(sub.id),
        "pdf_url": pdf_url,
        "share_text": _share_text(
            s.language, review["template"]["name"].get(s.language, s.template_id), pdf_url
        ),
    }


@router.get("/submissions/{submission_id}.pdf")
def get_submission_pdf(submission_id: str, db: DBSession = Depends(get_db)):
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise HTTPException(404, "unknown submission")
    sub = db.get(Submission, sid)
    if sub is None:
        raise HTTPException(404, "unknown submission")
    path = pdfs_dir() / f"{sub.id}.pdf"
    if not path.exists():
        raise HTTPException(404, "submission file missing")
    return FileResponse(path, media_type="application/pdf", filename=f"speakfill-{sub.id}.pdf")
