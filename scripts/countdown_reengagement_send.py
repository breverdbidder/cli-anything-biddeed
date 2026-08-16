#!/usr/bin/env python3
"""
Countdown-based re-engagement: T-14/T-7/T-3 auction reminder emails for
lead_auction_countdown rows, sent via Resend. CAN-SPAM compliant (same
footer/unsubscribe pattern as acquisition_cold_email.py).

Consent gate (hard requirement, not a suggestion):
  - lead_profiles.email IS NOT NULL
  - lead_profiles.email_consent = true
No exceptions. A row with a due threshold but no consented email is skipped
and left unsent (sent flag stays false) — it never retries on its own,
since each threshold only matches on its exact calendar day.

Run:
  python scripts/countdown_reengagement_send.py [--dry-run] [--limit N] [--test-email you@x.com]
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

FROM_EMAIL = "Ariel Shapira <ariel@biddeed.ai>"
UNSUBSCRIBE_URL = "https://biddeed.ai/unsubscribe"
PHYSICAL_ADDRESS = "Everest Capital USA · 1901 S Harbor City Blvd Ste 551 · Melbourne, FL 32901"

TEMPLATES = {
    "t14": {
        "subject": "Heads up: another {county} County auction in 14 days",
        "days_label": "14 days",
        "tone": "Just a heads-up — a new {county} County auction is coming up on {auction_date}. "
                "Since you've won there before, wanted to make sure it's on your radar early.",
    },
    "t7": {
        "subject": "1 week out — {county} County auction on {auction_date}",
        "days_label": "7 days",
        "tone": "One week until the {county} County auction on {auction_date}. Worth pulling your "
                "target list now — properties move fast once bidding opens.",
    },
    "t3": {
        "subject": "Last call — {county} County auction in 3 days ({auction_date})",
        "days_label": "3 days",
        "tone": "Final reminder: the {county} County auction is in 3 days ({auction_date}). "
                "If you're bidding, this is your last window to run numbers.",
    },
}

EMAIL_TEXT = """\
Hi {name},

{tone}

Run the Shapira formula (ARV x 70% - Repairs - costs) and check for lien traps before you bid:
https://biddeed.ai/auctions?county={county_slug}

— Ariel Shapira
BidDeed.AI / Everest Capital USA

---
{physical_address}
To stop receiving emails from BidDeed.AI: {unsubscribe_url}?email={email_encoded}
This is a commercial email. BidDeed.AI is an information platform, not legal or \
financial advice.
"""

EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:0}}
.wrap{{max-width:560px;margin:0 auto;padding:32px 24px}}
h2{{color:white;font-size:1.2rem;margin:0 0 16px}}
p{{color:#cbd5e1;line-height:1.6;margin:0 0 12px;font-size:15px}}
.cta{{display:inline-block;background:#f59e0b;color:#020617;padding:12px 24px;border-radius:8px;font-weight:700;text-decoration:none;font-size:15px;margin:8px 0}}
.footer{{margin-top:32px;padding-top:16px;border-top:1px solid #1e293b;font-size:11px;color:#64748b;line-height:1.6}}
.footer a{{color:#64748b}}
</style>
</head>
<body>
<div class="wrap">
  <h2>{county} County auction — {days_label} away</h2>
  <p>Hi {name},</p>
  <p>{tone}</p>
  <p><a href="https://biddeed.ai/auctions?county={county_slug}" class="cta">View {county} County Auction →</a></p>
  <p>— Ariel Shapira<br>BidDeed.AI / Everest Capital USA</p>
  <div class="footer">
    {physical_address}<br>
    This is a commercial email from BidDeed.AI.<br>
    <a href="{unsubscribe_url}?email={email_encoded}">Unsubscribe</a> · <a href="https://biddeed.ai/privacy">Privacy Policy</a>
  </div>
</div>
</body></html>
"""


def sb_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def sb_patch(path, body):
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
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def sb_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=data,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def fetch_due_rows(limit):
    """Rows where a threshold's send date is exactly today and not yet sent.
    Exact-day match (not <=) is deliberate: a threshold whose date already
    passed before the row existed (e.g. a near-term auction backfilled after
    T-14 lapsed) must never fire retroactively — see migration comments."""
    rows = sb_get(
        f"lead_auction_countdown?select=*&auction_date=gte.{TODAY}"
        f"&limit={limit * 3}"
    )
    due = []
    for row in rows:
        for key in ("t14", "t7", "t3"):
            if row[f"{key}_sent"]:
                continue
            send_at = row[f"send_{key}_at"][:10]
            if send_at == TODAY:
                due.append((key, row))
    return due[:limit]


def send_email(to_email, template_key, county, county_slug, auction_date, dry_run=False):
    tmpl = TEMPLATES[template_key]
    email_encoded = urllib.parse.quote(to_email)
    county_display = county.replace("_", " ").title() if county else "Florida"

    subject = tmpl["subject"].format(county=county_display, auction_date=auction_date)
    tone = tmpl["tone"].format(county=county_display, auction_date=auction_date)
    name_part = "there"

    text_body = EMAIL_TEXT.format(
        name=name_part, tone=tone, county_slug=county_slug,
        physical_address=PHYSICAL_ADDRESS, unsubscribe_url=UNSUBSCRIBE_URL,
        email_encoded=email_encoded,
    )
    html_body = EMAIL_HTML.format(
        county=county_display, days_label=tmpl["days_label"], name=name_part, tone=tone,
        county_slug=county_slug, physical_address=PHYSICAL_ADDRESS,
        unsubscribe_url=UNSUBSCRIBE_URL, email_encoded=email_encoded,
    )

    if dry_run:
        print(f"  [DRY-RUN] Would send {template_key} to {to_email} — subject: {subject}")
        return "dry_run_msg_id"

    payload = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
        "headers": {
            "List-Unsubscribe": f"<{UNSUBSCRIBE_URL}?email={email_encoded}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "BidDeedAI-CountdownReengagement/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()).get("id")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] Resend HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return None


def main():
    global TODAY
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--test-email", default=None,
                         help="Route all sends this run to a single test address (deliverability check)")
    args = parser.parse_args()

    import datetime
    TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not RESEND_API_KEY and not args.dry_run:
        print("FATAL: RESEND_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"=== Countdown Re-engagement Send (dry_run={args.dry_run}, limit={args.limit}, date={TODAY}) ===\n")

    due = fetch_due_rows(args.limit)
    print(f"Rows with a threshold due today: {len(due)}")

    sent, skipped_no_consent, errors = 0, 0, 0

    for template_key, row in due:
        lead = sb_get(f"lead_profiles?select=id,email,email_consent&id=eq.{row['lead_id']}")
        if not lead:
            skipped_no_consent += 1
            continue
        lead = lead[0]

        target_email = args.test_email or lead.get("email")
        eligible = args.test_email or (lead.get("email") and lead.get("email_consent") is True)

        if not eligible:
            skipped_no_consent += 1
            continue

        county_slug = row["county"]
        print(f"  [{template_key}] lead={row['lead_id']} county={row['county']} auction={row['auction_date']} -> {target_email} ...", end=" ")
        msg_id = send_email(target_email, template_key, row["county"], county_slug, row["auction_date"], dry_run=args.dry_run)

        if msg_id:
            print(f"OK msg_id={msg_id}")
            if not args.dry_run:
                sb_patch(
                    f"lead_auction_countdown?id=eq.{row['id']}",
                    {f"{template_key}_sent": True, f"{template_key}_sent_at": "now()", "updated_at": "now()"},
                )
                sb_post("cold_outreach_log", {
                    "lead_id": row["lead_id"],
                    "email": target_email,
                    "resend_message_id": msg_id,
                    "status": "sent",
                    "subject": TEMPLATES[template_key]["subject"].format(
                        county=row["county"].replace("_", " ").title(), auction_date=row["auction_date"]),
                    "template": f"countdown_{template_key}_v1",
                    "county": row["county"],
                })
            sent += 1
        else:
            print("FAILED")
            errors += 1

        if not args.dry_run:
            time.sleep(0.3)

    print("\n=== RESULT ===")
    print(f"  Sent:                {sent}")
    print(f"  Skipped (no consent/email): {skipped_no_consent}")
    print(f"  Errors:              {errors}")


if __name__ == "__main__":
    main()
