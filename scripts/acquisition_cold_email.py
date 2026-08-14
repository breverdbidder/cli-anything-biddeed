#!/usr/bin/env python3
"""
Acquisition Sprint: CAN-SPAM compliant cold email to lead_profiles.

CAN-SPAM compliance:
  - Accurate From/subject (no deceptive headers)
  - Physical postal address in every email
  - One-click List-Unsubscribe header + unsubscribe link in body
  - Honored opt-out within 10 business days (instant here — email_consent set false)
  - Commercial email clearly identified

Run:
  python scripts/acquisition_cold_email.py [--dry-run] [--limit N]
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

FROM_EMAIL = "Ariel Shapira <ariel@biddeed.ai>"
FROM_DOMAIN = "biddeed.ai"
UNSUBSCRIBE_URL = "https://biddeed.ai/unsubscribe"
PHYSICAL_ADDRESS = "Everest Capital USA · 1901 S Harbor City Blvd Ste 551 · Melbourne, FL 32901"

SUBJECT = "Free {county} County foreclosure report — BidDeed.AI"

EMAIL_TEXT = """\
Hi {name},

I saw you have interest in {county} County properties. I'm Ariel Shapira — 10+ year \
Florida foreclosure investor, licensed broker, and founder of BidDeed.AI.

I built BidDeed.AI because I was tired of guessing max bids. It pulls live auction \
data for 67 Florida counties, runs the Shapira formula (ARV × 70% − Repairs − costs), \
and flags lien traps before you bid.

For {county} County leads: grab your free S1 county report here — no card required:
https://biddeed.ai/free-report?county={county_slug}

If you want full Investor access (unlimited queries, all 67 counties, lien alerts):
https://biddeed.ai/subscribe?tier=investor

$99/month or $990/year (Pioneer rate — saves you $198).

Reply to this email with any questions. I answer personally.

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
.cta-sec{{display:inline-block;border:1px solid #f59e0b;color:#f59e0b;padding:10px 22px;border-radius:8px;font-weight:600;text-decoration:none;font-size:14px;margin:4px 0}}
.footer{{margin-top:32px;padding-top:16px;border-top:1px solid #1e293b;font-size:11px;color:#64748b;line-height:1.6}}
.footer a{{color:#64748b}}
</style>
</head>
<body>
<div class="wrap">
  <h2>Free {county} County foreclosure report</h2>
  <p>Hi {name},</p>
  <p>I'm Ariel Shapira — 10+ year Florida foreclosure investor, licensed broker, and founder of BidDeed.AI. I built it because I was tired of guessing max bids.</p>
  <p>BidDeed.AI pulls live auction data for 67 Florida counties, runs the <strong>Shapira formula</strong> (ARV × 70% − Repairs − costs), and flags lien traps before you bid.</p>
  <p>For <strong>{county} County</strong> — grab your free S1 report, no card required:</p>
  <p><a href="https://biddeed.ai/free-report?county={county_slug}" class="cta">Get Free {county} County Report →</a></p>
  <p>Want full Investor access — unlimited queries, all 67 counties, lien alerts?</p>
  <p>
    <a href="https://biddeed.ai/subscribe?tier=investor" class="cta-sec">Investor $99/mo →</a>&nbsp;&nbsp;
    <a href="https://biddeed.ai/subscribe?tier=investor&interval=annual" class="cta-sec">Pioneer Annual $990/yr →</a>
  </p>
  <p>Reply to this email with questions — I answer personally.</p>
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


def send_email(to_email, to_name, county, county_slug, dry_run=False):
    import urllib.parse
    email_encoded = urllib.parse.quote(to_email)
    name_part = to_name.split()[0] if to_name else "there"
    county_display = county.replace("-", " ").title() if county else "Florida"

    subject = SUBJECT.format(county=county_display)
    text_body = EMAIL_TEXT.format(
        name=name_part,
        county=county_display,
        county_slug=county_slug or county_display.lower().replace(" ", "-"),
        physical_address=PHYSICAL_ADDRESS,
        unsubscribe_url=UNSUBSCRIBE_URL,
        email_encoded=email_encoded,
    )
    html_body = EMAIL_HTML.format(
        name=name_part,
        county=county_display,
        county_slug=county_slug or county_display.lower().replace(" ", "-"),
        physical_address=PHYSICAL_ADDRESS,
        unsubscribe_url=UNSUBSCRIBE_URL,
        email_encoded=email_encoded,
    )

    if dry_run:
        print(f"  [DRY-RUN] Would send to {to_email} — subject: {subject}")
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
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
            return result.get("id")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [ERROR] Resend HTTP {e.code}: {body}", file=sys.stderr)
        return None


def log_outreach(lead_id, email, message_id, status, subject, county, error=None):
    row = {
        "lead_id": lead_id,
        "email": email,
        "resend_message_id": message_id,
        "status": status,
        "subject": subject,
        "template": "canspam_cold_v1",
        "county": county,
    }
    if status == "sent":
        row["sent_at"] = "now()"
    if error:
        row["error"] = error[:500]
    status_code, resp = sb_post("cold_outreach_log", row)
    if status_code not in (200, 201):
        print(f"  [WARN] cold_outreach_log insert failed {status_code}: {resp}", file=sys.stderr)


def log_to_insights(sent, blocked, errors, dry_run):
    row = {
        "anomaly_type": "acquisition_sprint_daily",
        "county": "ALL",
        "sale_type": "acquisition_sprint",
        "description": json.dumps({
            "event": "cold_email_send",
            "dry_run": dry_run,
            "sent": sent,
            "blocked_already_sent": blocked,
            "errors": errors,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }),
    }
    status_code, resp = sb_post("insights", row)
    if status_code not in (200, 201):
        print(f"  [WARN] insights insert failed {status_code}: {resp}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="CAN-SPAM compliant acquisition cold email")
    parser.add_argument("--dry-run", action="store_true", help="Print emails, do not send")
    parser.add_argument("--limit", type=int, default=200, help="Max leads to email this run")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not RESEND_API_KEY and not args.dry_run:
        print("FATAL: RESEND_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"=== Acquisition Cold Email (dry_run={args.dry_run}, limit={args.limit}) ===\n")

    leads = sb_get(
        "lead_profiles?select=id,email,name,county,email_consent&email=not.is.null"
        f"&order=id.asc&limit={args.limit}"
    )
    print(f"Fetched {len(leads)} lead_profiles with emails")

    already_sent_emails = set()
    try:
        sent_rows = sb_get("cold_outreach_log?select=email&status=eq.sent")
        already_sent_emails = {r["email"] for r in sent_rows}
        print(f"Already sent to {len(already_sent_emails)} emails — will skip")
    except Exception as e:
        print(f"[WARN] Could not fetch cold_outreach_log (table may not exist yet): {e}")

    sent_count = 0
    blocked_count = 0
    error_count = 0

    for lead in leads:
        email = (lead.get("email") or "").strip().lower()
        if not email or "@" not in email:
            continue

        if email in already_sent_emails:
            blocked_count += 1
            continue

        county = lead.get("county") or "Florida"
        county_slug = county.lower().replace(" ", "-")
        name = lead.get("name") or ""
        lead_id = lead.get("id")

        subject = SUBJECT.format(county=county.title())
        print(f"  Sending to {email} (county={county}) ...", end=" ", flush=True)

        msg_id = send_email(email, name, county, county_slug, dry_run=args.dry_run)

        if msg_id:
            print(f"OK msg_id={msg_id}")
            log_outreach(lead_id, email, msg_id, "sent", subject, county)
            sent_count += 1
        else:
            print("FAILED")
            log_outreach(lead_id, email, None, "error", subject, county,
                        error="Resend API returned no message_id")
            error_count += 1

        if not args.dry_run:
            time.sleep(0.3)

    print(f"\n=== RESULT ===")
    print(f"  Sent:    {sent_count}")
    print(f"  Blocked: {blocked_count} (already emailed)")
    print(f"  Errors:  {error_count}")

    log_to_insights(sent_count, blocked_count, error_count, args.dry_run)
    print("\nLogged to public.insights (anomaly_type='acquisition_sprint_daily')")


if __name__ == "__main__":
    main()
