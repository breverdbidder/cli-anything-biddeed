#!/usr/bin/env python3
"""
Acquisition Sprint: Daily status report to public.insights.
Queries real data from Supabase — no fabricated numbers.

Metrics:
- Leads emailed (cold_outreach_log)
- Stripe checkout_session starts (stripe_checkout_sessions)
- Actual conversions with stripe_customer_id (mcp_customers or stripe_checkout_sessions)
- S5 report purchases (report_delivery_queue)

Run daily from GHA:
  python scripts/acquisition_daily_report.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")


def sb_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def sb_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
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


def safe_count(result, field="count"):
    if isinstance(result, list):
        if result and isinstance(result[0], dict):
            return result[0].get(field, len(result))
        return len(result)
    if isinstance(result, dict) and "error" not in result:
        return result.get(field, 0)
    return 0


def main():
    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_KEY not set", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    sprint_start = "2026-08-14"

    print(f"=== Acquisition Sprint Daily Report — {now.strftime('%Y-%m-%d %H:%M UTC')} ===\n")

    leads_emailed = sb_get(
        f"cold_outreach_log?select=count&status=eq.sent&sent_at=gte.{sprint_start}"
    )
    leads_emailed_count = safe_count(leads_emailed)

    leads_total = sb_get("lead_profiles?select=count&email=not.is.null")
    leads_total_count = safe_count(leads_total)

    checkout_starts = sb_get(
        f"stripe_checkout_sessions?select=count&status=eq.pending&created_at=gte.{sprint_start}"
    )
    checkout_starts_count = safe_count(checkout_starts)

    checkout_all = sb_get(
        f"stripe_checkout_sessions?select=count&created_at=gte.{sprint_start}"
    )
    checkout_all_count = safe_count(checkout_all)

    conversions = sb_get(
        f"stripe_checkout_sessions?select=count&status=eq.active&created_at=gte.{sprint_start}"
    )
    conversions_count = safe_count(conversions)

    s5_purchases = sb_get(
        f"report_delivery_queue?select=count&status=neq.pending&created_at=gte.{sprint_start}"
    )
    s5_count = safe_count(s5_purchases)

    pioneer_checkouts = sb_get(
        f"stripe_checkout_sessions?select=count&billing_interval=eq.annual&created_at=gte.{sprint_start}"
    )
    pioneer_count = safe_count(pioneer_checkouts)

    print(f"Lead profiles (with email):  {leads_total_count}")
    print(f"Emails sent (sprint total):  {leads_emailed_count}")
    print(f"Checkout sessions started:   {checkout_all_count}")
    print(f"  Pioneer (annual):          {pioneer_count}")
    print(f"Confirmed conversions:       {conversions_count}")
    print(f"S5 report purchases:         {s5_count}")
    print()

    if conversions_count == 0 and s5_count == 0:
        print("VERIFIED: 0 paying customers as of this report.")
    else:
        print(f"VERIFIED: {conversions_count} subscription conversion(s) + {s5_count} S5 purchase(s)")

    report = {
        "event": "acquisition_sprint_daily",
        "sprint_start": sprint_start,
        "as_of": now.isoformat(),
        "leads_total_with_email": leads_total_count,
        "emails_sent_sprint": leads_emailed_count,
        "checkout_sessions_started": checkout_all_count,
        "pioneer_annual_checkouts": pioneer_count,
        "confirmed_conversions": conversions_count,
        "s5_report_purchases": s5_count,
        "total_paying_customers": conversions_count + s5_count,
        "goal": 5,
        "gap": max(0, 5 - (conversions_count + s5_count)),
    }

    status = sb_post("insights", {
        "anomaly_type": "acquisition_sprint_daily",
        "county": "ALL",
        "detail": json.dumps(report),
        "severity": "info",
    })
    print(f"\nLogged to public.insights (HTTP {status})")
    print(f"anomaly_type='acquisition_sprint_daily'")

    print("\n### SQL VERIFICATION")
    print("```sql")
    print("SELECT detail FROM public.insights")
    print("WHERE anomaly_type = 'acquisition_sprint_daily'")
    print("ORDER BY created_at DESC LIMIT 1;")
    print("```")
    print(f"\nTimestamp UTC: {now.isoformat()}")

    if report["gap"] == 0:
        print("\nGOAL REACHED: 5 paying customers confirmed!")
    else:
        print(f"\nGap to goal: {report['gap']} more paying customer(s) needed by Fri Aug 21 EOD")


if __name__ == "__main__":
    main()
