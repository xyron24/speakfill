"""Photo pre-fill tests (canned vision — no model key needed for pipeline mechanics)."""

import io
import pathlib
import time

import pytest
from PIL import Image

import app.services.photo as photo_mod
from app.db import SessionLocal
from app.models import Job
from app.services.llm import StubAdapter, VisionField, VisionResult
from app.services.photo import PhotoError, normalize_image

FIX = pathlib.Path(__file__).with_name("fixtures")

CLEAN_VISION = VisionResult(fields=[
    VisionField(key="full_name", value="Rahul Sharma", confidence=0.95),
    VisionField(key="date_of_birth", value="2004-03-12", confidence=0.9),
    VisionField(key="gender", value="M", confidence=0.9),
    VisionField(key="phone", value="9876543210", confidence=0.9),
    VisionField(key="email", value="rahul.sharma@example.com", confidence=0.85),
    VisionField(key="university", value="Polaris School of Technology", confidence=0.8),
    VisionField(key="course_of_study", value="B.Tech Computer Science", confidence=0.8),
    VisionField(key="year_of_study", value="y2", confidence=0.85),
    VisionField(key="cgpa", value={"value": 8.5, "scale": "cgpa"}, confidence=0.9),
    VisionField(key="family_income", value="i2", confidence=0.7),
    VisionField(key="UNKNOWN", value="Ref No: near canteen counter", confidence=0.5),
])

LOWCONF_VISION = VisionResult(fields=[
    VisionField(key="full_name", value="Rahul Sharma", confidence=0.3),
    VisionField(key="phone", value="9876543210", confidence=0.25),
])


def _new_session(client, language="en"):
    r = client.post("/api/sessions", json={"template_id": "scholarship-v1", "language": language})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def _poll_done(client, job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never finished")


def _upload(client, sid, name):
    with open(FIX / name, "rb") as f:
        return client.post(f"/api/sessions/{sid}/photo", files={"photo": (name, f, "image/png")})


def test_clean_photo_maps_10_fields_and_quarantines_unknown(client, monkeypatch):
    monkeypatch.setattr(StubAdapter, "extract_fields", lambda self, img, schema: CLEAN_VISION)
    sid = _new_session(client)
    r = _upload(client, sid, "clean.png")
    assert r.status_code == 202, r.text
    job = _poll_done(client, r.json()["job_id"])
    assert job["status"] == "done", job
    assert len(job["result"]["fields"]) == 10
    assert len(job["result"]["unknown"]) == 1
    # Photo values are unconfirmed -> interview starts at field 1 for voice confirm.
    assert job["result"]["next_ord"] == 1

    state = client.get(f"/api/sessions/{sid}").json()
    assert state["current_ord"] == 1
    by_key = {a["key"]: a for a in state["answers"]}
    assert by_key["full_name"]["value"] == "Rahul Sharma"
    assert by_key["full_name"]["confirmed"] is False
    assert by_key["full_name"]["source"] == "photo"
    assert by_key["need_statement"]["value"] is None  # not on paper -> stays for voice

    # Confirming the pre-filled value directly (no re-answer) advances the loop.
    c = client.post(f"/api/sessions/{sid}/confirm", json={"accepted": True}).json()
    assert c["current_field"]["key"] == "date_of_birth"


def test_degraded_photos_complete_with_low_confidence(client, monkeypatch):
    monkeypatch.setattr(StubAdapter, "extract_fields", lambda self, img, schema: LOWCONF_VISION)
    for name in ("skewed.png", "lowlight.png"):
        sid = _new_session(client)
        r = _upload(client, sid, name)
        assert r.status_code == 202, r.text
        job = _poll_done(client, r.json()["job_id"])
        assert job["status"] == "done", (name, job)
        assert job["result"]["fields"][0]["confidence"] == pytest.approx(0.3)


def test_non_image_and_oversize_rejected_without_trace(client):
    sid = _new_session(client)
    r = client.post(f"/api/sessions/{sid}/photo", files={"photo": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400
    big = b"\xff" * (8 * 1024 * 1024 + 1)
    r = client.post(f"/api/sessions/{sid}/photo", files={"photo": ("big.png", big, "image/png")})
    assert r.status_code == 400
    r = client.post(
        f"/api/sessions/{sid}/photo", files={"photo": ("fake.png", b"not-an-image", "image/png")}
    )
    assert r.status_code == 400
    with SessionLocal() as db:
        assert db.query(Job).count() == 0  # 400s persist nothing


def test_photo_on_finished_session_rejected(client):
    sid = _new_session(client)
    with SessionLocal() as db:
        from app.models import Session as SessionRow

        db.get(SessionRow, sid).status = "review"
        db.commit()
    with open(FIX / "clean.png", "rb") as f:
        r = client.post(f"/api/sessions/{sid}/photo", files={"photo": ("clean.png", f, "image/png")})
    assert r.status_code == 409


def test_unknown_session_and_job_404(client):
    with open(FIX / "clean.png", "rb") as f:
        r = client.post(
            "/api/sessions/00000000-0000-0000-0000-000000000000/photo",
            files={"photo": ("clean.png", f, "image/png")},
        )
    assert r.status_code == 404
    assert client.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code == 404


def test_normalize_strips_exif_and_rejects_gif():
    img = Image.new("RGB", (40, 30), "white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=Image.Exif())
    out = normalize_image(buf.getvalue())
    assert Image.open(io.BytesIO(out)).format == "PNG"
    assert Image.open(io.BytesIO(out)).info.get("exif") is None

    gif = io.BytesIO()
    img.save(gif, format="GIF")
    with pytest.raises(PhotoError):
        normalize_image(gif.getvalue())


def test_vision_failure_marks_job_failed_not_500(client):
    sid = _new_session(client)  # stub adapter raises VisionError (no monkeypatch)
    r = _upload(client, sid, "clean.png")
    assert r.status_code == 202
    job = _poll_done(client, r.json()["job_id"])
    assert job["status"] == "failed"
    assert "vision" in job["error"].lower()
