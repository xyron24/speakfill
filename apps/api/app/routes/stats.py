from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import Feedback, Session

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def get_stats(db: DBSession = Depends(get_db)):
    sessions_total = db.execute(select(func.count()).select_from(Session)).scalar() or 0
    sessions_done = (
        db.execute(
            select(func.count()).select_from(Session).where(Session.status == "done")
        ).scalar()
        or 0
    )
    by_language = {
        lang: n
        for lang, n in db.execute(
            select(Session.language, func.count()).group_by(Session.language)
        ).all()
    }
    feedback_count = db.execute(select(func.count()).select_from(Feedback)).scalar() or 0
    by_country = {
        country: n
        for country, n in db.execute(
            select(Feedback.country, func.count()).group_by(Feedback.country)
        ).all()
    }
    avg_rating = db.execute(select(func.avg(Feedback.rating))).scalar()
    return {
        "sessions_total": sessions_total,
        "sessions_done": sessions_done,
        "sessions_by_language": by_language,
        "feedback_count": feedback_count,
        "feedback_by_country": by_country,
        "avg_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
    }
