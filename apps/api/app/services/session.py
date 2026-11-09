"""SessionService: the interview state machine.

Turn states: ASKING -> TRANSCRIBING -> EXTRACTING -> CONFIRMING -> next ASKING | REVIEW.
Session statuses persisted in DB: active | review | done | abandoned.
Routes never mutate state directly — everything funnels through here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from app.models import Answer, Job, Session, Template, TemplateField
from app.services.llm import LLMAdapter
from app.vocab import confirm_prompt, retry_prompt

MAX_ATTEMPTS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def field_payload(field: TemplateField, language: str) -> dict:
    prompts = field.prompts.get(language) or field.prompts.get("en", {})
    options = None
    if field.options:
        options = [{"key": o["key"], "label": o.get(language) or o.get("en")} for o in field.options]
    return {
        "key": field.field_key,
        "ord": field.ord,
        "type": field.ftype,
        "required": field.required,
        "prompt_text": prompts.get("ask", ""),
        "prompt_hint": prompts.get("hint", ""),
        "options": options,
    }


class SessionService:
    def __init__(self, db: DBSession, llm: LLMAdapter):
        self.db = db
        self.llm = llm

    # ------------------------------------------------------------ helpers
    def _get_session(self, session_id: uuid.UUID) -> Session:
        s = self.db.get(Session, session_id)
        if s is None:
            raise HTTPException(404, f"unknown session: {session_id}")
        return s

    def _fields(self, s: Session) -> list[TemplateField]:
        return list(
            self.db.execute(
                select(TemplateField)
                .where(TemplateField.template_id == s.template_id)
                .order_by(TemplateField.ord)
            )
            .scalars()
            .all()
        )

    def _current_field(self, s: Session) -> TemplateField | None:
        for f in self._fields(s):
            if f.ord == s.current_ord:
                return f
        return None

    def _pending(self, s: Session, field_key: str) -> Answer | None:
        return (
            self.db.execute(
                select(Answer)
                .where(
                    Answer.session_id == s.id,
                    Answer.field_key == field_key,
                    Answer.confirmed.is_(False),
                )
                .order_by(Answer.id.desc())
            )
            .scalars()
            .first()
        )

    def _attempt_count(self, s: Session, field_key: str) -> int:
        return (
            self.db.execute(
                select(func.count())
                .select_from(Answer)
                .where(Answer.session_id == s.id, Answer.field_key == field_key)
            ).scalar()
            or 0
        )

    def _latest_value(self, s: Session, field_key: str):
        row = (
            self.db.execute(
                select(Answer)
                .where(Answer.session_id == s.id, Answer.field_key == field_key)
                .order_by(Answer.id.desc())
            )
            .scalars()
            .first()
        )
        return (row.extracted or {}).get("value") if row else None

    def _confirmed_map(self, s: Session) -> dict[str, Answer]:
        rows = (
            self.db.execute(
                select(Answer)
                .where(Answer.session_id == s.id, Answer.confirmed.is_(True))
                .order_by(Answer.id)
            )
            .scalars()
            .all()
        )
        return {r.field_key: r for r in rows}

    # ---------------------------------------------------------------- API
    def create(self, template_id: str, language: str) -> dict:
        if language not in ("en", "hi"):
            raise HTTPException(422, f"unsupported language: {language} (use 'en' or 'hi')")
        tpl = self.db.get(Template, template_id)
        if tpl is None or not tpl.is_active:
            raise HTTPException(404, f"unknown template: {template_id}")
        s = Session(
            template_id=tpl.id,
            template_version=tpl.version,  # sessions pin the version they started with
            language=language,
            status="active",
            current_ord=1,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        fields = self._fields(s)
        first = next(f for f in fields if f.ord == 1)
        return {
            "session_id": str(s.id),
            "template_id": s.template_id,
            "template_version": s.template_version,
            "language": s.language,
            "status": s.status,
            "current_field": field_payload(first, s.language),
            "total_fields": len(fields),
        }

    def answer(self, session_id: uuid.UUID, text: str, source: str = "typed") -> dict:
        s = self._get_session(session_id)
        if s.status in ("done", "abandoned"):
            raise HTTPException(409, f"session is {s.status}")
        if s.status == "review":
            raise HTTPException(409, "session is in review")
        field = self._current_field(s)
        if field is None:
            raise HTTPException(409, "no current field for this session")

        attempt = self._attempt_count(s, field.field_key) + 1
        prev = self._latest_value(s, field.field_key)
        result = self.llm.normalize(
            field_schema={
                "key": field.field_key, "type": field.ftype,
                "options": field.options, "validation": field.validation,
            },
            transcript=text,
            locale=s.language,
            previous_value=prev,
        )
        self.db.add(
            Answer(
                session_id=s.id,
                field_key=field.field_key,
                attempt=attempt,
                transcript=text,
                extracted=result.model_dump(),
                confidence=result.confidence,
                source=source,
                confirmed=False,
                created_at=_now(),
            )
        )
        s.updated_at = _now()
        self.db.commit()

        typed_nudge = attempt > MAX_ATTEMPTS or result.clarify_reason == "user_requested_typed"
        payload = field_payload(field, s.language)
        if result.needs_clarify:
            next_prompt = retry_prompt(s.language, payload["prompt_text"], payload["prompt_hint"])
        else:
            next_prompt = confirm_prompt(s.language, result.readable)
        return {
            "transcript": text,
            "value": result.value,
            "readable": result.readable,
            "confidence": result.confidence,
            "needs_clarify": result.needs_clarify,
            "clarify_reason": result.clarify_reason,
            "attempt": attempt,
            "max_attempts": MAX_ATTEMPTS,
            "typed_nudge": typed_nudge,
            "next_prompt": next_prompt,
        }

    def confirm(self, session_id: uuid.UUID, accepted: bool) -> dict:
        s = self._get_session(session_id)
        if s.status in ("done", "abandoned"):
            raise HTTPException(409, f"session is {s.status}")
        field = self._current_field(s)
        pending = self._pending(s, field.field_key) if field else None
        if pending is None:
            raise HTTPException(409, "nothing to confirm — answer first")
        if (pending.extracted or {}).get("needs_clarify"):
            raise HTTPException(409, "last answer needs clarification — answer again")

        if not accepted:
            payload = field_payload(field, s.language)
            return {
                "accepted": False,
                "status": s.status,
                "current_field": payload,
                "attempt_next": pending.attempt + 1,
                "next_prompt": retry_prompt(s.language, payload["prompt_text"], payload["prompt_hint"]),
            }

        pending.confirmed = True
        value = (pending.extracted or {}).get("value")

        # Consent refused: park in review, blocked, with a restart offer.
        if field.field_key == "consent" and value is False:
            s.status = "review"
            s.updated_at = _now()
            self.db.commit()
            msg = (
                "Declaration declined, so this form can't be submitted. "
                "Say 'restart' (POST /api/sessions/{id}/restart) to start over."
                if s.language == "en"
                else "घोषणा अस्वीकार — यह फॉर्म जमा नहीं हो सकता। заново शुरू करने के लिए restart कहें।"
            )
            return {"accepted": True, "status": "review", "blocked": True, "message": msg}

        fields = self._fields(s)
        remaining = [f for f in fields if f.ord > s.current_ord and f.required]
        if not remaining:
            s.status = "review"
            s.updated_at = _now()
            self.db.commit()
            return {"accepted": True, "status": "review", "blocked": False}
        s.current_ord = remaining[0].ord
        s.updated_at = _now()
        self.db.commit()
        return {
            "accepted": True,
            "status": s.status,
            "current_field": field_payload(remaining[0], s.language),
        }

    def state(self, session_id: uuid.UUID) -> dict:
        s = self._get_session(session_id)
        fields = self._fields(s)
        confirmed = self._confirmed_map(s)
        latest: dict[str, Answer] = {}
        for row in (
            self.db.execute(
                select(Answer).where(Answer.session_id == s.id).order_by(Answer.id)
            )
            .scalars()
            .all()
        ):
            latest[row.field_key] = row
        answers = []
        for f in fields:
            shown = confirmed.get(f.field_key) or latest.get(f.field_key)
            answers.append(
                {
                    "key": f.field_key,
                    "ord": f.ord,
                    "confirmed": f.field_key in confirmed,
                    "pending": shown is not None and not (f.field_key in confirmed),
                    "value": (shown.extracted or {}).get("value") if shown else None,
                    "source": shown.source if shown else None,
                }
            )
        missing = [f.field_key for f in fields if f.required and f.field_key not in confirmed]
        consent = confirmed.get("consent")
        blocked = bool(missing) or (consent is not None and (consent.extracted or {}).get("value") is False)
        current = self._current_field(s)
        return {
            "session_id": str(s.id),
            "template_id": s.template_id,
            "template_version": s.template_version,
            "language": s.language,
            "status": s.status,
            "blocked": blocked,
            "current_ord": s.current_ord,
            "current_field": field_payload(current, s.language) if current and s.status == "active" else None,
            "answers": answers,
        }

    def restart(self, session_id: uuid.UUID) -> dict:
        s = self._get_session(session_id)
        for row in self.db.query(Answer).filter_by(session_id=s.id).all():
            self.db.delete(row)
        for row in self.db.query(Job).filter_by(session_id=s.id).all():
            self.db.delete(row)
        s.status = "active"
        s.current_ord = 1
        s.updated_at = _now()
        self.db.commit()
        first = next(f for f in self._fields(s) if f.ord == 1)
        return {"session_id": str(s.id), "status": s.status, "current_field": field_payload(first, s.language)}
