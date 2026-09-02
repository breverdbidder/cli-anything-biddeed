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
# P0 fix (2026-09-01): ff.winnerdataai.com now resolves -- Ariel manually
# added the proxied A record in the Cloudflare dashboard, working around the
# CF_API_TOKEN's missing Zone:DNS:Edit permission that blocked automated DNS
# writes (see workers/winnerdata-ff/wrangler.toml). Confirmed live via curl:
# /healthz returns 200 JSON and /ff/<real lead_id> renders the same template
# content as the workers.dev fallback used since the earlier outage.
FF_BASE_URL = "https://ff.winnerdataai.com/ff"

MGMT_API_RETRIES = 3
MGMT_API_BACKOFF_SECONDS = 3

# issue #19659 item 2: Resend's test sandbox always reports "sent" without
# delivering anything real -- never a valid recipient_kind, regardless of
# who the batch's intended recipient is. Internal Everest/BidDeed addresses
# ARE valid real sends (Ariel doing QA/review) but must never be counted
# billable, so they get their own recipient_kind rather than being lumped
# in with producer sends.
SANDBOX_RECIPIENT_DOMAINS = ("resend.dev",)
INTERNAL_QA_RECIPIENT_DOMAINS = ("biddeed.ai", "everestcapitalusa.com")


def classify_recipient(email):
    """Returns 'sandbox', 'internal_qa', or 'producer' for a send recipient.

    'sandbox' must never be allowed to reach status='sent' -- see
    winnerdata_ff_send_approved.py's use of this. 'internal_qa' may reach
    status='sent' (Ariel's own review sends) but is never billable.
    'producer' is the only recipient_kind that can back a
    winnerdata.billable_ff_events row.
    """
    domain = (email or "").strip().lower().rsplit("@", 1)[-1]

    def _matches(domains):
        return any(domain == d or domain.endswith("." + d) for d in domains)

    if _matches(SANDBOX_RECIPIENT_DOMAINS):
        return "sandbox"
    if _matches(INTERNAL_QA_RECIPIENT_DOMAINS):
        return "internal_qa"
    return "producer"


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
    # issue #19659 item 1: explicit "email is not null" guard in the query
    # itself (not just a truthiness check on the returned rows) -- so a
    # producer with an empty-string email on file can't slip through either.
    rows = run_sql(f"""
        select p.producer_id, p.full_name, p.email
        from winnerdata.producers p
        where p.org_id = '{PROTECTION_PARTNERS_ORG_ID}'
          and p.full_name = 'Mariam Shapira'
          and p.active = true
          and p.email is not null
          and length(trim(p.email)) > 0
        order by p.created_at asc;
    """)
    return rows[0]["email"] if rows else None


def get_batch_leads(batch_date):
    # issue P0 (2026-09-01) bug 2: l.consent_certificate #>> '{contact_resolution_v2,...}'
    # is NULL on every lead row, live-verified -- that path was never populated.
    # The real, populated contact-confidence value lives on
    # winnerdata.ff_batch_leads.contact_confidence, keyed by (batch_date, auction_id)
    # -- NOT by lead_id, so it can't be joined directly. ff_batch_leads has no
    # lead_id/auction_id link back to winnerdata.leads either. Live-verified the
    # only reliable join key is case_number: it's globally unique across all 37
    # rows in ff_batch_leads today, and joining on it (not batch_date -- see the
    # separate batch_date mislabeling bug where ff_batch_leads.batch_date=2026-08-27
    # for the same 28 leads whose routing_decisions.routed_at::date=2026-08-29)
    # is what actually recovers non-null tiers for the real, already-sent batch.
    # email_tier/phone_tier are kept as-is (still NULL today, pre-existing and
    # out of scope here) -- scripts/winnerdata_daily_winner_ff_digest.py and
    # scripts/seller_digest_backfill.py persist those two keys into the
    # separate winnerdata.seller_digest_leads table and must not regress.
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
          fbl.contact_confidence as confidence_tier,
          rd.routed_at
        from winnerdata.leads l
        join winnerdata.signal_events se on se.signal_id = l.signal_id
        join winnerdata.routing_decisions rd on rd.lead_id = l.lead_id
        left join winnerdata.ff_batch_leads fbl
          on fbl.case_number = se.event_payload->>'case_number'
        where l.org_id = '{PROTECTION_PARTNERS_ORG_ID}'
          and rd.routed_at::date = {sql_str(batch_date)}
          and (l.is_lender_or_plaintiff = false or l.manual_buyer_override = true)
        order by l.lead_id, rd.routed_at desc;
    """)


def get_batch_lead_reviews(batch_date):
    """Per-lead approve/reject/request-improvement decisions from the LMS FF
    Batch Review screen (winnerdata.ff_batch_lead_review, 2026-09-01), keyed
    by case_number -- the same join key get_batch_leads() already uses for
    winnerdata.ff_batch_leads.contact_confidence. Returns {case_number: decision}.
    A case_number with no entry here is unreviewed -- callers must treat that
    as excluded-from-send (Ariel's explicit conservative default), not as an
    implicit approval.
    """
    rows = run_sql(f"""
        select case_number, decision
        from winnerdata.ff_batch_lead_review
        where batch_date = {sql_str(batch_date)};
    """)
    return {r["case_number"]: r["decision"] for r in rows}


def get_verified_approval(batch_date, batch_kind, lead_count):
    """Issue #19745 send-path gate: the send step must VERIFY, not trust
    winnerdata.ff_batches.status='approved' -- that column can still be
    flipped by the old service-role public.ff_approve_batch() RPC (kept live
    for the pre-existing Cowork-task flow), which proves nothing about who
    actually issued the call (the 2026-09-01 incident this issue closes).

    Returns the most recent winnerdata.ff_batch_approvals row for batch_date
    IF its snapshot_hash matches the batch's CURRENT (batch_date, batch_kind,
    lead_count) -- i.e. an authenticated LMS click approved exactly this
    batch state, not a since-changed one. Returns None otherwise (no approval
    row at all, or the batch changed since the last approval).
    """
    expected = run_sql(f"""
        select encode(
          extensions.digest({sql_str(batch_date)} || '|' || {sql_str(batch_kind)} || '|' || {lead_count}::text, 'sha256'),
          'hex'
        ) as expected_hash;
    """)
    expected_hash = expected[0]["expected_hash"]

    rows = run_sql(f"""
        select snapshot_hash, approved_by_email, approved_at
        from winnerdata.ff_batch_approvals
        where batch_date = {sql_str(batch_date)}
        order by approved_at desc
        limit 1;
    """)
    if not rows or rows[0]["snapshot_hash"] != expected_hash:
        return None
    return rows[0]


def confidence_label(confidence_tier):
    # Honest passthrough of whatever winnerdata.ff_batch_leads.contact_confidence
    # already recorded (e.g. "VERIFIED-CROSS-CHECKED", "LIKELY-SINGLE-SOURCE",
    # "NOT AVAILABLE") -- not remapped to the FF template's badge names
    # (verified-primary / etc.) because no code anywhere in this repo defines
    # that mapping; inventing one here would be an unverified claim about a
    # compliance-sensitive field.
    return confidence_tier if confidence_tier else "not available"


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
        tier = confidence_label(lead.get("confidence_tier"))
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


def log_digest(batch_date, recipient, lead_count, message_id, status, error=None, recipient_kind=None):
    row = {
        "batch_date": batch_date,
        "org_id": PROTECTION_PARTNERS_ORG_ID,
        "recipient": recipient,
        "recipient_kind": recipient_kind or (classify_recipient(recipient) if recipient else None),
        "lead_count": lead_count,
        "resend_message_id": message_id,
        "status": status,
    }
    if error:
        row["error"] = error[:500]
    cols = ", ".join(row.keys())
    vals = ", ".join(sql_str(v) if k != "lead_count" and k != "org_id" else (str(v) if k == "lead_count" else f"'{v}'::uuid") for k, v in row.items())
    run_sql(f"insert into winnerdata.ff_digest_log ({cols}) values ({vals});")
