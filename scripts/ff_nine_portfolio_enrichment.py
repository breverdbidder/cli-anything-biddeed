#!/usr/bin/env python3
"""Nine-case FF enrichment runner.

Reads 2026-08-26 third-party auctions from multi_county_auctions, applies the
validated parcel crosswalk, enriches property/portfolio fields from ZoneWise,
and optionally calls Tracerfy only when a prior buyer-owned mailing address is
available. No find_owner call is made and no purchased-property address is
used as a buyer contact anchor.

Writes results back to winnerdata.ff_batch_leads (phone/email/qa_status) and
flips winnerdata.ff_batches.enrichment_status to complete/failed. Only
invoked by winnerdata-nine-ff-enrichment.yml, itself only dispatched by the
winnerdata.notify_ff_batch_approved() trigger after Ariel approves via
public.ff_approve_batch() -- see
supabase/migrations/20260827_approval_tracerfy_enrichment_gate.sql. Do not
run this ahead of approval: gating paid Tracerfy lookups behind approval is
the explicit point of that migration, not an incidental side effect.
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import ff_credit_ledger  # noqa: E402
import tracerfy_client  # noqa: E402
from entity_portfolio_resolver import resolve_entity_portfolio, normalize  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = os.environ.get("BATCH_DATE", "2026-08-26")
OUT = os.environ.get("OUT", f"ff_nine_enrichment_{BATCH_DATE}.json")
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
TRACERFY_KEY = os.environ.get("TRACERFY_API_KEY", "")


def sql(q: str):
    if not SB_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    req = urllib.request.Request(MGMT_URL, data=json.dumps({"query": q}).encode(), headers={"Authorization": f"Bearer {SB_TOKEN}", "Content-Type": "application/json", "User-Agent": "winnerdata-ff-nine-enrichment/1.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.loads(r.read())
    if isinstance(body, dict) and body.get("message"):
        raise RuntimeError(body["message"])
    return body


def esc(v):
    return str(v or "").replace("'", "''")


def norm(v):
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


def tracerfy(name, address, city, state, zipcode):
    """Thin wrapper over tracerfy_client.trace_lead -- do not reimplement name
    splitting or the request here. An earlier version of this function had
    its own naive `name.split(",", 1)` logic that reversed surname-first
    names (e.g. "DAVIS, RONALD L.") exactly the way tracerfy_client's
    _split_owner_name() docstring warns against; that bug already cost a
    full session of false NO_MATCH results once and must not be reintroduced
    here by drift between the two modules.
    """
    if not TRACERFY_KEY or not address:
        return {"status": "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS"}
    ledger = ff_credit_ledger.spend("tracerfy", 1)
    if not ledger.get("granted"):
        return {"status": "SKIPPED_DAILY_CAP", "ledger": ledger}
    result = tracerfy_client.trace_lead(name, address, city, state, zipcode)
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
        "queried_anchor": {"address": address, "city": city, "state": state, "zip": zipcode},
    }


def web_search_cross_check_eligible(row: dict) -> tuple[bool, str]:
    """Trigger condition for the "web-search cross-check for principals /
    registered agents" step (issue #19533, documented in full in
    CC_META_PROMPT.md). Runs only after Sunbiz + Tracerfy + ZoneWise have
    already been tried and a case still has an unresolved business contact
    field AND a named individual (principal or registered agent) to search
    on -- an LLC with no natural person attached has nothing for a general
    web search to anchor to. This function only decides eligibility; the
    search itself is an agent/manual step (matching entity vs. same-named
    different entity, judging source independence, etc. is not something a
    deterministic batch script should attempt -- see the acceptance-bar
    enforcement in validate_web_search_cross_check below for what a human/
    agent session must satisfy before writing a result)."""
    already_resolved = bool(row.get("business_phone") or row.get("business_website") or row.get("business_email"))
    if already_resolved:
        return False, "business_phone/website/email already resolved -- no cross-check needed"
    principal = row.get("resolved_principal_name") or row.get("registered_agent_name")
    if not principal:
        return False, "no named individual principal or registered agent on file to search"
    return True, f"eligible for web-search cross-check on {principal!r}"


def validate_web_search_cross_check(sources: list, is_related_entity: bool = False, relationship_note: str | None = None) -> None:
    """Enforces the acceptance bar before a web-search cross-check result may
    be written as VERIFIED: two independent, mutually corroborating sources
    minimum (a single source is a candidate/unconfirmed, never VERIFIED; zero
    sources means leave the field blank). A related-entity contact (e.g. the
    principal's other company) must always carry an explicit relationship
    note -- never presented as if it were the target entity's own contact.
    Raises ValueError on violation; callers must not silently downgrade and
    write anyway."""
    distinct = {s for s in (sources or []) if s}
    if len(distinct) < 2:
        raise ValueError(
            f"web-search cross-check requires 2+ independent, mutually corroborating sources; "
            f"got {len(distinct)}. Write as a candidate/unconfirmed field, not VERIFIED, or leave blank."
        )
    if is_related_entity and not relationship_note:
        raise ValueError(
            "related-entity contact requires an explicit relationship note in the evidence_ledger entry "
            "(e.g. 'President/CEO of <related company>, a related entity <principal> also controls') -- "
            "never write a related entity's contact as if it were the target entity's own."
        )


def build_web_search_evidence_entry(sources: list, fields_supported: list, match_method: str,
                                     is_related_entity: bool = False, relationship_note: str | None = None) -> dict:
    """Builds the evidence_ledger entry for a web-search cross-check result,
    in the shape scripts/render_ff_9buyer_20260827.py's
    _related_entity_contact_note() scans for (a 'note' + 'fields_supported'
    pair identifies a related-entity contact regardless of the dict key name
    used). Keep the two in sync if either shape changes. Validates the
    acceptance bar first -- raises rather than building an entry that would
    fail policy."""
    validate_web_search_cross_check(sources, is_related_entity, relationship_note)
    entry = {
        "sources": sources,
        "confidence": "verified_cross_checked_two_independent_sources",
        "match_method": match_method,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "fields_supported": fields_supported,
    }
    if relationship_note:
        entry["note"] = relationship_note
    return entry


def set_enrichment_status(status: str, error: str | None = None):
    fields = [f"enrichment_status = '{esc(status)}'", "updated_at = now()"]
    if status == "running":
        fields.append("enrichment_started_at = now()")
        fields.append("enrichment_error = null")
    if status in ("complete", "failed"):
        fields.append("enrichment_completed_at = now()")
    if status == "failed":
        error_lit = "'" + esc(error) + "'" if error else "null"
        fields.append(f"enrichment_error = {error_lit}")
    set_clause = ", ".join(fields)
    sql(f"update winnerdata.ff_batches set {set_clause} where batch_date = date '{esc(BATCH_DATE)}'")


def persist_lead(auction_id: str, tf: dict, qa_status: str):
    phone = tf.get("phone") if tf.get("status") == "OK" else None
    email = tf.get("email") if tf.get("status") == "OK" else None
    provider = "tracerfy" if tf.get("status") == "OK" else None
    phone_lit = f"'{esc(phone)}'" if phone else "null"
    email_lit = f"'{esc(email)}'" if email else "null"
    provider_lit = f"'{provider}'" if provider else "null"
    verified_lit = "now()" if provider else "null"
    ev = json.dumps({"tracerfy_enrichment": tf, "ran_at": datetime.now(timezone.utc).isoformat()})
    sql(f"""
        update winnerdata.ff_batch_leads
        set phone = {phone_lit},
            email = {email_lit},
            contact_provider = {provider_lit},
            contact_verified_at = {verified_lit},
            qa_status = '{esc(qa_status)}',
            unresolved_field_count =
              (case when owner_name is null then 1 else 0 end)
              + (case when resolved_principal_name is null then 1 else 0 end)
              + (case when {phone_lit} is null then 1 else 0 end)
              + (case when {email_lit} is null then 1 else 0 end)
              + (case when business_website is null then 1 else 0 end),
            evidence_ledger = evidence_ledger || '{esc(ev)}'::jsonb
        where batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}'
    """)


# ---------------------------------------------------------------------------
# Entity/Portfolio Correlation pass (P0 follow-up to issue #19547, 2026-08-28).
#
# Generalizes scripts/skiptrace_20260825_portfolio_batch.py's hardcoded
# 15-row owner_portfolio (batch_id='20260825_third_party_portfolio') by
# running scripts/entity_portfolio_resolver.py's statewide zw_parcels +
# auction_buyer_sightings + Sunbiz walk for every buyer in THIS batch, not
# just the two hand-picked test entities the resolver was proven against.
# Writes each resolved property edge through
# winnerdata.upsert_entity_portfolio_edge() (the one narrow write path the
# 2026-08-28 migration ships, rather than ad hoc INSERTs), and persists the
# per-buyer KPI summary onto the buyer's own winnerdata.ff_batch_leads
# row(s) so portfolio_fact_finder_render.py can render it without a second
# live resolver call at render time.
# ---------------------------------------------------------------------------

ENTITY_PORTFOLIO_BATCH_ID_PREFIX = "entity_portfolio_"


def sql_lit(v):
    return "null" if v in (None, "") else "'" + esc(v) + "'"


def sql_num(v):
    try:
        return "null" if v in (None, "") else str(float(v))
    except (TypeError, ValueError):
        return "null"


def sql_int(v):
    try:
        return "null" if v in (None, "") else str(int(v))
    except (TypeError, ValueError):
        return "null"


def county_slug(county: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (county or "").strip().lower()).strip("_")


def county_co_no_map() -> dict:
    rows = sql("select co_no, slug from public.fl_counties")
    return {r["slug"]: r["co_no"] for r in rows if r.get("slug")}


def write_portfolio_edge(owner_key, entity_name, county_map, prop, batch_id):
    slug = county_slug(prop.get("county"))
    co_no = county_map.get(slug)
    if co_no is None:
        return False, f"no co_no match for county={prop.get('county')!r} (slug={slug!r})"
    if prop.get("source") == "zw_parcels":
        parcel_id = prop.get("pin_clean")
        address = prop.get("site_addr") or prop.get("owner_addr1")
        dor_uc = prop.get("luse_code")
        jv = prop.get("val_assessed")
        acquisition_source = "prior_holding"
        case_number = None
    else:  # auction_buyer_sightings -- a real win, but not yet crosswalked to a zw_parcels pin
        parcel_id = f"CASE:{prop.get('case_number')}" if prop.get("case_number") else None
        address = prop.get("site_addr")
        dor_uc = None
        jv = None  # sold_amount is a price, not a Just Value -- never conflate the two (Honesty Protocol)
        acquisition_source = "auction_win"
        case_number = prop.get("case_number")
    if not parcel_id:
        return False, "no parcel_id or case_number to key this edge on"
    q = f"""select winnerdata.upsert_entity_portfolio_edge(
        {sql_lit(owner_key)}, {sql_lit(entity_name)}, {sql_lit(county_slug(prop.get('county')))}, {co_no}, {sql_lit(parcel_id)},
        {sql_lit(address)}, {sql_lit(dor_uc)}, null, {sql_num(jv)},
        {sql_lit(acquisition_source)}, {sql_lit(prop.get('linked_via'))}, {sql_lit(prop.get('linked_via_detail'))},
        {sql_lit(batch_id)}, {sql_lit(case_number)}, {sql_lit(prop.get('source'))}, {sql_lit(prop.get('confidence_tier'))}
    );"""
    sql(q)
    return True, None


def entity_portfolio_pass(auctions: list[dict]) -> list[dict]:
    county_map = county_co_no_map()
    batch_id = f"{ENTITY_PORTFOLIO_BATCH_ID_PREFIX}{BATCH_DATE}"
    by_buyer: dict[str, list[dict]] = {}
    for a in auctions:
        name = a.get("winning_bidder")
        if name:
            by_buyer.setdefault(name, []).append(a["id"])

    report = []
    for name, auction_ids in by_buyer.items():
        entry = {"winning_bidder": name, "auction_ids": auction_ids}
        try:
            result = resolve_entity_portfolio(name, run_live_cascade=False)
            kpi = result["kpi"]
            all_props = result["properties_from_ownership_records"] + result["auction_wins_not_yet_crosswalked"]
            written, skipped = 0, 0
            for prop in all_props:
                ok, why = write_portfolio_edge(result["owner_key"], name, county_map, prop, batch_id)
                if ok:
                    written += 1
                else:
                    skipped += 1
            entry.update({
                "status": "OK",
                "total_properties": kpi["total_properties"],
                "counties": kpi["counties"],
                "confidence_summary": kpi["confidence_summary"],
                "acquisition_velocity": kpi["acquisition_velocity"],
                "edges_written": written,
                "edges_skipped": skipped,
            })
            props_json = json.dumps(all_props, default=str)
            counties_arr = "array[" + ",".join(sql_lit(c) for c in kpi["counties"]) + "]::text[]" if kpi["counties"] else "null"
            for auction_id in auction_ids:
                sql(f"""
                    update winnerdata.ff_batch_leads
                    set portfolio_property_count = {kpi['total_properties']},
                        portfolio_county_count = {kpi['county_spread']},
                        portfolio_counties = {counties_arr},
                        portfolio_assessed_value_total = {sql_num(kpi['total_assessed_value'])},
                        portfolio_market_value_total = {sql_num(kpi['total_market_value'])},
                        portfolio_properties_json = {sql_lit(props_json)}::jsonb,
                        portfolio_acquisition_velocity_per_year = {sql_num(kpi['acquisition_velocity'].get('velocity_per_year'))},
                        portfolio_wins_on_file = {sql_int(kpi['acquisition_velocity'].get('wins_on_file'))},
                        portfolio_confidence_summary = {sql_lit(json.dumps(kpi['confidence_summary']))}::jsonb
                    where batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}'
                """)
        except Exception as e:
            entry.update({"status": "FAILED", "error": str(e)[:500]})
            print(f"  entity/portfolio resolution FAILED for {name!r}: {e}", file=sys.stderr)
        report.append(entry)
        print(f"  entity/portfolio: {name!r} -> {entry.get('status')} "
              f"(total_properties={entry.get('total_properties')}, edges_written={entry.get('edges_written')})")
    return report


def main():
    set_enrichment_status("running")
    try:
        auctions = sql(f"""select id, county, auction_date, property_address, case_number, sale_type, tier1_buyer_type, winning_bidder, tier1_sold_amount, market_value, assessed_value, parcel_id, auction_url, source_url from public.multi_county_auctions where auction_date = date '{esc(BATCH_DATE)}' and tier1_buyer_type = 'third_party' and nullif(btrim(winning_bidder), '') is not null order by county, case_number limit 20""")
        if len(auctions) != 9:
            raise RuntimeError(f"Expected 9 third-party auctions for {BATCH_DATE}; got {len(auctions)}")
        out = []
        for a in auctions:
            auction_id = a["id"]

            # Idempotency guard: winnerdata.ff_batch_leads rows created by
            # build_ff_portfolio_batch() default qa_status to
            # 'PARTIAL_ENRICHMENT' and stay there until an enrichment pass
            # actually touches them. Any other value means a prior run
            # (this script or a parallel session's manual research) already
            # produced a real result -- re-running the fl_parcels-anchor
            # cascade below would blindly overwrite a resolved phone/email
            # with a null on a re-dispatch, destroying already-verified
            # work. FORCE_REFRESH=1 opts back in explicitly.
            existing = sql(f"select qa_status from winnerdata.ff_batch_leads where batch_date = date '{esc(BATCH_DATE)}' and auction_id = '{esc(auction_id)}' limit 1")
            if existing and existing[0].get("qa_status") not in (None, "PARTIAL_ENRICHMENT") and os.environ.get("FORCE_REFRESH") != "1":
                out.append({"auction": a, "qa_status": existing[0]["qa_status"], "skipped_already_enriched": True})
                continue

            x = sql(f"select auction_id, auction_parcel_id, pin_clean, match_method, verified_at, verified_by from winnerdata.ff_parcel_crosswalk where auction_id = '{esc(auction_id)}' limit 1")
            if not x:
                out.append({"auction": a, "qa_status": "BLOCKED_NO_VALIDATED_CROSSWALK"})
                persist_lead(auction_id, {"status": "SKIPPED_NO_CROSSWALK"}, "BLOCKED_NO_VALIDATED_CROSSWALK")
                continue
            pin = x[0]["pin_clean"]
            p = sql(f"select county, pin_clean, owner_name, owner_name2, owner_addr1, owner_addr2, owner_city, owner_state, owner_zip, site_addr, site_city, site_zip, luse_code, luse_desc, num_buildings, sqft_heated, year_built, val_market, val_assessed, pa_link, data_source, updated_at from public.zw_parcels where pin_clean = '{esc(pin)}' limit 2")
            parcel = p[0] if p else None
            # zw_parcels (10M rows) via idx_zw_fts, NOT fl_parcels: fl_parcels
            # is the older/superseded table (see
            # scripts/skiptrace_20260827_9buyer_ff_batch.py's own docstring),
            # and a normalized-regexp equality/ILIKE scan against zw_parcels
            # without the FTS index times out empirically on a table this
            # size. Excludes the just-purchased parcel; never anchors on it.
            anchor = None
            target_toks = {t for t in re.sub(r"[^A-Za-z ]", " ", a["winning_bidder"] or "").upper().split() if len(t) >= 2}
            if target_toks:
                fts_rows = sql(f"""
                    select owner_addr1, owner_city, owner_state, owner_zip, pin_clean, owner_name
                    from public.zw_parcels
                    where to_tsvector('english', ((((((coalesce(owner_name, '') || ' ') || coalesce(site_addr, '')) || ' ') || coalesce(site_city, '')) || ' ') || coalesce(subdivision, '')))
                          @@ plainto_tsquery('english', '{esc(a["winning_bidder"])}')
                    limit 30
                """)
                candidates = [r for r in fts_rows if r.get("pin_clean") != pin and r.get("owner_addr1")
                              and target_toks <= {t for t in re.sub(r"[^A-Za-z ]", " ", r.get("owner_name") or "").upper().split() if len(t) >= 2}]
                if candidates:
                    from collections import Counter as _Counter
                    key = lambda r: (norm(r.get("owner_addr1")), norm(r.get("owner_city")), (r.get("owner_state") or "").upper(), norm(r.get("owner_zip")))
                    best_key, _ = _Counter(key(r) for r in candidates).most_common(1)[0]
                    anchor = next(r for r in candidates if key(r) == best_key)
            prior = [anchor] if anchor else []
            tf = tracerfy(a["winning_bidder"], anchor.get("owner_addr1") if anchor else None, anchor.get("owner_city") if anchor else None, anchor.get("owner_state") if anchor else None, anchor.get("owner_zip") if anchor else None)
            qa = "SSOT_MATCHED" if parcel and parcel.get("owner_name") else "BLOCKED_NO_PARCEL_SSOT"
            if tf.get("status") == "OK":
                qa = "ENRICHED_CONTACT_FOUND"
            elif qa == "SSOT_MATCHED":
                qa = {"NO_MATCH": "ENRICHED_NO_CONTACT_MATCH", "SKIPPED_DAILY_CAP": "ENRICHMENT_SKIPPED_DAILY_CAP", "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS": "ENRICHMENT_SKIPPED_NO_PRIOR_ADDRESS", "REQUEST_FAILED": "ENRICHMENT_REQUEST_FAILED"}.get(tf.get("status"), "SSOT_MATCHED_NO_CONTACT")
            out.append({"auction": a, "crosswalk": x[0], "parcel": parcel, "prior_buyer_owned_addresses": prior, "tracerfy": tf, "qa_status": qa})
            persist_lead(auction_id, tf, qa)

        print("Running entity/portfolio correlation pass...")
        portfolio_report = entity_portfolio_pass(auctions)

        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "batch_date": BATCH_DATE, "candidate_count": len(auctions), "records": out, "entity_portfolio": portfolio_report, "bright_data": "NOT_RUN_NO_KEY", "policy": "BLANK_OVER_WRONG; no purchased-property address used for buyer contact"}
        with open(OUT, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(json.dumps({"output": OUT, "candidate_count": len(auctions), "contact_found": sum(r.get("qa_status") == "ENRICHED_CONTACT_FOUND" for r in out)}, indent=2))
        set_enrichment_status("complete")
    except Exception as e:
        set_enrichment_status("failed", str(e)[:500])
        raise


def main_portfolio_only():
    """Re-run just the entity/portfolio correlation pass against an
    already-enriched batch, without re-spending Tracerfy credits or
    resetting winnerdata.ff_batches.enrichment_status. Used to backfill the
    2026-08-26 batch, which was approved and contact-enriched (issue #19531)
    before this pass existed."""
    auctions = sql(f"""select id, county, auction_date, winning_bidder from public.multi_county_auctions where auction_date = date '{esc(BATCH_DATE)}' and tier1_buyer_type = 'third_party' and nullif(btrim(winning_bidder), '') is not null order by county, case_number""")
    print(f"{len(auctions)} third-party auction(s) for {BATCH_DATE}. Running entity/portfolio correlation pass...")
    portfolio_report = entity_portfolio_pass(auctions)
    print(json.dumps({"batch_date": BATCH_DATE, "buyers": len(portfolio_report),
                       "multi_property_buyers": sum(1 for r in portfolio_report if r.get("total_properties", 0) >= 2)}, indent=2))
    return portfolio_report


if __name__ == "__main__":
    if os.environ.get("PORTFOLIO_ONLY") == "1":
        main_portfolio_only()
    else:
        main()
