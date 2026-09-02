#!/usr/bin/env python3
"""Issue #19712 -- FF billable-loop: per-lead enrichment state machine.

Replaces the single-pass FF enrichment (a lead that missed once was labeled
NOT AVAILABLE and never touched again) with a resumable loop that keeps
working a lead through stage1_identity -> stage2_sunbiz_chain ->
stage3_skiptrace -> stage4_web -> stage5_dnc until it meets the 2-of-3
billable rule or every applicable stage has been genuinely exhausted.

Writes via the Supabase Management API SQL endpoint (winnerdata is not in
this project's PostgREST-exposed schema list -- see scripts/winnerdata_
pipeline.py's own docstring, the documented working pattern for this
schema). Reads against public.fl_parcels go over PostgREST, which does
expose the public schema.

Reuses, does not reimplement (SEARCH-FIRST mandate):
  - scripts/identity_cascade.py       resolve_identity() -- Exa/mirror/
                                       Bright Data/Playwright Sunbiz cascade
  - scripts/tracerfy_client.py        trace_lead(), dnc_scrub()
  - scripts/ff_credit_ledger.py       spend() -- the pre-call credit gate

Stage applicability by identity_type (per docs/intent/19712.md):
  person / person_joint      -> stage1, stage3, stage4, stage5
                                 (stage2 only if a Sunbiz officer link is
                                 already on file -- not attempted fresh here)
  business                   -> stage1, stage2, stage3, stage4, stage5
  land_trust_unpierceable    -> stage2, stage3, stage4, stage5
                                 (stage1 not applicable -- the trustee, not
                                 a self-match, is the identity)

EXHAUSTED is set only once every applicable stage for this lead's
identity_type has a ledger row AND none of those rows is 'skipped_gate'
(a gate skip always forces retry_due -- a credit ceiling is not evidence
of a dead end). This is stricter than "one miss" per the issue body.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import ff_credit_ledger  # noqa: E402
import identity_cascade  # noqa: E402
import tracerfy_client  # noqa: E402

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
RUN_ID = f"ff_billable_loop_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"

MAX_LEADS_PER_TICK = 40  # per intent DoD 6 -- ungated cap until quota_gate_check('engineering') returns a reading

STAGE_PLAN = {
    "person": ["stage1_identity", "stage3_skiptrace", "stage4_web", "stage5_dnc"],
    "person_joint": ["stage1_identity", "stage3_skiptrace", "stage4_web", "stage5_dnc"],
    "business": ["stage1_identity", "stage2_sunbiz_chain", "stage3_skiptrace", "stage4_web", "stage5_dnc"],
    "land_trust_unpierceable": ["stage2_sunbiz_chain", "stage3_skiptrace", "stage4_web", "stage5_dnc"],
}

CONFIDENCE_TIERS = (
    "VERIFIED·PRIMARY", "VERIFIED·CROSS-CHECKED",
    "LIKELY·SINGLE SOURCE", "UNCONFIRMED CLAIM", "NOT AVAILABLE",
)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def mgmt_sql(query: str, timeout: int = 90, retries: int = 3):
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set")
    req = urllib.request.Request(
        MGMT_URL, data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        },
        method="POST",
    )
    last_exc = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "message" in body:
                raise RuntimeError(f"{body['message']} -- query: {query[:300]}")
            return body
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
    raise last_exc


def pg_rest(table: str, params: str, timeout: int = 30) -> list[dict]:
    url = f"{SB_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"pg_rest {table} HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")
        return []


def _sql_str(v) -> str:
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def _sql_jsonb(v) -> str:
    return _sql_str(json.dumps(v, default=str)) + "::jsonb"


# ---------------------------------------------------------------------------
# Ledger + claim protocol
# ---------------------------------------------------------------------------

def log_attempt(batch_date: str, case_number: str, stage: str, provider: str,
                 input_obj: dict, output_obj: dict, outcome: str, credits_used: int = 0) -> None:
    assert outcome in ("hit", "miss", "error", "skipped_gate")
    mgmt_sql(f"""
        insert into winnerdata.ff_enrichment_attempts
          (batch_date, case_number, stage, provider, input_json, output_json, outcome, credits_used, run_id)
        values
          ({_sql_str(batch_date)}, {_sql_str(case_number)}, {_sql_str(stage)}, {_sql_str(provider)},
           {_sql_jsonb(input_obj)}, {_sql_jsonb(output_obj)}, {_sql_str(outcome)}, {credits_used}, {_sql_str(RUN_ID)});
    """)


def claim_next(batch_date: str, case_number: str, next_status: str) -> bool:
    """Shard claim protocol per docs/intent/19712.md: only advances a lead
    currently in ('not_started','retry_due'). Returns True if this process
    now owns the row."""
    out = mgmt_sql(f"""
        update winnerdata.ff_batch_leads
        set row_enrichment_status = {_sql_str(next_status)}
        where batch_date = {_sql_str(batch_date)} and case_number = {_sql_str(case_number)}
          and row_enrichment_status in ('not_started','retry_due')
        returning case_number;
    """)
    return bool(out)


def advance(batch_date: str, case_number: str, status: str, **fields) -> None:
    sets = [f"row_enrichment_status = {_sql_str(status)}"]
    for k, v in fields.items():
        if k in ("evidence_ledger", "enrichment_provider_status_json", "phone_email_evidence_json"):
            sets.append(f"{k} = {_sql_jsonb(v)}")
        else:
            sets.append(f"{k} = {_sql_str(v)}")
    mgmt_sql(f"""
        update winnerdata.ff_batch_leads
        set {', '.join(sets)}
        where batch_date = {_sql_str(batch_date)} and case_number = {_sql_str(case_number)};
    """)


def open_credit_gate(batch_date: str, case_number: str, source: str, balance: dict) -> None:
    gate_key = f"ff_billable_loop_{source}_credits"
    mgmt_sql(f"""
        insert into public.spi_gates (gate_key, title, opened_at, proof)
        values (
          {_sql_str(gate_key)},
          {_sql_str(f'{source} credit ceiling blocking FF billable-loop lead {case_number} ({batch_date})')},
          now(),
          {_sql_str(json.dumps(balance, default=str))}
        )
        on conflict (gate_key) do update set opened_at = excluded.opened_at, proof = excluded.proof;
    """)


# ---------------------------------------------------------------------------
# 2-of-3 evaluation + confidence tiering
# ---------------------------------------------------------------------------

def evaluate_2of3(lead: dict) -> tuple[bool, int]:
    has_addr = bool((lead.get("principal_home_address") or "").strip())
    has_phone = bool((lead.get("phone") or lead.get("individual_phone") or lead.get("business_phone") or "").strip() if any(
        (lead.get(k) or "").strip() for k in ("phone", "individual_phone", "business_phone")) else False)
    has_email = any((lead.get(k) or "").strip() for k in ("email", "individual_email", "business_email"))
    n = int(has_addr) + int(has_phone) + int(has_email)
    return n >= 2, n


def tier_for_evidence(cross_checked: bool, single_source: bool) -> str:
    if cross_checked:
        return "VERIFIED·CROSS-CHECKED"
    if single_source:
        return "LIKELY·SINGLE SOURCE"
    return "UNCONFIRMED CLAIM"


# ---------------------------------------------------------------------------
# Stage 1 -- identity (fl_parcels self-match; free, internal DB only)
# ---------------------------------------------------------------------------

def run_stage1_identity(lead: dict) -> dict:
    name = lead["winning_bidder"]
    # mgmt_sql (not PostgREST): the statewide trigram index
    # (idx_fl_parcels_ownname_trgm, migration 20260824_ff_own_name_trgm_index)
    # is built on upper(own_name), so only a query using that exact
    # expression hits the index on a 10.5M-row table -- PostgREST's
    # own_name=ilike.* filter does not match the expression and times out
    # (confirmed live 2026-09-02, 30s timeout on a single lookup).
    rows = mgmt_sql(f"""
        select own_name, own_addr1, own_city, own_state, own_zipcd, parcel_id
        from public.fl_parcels
        where upper(own_name) like upper({_sql_str('%' + name.strip() + '%')})
          and own_addr1 is not null
        limit 10;
    """)
    candidates = [r for r in rows if r.get("parcel_id") != lead.get("auction_parcel_id") and r.get("own_addr1")]
    input_obj = {"own_name_query": name, "exclude_parcel_id": lead.get("auction_parcel_id")}
    if candidates:
        best = candidates[0]
        addr = ", ".join(filter(None, [best.get("own_addr1"), best.get("own_city"), best.get("own_state"), best.get("own_zipcd")]))
        log_attempt(lead["batch_date"], lead["case_number"], "stage1_identity", "fl_parcels_self_match",
                    input_obj, {"matched_addr": addr, "candidate_count": len(candidates)}, "hit")
        return {"outcome": "hit", "principal_home_address": addr, "city": best.get("own_city"),
                "state": best.get("own_state"), "zip": best.get("own_zipcd")}
    log_attempt(lead["batch_date"], lead["case_number"], "stage1_identity", "fl_parcels_self_match",
                input_obj, {"candidate_count": 0}, "miss")
    return {"outcome": "miss"}


# ---------------------------------------------------------------------------
# Stage 2 -- Sunbiz chain (business / land_trust). Local table first (free),
# live Exa cascade fallback (real Exa spend, already-adopted tool).
# ---------------------------------------------------------------------------

def run_stage2_sunbiz_chain(lead: dict) -> dict:
    entity = lead.get("resolved_entity_name") or lead["winning_bidder"]
    batch_date, case_number = lead["batch_date"], lead["case_number"]

    if lead["identity_type"] == "land_trust_unpierceable":
        ra = (lead.get("registered_agent_name") or "").upper()
        is_attorney = "ESQ" in ra or "ESQUIRE" in ra or "ATTORNEY" in ra
        if is_attorney and lead.get("registered_agent_address"):
            siblings = mgmt_sql(f"""
                select batch_date, case_number, winning_bidder, resolved_principal_name
                from winnerdata.ff_batch_leads
                where registered_agent_address = {_sql_str(lead["registered_agent_address"])}
                  and case_number <> {_sql_str(case_number)}
                  and resolved_principal_name is not null;
            """)
            if siblings:
                sib = siblings[0]
                log_attempt(batch_date, case_number, "stage2_sunbiz_chain", "sibling_trust_correlation",
                            {"registered_agent_address": lead["registered_agent_address"]},
                            {"sibling_case": sib["case_number"], "named_principal": sib["resolved_principal_name"]}, "hit")
                return {"outcome": "hit", "principal_name": sib["resolved_principal_name"]}
            log_attempt(batch_date, case_number, "stage2_sunbiz_chain", "sibling_trust_correlation",
                        {"registered_agent_address": lead.get("registered_agent_address")},
                        {"reason": "attorney_trustee_shield", "sibling_count": 0}, "miss")
            return {"outcome": "miss", "reason": "attorney_trustee_shield"}
        log_attempt(batch_date, case_number, "stage2_sunbiz_chain", "attorney_trustee_check",
                    {"registered_agent_name": lead.get("registered_agent_name")},
                    {"reason": "attorney_trustee_shield_no_ra_address"}, "miss")
        return {"outcome": "miss", "reason": "attorney_trustee_shield"}

    # business
    if lead.get("resolved_principal_name") and lead["resolved_principal_name"] not in (None, entity):
        principal = lead["resolved_principal_name"]
        log_attempt(batch_date, case_number, "stage2_sunbiz_chain", "existing_principal_on_file",
                    {"entity": entity}, {"principal_name": principal}, "hit")
        return {"outcome": "hit", "principal_name": principal}

    try:
        result = identity_cascade.resolve_identity(entity)
    except Exception as e:
        log_attempt(batch_date, case_number, "stage2_sunbiz_chain", "identity_cascade",
                    {"entity": entity}, {"error": str(e)}, "error")
        return {"outcome": "error"}

    outcome = "hit" if result.get("resolved") and result.get("principal_name") else "miss"
    log_attempt(batch_date, case_number, "stage2_sunbiz_chain", f"identity_cascade:{result.get('source_step') or 'exhausted'}",
                {"entity": entity}, {k: result.get(k) for k in ("resolved", "principal_name", "source_step", "sources_tried")}, outcome)
    if outcome == "hit":
        return {"outcome": "hit", "principal_name": result["principal_name"]}
    return {"outcome": "miss"}


# ---------------------------------------------------------------------------
# Stage 3 -- skip trace (Tracerfy, credit-gated)
# ---------------------------------------------------------------------------

def _is_insufficient_credits(err_detail: dict) -> bool:
    """Tracerfy's real signature for a balance ceiling, confirmed live
    2026-09-02: HTTP 402 with 'Insufficient credits' in the body. This is
    checked IN ADDITION to ff_credit_ledger.spend() (a same-day call-count
    throttle, not a true account-balance check) because the account can be
    at 0 real credits while the daily counter still has headroom -- exactly
    the state observed this session (15/100 calls used, 0 Tracerfy credits)."""
    return err_detail.get("http_status") == 402 or "insufficient credit" in str(err_detail.get("response_body", "")).lower()


def run_stage3_skiptrace(lead: dict, target_name: str, target_addr: dict | None) -> dict:
    batch_date, case_number = lead["batch_date"], lead["case_number"]
    grant = ff_credit_ledger.spend("tracerfy", 1)
    if not grant.get("granted"):
        open_credit_gate(batch_date, case_number, "tracerfy", grant)
        log_attempt(batch_date, case_number, "stage3_skiptrace", "tracerfy_enhanced_trace",
                    {"target_name": target_name, "target_addr": target_addr}, grant, "skipped_gate")
        return {"outcome": "skipped_gate"}
    if not target_addr or not target_addr.get("principal_home_address"):
        log_attempt(batch_date, case_number, "stage3_skiptrace", "tracerfy_enhanced_trace",
                    {"target_name": target_name}, {"reason": "no_mailing_address_to_trace"}, "miss")
        return {"outcome": "miss"}
    # issue #19750: target_name is natural "First Last" order when it came from
    # Sunbiz resolution (lead["resolved_principal_name"], normalized by
    # identity_cascade.normalize_person_name()); it's surname-first when it's
    # the raw fl_parcels/auction winning_bidder. tracerfy_client needs to know
    # which, or it flips a natural-order name backwards -> false NO_MATCH.
    resp = tracerfy_client.enhanced_trace(
        target_name, target_addr.get("addr1", target_addr["principal_home_address"]),
        target_addr.get("city", ""), target_addr.get("state", "FL"), target_addr.get("zip", ""),
        name_is_natural_order=bool(lead.get("resolved_principal_name")),
    )
    if isinstance(resp, tuple):
        _, err_detail = resp
        if _is_insufficient_credits(err_detail):
            open_credit_gate(batch_date, case_number, "tracerfy", err_detail)
            log_attempt(batch_date, case_number, "stage3_skiptrace", "tracerfy_enhanced_trace",
                        {"target_name": target_name}, err_detail, "skipped_gate")
            return {"outcome": "skipped_gate"}
        log_attempt(batch_date, case_number, "stage3_skiptrace", "tracerfy_enhanced_trace",
                    {"target_name": target_name}, err_detail, "error")
        return {"outcome": "error"}
    parsed = tracerfy_client._parse_trace_response(resp)
    outcome = "hit" if parsed.get("phone") or parsed.get("email") else "miss"
    log_attempt(batch_date, case_number, "stage3_skiptrace", "tracerfy_enhanced_trace",
                {"target_name": target_name}, parsed, outcome, credits_used=1)
    return {"outcome": outcome, "phone": parsed.get("phone"), "email": parsed.get("email")}


# ---------------------------------------------------------------------------
# Stage 4 -- web (Exa; business email/phone/site/LinkedIn)
# ---------------------------------------------------------------------------

def run_stage4_web(lead: dict) -> dict:
    batch_date, case_number = lead["batch_date"], lead["case_number"]
    if lead["identity_type"] not in ("business",):
        log_attempt(batch_date, case_number, "stage4_web", "exa_search",
                    {"reason": "not_applicable_for_identity_type"}, {}, "miss")
        return {"outcome": "miss"}
    entity = lead.get("resolved_entity_name") or lead["winning_bidder"]
    try:
        results = identity_cascade.exa_search(f"{entity} Florida LLC contact phone email", num_results=3)
    except Exception as e:
        log_attempt(batch_date, case_number, "stage4_web", "exa_search", {"entity": entity}, {"error": str(e)}, "error")
        return {"outcome": "error"}
    outcome = "hit" if results else "miss"
    log_attempt(batch_date, case_number, "stage4_web", "exa_search", {"entity": entity},
                {"result_count": len(results), "urls": [r.get("url") for r in results[:3]]}, outcome)
    if results:
        return {"outcome": "hit", "business_website": results[0].get("url")}
    return {"outcome": "miss"}


# ---------------------------------------------------------------------------
# Stage 5 -- DNC scrub (Tracerfy, credit-gated)
# ---------------------------------------------------------------------------

def run_stage5_dnc(lead: dict, phone: str | None) -> dict:
    batch_date, case_number = lead["batch_date"], lead["case_number"]
    if not phone:
        log_attempt(batch_date, case_number, "stage5_dnc", "tracerfy_dnc_scrub", {}, {"reason": "no_phone_on_file"}, "miss")
        return {"outcome": "miss"}
    grant = ff_credit_ledger.spend("tracerfy", 1)
    if not grant.get("granted"):
        open_credit_gate(batch_date, case_number, "tracerfy", grant)
        log_attempt(batch_date, case_number, "stage5_dnc", "tracerfy_dnc_scrub", {"phone": phone}, grant, "skipped_gate")
        return {"outcome": "skipped_gate"}
    resp = tracerfy_client.dnc_scrub([phone])
    if isinstance(resp, tuple):
        _, err_detail = resp
        if _is_insufficient_credits(err_detail):
            open_credit_gate(batch_date, case_number, "tracerfy", err_detail)
            log_attempt(batch_date, case_number, "stage5_dnc", "tracerfy_dnc_scrub", {"phone": phone}, err_detail, "skipped_gate")
            return {"outcome": "skipped_gate"}
        log_attempt(batch_date, case_number, "stage5_dnc", "tracerfy_dnc_scrub", {"phone": phone}, err_detail, "error")
        return {"outcome": "error"}
    log_attempt(batch_date, case_number, "stage5_dnc", "tracerfy_dnc_scrub", {"phone": phone}, resp, "hit", credits_used=1)
    return {"outcome": "hit", "dnc_result": resp}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def fetch_ledger_stages(batch_date: str, case_number: str) -> dict[str, list[str]]:
    rows = mgmt_sql(f"""
        select stage, outcome from winnerdata.ff_enrichment_attempts
        where batch_date = {_sql_str(batch_date)} and case_number = {_sql_str(case_number)} and run_id = {_sql_str(RUN_ID)};
    """)
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["stage"], []).append(r["outcome"])
    return out


def process_lead(lead: dict) -> str:
    batch_date, case_number = lead["batch_date"], lead["case_number"]
    identity_type = lead.get("identity_type") or "person"
    plan = STAGE_PLAN.get(identity_type, STAGE_PLAN["person"])

    stage1_addr: dict | None = None
    principal_name = lead.get("resolved_principal_name") or lead["winning_bidder"]
    phone_found: str | None = None
    cross_checked = False
    single_source = False

    for idx, stage in enumerate(plan):
        if idx == 0:
            # Shard claim protocol (docs/intent/19712.md): gate ONLY the
            # initial pickup of a not_started/retry_due lead, so a
            # concurrent worker can't grab the same fresh lead. Once this
            # process owns it, later stages in this same pass are plain
            # advances (below) -- re-applying the not_started/retry_due
            # guard on every stage was a bug: it made every lead's second
            # stage fail to claim, since the first stage had already moved
            # row_enrichment_status off of 'not_started' (confirmed live
            # 2026-09-02, run ff_billable_loop_20260902T053206Z_3974393d --
            # 21/22 leads stopped after stage 1 with "already claimed
            # elsewhere" even though nothing else was running).
            if not claim_next(batch_date, case_number, stage):
                log(f"  {case_number}: could not claim for {stage} (already claimed elsewhere) -- stopping")
                return "skipped_claim_lost"

        if stage == "stage1_identity":
            r = run_stage1_identity(lead)
            if r["outcome"] == "hit":
                stage1_addr = r
                lead["principal_home_address"] = r["principal_home_address"]
                single_source = True
                advance(batch_date, case_number, stage, principal_home_address=r["principal_home_address"],
                        principal_address_source="fl_parcels_self_match")

        elif stage == "stage2_sunbiz_chain":
            r = run_stage2_sunbiz_chain(lead)
            if r["outcome"] == "hit" and r.get("principal_name"):
                principal_name = r["principal_name"]
                lead["resolved_principal_name"] = principal_name
                advance(batch_date, case_number, stage, resolved_principal_name=principal_name)
            else:
                advance(batch_date, case_number, stage)

        elif stage == "stage3_skiptrace":
            target_addr = stage1_addr or ({"principal_home_address": lead["principal_home_address"],
                                            "addr1": lead["principal_home_address"]}
                                           if lead.get("principal_home_address") else None)
            r = run_stage3_skiptrace(lead, principal_name, target_addr)
            if r["outcome"] == "skipped_gate":
                advance(batch_date, case_number, "retry_due")
                log(f"  {case_number}: stage3 gated (0 Tracerfy credits) -> retry_due")
                return "retry_due_gate"
            if r["outcome"] == "hit":
                if r.get("phone"):
                    lead["phone"] = phone_found = r["phone"]
                if r.get("email"):
                    lead["email"] = r["email"]
                cross_checked = bool(stage1_addr) and bool(r.get("phone") or r.get("email"))
                single_source = True
                advance(batch_date, case_number, stage, phone=lead.get("phone"), email=lead.get("email"),
                        contact_provider="tracerfy_enhanced_trace")
            else:
                advance(batch_date, case_number, stage)

        elif stage == "stage4_web":
            r = run_stage4_web(lead)
            if r["outcome"] == "hit" and r.get("business_website"):
                lead["business_website"] = r["business_website"]
                advance(batch_date, case_number, stage, business_website=r["business_website"],
                        business_website_source="exa_search")
            else:
                advance(batch_date, case_number, stage)

        elif stage == "stage5_dnc":
            r = run_stage5_dnc(lead, phone_found)
            if r["outcome"] == "skipped_gate":
                advance(batch_date, case_number, "retry_due")
                log(f"  {case_number}: stage5 gated (0 Tracerfy credits) -> retry_due")
                return "retry_due_gate"
            advance(batch_date, case_number, stage)

        met, n = evaluate_2of3(lead)
        if met:
            tier = tier_for_evidence(cross_checked, single_source)
            advance(batch_date, case_number, "BILLABLE", contact_confidence=tier, qa_status="CONTACT_ENRICHED")
            log(f"  {case_number}: BILLABLE ({n}/3 fields, tier={tier})")
            return "billable"

    # Every applicable stage attempted. EXHAUSTED only if none was skipped_gate.
    stages_done = fetch_ledger_stages(batch_date, case_number)
    any_gated = any("skipped_gate" in outcomes for outcomes in stages_done.values())
    all_present = all(s in stages_done for s in plan)
    if any_gated or not all_present:
        advance(batch_date, case_number, "retry_due")
        log(f"  {case_number}: stages incomplete/gated -> retry_due")
        return "retry_due"
    tier = tier_for_evidence(cross_checked, single_source) if (stage1_addr or phone_found) else "NOT AVAILABLE"
    advance(batch_date, case_number, "EXHAUSTED", contact_confidence=tier)
    log(f"  {case_number}: EXHAUSTED (all {len(plan)} applicable stages attempted, still <2-of-3)")
    return "exhausted"


def main() -> int:
    rows = mgmt_sql(f"""
        select batch_date, case_number, winning_bidder, identity_type, resolved_entity_name,
               resolved_principal_name, registered_agent_name, registered_agent_address,
               principal_home_address, phone, individual_phone, business_phone,
               email, individual_email, business_email, auction_parcel_id, pin_clean,
               row_enrichment_status
        from winnerdata.ff_batch_leads
        where row_enrichment_status in ('not_started','retry_due')
        order by batch_date, case_number
        limit {MAX_LEADS_PER_TICK};
    """)
    log(f"run_id={RUN_ID} -- {len(rows)} claimable leads (cap {MAX_LEADS_PER_TICK})")
    outcomes: dict[str, int] = {}
    for lead in rows:
        lead = {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in lead.items()}
        log(f"{lead['case_number']} ({lead['identity_type']}): starting")
        try:
            result = process_lead(lead)
        except Exception as e:
            log(f"  {lead['case_number']}: unhandled error {type(e).__name__}: {e}")
            result = "unhandled_error"
        outcomes[result] = outcomes.get(result, 0) + 1
    log(f"run_id={RUN_ID} summary: {json.dumps(outcomes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
