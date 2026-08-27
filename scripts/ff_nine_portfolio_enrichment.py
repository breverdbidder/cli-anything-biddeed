#!/usr/bin/env python3
"""Nine-case FF portfolio enrichment runner (issue #19531, Elementix parity).

Reads the third-party auctions for BATCH_DATE from public.multi_county_auctions,
applies the validated parcel crosswalk (winnerdata.ff_parcel_crosswalk),
resolves investor/operator identity and their full held portfolio, resolves
registered-agent/principal/contact facts from authoritative public records
and Tracerfy, and persists everything into winnerdata.ff_batch_leads with
field-level provenance. Only invoked by winnerdata-nine-ff-enrichment.yml,
itself only dispatched by winnerdata.notify_ff_batch_approved() after Ariel
approves via public.ff_approve_batch() -- see
supabase/migrations/20260827h_winnerdata_ff_nine_case_kpi_and_batch_kind.sql.
Do not run ahead of approval: gating paid Tracerfy/Bright Data lookups
behind approval is the point, not an incidental side effect.

Hard rules (BLANK OVER WRONG, never violate):
  - No find_owner call, ever.
  - Never use the just-purchased auction property's address as a personal
    contact anchor for the buyer -- only a prior-owned mailing address
    (found via an own-name search of public.zw_parcels, excluding the pin
    just won) or a registered-agent/Sunbiz address for the BUSINESS entity
    itself (never asserted as the principal's home address).
  - Every enriched value gets a provenance entry: source, query/match key,
    retrieved_at. Unresolved fields stay null with a reason, never guessed.
  - Idempotent: a row already row_enrichment_status='complete' is not
    re-queried against paid vendors on a re-run unless FORCE_REFRESH=1.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import contact_resolver  # noqa: E402
import ff_credit_ledger  # noqa: E402
import identity_cascade  # noqa: E402
import tracerfy_client  # noqa: E402

import urllib.error
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = os.environ.get("BATCH_DATE", "2026-08-26")
OUT = os.environ.get("OUT", f"/tmp/ff_nine_enrichment_{BATCH_DATE}.json")
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
APIFY_TOKEN = os.environ.get("APIFY_API_KEY", "")
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "") == "1"

BUSINESS_RE = re.compile(
    r"\b(LLC|L\.L\.C|INC|INCORPORATED|CORP|CORPORATION|LTD|LP|LLP|CO|COMPANY|"
    r"TRUST|ESTATE|ENTERPRISES?|HOLDINGS?|GROUP|PARTNERS?|VENTURES?|CAPITAL|"
    r"DEVELOPMENT|INVESTMENTS?|PROPERTIES|MARKETING|BUSINESS|REALTY|HOMES|"
    r"BUILDERS?|CONSTRUCTION)\b",
    re.I,
)
STOPWORDS = {"AND", "ET", "AL", "ETUX", "ETVIR", "JR", "SR", "II", "III", "IV"}


def sql(q: str, timeout: int = 90, retries: int = 3):
    if not SB_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    req = urllib.request.Request(
        MGMT_URL, data=json.dumps({"query": q}).encode(),
        headers={"Authorization": f"Bearer {SB_TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "winnerdata-ff-nine-enrichment/2.0"},
        method="POST",
    )
    last_exc = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read())
            if isinstance(body, dict) and body.get("message"):
                raise RuntimeError(f"{body['message']} -- query: {q[:200]}")
            return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_exc = e
            if attempt < retries - 1:
                import time
                time.sleep(3 * (attempt + 1))
    raise last_exc


def esc(v):
    return str(v).replace("'", "''")


def norm(v):
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


class Raw:
    """Wraps a literal SQL fragment (e.g. now()) so sql_lit() does not quote it."""
    def __init__(self, s):
        self.s = s


def sql_lit(v):
    if v is None:
        return "null"
    if isinstance(v, Raw):
        return v.s
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, dict)):
        return "'" + json.dumps(v, default=str).replace("'", "''") + "'::jsonb"
    return "'" + esc(v) + "'"


def build_update(table: str, fields: dict, where: str) -> str:
    set_clause = ", ".join(f"{k} = {sql_lit(v)}" for k, v in fields.items())
    return f"update {table} set {set_clause} where {where}"


def classify_entity(name: str) -> str:
    return "business" if BUSINESS_RE.search(name or "") else "person"


def name_tokens(s: str) -> set[str]:
    toks = {t for t in re.sub(r"[^A-Za-z ]", " ", s or "").upper().split() if t and t not in STOPWORDS}
    return {t for t in toks if len(t) >= 2}


def split_persons(name: str) -> list[str]:
    parts = re.split(r"\s+AND\s+|&|,", name or "", flags=re.I)
    return [p.strip() for p in parts if p.strip()]


FTS_EXPR = (
    "to_tsvector('english', ((((((coalesce(owner_name, '') || ' ') || coalesce(site_addr, '')) "
    "|| ' ') || coalesce(site_city, '')) || ' ') || coalesce(subdivision, '')))"
)


def _fts_search(query_terms: str, limit: int = 30) -> list[dict]:
    """Uses idx_zw_fts (GIN) -- must match its indexed expression exactly or
    Postgres falls back to a 10M-row sequential scan (confirmed empirically:
    a normalized-regexp equality/ILIKE scan on zw_parcels.owner_name timed
    out; this FTS form returns in <2s)."""
    return sql(f"""
        select owner_addr1, owner_addr2, owner_city, owner_state, owner_zip, pin_clean, owner_name
        from public.zw_parcels
        where {FTS_EXPR} @@ plainto_tsquery('english', '{esc(query_terms)}')
        limit {limit}
    """)


def find_prior_owned_address(winning_bidder: str, exclude_pin_clean: str, entity_type: str):
    """Own-name search of public.zw_parcels for a mailing address independent
    of the just-purchased parcel, via the owner_name+site_addr+site_city+
    subdivision full-text index (idx_zw_fts). Businesses: full-name FTS
    query, kept only if owner_name itself token-matches the target (FTS also
    indexes site_addr/subdivision text, so an address-field-only hit must be
    discarded). Persons: per-individual FTS query, same owner_name-token
    verification. Address chosen by cross-corroboration count. Returns
    (address_dict_or_None, corroborating_row_count, method_str)."""
    candidates = []
    if entity_type == "business":
        target_toks = name_tokens(winning_bidder)
        if not target_toks:
            return None, 0, "no_target_name"
        rows = _fts_search(winning_bidder)
        candidates = [r for r in rows if r.get("pin_clean") != exclude_pin_clean and target_toks <= name_tokens(r.get("owner_name"))]
        method = "zw_parcels_fts_ownname_exact_token_verified"
    else:
        method = "zw_parcels_fts_multiperson_ownname_search"
        for person in split_persons(winning_bidder):
            toks = name_tokens(person)
            if len(toks) < 2:
                continue
            rows = _fts_search(person)
            candidates.extend(r for r in rows if r.get("pin_clean") != exclude_pin_clean and toks <= name_tokens(r.get("owner_name")))

    if not candidates:
        return None, 0, method

    def key(r):
        return (norm(r.get("owner_addr1")), norm(r.get("owner_city")), (r.get("owner_state") or "").upper(), norm(r.get("owner_zip")))

    valid = [r for r in candidates if r.get("owner_addr1")]
    if not valid:
        return None, 0, method
    counts = Counter(key(r) for r in valid)
    best_key, best_count = counts.most_common(1)[0]
    best_row = next(r for r in valid if key(r) == best_key)
    return best_row, best_count, method


def portfolio_snapshot(winning_bidder: str) -> dict:
    target = norm(winning_bidder)
    rows = sql(f"""
        select owner_key, entity_name_raw, county, parcel_id, address, dor_uc, no_buldng, jv,
               coastal_flood_indicator, acquisition_source, case_number
        from winnerdata.owner_portfolio
        where upper(regexp_replace(coalesce(entity_name_raw,''),'[^A-Z0-9]','','g')) = '{esc(target)}'
        order by county, parcel_id
    """) if target else []
    if not rows:
        # Absence of evidence is not evidence of zero holdings: winnerdata.owner_portfolio
        # is populated per-batch (see scripts/skiptrace_20260825_portfolio_batch.py), not a
        # live comprehensive scan -- zero matching rows here means "not yet processed for
        # this buyer," not "confirmed to own nothing else." Never report 0 as if verified.
        return {
            "property_count": None, "county_count": None, "total_jv": None, "total_buildings": None,
            "dor_mix": {}, "acquisition_source_mix": {}, "properties": [], "counties": [],
            "coverage": "no_owner_portfolio_coverage_for_this_entity",
        }
    dor_mix, acq_mix = Counter(), Counter()
    total_jv, total_buildings = 0.0, 0
    for r in rows:
        dor_mix[r.get("dor_uc") or "unknown"] += 1
        acq_mix[r.get("acquisition_source") or "unknown"] += 1
        total_jv += float(r["jv"]) if r.get("jv") not in (None, "") else 0.0
        total_buildings += int(r["no_buldng"]) if r.get("no_buldng") not in (None, "") else 0
    counties = sorted({r["county"] for r in rows if r.get("county")})
    return {
        "property_count": len(rows), "county_count": len(counties), "total_jv": total_jv,
        "total_buildings": total_buildings, "dor_mix": dict(dor_mix), "acquisition_source_mix": dict(acq_mix),
        "properties": rows, "counties": counties,
    }


def bundle_flags(portfolio: dict) -> dict:
    pc = portfolio["property_count"]
    if pc is None:
        return {
            "umbrella_opportunity": None, "master_policy_opportunity": None,
            "commercial_bop_opportunity": None, "flood_opportunity": "unknown_no_owner_portfolio_coverage",
        }
    commercial = any((p.get("dor_uc") or "").startswith(("01", "02")) or (p.get("no_buldng") or 0) >= 3 for p in portfolio["properties"])
    coastal = any(p.get("coastal_flood_indicator") not in (None, "UNKNOWN") for p in portfolio["properties"])
    return {
        "umbrella_opportunity": pc >= 2,
        "master_policy_opportunity": pc >= 5,
        "commercial_bop_opportunity": commercial,
        "flood_opportunity": "flagged" if coastal else ("unknown_no_coverage" if pc else "not_applicable"),
    }


def existing_row(auction_id: str) -> dict | None:
    rows = sql(f"select * from winnerdata.ff_batch_leads where batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}' limit 1")
    return rows[0] if rows else None


def set_batch_status(status: str, error: str | None = None):
    fields = {"enrichment_status": status, "updated_at": Raw("now()")}
    if status == "running":
        fields["enrichment_started_at"] = Raw("now()")
        fields["enrichment_error"] = None
    if status in ("complete", "failed"):
        fields["enrichment_completed_at"] = Raw("now()")
    if status == "failed":
        fields["enrichment_error"] = (error or "")[:500]
    sql(build_update("winnerdata.ff_batches", fields, f"batch_date = date '{esc(BATCH_DATE)}'"))


def enrich_one(a: dict, crosswalk: dict, parcel: dict | None) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    winning_bidder = a["winning_bidder"]
    entity_type = classify_entity(winning_bidder)
    provenance = {}
    qa_errors = []

    fields = {
        "parcel_match_method": crosswalk["match_method"],
        "parcel_match_confidence": "verified" if crosswalk["match_method"] == "validated_normalization" else "probable",
        "parcel_source": "public.zw_parcels",
        "parcel_source_updated_at": parcel.get("updated_at") if parcel else None,
        "auction_url": a.get("auction_url"),
        "source_url": a.get("source_url"),
        "identity_type": "business" if entity_type == "business" else "individual",
        "resolved_entity_name": winning_bidder,
        "row_enrichment_status": "running",
        "freshness_checked_at": Raw("now()"),
    }
    provenance["parcel"] = {"source": "public.zw_parcels", "match_key": "pin_clean", "retrieved_at": now_iso}

    registered_agent_name = registered_agent_address = None
    principal_name = None
    identity_confidence = "unresolved"

    if entity_type == "business":
        identity = identity_cascade.resolve_identity(winning_bidder)
        provenance["identity"] = {"sources_tried": identity.get("sources_tried"), "retrieved_at": now_iso}
        if identity.get("resolved"):
            officers = identity.get("officers") or []
            ra = next((o for o in officers if "registered agent" in (o.get("position") or "").lower()), None)
            registered_agent_name = ra["name"] if ra else None
            registered_agent_address = ra.get("address") if ra else identity.get("principal_address")
            principal_name = identity.get("principal_name")
            identity_confidence = "verified"
            fields.update({
                "resolved_principal_name": principal_name,
                "identity_match_method": identity.get("source_step"),
                "identity_match_confidence": identity_confidence,
                "identity_match_rationale": f"Sunbiz cascade resolved via {identity.get('source_step')} ({identity.get('source_url') or 'no url'})",
                "registered_agent_name": registered_agent_name,
                "registered_agent_address": registered_agent_address,
                "registered_agent_source": identity.get("source_step"),
                "registered_agent_confidence": "verified" if registered_agent_name else "unresolved",
                "related_entities": [o for o in officers if o.get("name") != registered_agent_name],
                "relationship_evidence_json": {"officers": officers, "doc_number": identity.get("doc_number"), "status": identity.get("status"), "source_step": identity.get("source_step")},
                "relationship_conflict_status": "no_conflict",
            })
        else:
            qa_errors.append({"field": "resolved_principal_name", "reason": f"Sunbiz cascade unresolved after {identity.get('sources_tried')}"})
            fields.update({
                "identity_match_method": "sunbiz_cascade_exhausted",
                "identity_match_confidence": "unresolved",
                "identity_match_rationale": f"Unresolved after {identity.get('sources_tried')}",
                "registered_agent_confidence": "unresolved",
                "relationship_conflict_status": "no_conflict",
            })
    else:
        fields.update({"identity_match_method": "self_identified_individual", "identity_match_confidence": "verified", "identity_match_rationale": "Buyer name on the auction record IS the individual; no separate identity resolution required."})

    anchor_row, corroboration, method = find_prior_owned_address(winning_bidder, crosswalk["pin_clean"], entity_type)
    provenance["prior_address"] = {"source": "public.zw_parcels", "method": method, "corroborating_rows": corroboration, "retrieved_at": now_iso}
    if anchor_row:
        confidence = "verified" if corroboration >= 2 else "probable"
        if entity_type == "business":
            fields.update({"principal_address_type": "business_own_name_prior_property", "principal_address_source": method, "principal_address": f"{anchor_row.get('owner_addr1')}, {anchor_row.get('owner_city')}, {anchor_row.get('owner_state')} {anchor_row.get('owner_zip')}"})
        else:
            fields.update({"principal_address_type": "individual_own_name_prior_property", "principal_address_source": method, "principal_address": f"{anchor_row.get('owner_addr1')}, {anchor_row.get('owner_city')}, {anchor_row.get('owner_state')} {anchor_row.get('owner_zip')}"})
    else:
        qa_errors.append({"field": "principal_address", "reason": f"No prior-owned zw_parcels record found via {method} (own-name search, excludes just-purchased parcel)"})

    business_phone = business_email = individual_phone = individual_email = None
    contact_confidence = "unresolved"
    contact_sources = []

    if entity_type == "business":
        city = anchor_row.get("owner_city") if anchor_row else None
        biz = contact_resolver.resolve_business_contact(winning_bidder, city, "FL", APIFY_TOKEN, principal_name)
        contact_sources += biz.get("sources_tried", [])
        provenance["business_contact"] = {"sources_tried": biz.get("sources_tried"), "retrieved_at": now_iso}
        if biz.get("phone"):
            business_phone = biz["phone"]["value"]
            fields.update({"business_phone": business_phone, "business_phone_type": "business_line", "business_phone_source": biz["phone"]["source"]})
        else:
            if not APIFY_TOKEN:
                reason = "not_run_no_key (APIFY_API_KEY not configured in this environment)"
            elif biz.get("apify_dropped_no_name_match"):
                reason = "Google Maps listing found but did not name-match"
            else:
                reason = "no Google Maps listing found"
            qa_errors.append({"field": "business_phone", "reason": reason})
        if biz.get("email"):
            business_email = biz["email"]["value"]
            fields.update({"business_email": business_email, "business_email_source": biz["email"]["source"], "business_website": biz["email"].get("detail")})
        else:
            qa_errors.append({"field": "business_email", "reason": "no verified email found (Hunter + OSS SMTP cascade exhausted)"})

        if principal_name and not business_phone:
            p_anchor, p_corrob, p_method = find_prior_owned_address(principal_name, crosswalk["pin_clean"], "person")
            if p_anchor:
                ledger = ff_credit_ledger.spend("tracerfy", 1)
                provenance["principal_tracerfy"] = {"granted": ledger.get("granted"), "retrieved_at": now_iso}
                if ledger.get("granted"):
                    trace = tracerfy_client.trace_lead(principal_name, p_anchor.get("owner_addr1"), p_anchor.get("owner_city"), p_anchor.get("owner_state"), p_anchor.get("owner_zip"))
                    if trace.get("phone"):
                        individual_phone = trace["phone"]
                        fields.update({"individual_phone": individual_phone, "individual_phone_type": "principal_personal", "individual_phone_source": "tracerfy_enhanced_trace"})
                    if trace.get("email"):
                        individual_email = trace["email"]
                        fields.update({"individual_email": individual_email, "individual_email_source": "tracerfy_enhanced_trace"})
                    if not trace.get("phone") and not trace.get("email"):
                        qa_errors.append({"field": "individual_phone/email", "reason": f"tracerfy: {trace.get('parse_status')}"})
                else:
                    qa_errors.append({"field": "individual_phone/email", "reason": f"tracerfy SKIPPED: {ledger}"})
            else:
                qa_errors.append({"field": "individual_phone/email", "reason": f"no prior-owned address for principal {principal_name!r} via {p_method}"})
    else:
        if anchor_row:
            ledger = ff_credit_ledger.spend("tracerfy", 1)
            provenance["tracerfy"] = {"granted": ledger.get("granted"), "retrieved_at": now_iso}
            if ledger.get("granted"):
                trace = tracerfy_client.trace_lead(winning_bidder, anchor_row.get("owner_addr1"), anchor_row.get("owner_city"), anchor_row.get("owner_state"), anchor_row.get("owner_zip"))
                contact_sources.append("tracerfy_enhanced_trace")
                if trace.get("phone"):
                    individual_phone = trace["phone"]
                    fields.update({"individual_phone": individual_phone, "individual_phone_type": "personal", "individual_phone_source": "tracerfy_enhanced_trace"})
                if trace.get("email"):
                    individual_email = trace["email"]
                    fields.update({"individual_email": individual_email, "individual_email_source": "tracerfy_enhanced_trace"})
                if not trace.get("phone") and not trace.get("email"):
                    qa_errors.append({"field": "individual_phone/email", "reason": f"tracerfy: {trace.get('parse_status')}"})
            else:
                qa_errors.append({"field": "individual_phone/email", "reason": f"tracerfy SKIPPED_DAILY_CAP: {ledger}"})
        else:
            qa_errors.append({"field": "individual_phone/email", "reason": "SKIPPED, no prior-owned mailing address on file (own-name search exhausted)"})

    phone_for_dnc = individual_phone or business_phone
    is_dnc = None
    if phone_for_dnc:
        dnc_ledger = ff_credit_ledger.spend("tracerfy", 1)
        if dnc_ledger.get("granted"):
            resp = tracerfy_client.dnc_scrub([phone_for_dnc])
            queue_id = (resp or {}).get("dnc_queue_id")
            if queue_id is not None:
                import time
                for _ in range(4):
                    q = tracerfy_client.get_queue_status(queue_id)
                    if q and q.get("pending") is False:
                        checked, clean = q.get("phones_checked"), q.get("phones_clean")
                        is_dnc = (clean == 0) if checked == 1 and clean is not None else None
                        break
                    time.sleep(15)
    fields["is_dnc"] = is_dnc
    fields["is_tcpa_litigator"] = None  # no litigator-list vendor wired; honest unresolved, not a fabricated negative

    if business_phone or individual_phone:
        contact_confidence = "verified"
    elif business_email or individual_email:
        contact_confidence = "probable"
    fields.update({
        "contact_match_status": "verified" if (business_phone or individual_phone or business_email or individual_email) else "unresolved",
        "contact_confidence": contact_confidence,
        "contact_verified_at": Raw("now()") if (business_phone or individual_phone or business_email or individual_email) else None,
        "phone_email_evidence_json": {"sources_tried": contact_sources},
    })
    # Backward-compat single-seller renderer columns
    fields.update({
        "phone": individual_phone or business_phone,
        "email": individual_email or business_email,
        "contact_provider": "tracerfy" if (individual_phone or individual_email) else ("apify/hunter" if (business_phone or business_email) else None),
        "dnc_state": ("flagged" if is_dnc else ("clear" if is_dnc is False else "not_scrubbed")),
    })

    portfolio = portfolio_snapshot(winning_bidder)
    flags = bundle_flags(portfolio)
    fields.update({
        "portfolio_property_count": portfolio["property_count"],
        "portfolio_county_count": portfolio["county_count"],
        "portfolio_counties": portfolio["counties"],
        "portfolio_total_jv": portfolio["total_jv"],
        "portfolio_assessed_value_total": portfolio["total_jv"],
        "portfolio_total_buildings": portfolio["total_buildings"],
        "portfolio_dor_mix_json": portfolio["dor_mix"],
        "portfolio_acquisition_source_mix_json": portfolio["acquisition_source_mix"],
        "portfolio_properties_json": portfolio["properties"],
        **flags,
    })
    provenance["portfolio"] = {"source": "winnerdata.owner_portfolio", "match_key": "entity_name_raw normalized exact", "retrieved_at": now_iso}

    required = ["resolved_entity_name"]
    if entity_type == "business":
        required += ["resolved_principal_name", "registered_agent_name", "business_phone", "business_email"]
    else:
        required += ["individual_phone", "individual_email"]
    unresolved = sum(1 for f in required if not fields.get(f))
    fields["unresolved_field_count"] = unresolved
    fields["qa_status"] = "FULLY_ENRICHED" if unresolved == 0 else ("PARTIAL_ENRICHMENT" if unresolved < len(required) else "PARCEL_ONLY_NO_CONTACT")
    fields["qa_errors_json"] = qa_errors
    fields["field_provenance_json"] = provenance
    fields["enrichment_provider_status_json"] = {
        "tracerfy": "called" if ("tracerfy" in provenance or "principal_tracerfy" in provenance) else "not_applicable",
        "brightdata": "delegated_to_identity_cascade_cascade_step_4",
        "apify": ("not_run_no_key" if not APIFY_TOKEN else "called") if entity_type == "business" else "not_applicable",
        "hunter": "called" if entity_type == "business" else "not_applicable",
    }
    fields["source_snapshot_hash"] = __import__("hashlib").md5(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()
    fields["row_enrichment_status"] = "complete"
    return fields


def main():
    set_batch_status("running")
    try:
        auctions = sql(f"""
            select id, county, auction_date, property_address, case_number, sale_type, tier1_buyer_type,
                   winning_bidder, tier1_sold_amount, market_value, assessed_value, parcel_id, auction_url, source_url
            from public.multi_county_auctions
            where auction_date = date '{esc(BATCH_DATE)}' and tier1_buyer_type = 'third_party'
              and nullif(btrim(winning_bidder), '') is not null
            order by county, case_number limit 20
        """)
        if len(auctions) != 9:
            raise RuntimeError(f"Expected 9 third-party auctions for {BATCH_DATE}; got {len(auctions)}")

        results = []
        all_complete = True
        for a in auctions:
            auction_id = a["id"]
            crosswalk_rows = sql(f"select auction_id, auction_parcel_id, pin_clean, match_method, verified_at, verified_by from winnerdata.ff_parcel_crosswalk where auction_id = '{esc(auction_id)}' limit 1")
            if not crosswalk_rows:
                sql(build_update("winnerdata.ff_batch_leads", {"row_enrichment_status": "failed", "qa_status": "BLOCKED_NO_VALIDATED_CROSSWALK"}, f"batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}'"))
                results.append({"auction_id": auction_id, "qa_status": "BLOCKED_NO_VALIDATED_CROSSWALK"})
                all_complete = False
                continue
            crosswalk = crosswalk_rows[0]

            prior = existing_row(auction_id)
            if prior and prior.get("row_enrichment_status") == "complete" and not FORCE_REFRESH:
                results.append({"auction_id": auction_id, "qa_status": prior.get("qa_status"), "skipped_already_complete": True})
                continue

            parcel_rows = sql(f"select county, pin_clean, owner_name, updated_at from public.zw_parcels where pin_clean = '{esc(crosswalk['pin_clean'])}' limit 1")
            parcel = parcel_rows[0] if parcel_rows else None
            if not parcel or not parcel.get("owner_name"):
                sql(build_update("winnerdata.ff_batch_leads", {"row_enrichment_status": "failed", "qa_status": "BLOCKED_NO_PARCEL_SSOT"}, f"batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}'"))
                results.append({"auction_id": auction_id, "qa_status": "BLOCKED_NO_PARCEL_SSOT"})
                all_complete = False
                continue

            try:
                fields = enrich_one(a, crosswalk, parcel)
            except Exception as e:
                sql(build_update("winnerdata.ff_batch_leads", {"row_enrichment_status": "failed", "qa_errors_json": [{"field": "*", "reason": str(e)[:300]}]}, f"batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}'"))
                results.append({"auction_id": auction_id, "qa_status": "ENRICHMENT_EXCEPTION", "error": str(e)[:300]})
                all_complete = False
                continue

            sql(build_update("winnerdata.ff_batch_leads", fields, f"batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}'"))
            results.append({"auction_id": auction_id, "winning_bidder": a["winning_bidder"], "qa_status": fields["qa_status"], "unresolved_field_count": fields["unresolved_field_count"]})

        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "batch_date": BATCH_DATE, "candidate_count": len(auctions), "results": results}
        with open(OUT, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(json.dumps({"output": OUT, "candidate_count": len(auctions), "fully_enriched": sum(r.get("qa_status") == "FULLY_ENRICHED" for r in results), "results": results}, indent=2, default=str))

        set_batch_status("complete" if all_complete else "failed", None if all_complete else "one or more rows failed crosswalk/parcel/enrichment gate -- see per-row qa_status")
        if not all_complete:
            sys.exit(1)
    except Exception as e:
        set_batch_status("failed", str(e)[:500])
        raise


if __name__ == "__main__":
    main()
