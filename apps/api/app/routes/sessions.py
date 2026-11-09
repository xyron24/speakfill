import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import Session as SessionRow
from app.services.llm import LLMAdapter, get_adapter
from app.services.session import SessionService
from app.services.stt import ALLOWED_MIME, MAX_AUDIO_BYTES, VoiceError, transcribe
from app.services.tts import speak
from app.vocab import match_yes_no

router = APIRouter(prefix="/api", tags=["sessions"])


class CreateSessionBody(BaseModel):
    template_id: str
    language: str = "en"


class AnswerBody(BaseModel):
    text: str  # JSON clients: tests and typed input


class ConfirmBody(BaseModel):
    accepted: bool  # JSON clients; multipart {audio} alternative below


def get_llm() -> LLMAdapter:
    return get_adapter()


def _locale_of(db: DBSession, session_id: uuid.UUID) -> str:
    s = db.get(SessionRow, session_id)
    if s is None:
        raise HTTPException(404, f"unknown session: {session_id}")
    return s.language


def _with_prompt_audio(result: dict, locale: str) -> dict:
    """Attach TTS read-back audio. Non-fatal: text flow survives voice outages."""
    try:
        result["prompt_audio_url"] = speak(result["next_prompt"], locale)
    except VoiceError as e:
        result["prompt_audio_url"] = None
        result["audio_error"] = str(e)
    return result


@router.post("/sessions", status_code=201)
def create_session(
    body: CreateSessionBody, db: DBSession = Depends(get_db), llm: LLMAdapter = Depends(get_llm)
):
    return SessionService(db, llm).create(body.template_id, body.language)


@router.get("/sessions/{session_id}")
def get_session(
    session_id: uuid.UUID, db: DBSession = Depends(get_db), llm: LLMAdapter = Depends(get_llm)
):
    return SessionService(db, llm).state(session_id)


@router.post("/sessions/{session_id}/answer")
async def answer(
    session_id: uuid.UUID,
    request: Request,
    db: DBSession = Depends(get_db),
    llm: LLMAdapter = Depends(get_llm),
):
    """Accepts JSON {text} (typed) or multipart (audio file + optional text)."""
    ctype = request.headers.get("content-type", "")
    text: str | None = None
    source = "typed"

    if ctype.startswith("multipart/"):
        form = await request.form()
        audio = form.get("audio")
        if audio is not None:
            data: bytes = await audio.read()
            if len(data) > MAX_AUDIO_BYTES:
                raise HTTPException(400, f"audio too large (>{MAX_AUDIO_BYTES} bytes)")
            mime = (audio.content_type or "").split(";")[0].strip()
            if mime not in ALLOWED_MIME:
                raise HTTPException(400, f"unsupported audio type: {mime or 'unknown'}")
            locale = _locale_of(db, session_id)
            try:
                text = transcribe(data, mime, locale).transcript
            except VoiceError as e:
                raise HTTPException(502, {"message": str(e), "fallback": "typed"})
            source = "voice"
        elif form.get("text"):
            text = str(form.get("text"))
        else:
            raise HTTPException(422, "multipart needs an 'audio' file or a 'text' field")
    else:
        text = AnswerBody.model_validate(await request.json()).text

    locale = _locale_of(db, session_id)
    result = SessionService(db, llm).answer(session_id, text, source=source)
    return _with_prompt_audio(result, locale)


@router.post("/sessions/{session_id}/confirm")
async def confirm(
    session_id: uuid.UUID,
    request: Request,
    db: DBSession = Depends(get_db),
    llm: LLMAdapter = Depends(get_llm),
):
    """Accepts JSON {accepted} or multipart {audio} (yes/no matched post-STT)."""
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/"):
        form = await request.form()
        audio = form.get("audio")
        if audio is None:
            raise HTTPException(422, "multipart confirm needs an 'audio' file")
        data: bytes = await audio.read()
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(400, f"audio too large (>{MAX_AUDIO_BYTES} bytes)")
        locale = _locale_of(db, session_id)
        try:
            transcript = transcribe(data, (audio.content_type or "").split(";")[0], locale).transcript
        except VoiceError as e:
            raise HTTPException(502, {"message": str(e), "fallback": "typed"})
        accepted = match_yes_no(transcript, locale)
        if accepted is None:
            raise HTTPException(
                422, {"message": f"unclear confirmation: {transcript!r}", "fallback": "typed"}
            )
    else:
        accepted = ConfirmBody.model_validate(await request.json()).accepted

    result = SessionService(db, llm).confirm(session_id, accepted)
    if result.get("next_prompt"):
        result = _with_prompt_audio(result, _locale_of(db, session_id))
    return result


@router.post("/sessions/{session_id}/restart")
def restart(
    session_id: uuid.UUID, db: DBSession = Depends(get_db), llm: LLMAdapter = Depends(get_llm)
):
    return SessionService(db, llm).restart(session_id)
