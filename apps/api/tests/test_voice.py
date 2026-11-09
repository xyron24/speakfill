"""Voice pipeline tests (stub provider — deterministic, no keys, no network)."""

import re

import app.services.stt as stt_mod
import app.services.tts as tts_mod
from app.config import settings


def _new_session(client, language="en"):
    r = client.post("/api/sessions", json={"template_id": "scholarship-v1", "language": language})
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def test_tts_cache_hit_means_no_resynth(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    tts_mod._synth_calls.clear()
    url1 = tts_mod.speak("What is your full name?", "en")
    url2 = tts_mod.speak("What is your full name?", "en")
    assert url1 == url2 and url1.endswith(".wav")
    assert len(tts_mod._synth_calls) == 1  # second call was a pure cache hit
    assert (tmp_path / "audio_cache").glob("*.wav")


def test_answer_includes_playable_prompt_audio(client):
    sid = _new_session(client)
    a = client.post(f"/api/sessions/{sid}/answer", json={"text": "Vaibhav Pandey"}).json()
    assert a["prompt_audio_url"].endswith(".wav")
    r = client.get(a["prompt_audio_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.content.startswith(b"RIFF")  # valid WAV (stub silence)


def test_audio_serving_rejects_unknown_and_traversal(client):
    assert client.get("/api/audio/" + "0" * 64 + ".wav").status_code == 404
    assert client.get("/api/audio/..%2f..%2fetc%2fpasswd").status_code in (404, 422)
    assert client.get("/api/audio/anything.mp3").status_code == 404


def test_audio_answer_transcribes_and_marks_voice_source(client, monkeypatch):
    monkeypatch.setattr(stt_mod, "_stub_hook", lambda audio, mime, loc: "Vaibhav Pandey")
    sid = _new_session(client)
    r = client.post(
        f"/api/sessions/{sid}/answer",
        files={"audio": ("clip.webm", b"fake-opus-bytes", "audio/webm")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["value"] == "Vaibhav Pandey"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["current_ord"] == 1  # STT filled the turn; confirmation still pending


def test_audio_answer_without_key_returns_typed_fallback(client, monkeypatch):
    monkeypatch.setattr(settings, "voice_provider", "smallest")
    monkeypatch.setattr(settings, "smallest_api_key", "")
    sid = _new_session(client)
    r = client.post(
        f"/api/sessions/{sid}/answer",
        files={"audio": ("clip.webm", b"fake-opus-bytes", "audio/webm")},
    )
    assert r.status_code == 502, r.text
    body = r.json()["detail"]
    assert body["fallback"] == "typed" and "Traceback" not in r.text


def test_oversize_and_bad_audio_rejected(client):
    sid = _new_session(client)
    big = b"x" * (2 * 1024 * 1024 + 1)
    r = client.post(f"/api/sessions/{sid}/answer", files={"audio": ("big.webm", big, "audio/webm")})
    assert r.status_code == 400
    r = client.post(f"/api/sessions/{sid}/answer", files={"audio": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400


def test_confirm_audio_yes_advances(client, monkeypatch):
    monkeypatch.setattr(stt_mod, "_stub_hook", lambda audio, mime, loc: "yes")
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/answer", json={"text": "Vaibhav Pandey"})
    r = client.post(
        f"/api/sessions/{sid}/confirm", files={"audio": ("y.webm", b"fake", "audio/webm")}
    )
    assert r.status_code == 200, r.text
    assert r.json()["current_field"]["key"] == "date_of_birth"


def test_confirm_audio_unclear_is_422(client, monkeypatch):
    monkeypatch.setattr(stt_mod, "_stub_hook", lambda audio, mime, loc: "maybe tomorrow")
    sid = _new_session(client)
    client.post(f"/api/sessions/{sid}/answer", json={"text": "Vaibhav Pandey"})
    r = client.post(
        f"/api/sessions/{sid}/confirm", files={"audio": ("m.webm", b"fake", "audio/webm")}
    )
    assert r.status_code == 422


def test_hindi_answer_gets_hindi_audio_url(client, monkeypatch):
    monkeypatch.setattr(stt_mod, "_stub_hook", lambda audio, mime, loc: "राहुल शर्मा")
    sid = _new_session(client, language="hi")
    r = client.post(
        f"/api/sessions/{sid}/answer",
        files={"audio": ("clip.webm", b"fake", "audio/webm")},
    )
    assert r.status_code == 200, r.text
    assert "राहुल" in r.json()["value"]
    assert re.match(r"^/api/audio/[a-f0-9]{64}\.wav$", r.json()["prompt_audio_url"])
