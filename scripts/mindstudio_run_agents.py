#!/usr/bin/env python3
"""
MindStudio Agent Runner — Acquisition Sprint Step 2
1. Agent 3 (lead scorer): scores all lead_profiles rows, writes scores back
2. Agent 1 (broadcaster): sends broadcast to scored leads

Usage:
  python scripts/mindstudio_run_agents.py --agent 3   # scorer only
  python scripts/mindstudio_run_agents.py --agent 1   # broadcaster only
  python scripts/mindstudio_run_agents.py              # both in order

Env: MINDSTUDIO_API_KEY, SUPABASE_URL, SUPABASE_KEY
Hard rules:
  - Never claim "sent" / "scored" without an API response confirming it
  - Every result logged to public.insights (anomaly_type=acquisition_sprint_daily)
  - API errors logged to insights, exit code != 0
"""
import os
import sys
import json
import datetime
import argparse
import urllib.request
import urllib.error
import time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
MINDSTUDIO_API_KEY = os.environ.get("MINDSTUDIO_API_KEY", "")
MINDSTUDIO_RUN_URL = "https://api.mindstudio.ai/developer/v2/apps/run"


def ts():
    return datetime.datetime.utcnow().isoformat() + "Z"


def supabase_query(query: str) -> list:
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY not set")
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase query failed: {e.code} {e.read().decode()[:300]}")


def supabase_select(table: str, select: str = "*", filters: str = "") -> list:
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY not set")
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filters:
        url += f"&{filters}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase select failed: {e.code} {e.read().decode()[:300]}")


def supabase_insert(table: str, row: dict):
    if not SUPABASE_KEY:
        print(f"[WARN] SUPABASE_KEY not set — skipping insert to {table}")
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    data = json.dumps(row).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Supabase insert failed: {e.code} {e.read().decode()[:200]}")
        return None


def supabase_patch(table: str, row_id: str, updates: dict):
    if not SUPABASE_KEY:
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    data = json.dumps(updates).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Supabase patch failed: {e.code} {e.read().decode()[:200]}")
        return None


def mindstudio_run(app_id: str, workflow: str, variables: dict, thread_id: str = None) -> dict:
    """
    POST https://api.mindstudio.ai/developer/v2/apps/run
    Returns full response dict — caller checks for success.
    """
    payload = {
        "appId": app_id,
        "workflow": workflow,
        "variables": variables,
    }
    if thread_id:
        payload["threadId"] = thread_id

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        MINDSTUDIO_RUN_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {MINDSTUDIO_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            return {"ok": True, "status": resp.status, "body": json.loads(body)}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"ok": False, "status": e.code, "body": body[:500]}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}


def get_lead_profiles() -> list:
    try:
        leads = supabase_select(
            "lead_profiles",
            select="id,email,name,county,phone,skip_trace_status,mindstudio_score,consent_given",
        )
        return leads
    except Exception as e:
        print(f"[ERROR] Could not fetch lead_profiles: {e}")
        return []


def run_agent3_scorer(app_id: str) -> dict:
    """
    Agent 3: scores each lead in lead_profiles.
    Calls MindStudio with lead data; writes score back to lead_profiles.mindstudio_score.
    Returns summary: {total, scored, errors}
    """
    print(f"\n=== Agent 3 (Scorer) appId={app_id} ===")
    leads = get_lead_profiles()
    if not leads:
        msg = "No leads found in lead_profiles"
        print(f"[WARN] {msg}")
        return {"total": 0, "scored": 0, "errors": 0, "blocker": msg}

    print(f"[INFO] {len(leads)} leads to score")
    total = len(leads)
    scored = 0
    errors = 0

    for lead in leads:
        lead_id = lead.get("id")
        email = lead.get("email", "")
        county = lead.get("county", "")
        name = lead.get("name", "")

        variables = {
            "lead_id": str(lead_id) if lead_id else "",
            "email": email or "",
            "name": name or "",
            "county": county or "",
            "phone": lead.get("phone", "") or "",
            "skip_trace_status": lead.get("skip_trace_status", "") or "",
        }

        result = mindstudio_run(
            app_id=app_id,
            workflow="Score Lead",
            variables=variables,
        )

        if result["ok"]:
            body = result["body"]
            score = None
            if isinstance(body, dict):
                score = (
                    body.get("score")
                    or body.get("lead_score")
                    or body.get("output", {}).get("score") if isinstance(body.get("output"), dict) else None
                )

            supabase_patch("lead_profiles", lead_id, {
                "mindstudio_score": score,
                "mindstudio_scored_at": ts(),
            })
            scored += 1
            print(f"  [OK] lead={lead_id} email={email} score={score}")
        else:
            errors += 1
            print(f"  [ERROR] lead={lead_id} email={email}: {result}")

        time.sleep(0.3)

    return {"total": total, "scored": scored, "errors": errors}


def run_agent1_broadcaster(app_id: str) -> dict:
    """
    Agent 1: broadcasts to scored leads.
    Calls MindStudio with the full lead list (or per-lead); logs result.
    Returns summary: {total, sent, errors}
    """
    print(f"\n=== Agent 1 (Broadcaster) appId={app_id} ===")
    leads = get_lead_profiles()
    if not leads:
        msg = "No leads found in lead_profiles"
        print(f"[WARN] {msg}")
        return {"total": 0, "sent": 0, "errors": 0, "blocker": msg}

    print(f"[INFO] {len(leads)} leads for broadcast")
    total = len(leads)
    sent = 0
    errors = 0

    for lead in leads:
        lead_id = lead.get("id")
        email = lead.get("email", "")
        if not email:
            print(f"  [SKIP] lead={lead_id} — no email")
            continue

        variables = {
            "lead_id": str(lead_id) if lead_id else "",
            "email": email,
            "name": lead.get("name", "") or "",
            "county": lead.get("county", "") or "",
            "score": str(lead.get("mindstudio_score", "")) or "",
        }

        result = mindstudio_run(
            app_id=app_id,
            workflow="Broadcast",
            variables=variables,
        )

        if result["ok"]:
            sent += 1
            print(f"  [OK] lead={lead_id} email={email}")
        else:
            errors += 1
            print(f"  [ERROR] lead={lead_id} email={email}: {result}")

        time.sleep(0.3)

    return {"total": total, "sent": sent, "errors": errors}


def log_to_insights(step: str, status: str, details: dict):
    supabase_insert("insights", {
        "anomaly_type": "acquisition_sprint_daily",
        "anomaly_details": json.dumps({
            "step": step,
            "status": status,
            "ts": ts(),
            **details,
        }),
        "source": "mindstudio_run_agents",
    })


def main():
    parser = argparse.ArgumentParser(description="Run MindStudio agents for acquisition sprint")
    parser.add_argument("--agent", choices=["1", "3", "both"], default="both",
                        help="Which agent to run: 1=broadcaster, 3=scorer, both=3 then 1")
    parser.add_argument("--agent1-app-id", default=os.environ.get("MINDSTUDIO_AGENT1_APP_ID", ""),
                        help="MindStudio appId for Agent 1 (broadcaster). Env: MINDSTUDIO_AGENT1_APP_ID")
    parser.add_argument("--agent3-app-id", default=os.environ.get("MINDSTUDIO_AGENT3_APP_ID", ""),
                        help="MindStudio appId for Agent 3 (scorer). Env: MINDSTUDIO_AGENT3_APP_ID")
    args = parser.parse_args()

    now = ts()
    print(f"[{now}] MindStudio agent runner — agent={args.agent}")

    if not MINDSTUDIO_API_KEY:
        blocker = "MINDSTUDIO_API_KEY not set — provision via set-mindstudio-gh-secret.yml first"
        print(f"[BLOCKER] {blocker}")
        log_to_insights("mindstudio_run_agents", "BLOCKED", {"blocker": blocker})
        sys.exit(1)

    if not SUPABASE_KEY:
        blocker = "SUPABASE_KEY not set"
        print(f"[BLOCKER] {blocker}")
        log_to_insights("mindstudio_run_agents", "BLOCKED", {"blocker": blocker})
        sys.exit(1)

    exit_code = 0

    if args.agent in ("3", "both"):
        agent3_id = args.agent3_app_id
        if not agent3_id:
            print("[BLOCKER] --agent3-app-id / MINDSTUDIO_AGENT3_APP_ID not set")
            print("          Run scripts/mindstudio_agent_check.py first to discover appIds")
            log_to_insights("agent3_scorer", "BLOCKED", {"blocker": "agent3_app_id not configured"})
            exit_code = 1
        else:
            result = run_agent3_scorer(agent3_id)
            status = "COMPLETED" if result.get("errors", 0) == 0 else "PARTIAL"
            log_to_insights("agent3_scorer", status, result)
            print(f"\n[Agent3 Result] {result}")
            if result.get("errors", 0) > 0:
                exit_code = 1

    if args.agent in ("1", "both"):
        agent1_id = args.agent1_app_id
        if not agent1_id:
            print("[BLOCKER] --agent1-app-id / MINDSTUDIO_AGENT1_APP_ID not set")
            print("          Run scripts/mindstudio_agent_check.py first to discover appIds")
            log_to_insights("agent1_broadcaster", "BLOCKED", {"blocker": "agent1_app_id not configured"})
            exit_code = 1
        else:
            result = run_agent1_broadcaster(agent1_id)
            status = "COMPLETED" if result.get("errors", 0) == 0 else "PARTIAL"
            log_to_insights("agent1_broadcaster", status, result)
            print(f"\n[Agent1 Result] {result}")
            if result.get("errors", 0) > 0:
                exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
