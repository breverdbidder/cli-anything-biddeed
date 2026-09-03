"""Shared harness for agents/reel_studio/eval_*.py.

Writes real rows to public.skill_eval_runs/public.skill_eval_results via
scripts/skill_eval_report.py (the canonical current reporter -- see that
file's docstring; it superseded the older eval_runner.py/AUTOLOOP system
per .github/workflows/skill-eval.yml's own header comment). Each eval_*.py
module runs a set of genuinely-executed, code-level binary assertions
against the real agent module (not a simulated/expected transcript) and
reports pass/fail/error per assertion honestly -- an assertion this harness
did not actually execute is never reported as pass.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

REPORTER = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "skill_eval_report.py")


def create_run(skill_name: str, skills_total: int = 4) -> int:
    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"
    out = subprocess.run(
        [sys.executable, REPORTER, "create-run",
         "--git-sha", git_sha, "--skills-total", str(skills_total),
         "--quota-gate", json.dumps({"note": "reel_studio self-eval, not gated by quota_gate_check", "allow": True}),
         "--model", "reel_studio_eval (non-anthropic, code-level assertions)",
         "--notes", f"agents/reel_studio/eval_{skill_name.replace('-', '_')}.py self-run"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"create-run failed: {out.stderr}")
    return json.loads(out.stdout)["run_id"]


def add_result(run_id: int, skill_name: str, case_id: str, outcome: str, evidence: dict, duration_ms: int | None = None):
    assert outcome in ("pass", "fail", "error", "skipped")
    cmd = [sys.executable, REPORTER, "add-result",
           "--run-id", str(run_id), "--skill-name", skill_name, "--case-id", str(case_id),
           "--outcome", outcome, "--evidence", json.dumps(evidence, default=str)]
    if duration_ms is not None:
        cmd += ["--duration-ms", str(duration_ms)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print(f"WARN: add-result failed for {skill_name}/{case_id}: {out.stderr}", file=sys.stderr)


def finish_run(run_id: int, evaluated: int, passed: int, failed: int, errored: int, notes: str = ""):
    subprocess.run(
        [sys.executable, REPORTER, "finish-run", "--run-id", str(run_id),
         "--skills-evaluated", str(evaluated), "--passed", str(passed),
         "--failed", str(failed), "--errored", str(errored), "--notes", notes],
        capture_output=True, text=True,
    )


def run_assertions(skill_name: str, assertions: list[tuple[str, callable]]) -> dict:
    """assertions: list of (case_id, fn) where fn() returns (bool, evidence_dict)
    or raises. Runs each for real, reports honestly, returns a summary."""
    run_id = create_run(skill_name)
    passed = failed = errored = 0
    results = []
    for case_id, fn in assertions:
        t0 = time.time()
        try:
            ok, evidence = fn()
            outcome = "pass" if ok else "fail"
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:  # noqa: BLE001
            outcome = "error"
            evidence = {"exception": repr(e)}
            errored += 1
        duration_ms = int((time.time() - t0) * 1000)
        add_result(run_id, skill_name, case_id, outcome, evidence, duration_ms)
        results.append({"case_id": case_id, "outcome": outcome, "evidence": evidence})

    finish_run(run_id, len(assertions), passed, failed, errored,
               notes=f"{passed} pass / {failed} fail / {errored} error of {len(assertions)}")
    summary = {"run_id": run_id, "skill_name": skill_name, "total": len(assertions),
               "passed": passed, "failed": failed, "errored": errored, "results": results}
    print(json.dumps(summary, indent=2, default=str))
    return summary
