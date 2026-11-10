"""Review, export, PDF content, and feedback tests."""

import io

from pypdf import PdfReader

from app.db import SessionLocal
from app.models import Answer
from tests.test_loop import FULL_RUN


def _new_session(client, language="en"):
    r = client.post("/api/sessions", json={"template_id": "scholarship-v1", "language": language})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def _walk_to_review(client, sid, consent_text="yes, I agree"):
    for key, text in FULL_RUN:
        a = client.post(f"/api/sessions/{sid}/answer", json={"text": text}).json()
        assert not a["needs_clarify"], (key, a)
        client.post(f"/api/sessions/{sid}/confirm", json={"accepted": True})
    a = client.post(f"/api/sessions/{sid}/answer", json={"text": consent_text}).json()
    assert not a["needs_clarify"], a
    return client.post(f"/api/sessions/{sid}/confirm", json={"accepted": True}).json()


def _pdf_text(client, pdf_url):
    r = client.get(pdf_url)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    return PdfReader(io.BytesIO(r.content)).pages[0].extract_text()


def test_review_lists_12_fields_with_labels_and_script(client):
    sid = _new_session(client)
    _walk_to_review(client, sid)
    review = client.get(f"/api/sessions/{sid}/review").json()
    assert len(review["fields"]) == 12
    assert review["blocked"] is False and review["can_export"] is True
    assert review["fields"][0]["label"] == "Full name"
    assert review["fields"][0]["value"] == "Vaibhav Pandey"
    assert all(f["confirmed"] for f in review["fields"])
    assert "Vaibhav Pandey" in review["readback_script"]
    assert review["readback_audio_url"].endswith(".wav")


def test_export_produces_pdf_with_values_and_markers(client):
    sid = _new_session(client)
    _walk_to_review(client, sid)
    ex = client.post(f"/api/sessions/{sid}/export").json()
    assert ex["pdf_url"].endswith(".pdf") and "SpeakFill" in ex["share_text"]
    text = _pdf_text(client, f"/api/submissions/{ex['submission_id']}.pdf")
    for needle in ("Vaibhav Pandey", "Scholarship Application", "Typed", "Declaration"):
        assert needle in text, needle
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["status"] == "done"


def test_reexport_same_id_until_answers_change(client):
    sid = _new_session(client)
    _walk_to_review(client, sid)
    first = client.post(f"/api/sessions/{sid}/export").json()["submission_id"]
    again = client.post(f"/api/sessions/{sid}/export").json()["submission_id"]
    assert again == first

    with SessionLocal() as db:
        row = db.query(Answer).filter_by(session_id=sid, field_key="full_name", confirmed=True).one()
        blob = dict(row.extracted)
        blob["value"] = "Changed Name"  # real edits rewrite value + readable together
        blob["readable"] = "Changed Name"
        row.extracted = blob
        db.commit()
    # Back to review so export is allowed again (simulates an edit flow).
    with SessionLocal() as db:
        from app.models import Session as SessionRow

        db.get(SessionRow, sid).status = "review"
        db.commit()
    third = client.post(f"/api/sessions/{sid}/export").json()["submission_id"]
    assert third != first
    text = _pdf_text(client, f"/api/submissions/{third}.pdf")
    assert "Changed Name" in text


def test_export_blocked_consent_no_and_active_session(client):
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/export")
    assert r.status_code == 409  # still active

    sid2 = _new_session(client)
    end = _walk_to_review(client, sid2, consent_text="no")
    assert end["blocked"] is True
    r = client.post(f"/api/sessions/{sid2}/export")
    assert r.status_code == 422
    assert any("consent" in reason for reason in r.json()["detail"]["reasons"])


def test_export_blocked_when_fields_missing(client):
    sid = _new_session(client)
    with SessionLocal() as db:
        from app.models import Session as SessionRow

        db.get(SessionRow, sid).status = "review"
        db.commit()
    r = client.post(f"/api/sessions/{sid}/export")
    assert r.status_code == 422
    assert any("missing" in reason for reason in r.json()["detail"]["reasons"])


def test_hindi_review_uses_hindi_labels(client):
    sid = _new_session(client, language="hi")
    _walk_to_review(client, sid)
    review = client.get(f"/api/sessions/{sid}/review").json()
    assert review["fields"][0]["label"] == "पूरा नाम"
    assert "फॉर्म" in review["readback_script"]


def test_feedback_ok_and_validation(client):
    sid = _new_session(client)
    r = client.post(
        "/api/feedback",
        json={"session_id": sid, "country": "India", "rating": 5, "comment": "Bahut badhiya!"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["session_id"] == sid

    bad = client.post(
        "/api/feedback", json={"session_id": sid, "country": "IN", "rating": 9}
    )
    assert bad.status_code == 422
    missing = client.post(
        "/api/feedback",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "country": "IN", "rating": 4},
    )
    assert missing.status_code == 404


def test_unknown_pdf_404s(client):
    assert client.get("/api/submissions/00000000-0000-0000-0000-000000000000.pdf").status_code == 404
    assert client.get("/api/submissions/not-a-uuid.pdf").status_code == 404
