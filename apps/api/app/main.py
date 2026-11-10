from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.audio import router as audio_router
from app.routes.feedback import router as feedback_router
from app.routes.photos import router as photos_router
from app.routes.review import router as review_router
from app.routes.sessions import router as sessions_router
from app.routes.templates import router as templates_router

app = FastAPI(title="SpeakFill API", version="0.5.0")
app.include_router(templates_router)
app.include_router(sessions_router)
app.include_router(audio_router)
app.include_router(photos_router)
app.include_router(review_router)
app.include_router(feedback_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "service": "speakfill-api",
        "app": settings.app_name,
        "time": datetime.now(timezone.utc).isoformat(),
    }
