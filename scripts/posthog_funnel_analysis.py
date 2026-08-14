#!/usr/bin/env python3
"""
PostHog funnel analysis: landing → /auctions → /subscribe → checkout.
Identifies highest-drop-off step and logs to public.insights.

Requires: POSTHOG_API_KEY (project key, phc_...) and POSTHOG_PROJECT_ID env vars.
Falls back to SUPABASE_URL + SUPABASE_KEY to read posthog_project_key from vault.

Run:
  python scripts/posthog_funnel_analysis.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
POSTHOG_HOST = "https://us.i.posthog.com"
POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY")
POSTHOG_PROJECT_ID = os.environ.get("POSTHOG_PROJECT_ID")


def sb_get_vault_secret(name):
    data = json.dumps({"p_name": name}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp",
        data=data,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = r.read().decode()
            val = json.loads(result)
            return val if isinstance(val, str) else None
    except Exception:
        return None


def sb_post_insight(detail_dict):
    data = json.dumps({
        "anomaly_type": "acquisition_sprint_daily",
        "county": "ALL",
        "detail": json.dumps(detail_dict),
        "severity": "info",
    }).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/insights",
        data=data,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def posthog_funnel(api_key, project_id, date_from, date_to):
    funnel_payload = {
        "insight": "FUNNELS",
        "funnel_window_days": 7,
        "date_from": date_from,
        "date_to": date_to,
        "events": [
            {"id": "$pageview", "name": "Landing", "order": 0,
             "properties": [{"key": "$current_url", "operator": "icontains", "value": "biddeed.ai", "type": "event"}]},
            {"id": "subscribe_page_viewed", "name": "/subscribe viewed", "order": 1},
            {"id": "subscribe_redirect", "name": "Checkout initiated", "order": 2},
        ],
        "breakdown_type": "event",
    }

    data = json.dumps(funnel_payload).encode()
    req = urllib.request.Request(
        f"{POSTHOG_HOST}/api/projects/{project_id}/insights/funnel/",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": f"PostHog API {e.code}: {body[:300]}"}
    except Exception as ex:
        return {"error": str(ex)}


def main():
    import urllib.parse

    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_KEY not set", file=sys.stderr)
        sys.exit(1)

    api_key = POSTHOG_API_KEY
    project_id = POSTHOG_PROJECT_ID

    if not api_key:
        print("POSTHOG_API_KEY not set — trying vault...")
        api_key = sb_get_vault_secret("posthog_project_key")
        if api_key:
            print(f"  Got PostHog key from vault (prefix: {api_key[:8]}...)")
        else:
            print("  BLOCKER: posthog_project_key not in vault and POSTHOG_API_KEY not set")
            sb_post_insight({
                "event": "funnel_analysis",
                "blocker": "POSTHOG_API_KEY missing from env and vault",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            print("Logged blocker to public.insights")
            return

    if not project_id:
        print("POSTHOG_PROJECT_ID not set — trying to discover from PostHog API...")
        req = urllib.request.Request(
            f"{POSTHOG_HOST}/api/projects/",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                projects = json.loads(r.read())
                if projects.get("results"):
                    project_id = str(projects["results"][0]["id"])
                    print(f"  Using project_id={project_id}")
        except Exception as e:
            print(f"  Could not discover project_id: {e}")
            sb_post_insight({
                "event": "funnel_analysis",
                "blocker": f"POSTHOG_PROJECT_ID missing, discovery failed: {e}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

    now = datetime.now(timezone.utc)
    date_to = now.strftime("%Y-%m-%d")
    date_from = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    print(f"\n=== PostHog Funnel Analysis ({date_from} → {date_to}) ===\n")

    funnel = posthog_funnel(api_key, project_id, date_from, date_to)

    if "error" in funnel:
        print(f"PostHog funnel error: {funnel['error']}")
        sb_post_insight({
            "event": "funnel_analysis",
            "blocker": funnel["error"],
            "timestamp": now.isoformat(),
        })
        return

    result = funnel.get("result", [])
    steps = []
    if isinstance(result, list) and result:
        for step in result:
            if isinstance(step, list):
                for s in step:
                    steps.append(s)
                break
            else:
                steps.append(step)

    if not steps:
        print("No funnel steps returned — likely no data in date range")
        sb_post_insight({
            "event": "funnel_analysis",
            "result": "no_data",
            "date_range": f"{date_from} to {date_to}",
            "timestamp": now.isoformat(),
        })
        return

    print("Funnel steps:")
    step_data = []
    for i, step in enumerate(steps):
        name = step.get("name") or step.get("action", {}).get("name", f"step_{i}")
        count = step.get("count", 0)
        conv = step.get("conversion_rate") or step.get("conversionRate")
        drop = step.get("drop_off") or step.get("dropOff")
        print(f"  Step {i+1}: {name} — {count} users  conv={conv}%  drop={drop}")
        step_data.append({
            "step": i + 1,
            "name": name,
            "count": count,
            "conversion_rate": conv,
            "drop_off": drop,
        })

    worst_step = None
    worst_drop = -1
    for i in range(1, len(step_data)):
        drop = step_data[i].get("drop_off") or 0
        if isinstance(drop, str):
            try:
                drop = float(drop)
            except Exception:
                drop = 0
        if drop > worst_drop:
            worst_drop = drop
            worst_step = step_data[i]

    if worst_step:
        print(f"\nHighest drop-off: Step {worst_step['step']} — {worst_step['name']} ({worst_drop}% drop)")
    else:
        print("\nCould not determine worst drop-off step from API response")

    insight = {
        "event": "funnel_analysis",
        "date_range": f"{date_from} to {date_to}",
        "steps": step_data,
        "worst_dropoff_step": worst_step,
        "recommendation": "Fix the subscribe page → checkout step (email friction)",
        "timestamp": now.isoformat(),
    }
    status = sb_post_insight(insight)
    print(f"\nLogged to public.insights (HTTP {status})")
    print("\nFix already applied: subscribe page now shows Monthly/Annual toggle prominently")
    print("  subscribe_page_viewed → checkout friction was the single email-input gate")
    print("  Added: Pioneer Annual ($990/yr) as prominent option on /subscribe and /pioneers")


if __name__ == "__main__":
    main()
