"""LLM value-normalization behind a thin adapter.

- StubAdapter: deterministic offline rules (tests, curl walkthroughs, no-key demos).
- OpenAICompatAdapter: any OpenAI-compatible chat-completions endpoint, temp 0, strict JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from app.config import settings
from app.vocab import match_yes_no

SYSTEM_PROMPT = """You extract ONE form-field value. Output strict JSON: {"value": <typed|null>, "readable": "<short spoken read-back in locale>", "confidence": 0..1, "needs_clarify": bool, "clarify_reason": "<short>"}.
Rules: never invent values; return null+needs_clarify when unsure; apply field type rules (date→ISO YYYY-MM-DD, phone→digits only, choice→canonical key, boolean→true/false, email→lowercase, number→{"value": <float>, "scale": "cgpa"|"percent"}); interpret corrections against previous_value ("No, I said Sharma" fixes the name); map locale yes/no words."""


class NormalizeResult(BaseModel):
    value: Any = None
    readable: str = ""
    confidence: float = 0.0
    needs_clarify: bool = False
    clarify_reason: str | None = None


class VisionError(Exception):
    """Vision extraction failure (no model, bad image, invalid JSON)."""


class VisionField(BaseModel):
    key: str  # schema key, or "UNKNOWN" for unmappable content
    value: Any = None
    confidence: float = 0.0


class VisionResult(BaseModel):
    fields: list[VisionField] = []


VISION_SYSTEM_PROMPT = """You read a photographed paper form. Output strict JSON: {"fields": [{"key": "<schema key or UNKNOWN>", "value": <typed>, "confidence": 0..1}]}.
Rules: only use keys from the provided schema; anything else → "UNKNOWN" (quarantined, never forced into schema); dates→ISO YYYY-MM-DD; digits only for phones; booleans→true/false; choice→canonical option key; numbers→{"value": <float>, "scale": "cgpa"|"percent"}; confidence below 0.5 must still be returned."""


class LLMAdapter:
    def normalize(
        self, field_schema: dict, transcript: str, locale: str, previous_value: Any = None
    ) -> NormalizeResult:
        raise NotImplementedError

    def extract_fields(self, image_png: bytes, schema: list[dict]) -> VisionResult:
        raise NotImplementedError


# ---------------------------------------------------------------- stub ---

_FILLERS = {"uhh", "uh", "hmm", "hmmm", "umm", "um", "er", "ah", "huh"}
_UNKNOWN = {"i don't know", "i dont know", "dont know", "don't know", "no idea",
            "pata nahin", "pata nahi", "maloom nahin", "maloom nahi", "nahin pata"}
_TYPED_REQUESTS = {"type it", "type", "i'll type", "i will type", "let me type",
                   "likhunga", "likh leti hoon", "likh leta hoon", "type karoonga"}
_CORRECTION_RES = [
    re.compile(r"^\s*(?:no,?\s+)?i\s+(?:said|meant)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\s*nahin,?\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\s*no,?\s+(.+)$", re.IGNORECASE),
]
_LEADER_RES = [
    re.compile(r"^(?:my name is|this is|i am|i'm)\s+", re.IGNORECASE),
    re.compile(r"^(?:mera naam|mera name|main hoon|mein hoon)\s+", re.IGNORECASE),
]
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12,
}
_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DATE_WORD_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z\u0900-\u097F]+)\s+(\d{4})")
_DATE_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_NUMERIC_RE = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$")


def _clarify(reason: str, confidence: float = 0.2) -> NormalizeResult:
    return NormalizeResult(value=None, readable="", confidence=confidence,
                           needs_clarify=True, clarify_reason=reason)


class StubAdapter(LLMAdapter):
    """Deterministic rules. Good enough for tests/demos; the live adapter handles the wild."""

    def extract_fields(self, image_png: bytes, schema: list[dict]) -> VisionResult:
        raise VisionError("stub adapter has no vision model (tests monkeypatch this method)")

    def normalize(self, field_schema, transcript, locale, previous_value=None) -> NormalizeResult:
        t = (transcript or "").strip()
        low = t.lower()

        if low in _TYPED_REQUESTS:
            return _clarify("user_requested_typed", 0.0)
        if low in _UNKNOWN or any(p in low for p in _UNKNOWN):
            return _clarify("unknown_ask_hint")
        if len(t) < 2 or low in _FILLERS or all(w in _FILLERS for w in low.split()):
            return _clarify("unclear")

        if previous_value is not None:
            for rx in _CORRECTION_RES:
                m = rx.match(t)
                if m:
                    cand = re.sub(r"\s+not\s+.+$", "", m.group(1), flags=re.IGNORECASE).strip(" .")
                    if cand:
                        r = self._extract(field_schema, cand, locale)
                        r.confidence = min(r.confidence, 0.7)
                        return r

        return self._extract(field_schema, t, locale)

    # -- per-type extraction -------------------------------------------
    def _extract(self, field_schema, t: str, locale: str) -> NormalizeResult:
        ftype = field_schema.get("type")
        if ftype in ("text", "longtext"):
            v = t
            for rx in _LEADER_RES:
                v = rx.sub("", v).strip()
            v = v.strip(" .")
            max_len = (field_schema.get("validation") or {}).get("max_length")
            if max_len and len(v) > max_len:
                v = v[:max_len]
            if not v:
                return _clarify("unclear")
            return NormalizeResult(value=v, readable=v, confidence=0.9)
        if ftype == "date":
            return self._date(t)
        if ftype == "phone":
            digits = re.sub(r"\D", "", t)
            if 7 <= len(digits) <= 15:
                readable = f"{digits[:5]} {digits[5:]}" if len(digits) == 10 else digits
                return NormalizeResult(value=digits, readable=readable, confidence=0.85)
            return _clarify("invalid_phone")
        if ftype == "email":
            v = re.sub(r"\s+", "", t).lower().replace(" at ", "@").replace(" dot ", ".")
            v = v.replace(" at ", "@").replace(" dot ", ".")
            if re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", v):
                return NormalizeResult(value=v, readable=v, confidence=0.85)
            return _clarify("invalid_email")
        if ftype == "choice":
            return self._choice(field_schema.get("options") or [], t, locale)
        if ftype == "number":
            m = re.search(r"\d+(?:\.\d+)?", t.replace(",", ""))
            if not m:
                return _clarify("invalid_number")
            v = float(m.group(0))
            scale = "percent" if v > 10 else "cgpa"
            label = "percent" if scale == "percent" else "CGPA"
            return NormalizeResult(value={"value": v, "scale": scale},
                                   readable=f"{v:g} {label}", confidence=0.85)
        if ftype == "boolean":
            yn = match_yes_no(t, locale) if locale in ("en", "hi") else None
            if yn is None:  # try the other locale too (mixed speech happens)
                yn = match_yes_no(t, "hi" if locale == "en" else "en")
            if yn is None:
                return _clarify("unclear_yes_no")
            word = "yes" if yn else "no"
            return NormalizeResult(value=yn, readable=word, confidence=0.9)
        return _clarify("unsupported_type")

    def _date(self, t: str) -> NormalizeResult:
        m = _DATE_ISO_RE.match(t.strip())
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return NormalizeResult(value=f"{y:04d}-{mo:02d}-{d:02d}",
                                   readable=f"{d} {_MONTH_NAMES[mo]} {y}", confidence=0.9)
        m = _DATE_WORD_RE.search(t)
        if m:
            d, mon, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            mo = _MONTHS.get(mon)
            if mo and 1 <= d <= 31 and 1900 <= y <= 2100:
                return NormalizeResult(value=f"{y:04d}-{mo:02d}-{d:02d}",
                                       readable=f"{d} {_MONTH_NAMES[mo]} {y}", confidence=0.9)
            return _clarify("invalid_date")
        if _DATE_NUMERIC_RE.match(t.strip()):
            return _clarify("ambiguous_date")
        return _clarify("invalid_date")

    def _choice(self, options: list[dict], t: str, locale: str) -> NormalizeResult:
        low = t.lower()
        # Exact key/code matches first ("i2", "y1").
        for o in options:
            if low == o["key"].lower():
                return NormalizeResult(value=o["key"], readable=o.get(locale) or o["key"],
                                       confidence=0.9)
        # Label matches, longest first ("female" before "male").
        labels: list[tuple[str, dict]] = []
        for o in options:
            for loc in ("en", "hi"):
                if o.get(loc):
                    labels.append((o[loc], o))
        for label, o in sorted(labels, key=lambda x: -len(x[0])):
            if re.search(rf"\b{re.escape(label.lower())}\b", low):
                return NormalizeResult(value=o["key"],
                                       readable=o.get(locale) or o["key"], confidence=0.85)
        return _clarify("unknown_choice")


# ------------------------------------------------------- live adapter ---

class OpenAICompatAdapter(LLMAdapter):
    """Any OpenAI-compatible /chat/completions endpoint. Temp 0, JSON-only, one repair retry."""

    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is empty but llm_provider != 'stub'")
        base = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
        self.url = f"{base}/chat/completions"
        self.model = settings.llm_model or "gpt-4o-mini"

    def normalize(self, field_schema, transcript, locale, previous_value=None) -> NormalizeResult:
        user_msg = json.dumps({
            "field": field_schema, "transcript": transcript,
            "locale": locale, "previous_value": previous_value,
        }, ensure_ascii=False)
        data = self._chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        if data is None:  # repair retry, once
            data = self._chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
                {"role": "user", "content": "Return ONLY the JSON object, no other text."},
            ])
        if data is None:
            raise HTTPException(502, "LLM returned invalid JSON twice")
        return NormalizeResult.model_validate(data)

    def extract_fields(self, image_png: bytes, schema: list[dict]) -> VisionResult:
        import base64

        data_url = "data:image/png;base64," + base64.b64encode(image_png).decode()
        user_text = json.dumps(
            {"schema": schema, "instruction": "Extract all visible filled values."},
            ensure_ascii=False,
        )
        messages = [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ]
        data = self._chat(messages, timeout=60.0)
        if data is None:  # repair retry, once
            data = self._chat(
                messages + [{"role": "user", "content": "Return ONLY the JSON object."}],
                timeout=60.0,
            )
        if data is None:
            raise VisionError("vision model returned invalid JSON twice")
        try:
            return VisionResult.model_validate(data)
        except ValueError as e:
            raise VisionError(f"vision JSON failed validation: {e}") from e

    def _chat(self, messages: list[dict], timeout: float = 30.0) -> dict | None:
        try:
            r = httpx.post(
                self.url,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": self.model, "temperature": 0,
                      "response_format": {"type": "json_object"}, "messages": messages},
                timeout=timeout,
            )
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, IndexError):
            return None


_adapter: LLMAdapter | None = None


def get_adapter() -> LLMAdapter:
    global _adapter
    if _adapter is None:
        _adapter = StubAdapter() if settings.llm_provider == "stub" else OpenAICompatAdapter()
    return _adapter
