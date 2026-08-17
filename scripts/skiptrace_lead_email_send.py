#!/usr/bin/env python3
"""
Skip-traced INVESTOR_LLC lead email send (issue #19176 follow-through).

Personalized version of acquisition_cold_email.py: same CAN-SPAM footer
(physical address, List-Unsubscribe header + link), but subject/body
reference the lead's real matched auction history and inline the Variant A
lead-audit card (scripts/generate_lead_audit_card.py, #19174/#19175) instead
of the generic county pitch.

Scope is explicit and hardcoded to LEAD_IDS, not "all INVESTOR_LLC with
email" -- of the 14 skip-traced real emails, only leads with a genuine
matched auctions_won>0 row in multi_county_auctions (no fabricated stats)
and a sane dollar figure (no $1 nominal-bid placeholder rows) are eligible.
See session notes for the excluded 12 and why.

Run:
  python scripts/skiptrace_lead_email_send.py [--dry-run] [--limit N]
"""

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

# lead_id -> (name, county, county_display, auctions_won, total_deployed_display, upcoming, email, card_url)
LEADS = [
    {
        "lead_id": "d4182030-02a8-4ddb-9bb0-929d15557411",
        "name": "DELANE FINANCIAL LLC",
        "county_display": "Pasco",
        "county_slug": "pasco",
        "auctions_won": 2,
        "total_deployed": "N/A",
        "upcoming": 53,
        "email": "mbanker@odonnellsnider.com",
        "card_url": "https://mocerqjnksmhcjzxrewo.supabase.co/storage/v1/object/public/social-banners/lead-cards/2026-08-17/A_d4182030-02a8-4ddb-9bb0-929d15557411.png",
    },
    {
        "lead_id": "d9e707db-34b8-4471-bc39-2d064a5785fd",
        "name": "DANIEL VARGO LLC",
        "county_display": "Broward",
        "county_slug": "broward",
        "auctions_won": 1,
        "total_deployed": "$150,100",
        "upcoming": 0,
        "email": "tina.lawless@hotmail.com",
        "card_url": "https://mocerqjnksmhcjzxrewo.supabase.co/storage/v1/object/public/social-banners/lead-cards/2026-08-17/A_d9e707db-34b8-4471-bc39-2d064a5785fd.png",
    },
]

EMAIL_TEXT = """\
Hi there,

I noticed {name} won {auctions_won} auction(s) in {county} County, FL -- \
tracked total deployed: {total_deployed}. I'm Ariel Shapira, founder of \
BidDeed.AI (10+ year FL foreclosure investor, licensed broker).

{county} County has {upcoming} auction(s) coming up in the next 30 days. \
Grab your free {county} County report (live auction data, Shapira formula \
max-bid, lien-trap flags) -- no card required:
https://biddeed.ai/free-report?county={county_slug}

Reply with any questions -- I answer personally.

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
img.card{{width:100%;border-radius:8px;margin:12px 0}}
.cta{{display:inline-block;background:#f59e0b;color:#020617;padding:12px 24px;border-radius:8px;font-weight:700;text-decoration:none;font-size:15px;margin:8px 0}}
.footer{{margin-top:32px;padding-top:16px;border-top:1px solid #1e293b;font-size:11px;color:#64748b;line-height:1.6}}
.footer a{{color:#64748b}}
</style>
</head>
<body>
<div class="wrap">
  <h2>Your {county} County auction activity</h2>
  <p>Hi there,</p>
  <p>I noticed <strong>{name}</strong> won <strong>{auctions_won}</strong> auction(s) in {county} County, FL -- tracked total deployed: <strong>{total_deployed}</strong>. I'm Ariel Shapira, founder of BidDeed.AI (10+ year FL foreclosure investor, licensed broker).</p>
  <img class="card" src="{card_url}" alt="{name} auction activity card">
  <p>{county} County has <strong>{upcoming}</strong> auction(s) coming up in the next 30 days. Grab your free {county} County report -- live auction data, Shapira formula max-bid, lien-trap flags, no card required:</p>
  <p><a href="https://biddeed.ai/free-report?county={county_slug}" class="cta">Get Free {county} County Report →</a></p>
  <p>Reply with any questions -- I answer personally.</p>
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
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


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


def build_payload(lead):
    email_encoded = urllib.parse.quote(lead["email"])
    fmt = dict(
        name=lead["name"],
        county=lead["county_display"],
        county_slug=lead["county_slug"],
        auctions_won=lead["auctions_won"],
        total_deployed=lead["total_deployed"],
        upcoming=lead["upcoming"],
        card_url=lead["card_url"],
        physical_address=PHYSICAL_ADDRESS,
        unsubscribe_url=UNSUBSCRIBE_URL,
        email_encoded=email_encoded,
    )
    subject = f"Your {lead['county_display']} County auction activity"
    text_body = EMAIL_TEXT.format(**fmt)
    html_body = EMAIL_HTML.format(**fmt)
    return {
        "from": FROM_EMAIL,
        "to": [lead["email"]],
        "subject": subject,
        "text": text_body,
        "html": html_body,
        "headers": {
            "List-Unsubscribe": f"<{UNSUBSCRIBE_URL}?email={email_encoded}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }, subject


def send_email(payload, dry_run):
    if dry_run:
        return "dry_run_msg_id"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "BidDeedAI-SkipTraceSprint/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()).get("id")
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] Resend HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return None


def log_outreach(lead_id, email, message_id, status, subject, county, error=None):
    row = {
        "lead_id": lead_id,
        "email": email,
        "resend_message_id": message_id,
        "status": status,
        "subject": subject,
        "template": "skiptrace_lead_audit_v1",
        "county": county,
    }
    if status == "sent":
        row["sent_at"] = "now()"
    if error:
        row["error"] = error[:500]
    code, resp = sb_post("cold_outreach_log", row)
    if code not in (200, 201):
        print(f"  [WARN] cold_outreach_log insert failed {code}: {resp}", file=sys.stderr)


def main():
    dry_run = "--dry-run" in sys.argv
    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not RESEND_API_KEY and not dry_run:
        print("FATAL: RESEND_API_KEY not set -- run with --dry-run to validate payloads only", file=sys.stderr)
        sys.exit(1)

    already_sent = set()
    try:
        rows = sb_get("cold_outreach_log?select=email&status=eq.sent")
        already_sent = {r["email"].lower() for r in rows}
    except Exception as e:
        print(f"[WARN] could not fetch cold_outreach_log: {e}", file=sys.stderr)

    sent, skipped, errors = 0, 0, 0
    for lead in LEADS:
        email = lead["email"].lower()
        if email in already_sent:
            print(f"  SKIP {email} -- already in cold_outreach_log")
            skipped += 1
            continue
        payload, subject = build_payload(lead)
        print(f"  {'[DRY-RUN] ' if dry_run else ''}Sending to {email} -- subject: {subject}")
        msg_id = send_email(payload, dry_run)
        if msg_id:
            print(f"    OK msg_id={msg_id}")
            log_outreach(lead["lead_id"], email, msg_id, "dry_run" if dry_run else "sent", subject, lead["county_slug"])
            sent += 1
        else:
            log_outreach(lead["lead_id"], email, None, "error", subject, lead["county_slug"], error="Resend returned no message_id")
            errors += 1
        if not dry_run:
            time.sleep(0.3)

    print(f"\n=== RESULT === sent={sent} skipped={skipped} errors={errors}")


if __name__ == "__main__":
    main()
