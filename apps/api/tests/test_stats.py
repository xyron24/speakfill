"""Traction counters for the pitch deck and Reach evidence."""


def test_stats_counts_sessions_and_feedback_by_country(client):
    empty = client.get("/api/stats").json()
    assert empty["sessions_total"] == 0 and empty["avg_rating"] is None

    s1 = client.post(
        "/api/sessions", json={"template_id": "scholarship-v1", "language": "en"}
    ).json()["session_id"]
    s2 = client.post(
        "/api/sessions", json={"template_id": "scholarship-v1", "language": "hi"}
    ).json()["session_id"]
    client.post(
        "/api/feedback",
        json={"session_id": s1, "country": "India", "rating": 5, "comment": "great"},
    )
    client.post(
        "/api/feedback",
        json={"session_id": s2, "country": "Spain", "rating": 4},
    )

    stats = client.get("/api/stats").json()
    assert stats["sessions_total"] == 2
    assert stats["sessions_done"] == 0
    assert stats["sessions_by_language"] == {"en": 1, "hi": 1}
    assert stats["feedback_count"] == 2
    assert stats["feedback_by_country"] == {"India": 1, "Spain": 1}
    assert stats["avg_rating"] == 4.5
