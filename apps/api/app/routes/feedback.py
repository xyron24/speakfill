import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import Feedback, Session as SessionRow

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackBody(BaseModel):
    session_id: uuid.UUID
    country: str = Field(min_length=1, max_length=64)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


@router.post("/feedback", status_code=201)
def submit_feedback(body: FeedbackBody, db: DBSession = Depends(get_db)):
    if db.get(SessionRow, body.session_id) is None:
        raise HTTPException(404, f"unknown session: {body.session_id}")
    row = Feedback(
        session_id=body.session_id,
        country=body.country.strip(),
        rating=body.rating,
        comment=(body.comment or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "session_id": str(row.session_id)}
