#!/usr/bin/env python3
"""
skill_eval_report.py — thin PostgREST reporter for the GHA-only skill-eval loop
(issue #19715). Writes into public.skill_eval_runs / public.skill_eval_results.
Creates no tables. Every write retries with backoff so a mid-run Supabase
restart (public.db_restart_log, 2026-09-02) does not lose a result.

Also hosts `detect-invocation`, a pure (no-network) parser that reads a
`claude -p --output-format stream-json` transcript and decides whether the
Skill tool fired for a given skill name. Kept in this file rather than a
second script per the issue's "one thin script" framing.

Subcommands:
  create-run          --git-sha --skills-total --quota-gate '<json>' [--notes] [--model]
                       -> prints {"run_id": N}
  add-result          --run-id --skill-name --case-id --outcome [pass|fail|error|skipped]
                       [--invoked true|false|null] [--expected] [--actual]
                       [--duration-ms] [--evidence '<json>']
  finish-run          --run-id [--skills-evaluated] [--passed] [--failed] [--errored] [--notes]
  detect-invocation   --transcript <path> --skill <name>
                       -> prints {"skill_invoked": true|false|null, ...}
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

MAX_ATTEMPTS = 5
BACKOFF_BASE_S = 2


def _headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _request(method, path, payload=None, extra_headers=None):
    """PostgREST call with retry/backoff. Retries on network errors and 5xx
    (the Supabase-restart case). Fails fast on 4xx (not retryable)."""
    url = f"{SUPABASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, data=data, method=method, headers=_headers(extra_headers))
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                return resp.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code < 500:
                print(f"::error::PostgREST {method} {path} failed non-retryable {e.code}: {body[:500]}", file=sys.stderr)
                sys.exit(1)
            last_err = f"HTTP {e.code}: {body[:300]}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = str(e)
        wait = min(BACKOFF_BASE_S * (2 ** (attempt - 1)), 30)
        print(f"PostgREST {method} {path} attempt {attempt}/{MAX_ATTEMPTS} failed ({last_err}); retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    print(f"::error::PostgREST {method} {path} failed after {MAX_ATTEMPTS} attempts: {last_err}", file=sys.stderr)
    sys.exit(1)


def cmd_create_run(args):
    payload = {
        "source": "skill-eval.yml",
        "git_sha": args.git_sha,
        "skills_total": args.skills_total,
        "quota_gate": json.loads(args.quota_gate),
    }
    if args.model:
        payload["model"] = args.model
    if args.notes:
        payload["notes"] = args.notes
    status, body = _request(
        "POST", "/rest/v1/skill_eval_runs", payload,
        extra_headers={"Prefer": "return=representation"},
    )
    row = body[0] if isinstance(body, list) else body
    print(json.dumps({"run_id": row["id"]}))


def cmd_add_result(args):
    invoked = None
    if args.invoked is not None:
        invoked = {"true": True, "false": False, "null": None}[args.invoked]
    payload = {
        "run_id": args.run_id,
        "skill_name": args.skill_name,
        "case_id": args.case_id,
        "outcome": args.outcome,
        "skill_invoked": invoked,
    }
    if args.expected is not None:
        payload["expected"] = args.expected
    if args.actual is not None:
        payload["actual"] = args.actual
    if args.duration_ms is not None:
        payload["duration_ms"] = args.duration_ms
    if args.evidence is not None:
        payload["evidence"] = json.loads(args.evidence)
    _request("POST", "/rest/v1/skill_eval_results", payload, extra_headers={"Prefer": "return=minimal"})
    print(f"result recorded: {args.skill_name}/{args.case_id} -> {args.outcome}")


def cmd_finish_run(args):
    payload = {"finished_at": "now()"}
    for k in ("skills_evaluated", "passed", "failed", "errored"):
        v = getattr(args, k)
        if v is not None:
            payload[k] = v
    if args.notes:
        payload["notes"] = args.notes
    # PostgREST doesn't accept the literal "now()" as JSON — use ISO timestamp instead.
    import datetime
    payload["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _request(
        "PATCH", f"/rest/v1/skill_eval_runs?id=eq.{args.run_id}", payload,
        extra_headers={"Prefer": "return=minimal"},
    )
    print(f"run {args.run_id} finalized")


def cmd_detect_invocation(args):
    """Parse a stream-json transcript for tool_use blocks calling the Skill
    tool. Returns skill_invoked=null (never a guessed True) whenever the
    transcript can't be parsed at all."""
    result = {
        "skill_invoked": None,
        "invoked_skill_names": [],
        "parse_ok": False,
        "lines_total": 0,
        "lines_parsed": 0,
        "is_error": None,
        "result_text": None,
    }
    target = args.skill.strip().lower()
    try:
        with open(args.transcript, "r", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        result["evidence_note"] = f"transcript unreadable: {e}"
        print(json.dumps(result))
        return

    result["lines_total"] = len(lines)
    invoked_names = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        result["lines_parsed"] += 1
        if obj.get("type") == "assistant":
            content = (obj.get("message") or {}).get("content") or []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                    skill_input = block.get("input") or {}
                    name = str(skill_input.get("skill") or skill_input.get("name") or "").strip()
                    if name:
                        invoked_names.append(name)
        if obj.get("type") == "result":
            result["is_error"] = bool(obj.get("is_error"))
            result["result_text"] = str(obj.get("result", ""))[:2000]

    result["invoked_skill_names"] = invoked_names
    if result["lines_parsed"] == 0:
        # Nothing parseable at all (e.g. auth failure printed as plain text) —
        # never guess. Honesty Protocol: skill_invoked stays null.
        result["evidence_note"] = "no parseable stream-json lines; cannot determine invocation"
        print(json.dumps(result))
        return

    result["parse_ok"] = True
    result["skill_invoked"] = any(n.lower() == target for n in invoked_names)
    print(json.dumps(result))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create-run")
    c.add_argument("--git-sha", required=True)
    c.add_argument("--skills-total", type=int, required=True)
    c.add_argument("--quota-gate", required=True)
    c.add_argument("--model")
    c.add_argument("--notes")
    c.set_defaults(func=cmd_create_run)

    c = sub.add_parser("add-result")
    c.add_argument("--run-id", type=int, required=True)
    c.add_argument("--skill-name", required=True)
    c.add_argument("--case-id", required=True)
    c.add_argument("--outcome", required=True, choices=["pass", "fail", "error", "skipped"])
    c.add_argument("--invoked", choices=["true", "false", "null"], default=None)
    c.add_argument("--expected")
    c.add_argument("--actual")
    c.add_argument("--duration-ms", type=int, default=None)
    c.add_argument("--evidence")
    c.set_defaults(func=cmd_add_result)

    c = sub.add_parser("finish-run")
    c.add_argument("--run-id", type=int, required=True)
    c.add_argument("--skills-evaluated", type=int, default=None)
    c.add_argument("--passed", type=int, default=None)
    c.add_argument("--failed", type=int, default=None)
    c.add_argument("--errored", type=int, default=None)
    c.add_argument("--notes")
    c.set_defaults(func=cmd_finish_run)

    c = sub.add_parser("detect-invocation")
    c.add_argument("--transcript", required=True)
    c.add_argument("--skill", required=True)
    c.set_defaults(func=cmd_detect_invocation)

    args = p.parse_args()
    if args.cmd in ("create-run", "add-result", "finish-run") and not (SUPABASE_URL and SUPABASE_KEY):
        print("::error::SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
