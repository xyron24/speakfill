#!/usr/bin/env python3
"""Post-deploy smoke test. Runs anywhere with stdlib-only Python 3.

Usage:  python3 scripts/smoke.py https://<domain>
Checks: healthz -> create session -> answer + confirm one field ->
review 12/12 shape -> export blocked (incomplete) behaves -> feedback validates.
Exits non-zero on any failure.
"""

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8080"


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name, detail)
    if not cond:
        sys.exit(1)


st, hz = call("GET", "/api/healthz")
check("healthz", st == 200 and hz.get("ok") is True, f"HTTP {st}")

st, s = call("POST", "/api/sessions", {"template_id": "scholarship-v1", "language": "en"})
check("create session", st == 201, f"HTTP {st}")
sid = s["session_id"]

st, a = call("POST", f"/api/sessions/{sid}/answer", {"text": "Smoke Test"})
check("answer", st == 200 and not a["needs_clarify"], f"HTTP {st}")

st, c = call("POST", f"/api/sessions/{sid}/confirm", {"accepted": True})
check("confirm advances", st == 200 and c["current_field"]["ord"] == 2, f"HTTP {st}")

st, review = call("GET", f"/api/sessions/{sid}/review")
check("review shape", st == 200 and len(review["fields"]) == 12, f"HTTP {st}")

st, _ = call("POST", f"/api/sessions/{sid}/export", {})
check("export blocked while active", st == 409, f"HTTP {st} (want 409)")

st, fb = call("POST", "/api/feedback", {"session_id": sid, "country": "Smoke", "rating": 5})
check("feedback", st == 201, f"HTTP {st}")

print("SMOKE OK:", BASE)
