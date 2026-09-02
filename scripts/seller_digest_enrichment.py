#!/usr/bin/env python3
"""Seller-digest FF enrichment runner (issue #19619, bug-fixes in #19626,
root-cause rewrite in #19729).

Runs after the build step persists seller_digest_leads rows for the batch and
BEFORE Ariel approves -- this is the pre-approval enrichment gate.

Issue #19729 (P0, 2026-09-02): the previous version of this script anchored
every Tracerfy lookup on `property_address` -- the auction property the buyer
just won. The buyer does not live there yet (deed records lag), so Tracerfy
correctly returned NO_MATCH on every one of 81 rows across 4 batches
(lifetime hit rate 0%). This rewrite ports the proven owner-match ->
mailing-address -> vendor sequence that `scripts/ff_billable_loop.py` (issue
#19712, same day) already runs for the sibling `ff_batch_leads` pipeline:

  1. Classify the buyer: person / person_joint / business / land_trust
     (same heuristic as scripts/skiptrace_20260827_28lead_ff_batch.py).
  2. stage1_identity: self-match the buyer's name against public.fl_parcels
     for a PRIOR-owned mailing address (excludes the just-purchased parcel).
     Reused via import, not reimplemented (SEARCH-FIRST mandate).
  3. business/land_trust only: stage2_sunbiz_chain resolves the LLC's
     principal / registered agent via the Sunbiz identity cascade. Reused
     via import.
  4. stage3_skiptrace: Tracerfy enhanced trace (name + the mailing address
     found in step 2/3 -- never the purchased-property address). Reused via
     import; retry-with-backoff on 5xx/544 now lives in tracerfy_client.py
     itself (issue #19729 T4), so every caller gets it for free.
  5. DNC scrub via Tracerfy, polled to a real determination before any
     phone/email is written (hard guardrail from issue #19619 -- NOT
     reused from ff_billable_loop.run_stage5_dnc, which only checks that the
     scrub request was accepted, not that DNC screening actually completed;
     see this script's dnc_scrub() docstring).
  6. Updates winnerdata.seller_digest_leads.row_enrichment_status per row,
     isolating one row's vendor/SQL failure from the rest of the batch
     (issue #19729 T3) -- 'error' is a new, distinct terminal state from
     'complete' (NO_MATCH is still 'complete': the vendor answered).
  7. Updates winnerdata.ff_batches.enrichment_status (not_started -> running
     -> complete/failed) with real timestamps and a real enrichment_run_id.

rerun_paid_lookups (env RERUN_PAID_LOOKUPS, default false): a row that
already has a resolved phone or email is never re-queried (real vendor spend
already paid for a real result). A row that is 'complete' but has NO
contact -- the entire lifetime population before this fix -- IS reprocessed,
because 'complete' under the old code meant "the wrong address was tried",
never "the right address came back empty". This is why 'complete-but-empty'
is not skipped by default the way FORCE_REFRESH=0 used to skip it.

Hard guardrails (from issue #19619, restated in #19729 M1):
  - Every external API call checks its own result before reporting success.
  - No PII (phone/email) may be written for a lead where DNC screening has
    not completed -- the row stays row_enrichment_status='skipped_dnc_incomplete'
    and the PDF render must omit contact fields for it.
  - enrichment_status transitions are written to the DB, not just printed.
  - Nothing in this script sends, digests, or approves anything.

Run:
  BATCH_DATE=2026-08-31 SUPABASE_ACCESS_TOKEN=... TRACERFY_API_KEY=... \\
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \\
    python scripts/seller_digest_enrichment.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import tracerfy_client  # noqa: E402
from ff_billable_loop import (  # noqa: E402  -- reused, not reimplemented
    STAGE_PLAN,
    evaluate_2of3,
    tier_for_evidence,
    run_stage1_identity,
    run_stage2_sunbiz_chain,
    run_stage3_skiptrace,
)
from identity_cascade import normalize_person_name  # noqa: E402  -- reused parser-boundary fix (#19746 item 3)

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = os.environ.get("BATCH_DATE", "")
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
TRACERFY_KEY = os.environ.get("TRACERFY_API_KEY", "")
RERUN_PAID_LOOKUPS = os.environ.get("RERUN_PAID_LOOKUPS", os.environ.get("FORCE_REFRESH", "0")) == "1"
RUN_ID = str(uuid.uuid4())

SQL_MAX_ATTEMPTS = 3  # issue #19729 T4: same proxy-layer 5xx/544 retry as tracerfy_client.py


def sql(q: str):
    if not SB_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    import urllib.error as _err
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
    last_exc = None
    for attempt in range(1, SQL_MAX_ATTEMPTS + 1):
        try:
            with _req.urlopen(req, timeout=90) as r:
                body = json.loads(r.read())
            if isinstance(body, dict) and body.get("message"):
                raise RuntimeError(body["message"])
            return body
        except (_err.HTTPError, _err.URLError, TimeoutError) as e:
            last_exc = e
            status = getattr(e, "code", None)
            retryable = status is None or status >= 500 or status == 544
            if retryable and attempt < SQL_MAX_ATTEMPTS:
                backoff = 2 ** (attempt - 1)
                print(f"  Management API {type(e).__name__} (attempt {attempt}/{SQL_MAX_ATTEMPTS}), retrying in {backoff}s: {e}", file=sys.stderr)
                time.sleep(backoff)
                continue
            raise
    raise last_exc


def esc(v):
    return str(v or "").replace("'", "''")


# ---------------------------------------------------------------------------
# Identity classification -- same heuristic as
# scripts/skiptrace_20260827_28lead_ff_batch.py::classify() (no per-buyer
# TYPE_OVERRIDE table here -- that script's overrides were a one-off
# hand-correction for its specific 28-row batch, not a generalizable rule).
# ---------------------------------------------------------------------------

def classify(entity_name: str) -> str:
    name = (entity_name or "").strip()
    upper = name.upper()
    if "trust" in name.lower() and "llc" not in name.lower():
        return "land_trust_unpierceable"
    if re.search(r"\b(LLC|INC|CORP|LP|LLP|GROUP)\b", upper):
        return "business"
    if re.search(r"\b(AND|&)\b", upper):
        return "person_joint"
    return "person"


def get_auction_parcel_id(case_number: str, entity_name: str) -> str | None:
    """The parcel this buyer just purchased -- excluded from the stage1
    fl_parcels self-match so we never anchor a lookup on the just-won
    property (the exact bug this issue exists to fix)."""
    if not case_number:
        return None
    rows = sql(f"""
        select parcel_id from public.multi_county_auctions
        where case_number = '{esc(case_number)}'
          and winning_bidder = '{esc(entity_name)}'
        limit 1
    """)
    return rows[0]["parcel_id"] if rows else None


# ---------------------------------------------------------------------------
# issue #19746 item 4: a PO Box is a genuine mailing address for fl_parcels'
# own purposes but is useless as a Tracerfy anchor (no residence to trace).
# Treat it as no-address so the caller falls through to the next source
# instead of burning a Tracerfy credit on a guaranteed miss (Florida
# Investors Capital LLC -> Casscap, LLC hit "PO BOX 2086 LUTZ" and Tracerfy
# never had a chance).
# ---------------------------------------------------------------------------

_PO_BOX_RE = re.compile(r"\bP\.?\s*O\.?\s*BOX\b", re.I)


def is_po_box(stage1_result: dict | None) -> bool:
    if not stage1_result:
        return False
    text = stage1_result.get("principal_home_address") or ""
    return bool(_PO_BOX_RE.search(text))


# ---------------------------------------------------------------------------
# issue #19746 items 1+3: fl_parcels.own_name is SURNAME-FIRST (confirmed
# live 2026-09-02: "PATEL RAJENDRAKUMAR", "STERN BEN" -- see
# tracerfy_client._split_owner_name's own docstring for the same convention
# on auction-winner names). A Sunbiz-resolved principal name comes back in
# natural First-Last human order ("Rajendrakumar Patel", "Ben Stern"), so a
# single-order LIKE substring query against fl_parcels never lines up even
# when a real match exists -- confirmed live: "Ben Stern" -> 0 rows, but
# "Stern Ben" -> real hit "STERN BEN, 9725 CAMBERLEY CIR, ORLANDO". Try both
# token orders (free -- run_stage1_identity is an internal fl_parcels query,
# no vendor credit spent) rather than guess which order is correct.
# ---------------------------------------------------------------------------

def stage1_self_match_both_orders(lead: dict, name: str) -> tuple[dict, str]:
    r = run_stage1_identity(dict(lead, winning_bidder=name))
    if r.get("outcome") == "hit":
        return r, name
    tokens = name.split()
    if len(tokens) == 2:
        swapped = f"{tokens[1]} {tokens[0]}"
        r2 = run_stage1_identity(dict(lead, winning_bidder=swapped))
        if r2.get("outcome") == "hit":
            return r2, swapped
    return r, name


# ---------------------------------------------------------------------------
# DNC scrub -- polled to a real determination. NOT reused from
# ff_billable_loop.run_stage5_dnc(): that function treats "Tracerfy accepted
# the scrub request" as outcome="hit" without ever polling the queue for the
# actual flagged/clean result (confirmed by reading its source, 2026-09-02).
# That is fine for ff_batch_leads' BILLABLE gate (which doesn't gate on DNC
# completion) but violates THIS pipeline's hard guardrail from issue #19619:
# phone/email may not be written until DNC screening has actually completed.
# Reuses the proven poll pattern from
# scripts/skiptrace_20260827_28lead_ff_batch.py::dnc_check().
# ---------------------------------------------------------------------------

def dnc_scrub(phone: str) -> dict:
    if not TRACERFY_KEY or not phone:
        return {"status": "SKIPPED_NO_KEY_OR_PHONE", "dnc": None}
    resp = tracerfy_client.dnc_scrub([phone])
    if isinstance(resp, tuple):
        _, err_detail = resp
        return {"status": "DNC_SCRUB_REQUEST_FAILED", "dnc": None, "error": err_detail}
    queue_id = resp.get("dnc_queue_id")
    if queue_id is None:
        return {"status": "DNC_SCRUB_UNEXPECTED_RESPONSE_SHAPE", "dnc": None, "raw": resp}
    for _ in range(6):
        q = tracerfy_client.get_queue_status(queue_id)
        if isinstance(q, dict) and q.get("pending") is False:
            checked, clean = q.get("phones_checked"), q.get("phones_clean")
            flagged = (clean == 0) if checked == 1 and clean is not None else None
            return {"status": "OK", "dnc": flagged, "provider": "tracerfy", "raw": q,
                     "checked_at": datetime.now(timezone.utc).isoformat()}
        time.sleep(20)
    return {"status": "DNC_SCRUB_TIMEOUT", "dnc": None}


# ---------------------------------------------------------------------------
# Batch/row status
# ---------------------------------------------------------------------------

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


def persist_row(batch_date: str, lead_id: str, status: str, phone: str | None, email: str | None,
                 provider: str | None, tier: str, dnc: dict | None, evidence: dict):
    phone_lit = f"'{esc(phone)}'" if phone else "null"
    email_lit = f"'{esc(email)}'" if email else "null"
    provider_lit = f"'{esc(provider)}'" if provider else "null"
    verified_lit = "now()" if provider else "null"
    phone_tier_lit = f"'{esc(tier if phone else 'NOT AVAILABLE')}'"
    email_tier_lit = f"'{esc(tier if email else 'NOT AVAILABLE')}'"
    is_dnc = (dnc or {}).get("dnc")
    is_dnc_lit = ("true" if is_dnc else "false") if is_dnc is not None else "null"
    dnc_checked_at_lit = f"'{esc(dnc.get('checked_at', ''))}'" if dnc and dnc.get("checked_at") else "null"
    dnc_provider_lit = f"'{esc(dnc.get('provider', ''))}'" if dnc and dnc.get("provider") else "null"
    ev = json.dumps(evidence, default=str)
    unresolved = sum([1 if not phone else 0, 1 if not email else 0, 1 if is_dnc is None and phone else 0])
    sql(f"""
        update winnerdata.seller_digest_leads
        set phone = {phone_lit},
            email = {email_lit},
            contact_provider = {provider_lit},
            contact_verified_at = {verified_lit},
            phone_tier = {phone_tier_lit},
            email_tier = {email_tier_lit},
            is_dnc = {is_dnc_lit},
            dnc_checked_at = {dnc_checked_at_lit},
            dnc_provider = {dnc_provider_lit},
            row_enrichment_status = '{esc(status)}',
            unresolved_field_count = {unresolved},
            evidence_ledger = evidence_ledger || '{esc(ev)}'::jsonb,
            updated_at = now()
        where batch_date = date '{esc(batch_date)}' and lead_id = '{esc(lead_id)}'::uuid
    """)


# ---------------------------------------------------------------------------
# Per-lead resolution -- mirrors ff_billable_loop.process_lead()'s stage
# sequencing, adapted to seller_digest_leads' simpler (batch_date, lead_id)
# key and status enum instead of ff_batch_leads' BILLABLE/EXHAUSTED machine.
# ---------------------------------------------------------------------------

def resolve_row(row: dict) -> dict:
    batch_date, case_number, entity_name = row["batch_date"], row.get("case_number"), row["entity_name"] or ""

    # issue #19744 item 3: a bare digit string (e.g. "36660") is a Lee County
    # RealAuction bidder-registration ID that leaked into
    # multi_county_auctions.winning_bidder BEFORE #19727's isdigit() guard
    # landed on the harvest side (scripts/realauction_winner_harvest.py:287)
    # -- that guard stops NEW numeric writes but does not retroactively clean
    # rows already poisoned, and this pipeline reads winning_bidder as-is via
    # winnerdata.leads.entity_name with no numeric check of its own. classify()
    # would otherwise call it "person" and spend real Tracerfy credits looking
    # up a phone number for a registration ID. Never a real buyer/plaintiff
    # name in this dataset -- short-circuit before any stage/vendor call.
    if entity_name.strip().isdigit():
        evidence = {"identity_type": "unresolved_bidder_id", "reason": "numeric_bidder_id_not_a_name",
                    "auction_parcel_id_excluded": None, "stages": {},
                    "ran_at": datetime.now(timezone.utc).isoformat()}
        return {"status": "complete", "phone": None, "email": None, "provider": None,
                "tier": "NOT AVAILABLE", "dnc": None, "evidence": evidence}

    identity_type = classify(entity_name)
    parcel_id = get_auction_parcel_id(case_number, entity_name)

    lead = {
        "batch_date": batch_date, "case_number": case_number or f"NO_CASE:{row['lead_id']}",
        "winning_bidder": entity_name, "identity_type": identity_type,
        "auction_parcel_id": parcel_id,
        "resolved_principal_name": None, "registered_agent_name": None, "registered_agent_address": None,
    }
    plan = STAGE_PLAN.get(identity_type, STAGE_PLAN["person"])
    evidence = {"identity_type": identity_type, "auction_parcel_id_excluded": parcel_id, "stages": {}}

    stage1_addr = None
    principal_name = entity_name
    phone = email = None
    cross_checked = single_source = False
    gated = False

    for stage in plan:
        if stage == "stage1_identity":
            # issue #19746 "Also report" spot-check: direct person/person_joint
            # buyers ("STEVE A MARSH", "Jean rosalva", "Dorin Birta") also hit
            # the same word-order problem as principal names -- confirmed live
            # 2026-09-02: "Dorin Birta" misses, but swapped "Birta Dorin" hits
            # a real fl_parcels record (BIRTA DORIN, 11412 JOHNSTONE DR,
            # PENSACOLA). Trivial reuse of the same dual-order helper (item 1/3
            # fix) for identity_type in (person, person_joint) only -- a
            # business/LLC name has no person-order ambiguity to swap.
            if identity_type in ("person", "person_joint"):
                r, matched_as = stage1_self_match_both_orders(lead, entity_name)
                r = dict(r, matched_as=matched_as)
            else:
                r = run_stage1_identity(lead)
            evidence["stages"]["stage1_identity"] = r
            if r.get("outcome") == "hit":
                if is_po_box(r):
                    r["po_box_excluded"] = True
                else:
                    stage1_addr = r
                    single_source = True

        elif stage == "stage2_sunbiz_chain":
            r = run_stage2_sunbiz_chain(lead)
            evidence["stages"]["stage2_sunbiz_chain"] = r

            # issue #19746 item 2: the resolved principal can itself be
            # another business (FLORIDA INVESTORS CAPITAL LLC -> "Casscap,
            # LLC"; Mr America Export LLC -> "Tokinvest LLC") -- Tracerfy got
            # a business name + the wrong (LLC-parcel) address for both and
            # missed. Hop stage2 once more on that LLC name (max depth 2
            # total stage2 calls) before giving up.
            chain, depth, current = [], 0, r
            while current.get("outcome") == "hit" and current.get("principal_name") and depth < 2:
                candidate = normalize_person_name(current["principal_name"])
                depth += 1
                chain.append(candidate)
                principal_name = candidate
                lead["resolved_principal_name"] = principal_name
                if classify(candidate) == "business" and depth < 2:
                    hop_lead = dict(lead, winning_bidder=candidate, resolved_entity_name=candidate,
                                     resolved_principal_name=None)
                    current = run_stage2_sunbiz_chain(hop_lead)
                    evidence["stages"][f"stage2_sunbiz_chain_hop{depth}"] = current
                else:
                    break
            if chain:
                evidence["principal_chain"] = chain

            # issue #19746 item 1 (the P0 root cause): once the chain lands
            # on a PERSON, ALWAYS attempt the fl_parcels self-match on that
            # person's own name -- not conditioned on "only if the LLC-level
            # stage1 already missed" (the old guard). Gayatri Parivar LLC ->
            # Shilpa Shah: the LLC-level stage1 HIT (its own registered
            # address), so the old code never tried the person, and Tracerfy
            # got the LLC's address instead of Shilpa Shah's own home. The
            # LLC-parcel address (stage1_addr, already PO-Box-filtered above)
            # is kept only as a fallback anchor if the person self-match misses.
            if principal_name != entity_name and classify(principal_name) != "business":
                pr, matched_as = stage1_self_match_both_orders(lead, principal_name)
                evidence["stages"]["stage1_identity_principal"] = dict(pr, matched_as=matched_as)
                if pr.get("outcome") == "hit" and not is_po_box(pr):
                    stage1_addr = pr
                    single_source = True

        elif stage == "stage3_skiptrace":
            target_addr = stage1_addr
            r = run_stage3_skiptrace(lead, principal_name, target_addr)
            evidence["stages"]["stage3_skiptrace"] = r
            if r.get("outcome") == "skipped_gate":
                gated = True
                break
            if r.get("outcome") == "error":
                evidence["stage3_error"] = True
                return {"status": "error", "phone": None, "email": None, "provider": None,
                        "tier": "NOT AVAILABLE", "dnc": None, "evidence": evidence}
            if r.get("outcome") == "hit":
                phone, email = r.get("phone"), r.get("email")
                cross_checked = bool(stage1_addr) and bool(phone or email)
                single_source = True

        elif stage == "stage4_web":
            continue  # business_website discovery -- not a seller_digest column target, skip

        elif stage == "stage5_dnc":
            continue  # handled below with the polling dnc_scrub(), not ff_billable_loop's non-polling version

    if gated:
        return {"status": "gated", "phone": None, "email": None, "provider": None,
                "tier": "NOT AVAILABLE", "dnc": None, "evidence": evidence}

    tier = tier_for_evidence(cross_checked, single_source) if (stage1_addr or phone or email) else "NOT AVAILABLE"

    if phone:
        dnc = dnc_scrub(phone)
        evidence["dnc_scrub"] = dnc
        if dnc.get("dnc") is None:
            return {"status": "skipped_dnc_incomplete", "phone": None, "email": None, "provider": None,
                    "tier": "NOT AVAILABLE", "dnc": dnc, "evidence": evidence}
        if dnc.get("dnc") is True:
            evidence["dnc_flagged"] = True
        return {"status": "complete", "phone": phone, "email": email, "provider": "tracerfy",
                "tier": tier, "dnc": dnc, "evidence": evidence}

    return {"status": "complete", "phone": None, "email": email, "provider": ("tracerfy" if email else None),
            "tier": tier, "dnc": None, "evidence": evidence}


def main():
    if not BATCH_DATE:
        print("ERROR: BATCH_DATE env var required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(1)

    tracerfy_key_status = "present" if TRACERFY_KEY else "ABSENT"
    sb_key_status = "present" if os.environ.get("SUPABASE_SERVICE_ROLE_KEY") else "ABSENT"
    print(f"seller_digest enrichment: batch_date={BATCH_DATE} run_id={RUN_ID} rerun_paid_lookups={RERUN_PAID_LOOKUPS}")
    print(f"  env check: TRACERFY_API_KEY={tracerfy_key_status} tracerfy_client.TRACERFY_KEY={'present' if tracerfy_client.TRACERFY_KEY else 'ABSENT'} SUPABASE_SERVICE_ROLE_KEY={sb_key_status}")

    # issue #19729 T3: a row stuck at 'running' from a prior crashed run must
    # not block this run from claiming it.
    reset = sql(f"""
        update winnerdata.seller_digest_leads
        set row_enrichment_status = 'not_started', updated_at = now()
        where batch_date = date '{esc(BATCH_DATE)}' and row_enrichment_status = 'running'
        returning lead_id
    """)
    if reset:
        print(f"  reset {len(reset)} stuck 'running' row(s) to 'not_started'.")

    set_batch_enrichment_status(BATCH_DATE, "running", run_id=RUN_ID)
    try:
        rows = sql(f"""
            select lead_id, entity_name, county, case_number, sale_type,
                   property_address, phone, email, row_enrichment_status
            from winnerdata.seller_digest_leads
            where batch_date = date '{esc(BATCH_DATE)}'
            order by lead_id
        """)
        if not rows:
            raise RuntimeError(f"No seller_digest_leads rows found for {BATCH_DATE}. "
                               "Run the build step first (winnerdata_daily_winner_ff_digest.py).")

        print(f"  {len(rows)} lead(s) on file for {BATCH_DATE}.")
        results = []
        stopped_on_daily_cap = False

        for r in rows:
            r["batch_date"] = BATCH_DATE
            lead_id = r["lead_id"]
            already_resolved = bool(r.get("phone") or r.get("email"))
            if already_resolved and not RERUN_PAID_LOOKUPS:
                print(f"  [{lead_id}] already has a resolved contact -- skipping (RERUN_PAID_LOOKUPS=1 to override)")
                results.append({"lead_id": lead_id, "skipped": True, "reason": "already_resolved"})
                continue
            if stopped_on_daily_cap:
                results.append({"lead_id": lead_id, "skipped": True, "reason": "daily_cap_reached_before_this_row"})
                continue

            set_row_enrichment_status(BATCH_DATE, lead_id, "running")
            try:
                out = resolve_row(r)
            except Exception as e:
                # issue #19729 T3: one row's unhandled exception must not
                # abort the batch -- isolate it and keep going.
                print(f"  [{lead_id}] UNHANDLED EXCEPTION: {type(e).__name__}: {e}", file=sys.stderr)
                try:
                    persist_row(BATCH_DATE, lead_id, "error", None, None, None, "NOT AVAILABLE", None,
                                {"unhandled_exception": f"{type(e).__name__}: {str(e)[:400]}",
                                 "ran_at": datetime.now(timezone.utc).isoformat()})
                except Exception as e2:
                    print(f"  [{lead_id}] ALSO failed to persist the error state: {e2}", file=sys.stderr)
                results.append({"lead_id": lead_id, "status": "error", "reason": str(e)[:200]})
                continue

            if out["status"] == "gated":
                # Daily Tracerfy/Bright Data credit ceiling (public.ff_ledger_spend,
                # 100 combined units/UTC day) -- a genuine, already-documented
                # resource ceiling, not a bug. Leave the row exactly where it
                # was (not_started) so tomorrow's run picks it up fresh, and
                # stop spending for the rest of this run.
                set_row_enrichment_status(BATCH_DATE, lead_id, "not_started")
                print(f"  [{lead_id}] Tracerfy daily credit ceiling reached -- leaving not_started, stopping further vendor calls this run.")
                results.append({"lead_id": lead_id, "status": "not_started", "reason": "daily_credit_ceiling"})
                stopped_on_daily_cap = True
                continue

            out["evidence"]["ran_at"] = datetime.now(timezone.utc).isoformat()
            persist_row(BATCH_DATE, lead_id, out["status"], out["phone"], out["email"], out["provider"],
                        out["tier"], out["dnc"], out["evidence"])
            print(f"  [{lead_id}] {r['entity_name']!r}: "
                  f"identity={out['evidence'].get('identity_type')} status={out['status']} "
                  f"phone={'YES' if out['phone'] else 'no'} email={'YES' if out['email'] else 'no'} tier={out['tier']}")
            results.append({"lead_id": lead_id, "status": out["status"],
                             "contact_found": bool(out["phone"] or out["email"])})

        complete = sum(1 for r in results if r.get("status") == "complete")
        contact_found = sum(1 for r in results if r.get("contact_found"))
        errored = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("skipped"))
        print(json.dumps({
            "batch_date": BATCH_DATE, "run_id": RUN_ID, "total": len(rows),
            "processed": len(rows) - skipped, "complete": complete, "contact_found": contact_found,
            "errored": errored, "skipped": skipped, "stopped_on_daily_cap": stopped_on_daily_cap,
        }, indent=2))

        verify = sql(f"""
            select row_enrichment_status, count(*) as n,
                   count(*) filter (where phone is not null or email is not null) as with_contact
            from winnerdata.seller_digest_leads
            where batch_date = date '{esc(BATCH_DATE)}'
            group by row_enrichment_status
            order by row_enrichment_status
        """)
        print("DB verification:", json.dumps(verify, indent=2))

        any_running_left = any(v["row_enrichment_status"] == "running" for v in verify)
        if any_running_left:
            # Should be unreachable (every row is set to a terminal status
            # above, in either the success or the except path) -- if it
            # happens anyway, the batch is honestly 'failed', not 'complete'.
            raise RuntimeError("rows remain in 'running' after the pass completed -- persist path has a gap")

        still_not_started = next((v["n"] for v in verify if v["row_enrichment_status"] == "not_started"), 0)
        # 'not_started' alone undercounts real remaining work: a row can be
        # stuck at a STALE 'complete' from before this fix (old wrong-anchor
        # NO_MATCH) that this run's daily-cap stop never reached in lead_id
        # order -- it will still be correctly reprocessed on the next run
        # (rerun_paid_lookups only skips rows with a real resolved contact),
        # but it is not honestly "done" today either. with_contact is 0 for
        # every status bucket in that case, so summing across all buckets
        # gives the true outstanding count.
        total_rows = sum(v["n"] for v in verify)
        with_contact_total = sum(v["with_contact"] for v in verify)
        still_unresolved = total_rows - with_contact_total
        if still_not_started or (stopped_on_daily_cap and still_unresolved):
            # Honesty Protocol: do not claim 'complete' while real work
            # remains outstanding. stopped_on_daily_cap is the expected
            # cause (ff_ledger_spend's 100 combined units/UTC day cap,
            # shared with ff_billable_loop.py) -- resumable tomorrow by
            # re-running this same script with the same BATCH_DATE, since
            # rows without a resolved phone/email are always reprocessed.
            reason = ("stopped at the shared Tracerfy/BrightData daily credit ceiling "
                      "(public.ff_ledger_spend, 100 combined units/UTC day) -- "
                      f"{still_unresolved} of {total_rows} row(s) still lack a resolved contact "
                      f"({still_not_started} explicitly not_started), resumable after UTC midnight"
                      if stopped_on_daily_cap else
                      f"{still_not_started} row(s) left not_started for an unknown reason -- investigate before re-running")
            set_batch_enrichment_status(BATCH_DATE, "failed", run_id=RUN_ID, error=reason)
        else:
            set_batch_enrichment_status(BATCH_DATE, "complete", run_id=RUN_ID)

    except Exception as e:
        set_batch_enrichment_status(BATCH_DATE, "failed", run_id=RUN_ID, error=str(e))
        raise


if __name__ == "__main__":
    main()
