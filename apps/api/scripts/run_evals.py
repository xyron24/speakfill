#!/usr/bin/env python3
"""Normalization eval runner: 10 scripted cases through an LLM adapter.

Usage (inside the api container):
    python -m scripts.run_evals                 # stub adapter (deterministic)
    python -m scripts.run_evals --adapter live  # OpenAICompatAdapter (needs LLM_API_KEY)

Exit 0 only on 10/10. Attempt counting + consent blocking are covered by
tests/test_loop.py (service-level); this file checks normalize() outputs.
"""

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CASES_PATH = pathlib.Path(__file__).resolve().parent.parent / "tests" / "eval_cases.json"


def check(case: dict, result) -> list[str]:
    failures = []
    exp = case["expect"]
    if "value" in exp and result.value != exp["value"]:
        failures.append(f"value={result.value!r} want {exp['value']!r}")
    if "value_contains" in exp and exp["value_contains"] not in str(result.value or ""):
        failures.append(f"value={result.value!r} missing {exp['value_contains']!r}")
    if "needs_clarify" in exp and result.needs_clarify != exp["needs_clarify"]:
        failures.append(f"needs_clarify={result.needs_clarify} want {exp['needs_clarify']}")
    if "clarify_reason" in exp and result.clarify_reason != exp["clarify_reason"]:
        failures.append(f"reason={result.clarify_reason!r} want {exp['clarify_reason']!r}")
    if "min_confidence" in exp and result.confidence < exp["min_confidence"]:
        failures.append(f"confidence={result.confidence} < {exp['min_confidence']}")
    return failures


def main() -> int:
    from app.services.llm import OpenAICompatAdapter, StubAdapter

    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=["stub", "live"], default="stub")
    args = ap.parse_args()

    if args.adapter == "live":
        if not os.environ.get("LLM_API_KEY"):
            print("live evals need LLM_API_KEY in the environment", file=sys.stderr)
            return 2
        adapter = OpenAICompatAdapter()
    else:
        adapter = StubAdapter()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    failed = 0
    for case in cases:
        try:
            result = adapter.normalize(
                field_schema=case["field"],
                transcript=case["transcript"],
                locale=case["locale"],
                previous_value=case.get("previous_value"),
            )
        except Exception as e:  # noqa: BLE001 - eval must report, not crash
            print(f"case {case['id']}: ERROR {e}")
            failed += 1
            continue
        problems = check(case, result)
        if problems:
            print(f"case {case['id']}: FAIL {'; '.join(problems)}")
            failed += 1
        else:
            print(f"case {case['id']}: PASS (value={result.value!r} conf={result.confidence})")
    print(f"eval: {len(cases) - failed}/{len(cases)} passed [{args.adapter}]")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
