"""Scripted walkthrough of the interview loop (StubAdapter — deterministic, no keys)."""

import os

import pytest


def _new_session(client, language="en"):
    r = client.post("/api/sessions", json={"template_id": "scholarship-v1", "language": language})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["current_field"]["key"] == "full_name"
    assert body["total_fields"] == 12
    return body["session_id"]


def _answer(client, sid, text):
    r = client.post(f"/api/sessions/{sid}/answer", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _confirm(client, sid, accepted):
    r = client.post(f"/api/sessions/{sid}/confirm", json={"accepted": accepted})
    assert r.status_code == 200, r.text
    return r.json()


def test_three_field_walkthrough(client):
    sid = _new_session(client)

    a = _answer(client, sid, "My name is Vaibhav Pandey")
    assert a["value"] == "Vaibhav Pandey" and not a["needs_clarify"]
    c = _confirm(client, sid, True)
    assert c["current_field"]["key"] == "date_of_birth"

    a = _answer(client, sid, "12th March 2004")
    assert a["value"] == "2004-03-12" and not a["needs_clarify"]
    c = _confirm(client, sid, True)
    assert c["current_field"]["key"] == "gender"

    a = _answer(client, sid, "male")
    assert a["value"] == "M"
    c = _confirm(client, sid, True)
    assert c["current_field"]["key"] == "phone"

    state = client.get(f"/api/sessions/{sid}").json()
    assert state["current_ord"] == 4
    assert [x["key"] for x in state["answers"] if x["confirmed"]] == [
        "full_name", "date_of_birth", "gender",
    ]


def test_correction_fixes_value(client):
    sid = _new_session(client)
    _answer(client, sid, "Verma")
    _confirm(client, sid, False)  # rejected at confirm step
    a = _answer(client, sid, "No, I said Sharma not Verma")
    assert a["value"] == "Sharma", a
    _confirm(client, sid, True)
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["answers"][0]["value"] == "Sharma"
    assert state["answers"][0]["confirmed"] is True


def test_unclear_triggers_typed_nudge_after_3_attempts(client):
    sid = _new_session(client)
    for i in range(1, 5):
        a = _answer(client, sid, "uhh hmm")
        assert a["needs_clarify"] is True
        assert a["attempt"] == i
    assert a["typed_nudge"] is True  # 4th attempt nudges to typed input


def test_dont_know_reasks_with_hint(client):
    sid = _new_session(client)
    a = _answer(client, sid, "I don't know")
    assert a["needs_clarify"] is True
    assert a["clarify_reason"] == "unknown_ask_hint"
    # Confirming a needs-clarify answer is rejected.
    r = client.post(f"/api/sessions/{sid}/confirm", json={"accepted": True})
    assert r.status_code == 409


FULL_RUN = [
    ("full_name", "Vaibhav Pandey"),
    ("date_of_birth", "12th March 2004"),
    ("gender", "male"),
    ("phone", "98 76 54 32 10"),
    ("email", "vaibhav@example.com"),
    ("university", "Polaris School of Technology"),
    ("course_of_study", "B.Tech Computer Science"),
    ("year_of_study", "2nd year"),
    ("cgpa", "8.5"),
    ("family_income", "2 से 5 लाख"),  # Hindi label -> i2 (locale-bridging)
    ("need_statement", "I need support for my tuition fees."),
]


def _walk_to_consent(client, sid):
    for key, text in FULL_RUN:
        a = _answer(client, sid, text)
        assert not a["needs_clarify"], (key, a)
        c = _confirm(client, sid, True)
    assert c["current_field"]["key"] == "consent"


def test_full_run_to_review_then_consent_yes(client):
    sid = _new_session(client)
    _walk_to_consent(client, sid)
    a = _answer(client, sid, "yes, I agree")
    assert a["value"] is True
    c = _confirm(client, sid, True)
    assert c["status"] == "review" and c["blocked"] is False
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["status"] == "review" and state["blocked"] is False
    assert all(x["confirmed"] for x in state["answers"])


def test_consent_no_blocks_export_with_restart_offer(client):
    sid = _new_session(client)
    _walk_to_consent(client, sid)
    a = _answer(client, sid, "no")
    assert a["value"] is False
    c = _confirm(client, sid, True)
    assert c["status"] == "review" and c["blocked"] is True
    assert "restart" in c["message"].lower()
    # Restart wipes answers and returns to field 1.
    r = client.post(f"/api/sessions/{sid}/restart")
    assert r.status_code == 200
    assert r.json()["current_field"]["key"] == "full_name"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["status"] == "active" and not any(x["confirmed"] for x in state["answers"])


def test_hindi_session_asks_in_hindi(client):
    sid = _new_session(client, language="hi")
    state = client.get(f"/api/sessions/{sid}").json()
    assert "पूरा नाम" in state["current_field"]["prompt_text"]
    a = _answer(client, sid, "मेरा नाम राहुल शर्मा है")
    assert a["value"] == "राहुल शर्मा है" or "राहुल" in a["value"], a


@pytest.mark.skipif(os.getenv("LLM_LIVE_TEST") != "1", reason="no live LLM key in this environment")
def test_live_adapter_smoke():
    """One real call through OpenAICompatAdapter. Set LLM_LIVE_TEST=1 + key to run."""
    from app.services.llm import OpenAICompatAdapter

    r = OpenAICompatAdapter().normalize(
        {"key": "full_name", "type": "text"}, "My name is Ada Lovelace", "en"
    )
    assert not r.needs_clarify and "ada" in r.readable.lower()
