"""Review assembly: localized labels, read-back script, block checks, answer hashing."""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import Answer, Session, Submission, Template, TemplateField

FIELD_LABELS: dict[str, dict[str, str]] = {
    "full_name": {"en": "Full name", "hi": "पूरा नाम"},
    "date_of_birth": {"en": "Date of birth", "hi": "जन्मतिथि"},
    "gender": {"en": "Gender", "hi": "लिंग"},
    "phone": {"en": "Phone", "hi": "मोबाइल नंबर"},
    "email": {"en": "Email", "hi": "ईमेल"},
    "university": {"en": "University", "hi": "विश्वविद्यालय"},
    "course_of_study": {"en": "Course", "hi": "कोर्स"},
    "year_of_study": {"en": "Year of study", "hi": "अध्ययन वर्ष"},
    "cgpa": {"en": "CGPA / Percentage", "hi": "सीजीपीए / प्रतिशत"},
    "family_income": {"en": "Family income", "hi": "पारिवारिक आय"},
    "need_statement": {"en": "Need statement", "hi": "आवश्यकता विवरण"},
    "consent": {"en": "Declaration consent", "hi": "घोषणा सहमति"},
}

SOURCE_LABELS: dict[str, dict[str, str]] = {
    "voice": {"en": "Voice", "hi": "आवाज़"},
    "photo": {"en": "Photo", "hi": "फ़ोटो"},
    "typed": {"en": "Typed", "hi": "लिखित"},
    "demo": {"en": "Demo", "hi": "डेमो"},
}


def _fields(db: DBSession, s: Session) -> list[TemplateField]:
    return list(
        db.execute(
            select(TemplateField)
            .where(TemplateField.template_id == s.template_id)
            .order_by(TemplateField.ord)
        )
        .scalars()
        .all()
    )


def _confirmed(db: DBSession, session_id: uuid.UUID) -> dict[str, Answer]:
    rows = (
        db.execute(
            select(Answer)
            .where(Answer.session_id == session_id, Answer.confirmed.is_(True))
            .order_by(Answer.id)
        )
        .scalars()
        .all()
    )
    return {r.field_key: r for r in rows}


def label_for(field_key: str, language: str) -> str:
    labels = FIELD_LABELS.get(field_key, {})
    return labels.get(language) or labels.get("en") or field_key.replace("_", " ").title()


def answers_hash(values: dict[str, object]) -> str:
    payload = {k: values[k] for k in sorted(values)}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def confirmed_values(db: DBSession, session_id: uuid.UUID) -> dict[str, object]:
    confirmed = _confirmed(db, session_id)
    return {k: (a.extracted or {}).get("value") for k, a in confirmed.items()}


def build_review(db: DBSession, s: Session) -> dict:
    """Ordered field rows + read-back script + export block state."""
    tpl = db.get(Template, s.template_id)
    fields = _fields(db, s)
    confirmed = _confirmed(db, s.id)

    rows = []
    for f in fields:
        a = confirmed.get(f.field_key)
        value = (a.extracted or {}).get("value") if a else None
        readable = (a.extracted or {}).get("readable") if a else None
        if a is not None and not readable:
            readable = str(value)
        rows.append({
            "key": f.field_key,
            "ord": f.ord,
            "label": label_for(f.field_key, s.language),
            "type": f.ftype,
            "value": value,
            "readable": readable,
            "source": a.source if a else None,
            "confirmed": a is not None,
        })

    missing = [f.field_key for f in fields if f.required and f.field_key not in confirmed]
    reasons = [f"missing: {k}" for k in missing]
    consent = confirmed.get("consent")
    if consent is not None and (consent.extracted or {}).get("value") is False:
        reasons.append("consent declined")

    if s.language == "hi":
        script = "कृपया अपना भरा हुआ फॉर्म सुनिए। " + " ".join(
            f"{r['label']}: {r['readable'] or 'उपलब्ध नहीं'}." for r in rows
        )
    else:
        script = "Please review your completed form. " + " ".join(
            f"{r['label']}: {r['readable'] or 'not provided'}." for r in rows
        )

    return {
        "session_id": str(s.id),
        "template": {"id": tpl.id, "name": tpl.name, "version": s.template_version},
        "language": s.language,
        "status": s.status,
        "blocked": bool(reasons),
        "block_reasons": reasons,
        "fields": rows,
        "readback_script": script,
    }


def existing_submission(db: DBSession, session_id: uuid.UUID) -> Submission | None:
    return db.execute(select(Submission).where(Submission.session_id == session_id)).scalars().first()
