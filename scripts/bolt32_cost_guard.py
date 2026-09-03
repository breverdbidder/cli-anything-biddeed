#!/usr/bin/env python3
"""GHA cost guard for the bolt32 caption pipeline (issue #19787). Wraps a
pipeline stage, records wall-clock seconds keyed by stage name, gates on
quota_gate_check('engineering'), and writes one row to agent_ops_log with the
per-stage timing as evidence. If the whisperX/faster-whisper caption stage
exceeds the 6-minute (360s) per-reel budget, recommends dropping to
faster-whisper small/int8 (logged, not auto-applied -- this is a
recommendation, the actual model-size choice stays a config value in
bolt32_recaption.py's transcribe_words_faster_whisper() call).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

WHISPERX_BUDGET_SEC = 360  # 6 minutes, per issue #19787


class StageTimer:
    def __init__(self):
        self.stages: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str):
        t0 = time.monotonic()
        yield
        self.stages[name] = round(time.monotonic() - t0, 2)

    def total(self) -> float:
        return round(sum(self.stages.values()), 2)


def quota_gate_check(category: str = "engineering") -> dict:
    supabase_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not key:
        return {"allow": False, "reason": "NO_READING", "note": "SUPABASE_URL/SERVICE_ROLE_KEY not set"}
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", f"{supabase_url}/rest/v1/rpc/quota_gate_check",
         "-H", f"apikey: {key}", "-H", f"Authorization: Bearer {key}",
         "-H", "Content-Type: application/json", "-d", json.dumps({"p_category": category})],
        capture_output=True, text=True,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"allow": False, "reason": "UNREACHABLE", "note": r.stdout[:200]}


def log_ops(task: str, status: str, evidence: dict, severity: str = "info") -> None:
    import mgmt_sql
    ev = json.dumps(evidence).replace("'", "''")
    mgmt_sql.run(
        f"insert into public.agent_ops_log (dispatch_id, task, status, evidence, severity) "
        f"values ('bolt32_cost_guard', '{task}', '{status}', '{ev}', '{severity}')"
    )


def evaluate(stage_seconds: dict) -> dict:
    whisperx_sec = stage_seconds.get("transcribe", 0)
    over_budget = whisperx_sec > WHISPERX_BUDGET_SEC
    return {
        "stage_seconds": stage_seconds,
        "total_seconds": round(sum(stage_seconds.values()), 2),
        "whisperx_budget_sec": WHISPERX_BUDGET_SEC,
        "over_budget": over_budget,
        "recommendation": (
            "drop to faster-whisper small/int8 (or the openai-whisper 'base' equivalent) -- "
            "current stage exceeds the 6-minute-per-reel budget"
            if over_budget else "within budget, no action needed"
        ),
    }


def _selftest() -> int:
    # over-budget case
    r = evaluate({"download": 1.0, "extract_audio": 0.1, "transcribe": 400.0, "burn_captions": 5.0})
    assert r["over_budget"] is True and "small/int8" in r["recommendation"]
    print("test_over_budget_recommends_small_int8: PASS")
    # within-budget case
    r = evaluate({"download": 1.0, "extract_audio": 0.13, "transcribe": 6.98, "burn_captions": 3.0})
    assert r["over_budget"] is False
    print("test_within_budget_no_recommendation: PASS")
    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
