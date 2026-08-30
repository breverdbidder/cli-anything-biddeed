#!/usr/bin/env python3
"""Seller-digest FF enrichment runner (issue #19619).

Runs after the build step persists seller_digest_leads rows for the batch and
BEFORE Ariel approves -- this is the pre-approval enrichment gate. Mirrors the
approach of scripts/ff_nine_portfolio_enrichment.py but generalized for the
seller_digest batch kind:

  1. Skip-trace via Tracerfy enhanced lookup (reuses the name + prior-owned-
     address anchor strategy from ff_nine_portfolio_enrichment -- no purchased-
     property address used as a contact anchor, per the documented lesson there).
  2. DNC scrub via Tracerfy before writing any phone/email to the row.
  3. Updates winnerdata.seller_digest_leads.row_enrichment_status per row.
  4. Updates winnerdata.ff_batches.enrichment_status (not_started → running →
     complete/failed) with real timestamps and a real enrichment_run_id.

Hard guardrails (from issue #19619):
  - Every external API call checks its own result before reporting success.
  - No PII (phone/email) may be written for a lead where DNC screening has
    not completed -- the row stays row_enrichment_status='skipped_dnc_incomplete'
    and the PDF render must omit contact fields for it.
  - enrichment_status transitions are written to the DB, not just printed.
  - FORCE_REFRESH=1 env var re-runs paid vendor lookups for already-complete rows.

Run:
  BATCH_DATE=2026-08-28 SUPABASE_ACCESS_TOKEN=... TRACERFY_API_KEY=... \\
    python scripts/seller_digest_enrichment.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import ff_credit_ledger  # noqa: E402
import tracerfy_client  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = os.environ.get("BATCH_DATE", "")
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
TRACERFY_KEY = os.environ.get("TRACERFY_API_KEY", "")
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "0") == "1"


def sql(q: str):
    if not SB_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    import urllib.request as _req
    req = _req.Request(
        MGMT_URL,
        data=json.dumps({"query": q}).encode(),
        headers={
            "Authorization": f"Bearer {SB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "winnerdata-seller-digest-enrichment/1.0",
        },
        method="POST",
    )
    import urllib.request as _u
    with _u.urlopen(req, timeout=90) as r:
        body = json.loads(r.read())
    if isinstance(body, dict) and body.get("message"):
        raise RuntimeError(body["message"])
    return body


def esc(v):
    return str(v or "").replace("'", "''")


def set_batch_enrichment_status(batch_date: str, status: str, run_id: str | None = None, error: str | None = None):
    fields = [f"enrichment_status = '{esc(status)}'", "updated_at = now()"]
    if run_id:
        fields.append(f"enrichment_run_id = '{esc(run_id)}'")
    if status == "running":
        fields.append("enrichment_started_at = now()")
        fields.append("enrichment_error = null")
    if status in ("complete", "failed"):
        fields.append("enrichment_completed_at = now()")
    if status == "failed" and error:
        fields.append(f"enrichment_error = '{esc(error[:500])}'")
    sql(f"update winnerdata.ff_batches set {', '.join(fields)} where batch_date = date '{esc(batch_date)}'")


def set_row_enrichment_status(batch_date: str, lead_id: str, status: str):
    sql(f"""
        update winnerdata.seller_digest_leads
        set row_enrichment_status = '{esc(status)}', updated_at = now()
        where batch_date = date '{esc(batch_date)}' and lead_id = '{esc(lead_id)}'::uuid
    """)


def get_prior_owned_address(entity_name: str) -> dict | None:
    """Look for a prior mailing address from zw_parcels where this entity is
    the owner of record (not the just-purchased address -- the same lesson as
    ff_nine_portfolio_enrichment.py). Uses FTS to avoid a full table scan on the
    10M-row zw_parcels table."""
    if not entity_name:
        return None
    import re
    target_toks = {t for t in re.sub(r"[^A-Za-z ]", " ", entity_name).upper().split() if len(t) >= 2}
    if not target_toks:
        return None
    try:
        rows = sql(f"""
            select owner_addr1, owner_city, owner_state, owner_zip, owner_name
            from public.zw_parcels
            where to_tsvector('english',
                coalesce(owner_name,'') || ' ' || coalesce(site_addr,'') || ' ' || coalesce(site_city,'')
            ) @@ plainto_tsquery('english', '{esc(entity_name)}')
            limit 20
        """)
        candidates = [
            r for r in rows
            if r.get("owner_addr1")
            and target_toks <= {t for t in re.sub(r"[^A-Za-z ]", " ", r.get("owner_name") or "").upper().split() if len(t) >= 2}
        ]
        if not candidates:
            return None
        from collections import Counter
        key = lambda r: (
            re.sub(r"[^A-Z0-9]", "", (r.get("owner_addr1") or "").upper()),
            re.sub(r"[^A-Z0-9]", "", (r.get("owner_city") or "").upper()),
            (r.get("owner_state") or "").upper(),
            re.sub(r"[^0-9]", "", (r.get("owner_zip") or "")),
        )
        best_key, _ = Counter(key(r) for r in candidates).most_common(1)[0]
        return next(r for r in candidates if key(r) == best_key)
    except Exception as e:
        print(f"  WARN: prior address lookup failed for {entity_name!r}: {e}", file=sys.stderr)
        return None


def tracerfy_lookup(entity_name: str, anchor: dict | None) -> dict:
    if not TRACERFY_KEY or not anchor:
        return {"status": "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS"}
    ledger = ff_credit_ledger.spend("tracerfy", 1)
    if not ledger.get("granted"):
        return {"status": "SKIPPED_DAILY_CAP", "ledger": ledger}
    result = tracerfy_client.trace_lead(
        entity_name,
        anchor.get("owner_addr1"),
        anchor.get("owner_city"),
        anchor.get("owner_state"),
        anchor.get("owner_zip"),
    )
    status_map = {
        "OK": "OK",
        "NO_MATCH": "NO_MATCH",
        "NO_MAILING_ADDRESS_AVAILABLE": "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS",
        "REQUEST_FAILED": "REQUEST_FAILED",
        "UNEXPECTED_RESPONSE_SHAPE": "REQUEST_FAILED",
        "HIT_BUT_NO_PERSONS_SHAPE_MISMATCH": "REQUEST_FAILED",
        "HIT_NO_CONTACT_FIELDS": "NO_MATCH",
    }
    status = status_map.get(result.get("parse_status"), "REQUEST_FAILED")
    if status != "OK":
        return {"status": status, "parse_status": result.get("parse_status")}
    return {
        "status": "OK",
        "full_name": result.get("full_name"),
        "phone": result.get("phone"),
        "email": result.get("email"),
        "source": "Tracerfy enhanced lookup",
    }


def dnc_scrub(phone: str) -> dict:
    """Check DNC status for a phone number via Tracerfy.
    Returns {"dnc": True/False, "provider": "tracerfy", "checked_at": ...}
    or {"dnc": None, "error": "..."} if the scrub call fails.

    CRITICAL: if this returns dnc=None (failed), the caller must NOT write
    phone/email to the row -- per the issue's hard guardrail.
    """
    if not TRACERFY_KEY or not phone:
        return {"dnc": None, "error": "no_key_or_no_phone"}
    try:
        result = tracerfy_client.dnc_scrub(phone)
        return {
            "dnc": result.get("is_dnc"),
            "provider": "tracerfy",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "raw": result,
        }
    except Exception as e:
        return {"dnc": None, "error": str(e)[:300]}


def persist_enriched_row(batch_date: str, lead_id: str, tf: dict, dnc: dict, qa_status: str):
    phone = tf.get("phone") if tf.get("status") == "OK" else None
    email = tf.get("email") if tf.get("status") == "OK" else None
    provider = "tracerfy" if tf.get("status") == "OK" else None
    phone_lit = f"'{esc(phone)}'" if phone else "null"
    email_lit = f"'{esc(email)}'" if email else "null"
    provider_lit = f"'{esc(provider)}'" if provider else "null"
    verified_lit = "now()" if provider else "null"
    is_dnc = dnc.get("dnc")
    is_dnc_lit = ("true" if is_dnc else "false") if is_dnc is not None else "null"
    dnc_checked_at_lit = f"'{esc(dnc.get('checked_at', ''))}'" if dnc.get("checked_at") else "null"
    dnc_provider_lit = f"'{esc(dnc.get('provider', ''))}'" if dnc.get("provider") else "null"
    ev = json.dumps({
        "tracerfy_enrichment": tf,
        "dnc_scrub": dnc,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    })
    unresolved = sum([
        1 if not phone else 0,
        1 if not email else 0,
        1 if is_dnc is None else 0,
    ])
    sql(f"""
        update winnerdata.seller_digest_leads
        set phone = {phone_lit},
            email = {email_lit},
            contact_provider = {provider_lit},
            contact_verified_at = {verified_lit},
            is_dnc = {is_dnc_lit},
            dnc_checked_at = {dnc_checked_at_lit},
            dnc_provider = {dnc_provider_lit},
            row_enrichment_status = '{esc(qa_status)}',
            unresolved_field_count = {unresolved},
            evidence_ledger = evidence_ledger || '{esc(ev)}'::jsonb,
            updated_at = now()
        where batch_date = date '{esc(batch_date)}' and lead_id = '{esc(lead_id)}'::uuid
    """)


def main():
    if not BATCH_DATE:
        print("ERROR: BATCH_DATE env var required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(1)

    run_id = str(uuid.uuid4())
    print(f"seller_digest enrichment: batch_date={BATCH_DATE} run_id={run_id}")

    set_batch_enrichment_status(BATCH_DATE, "running", run_id=run_id)
    try:
        rows = sql(f"""
            select lead_id, entity_name, county, case_number, sale_type,
                   property_address, email_tier, phone_tier, row_enrichment_status
            from winnerdata.seller_digest_leads
            where batch_date = date '{esc(BATCH_DATE)}'
            order by lead_id
        """)

        if not rows:
            raise RuntimeError(f"No seller_digest_leads rows found for {BATCH_DATE}. "
                               "Run the build step first (winnerdata_daily_winner_ff_digest.py).")

        print(f"  {len(rows)} lead(s) to process.")
        results = []
        for r in rows:
            lead_id = r["lead_id"]
            entity_name = r["entity_name"] or ""

            if r.get("row_enrichment_status") == "complete" and not FORCE_REFRESH:
                print(f"  [{lead_id}] already complete -- skipping (set FORCE_REFRESH=1 to override)")
                results.append({"lead_id": lead_id, "skipped": True})
                continue

            set_row_enrichment_status(BATCH_DATE, lead_id, "running")

            anchor = get_prior_owned_address(entity_name)
            tf = tracerfy_lookup(entity_name, anchor)
            print(f"  [{lead_id}] {entity_name!r}: tracerfy={tf.get('status')}")

            phone = tf.get("phone") if tf.get("status") == "OK" else None
            if phone:
                dnc = dnc_scrub(phone)
                print(f"  [{lead_id}] DNC scrub: dnc={dnc.get('dnc')} provider={dnc.get('provider')}")
            else:
                dnc = {"dnc": None, "error": "no_phone_from_tracerfy"}

            is_dnc = dnc.get("dnc")
            if phone and is_dnc is None:
                qa_status = "skipped_dnc_incomplete"
                set_row_enrichment_status(BATCH_DATE, lead_id, "skipped_dnc_incomplete")
                ev = json.dumps({"tracerfy_enrichment": tf, "dnc_scrub": dnc, "blocked_reason": "DNC scrub did not return a result", "ran_at": datetime.now(timezone.utc).isoformat()})
                sql(f"""
                    update winnerdata.seller_digest_leads
                    set evidence_ledger = evidence_ledger || '{esc(ev)}'::jsonb,
                        updated_at = now()
                    where batch_date = date '{esc(BATCH_DATE)}' and lead_id = '{esc(lead_id)}'::uuid
                """)
                results.append({"lead_id": lead_id, "qa_status": qa_status, "reason": "DNC scrub incomplete"})
                continue

            if tf.get("status") == "OK" and phone:
                qa_status = "complete"
            elif tf.get("status") in ("NO_MATCH", "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS", "SKIPPED_DAILY_CAP"):
                qa_status = "complete"
            else:
                qa_status = "failed"

            persist_enriched_row(BATCH_DATE, lead_id, tf, dnc, qa_status)
            results.append({"lead_id": lead_id, "qa_status": qa_status, "tracerfy_status": tf.get("status")})

        complete_count = sum(1 for r in results if r.get("qa_status") == "complete")
        skipped_count = sum(1 for r in results if r.get("skipped"))
        contact_found = sum(1 for r in results if r.get("tracerfy_status") == "OK")
        print(json.dumps({
            "batch_date": BATCH_DATE,
            "run_id": run_id,
            "total": len(rows),
            "complete": complete_count,
            "skipped_already_done": skipped_count,
            "contact_found": contact_found,
        }, indent=2))

        verify = sql(f"""
            select row_enrichment_status, count(*) as n
            from winnerdata.seller_digest_leads
            where batch_date = date '{esc(BATCH_DATE)}'
            group by row_enrichment_status
            order by row_enrichment_status
        """)
        print("DB verification:", json.dumps(verify, indent=2))

        set_batch_enrichment_status(BATCH_DATE, "complete", run_id=run_id)

    except Exception as e:
        set_batch_enrichment_status(BATCH_DATE, "failed", run_id=run_id, error=str(e))
        raise


if __name__ == "__main__":
    main()
