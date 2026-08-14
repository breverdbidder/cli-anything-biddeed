#!/usr/bin/env python3
"""
MindStudio Agent Status Check
Checks publish status of Agent 1 (broadcaster) and Agent 3 (scorer).

Usage: python scripts/mindstudio_agent_check.py
Env: MINDSTUDIO_API_KEY, SUPABASE_URL, SUPABASE_KEY
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
MINDSTUDIO_API_KEY = os.environ.get("MINDSTUDIO_API_KEY", "")

MINDSTUDIO_APPS_URL = "https://api.mindstudio.ai/developer/v2/apps"


def supabase_insert(table: str, row: dict):
    if not SUPABASE_KEY:
        print(f"[WARN] SUPABASE_KEY not set - skipping insert to {table}")
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
        print(f"[ERROR] Supabase insert failed: {e.code} {e.read()}")
        return None


def get_mindstudio_apps():
    if not MINDSTUDIO_API_KEY:
        print("[BLOCKER] MINDSTUDIO_API_KEY not set - cannot check agent status")
        return None, "MINDSTUDIO_API_KEY_MISSING"

    req = urllib.request.Request(
        MINDSTUDIO_APPS_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {MINDSTUDIO_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return None, f"HTTP_{e.code}: {body[:300]}"
    except Exception as e:
        return None, str(e)


def main():
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    print(f"[{ts}] MindStudio agent status check")

    if not MINDSTUDIO_API_KEY:
        blocker = "MINDSTUDIO_API_KEY not set - GHA secret not yet provisioned"
        print(f"[BLOCKER] {blocker}")
        supabase_insert("insights", {
            "anomaly_type": "acquisition_sprint_daily",
            "description": json.dumps({
                "step": "mindstudio_agent_check",
                "status": "BLOCKED",
                "blocker": blocker,
                "ts": ts,
            }),
        })
        sys.exit(1)

    apps_data, err = get_mindstudio_apps()

    if err:
        print(f"[ERROR] Could not fetch MindStudio apps: {err}")
        supabase_insert("insights", {
            "anomaly_type": "acquisition_sprint_daily",
            "description": json.dumps({
                "step": "mindstudio_agent_check",
                "status": "ERROR",
                "error": err,
                "ts": ts,
            }),
        })
        sys.exit(1)

    print(f"[INFO] Raw API response: {json.dumps(apps_data, indent=2)[:2000]}")

    apps = apps_data if isinstance(apps_data, list) else apps_data.get("apps", apps_data.get("data", []))

    agent_targets = {
        "agent_1_broadcaster": None,
        "agent_3_scorer": None,
    }

    findings = []
    for app in apps:
        name = app.get("name", "").lower()
        app_id = app.get("id") or app.get("appId") or app.get("app_id")
        status = app.get("status", app.get("publishStatus", "UNKNOWN"))

        findings.append({
            "name": app.get("name"),
            "app_id": app_id,
            "status": status,
        })

        if "broadcaster" in name or "agent 1" in name or "agent1" in name:
            agent_targets["agent_1_broadcaster"] = {"name": app.get("name"), "app_id": app_id, "status": status}
        elif "scorer" in name or "agent 3" in name or "agent3" in name or "lead scor" in name:
            agent_targets["agent_3_scorer"] = {"name": app.get("name"), "app_id": app_id, "status": status}

    print("\n=== Agent Status ===")
    for agent_key, info in agent_targets.items():
        if info:
            print(f"  {agent_key}: appId={info['app_id']} status={info['status']}")
        else:
            print(f"  {agent_key}: NOT FOUND in app list")

    print("\n=== All Apps ===")
    for f in findings:
        print(f"  {f['name']} | appId={f['app_id']} | status={f['status']}")

    supabase_insert("insights", {
        "anomaly_type": "acquisition_sprint_daily",
        "description": json.dumps({
            "step": "mindstudio_agent_check",
            "status": "COMPLETED",
            "all_apps": findings,
            "agent_1_broadcaster": agent_targets["agent_1_broadcaster"],
            "agent_3_scorer": agent_targets["agent_3_scorer"],
            "ts": ts,
        }),
    })

    any_blocked = False
    for agent_key, info in agent_targets.items():
        if not info:
            print(f"[WARN] {agent_key}: not found - check app name matching logic above")
        elif info["status"] not in ("PUBLISHED", "published", "Published", "active", "ACTIVE"):
            print(f"[WARN] {agent_key}: status={info['status']} - Draft agents cannot be triggered via API. Ariel must publish via dashboard.")
            any_blocked = True

    if any_blocked:
        sys.exit(2)

    print("\n[OK] Both agents appear published - ready to run")


if __name__ == "__main__":
    main()
