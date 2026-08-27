#!/usr/bin/env python3
"""Shared helpers for "The Daily Winner FFs" build/send scripts (issue #19482).

Split out of the original winnerdata_daily_winner_ff_digest.py when the Aug
27 scope change added the approval gate: build (compute + upsert
winnerdata.ff_batches) and send (fire on status='approved') are now separate
scripts that both need the same lead query, HTML render, and Resend call.

Uses the Supabase Management API (winnerdata schema is not exposed via
PostgREST -- see scripts/winnerdata_pipeline.py's docstring for the same,
already-diagnosed platform limitation).
"""
import json
import os
import time
import urllib.error
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
PROTECTION_PARTNERS_ORG_ID = "032f4717-545f-4a18-b48b-28ea4257699d"

FROM_EMAIL = "The Daily Winner FFs <ariel@biddeed.ai>"
FF_BASE_URL = "https://ff.winnerdataai.com/ff"

MGMT_API_RETRIES = 3
MGMT_API_BACKOFF_SECONDS = 3


def run_sql(query):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "winnerdata-ff-digest/1.0",
        },
        method="POST",
    )
    last_err = None
    for attempt in range(1, MGMT_API_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "message" in body:
                raise RuntimeError(body["message"])
            return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < MGMT_API_RETRIES:
                time.sleep(MGMT_API_BACKOFF_SECONDS * attempt)
    raise last_err


def sql_str(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def get_producer_email():
    rows = run_sql(f"""
        select p.producer_id, p.full_name, p.email
        from winnerdata.producers p
        where p.org_id = '{PROTECTION_PARTNERS_ORG_ID}' and p.full_name = 'Mariam Shapira' and p.active = true
        order by p.created_at asc;
    """)
    for r in rows:
        if r["email"]:
            return r["email"]
    return None


def get_batch_leads(batch_date):
    return run_sql(f"""
        select distinct on (l.lead_id)
          l.lead_id, l.entity_name,
          se.county,
          se.event_payload->>'sale_type' as sale_type,
          se.event_payload->>'case_number' as case_number,
          (se.event_payload->>'sold_amount')::numeric as sold_amount,
          se.event_payload->>'property_address' as property_address,
          l.consent_certificate #>> '{{contact_resolution_v2,email_tier}}' as email_tier,
          l.consent_certificate #>> '{{contact_resolution_v2,phone_tier}}' as phone_tier,
          rd.routed_at
        from winnerdata.leads l
        join winnerdata.signal_events se on se.signal_id = l.signal_id
        join winnerdata.routing_decisions rd on rd.lead_id = l.lead_id
        where l.org_id = '{PROTECTION_PARTNERS_ORG_ID}'
          and rd.routed_at::date = {sql_str(batch_date)}
          and (l.is_lender_or_plaintiff = false or l.manual_buyer_override = true)
        order by l.lead_id, rd.routed_at desc;
    """)


def confidence_label(email_tier, phone_tier):
    # Honest passthrough of whatever scripts/skiptrace_20260825_contact_resolver_v2.py
    # already recorded (tier number : source, e.g. "2:tracerfy_enhanced_trace") --
    # not remapped to the FF template's badge names (verified-primary / etc.)
    # because no code anywhere in this repo defines that mapping; inventing
    # one here would be an unverified claim about a compliance-sensitive field.
    tier = email_tier or phone_tier
    return tier if tier else "not available"


def render_email(batch_date, leads):
    subject = f"The Daily Winner FFs — {batch_date}"

    if not leads:
        text = (
            f"No qualifying leads today ({batch_date}).\n\n"
            "The pipeline ran and the plaintiff/lender guard is live -- there simply were no "
            "compliant buyer-prospect leads from yesterday's auctions. You'll get today's batch "
            "as soon as one clears.\n\n"
            "-- BidDeed.AI / Everest Capital USA"
        )
        html = (
            f"<div style=\"font-family:Inter,-apple-system,sans-serif;background:#020617;color:#e2e8f0;"
            f"padding:32px\"><h2 style=\"color:white\">The Daily Winner FFs — {batch_date}</h2>"
            f"<p>No qualifying leads today. The pipeline ran and the plaintiff/lender guard is live -- "
            f"there simply were no compliant buyer-prospect leads from yesterday's auctions.</p>"
            f"<p style=\"color:#64748b;font-size:12px\">Everest Capital USA · 1901 S Harbor City Blvd Ste 551 · "
            f"Melbourne, FL 32901</p></div>"
        )
        return subject, text, html

    rows_text = []
    rows_html = []
    for lead in leads:
        tier = confidence_label(lead.get("email_tier"), lead.get("phone_tier"))
        link = f"{FF_BASE_URL}/{lead['lead_id']}"
        rows_text.append(
            f"- {lead['entity_name']} | {lead['county'] or 'unknown county'} | "
            f"{lead['sale_type'] or 'unknown sale type'} | confidence: {tier}\n  {link}"
        )
        rows_html.append(
            f"<tr><td style=\"padding:8px;border-bottom:1px solid #1e293b\">{lead['county'] or '—'}</td>"
            f"<td style=\"padding:8px;border-bottom:1px solid #1e293b\">{lead['sale_type'] or '—'}</td>"
            f"<td style=\"padding:8px;border-bottom:1px solid #1e293b\">{lead['entity_name']}</td>"
            f"<td style=\"padding:8px;border-bottom:1px solid #1e293b\">{tier}</td>"
            f"<td style=\"padding:8px;border-bottom:1px solid #1e293b\">"
            f"<a href=\"{link}\" style=\"color:#f59e0b\">View FF →</a></td></tr>"
        )

    text = (
        f"The Daily Winner FFs — {batch_date}\n{len(leads)} qualifying lead(s):\n\n"
        + "\n\n".join(rows_text)
        + "\n\n-- BidDeed.AI / Everest Capital USA"
    )
    html = (
        "<div style=\"font-family:Inter,-apple-system,sans-serif;background:#020617;color:#e2e8f0;padding:32px\">"
        f"<h2 style=\"color:white\">The Daily Winner FFs — {batch_date}</h2>"
        f"<p>{len(leads)} qualifying lead(s):</p>"
        "<table style=\"width:100%;border-collapse:collapse;font-size:14px\">"
        "<tr style=\"text-align:left;color:#94a3b8\"><th style=\"padding:8px\">County</th>"
        "<th style=\"padding:8px\">Auction Type</th><th style=\"padding:8px\">Buyer</th>"
        "<th style=\"padding:8px\">Confidence</th><th style=\"padding:8px\">FF</th></tr>"
        + "".join(rows_html)
        + "</table>"
        "<p style=\"color:#64748b;font-size:12px;margin-top:24px\">Everest Capital USA · "
        "1901 S Harbor City Blvd Ste 551 · Melbourne, FL 32901</p></div>"
    )
    return subject, text, html


def send_resend(to_email, subject, text, html, dry_run):
    if dry_run:
        return "dry_run_msg_id", None
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return None, "RESEND_API_KEY not set"
    payload = {"from": FROM_EMAIL, "to": [to_email], "subject": subject, "text": text, "html": html}
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Winner Data-FF-Digest/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()).get("id"), None
    except urllib.error.HTTPError as e:
        return None, f"Resend HTTP {e.code}: {e.read().decode()}"


def log_digest(batch_date, recipient, lead_count, message_id, status, error=None):
    row = {
        "batch_date": batch_date,
        "org_id": PROTECTION_PARTNERS_ORG_ID,
        "recipient": recipient,
        "lead_count": lead_count,
        "resend_message_id": message_id,
        "status": status,
    }
    if error:
        row["error"] = error[:500]
    cols = ", ".join(row.keys())
    vals = ", ".join(sql_str(v) if k != "lead_count" and k != "org_id" else (str(v) if k == "lead_count" else f"'{v}'::uuid") for k, v in row.items())
    run_sql(f"insert into winnerdata.ff_digest_log ({cols}) values ({vals});")
