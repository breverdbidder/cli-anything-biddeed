#!/usr/bin/env python3
"""Elementix-parity entity/portfolio correlation layer for Daily Winner FFs.

Generalizes scripts/skiptrace_20260825_portfolio_batch.py's per-batch,
hand-typed-BUYERS-dict walk into a reusable function callable for ANY
resolved buyer/entity name, and adds the one correlation source that batch
script never touched: public.auction_buyer_profiles / auction_buyer_sightings
(the historical cross-county buyer graph). Sunbiz officer/registered-agent
piercing reuses scripts/identity_cascade.py unchanged -- not re-implemented.

Three data sources, walked in this order, matching the existing
no-strangers-merge rule (shared mailing address alone is never sufficient;
a second corroborator -- a shared Sunbiz principal -- is required before two
differently-named entities are merged into one owner_key):

  1. public.zw_parcels     -- statewide own_name exact match (the parcel SSOT;
                               10.1M rows, all 67 counties)
  2. public.auction_buyer_profiles + auction_buyer_sightings
                            -- prior/other auction wins under the same
                               buyer_name_normalized, independent of whether
                               that win produced a zw_parcels row yet
  3. public.sunbiz_entities (local bulk-sync table) with a live
     identity_cascade.resolve_identity() fallback -- officer/registered-agent
     names used ONLY to corroborate an address-sharing affiliate, never to
     merge on their own (an address+principal pair is VERIFIED-CROSS-CHECKED;
     an address alone is UNCONFIRMED and excluded from portfolio totals)

Every property row and every affiliate edge carries one of the five FF
confidence tiers (VERIFIED-PRIMARY / VERIFIED-CROSS-CHECKED /
LIKELY-SINGLE-SOURCE / UNCONFIRMED / NOT AVAILABLE) so a report author never
has to guess how solid a given line is.

Read path: PostgREST (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) against the
public schema only -- winnerdata is not in this project's exposed-schema
list, so any winnerdata.* read/write needs the Management API run_sql path
(mgmt_sql below), which is unreachable from a Cloudflare-blocked sandbox IP.
Callers must check reachable_backends() before trusting a "NOT AVAILABLE"
tag; it can mean "genuinely no record" OR "backend unreachable this run" and
this module never conflates the two.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from identity_cascade import normalize, resolve_identity  # noqa: E402

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

TIER_VERIFIED_PRIMARY = "VERIFIED-PRIMARY"
TIER_VERIFIED_CROSS_CHECKED = "VERIFIED-CROSS-CHECKED"
TIER_LIKELY_SINGLE_SOURCE = "LIKELY-SINGLE-SOURCE"
TIER_UNCONFIRMED = "UNCONFIRMED"
TIER_NOT_AVAILABLE = "NOT AVAILABLE"


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

def pg_rest(table: str, params: str, timeout: int = 60) -> list[dict]:
    """Read from a public-schema table via PostgREST. Raises on any HTTP
    error rather than returning [] -- a caller must not read '[]' as 'no
    match' when the real cause was a timeout or a bad column name."""
    if not (SB_URL and SB_KEY):
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    url = f"{SB_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def mgmt_sql(query: str, timeout: int = 90, retries: int = 2):
    """Read/write via the Supabase Management API (needed for winnerdata.*
    -- not exposed via PostgREST). Documented working pattern from
    scripts/render_ff_9buyer_20260827.py and skiptrace_20260825_portfolio_batch.py;
    confirmed 2026-08-28 that it returns Cloudflare error 1010 (browser/IP
    signature block) from THIS sandbox -- that is an infra-level block, not
    an auth failure, and is expected to work from cc-runner-ghonly.yml per
    every other script in this repo that already depends on it."""
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set")
    req = urllib.request.Request(
        MGMT_URL, data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "entity-portfolio-resolver/1.0"},
        method="POST",
    )
    last_exc = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "message" in body:
                raise RuntimeError(f"{body['message']} -- query: {query[:200]}")
            return body
        except Exception as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_exc


def reachable_backends() -> dict:
    """Live-checked (not assumed) reachability of each backend this module
    depends on. Call once per session, not once per entity -- cheap, but no
    reason to re-probe 20 times in a batch run."""
    out = {"postgrest": False, "mgmt_api": False}
    try:
        pg_rest("fl_counties", "select=co_no&limit=1", timeout=15)
        out["postgrest"] = True
    except Exception as e:
        out["postgrest_error"] = str(e)
    try:
        mgmt_sql("select 1;", timeout=15, retries=1)
        out["mgmt_api"] = True
    except Exception as e:
        out["mgmt_api_error"] = str(e)
    return out


# ---------------------------------------------------------------------------
# Source 1: zw_parcels statewide ownership walk
# ---------------------------------------------------------------------------

def _esc_ilike(v: str) -> str:
    return urllib.parse.quote(f"*{v}*")


def find_zw_parcels_exact(entity_name: str) -> list[dict]:
    """Exact normalized own_name match, statewide (no county filter). Uses
    ilike wildcard (no functional index on upper(owner_name) confirmed to
    exist here) then filters client-side to a true normalize() match, so a
    substring hit like 'MUNDI MARKETING LLC II' never counts as this
    entity's own property."""
    target = normalize(entity_name)
    rows = pg_rest(
        "zw_parcels",
        "select=pin_clean,county,owner_name,owner_addr1,owner_city,site_addr,"
        f"val_assessed,val_market,luse_code&owner_name=ilike.{_esc_ilike(entity_name)}&limit=200",
        timeout=90,
    )
    return [r for r in rows if normalize(r["owner_name"]) == target]


def find_zw_parcels_affiliate_by_addr(own_addr1: str, own_city: str, exclude_norm_names: set[str]) -> list[dict]:
    if not own_addr1 or not own_city:
        return []
    params = (
        "select=pin_clean,county,owner_name,owner_addr1,owner_city,site_addr,val_assessed,val_market,luse_code"
        f"&owner_addr1=ilike.{urllib.parse.quote(own_addr1)}&owner_city=ilike.{urllib.parse.quote(own_city)}&limit=500"
    )
    rows = pg_rest("zw_parcels", params, timeout=90)
    return [r for r in rows if normalize(r["owner_name"]) not in exclude_norm_names]


# ---------------------------------------------------------------------------
# Source 2: auction_buyer_profiles / auction_buyer_sightings (missing edge)
# ---------------------------------------------------------------------------

def find_auction_buyer_graph(entity_name: str) -> dict:
    """The correlation source the 2026-08-25 batch script never touched.
    Returns the buyer's rolled-up profile (if any) plus every individual
    sighting (one row per case won), which is what makes acquisition
    velocity computable -- the profile row alone only has first/last win
    date, not the full timeline."""
    key = normalize(entity_name).lower()
    profiles = pg_rest("auction_buyer_profiles", f"select=*&buyer_name_normalized=eq.{urllib.parse.quote(key)}", timeout=30)
    if not profiles:
        return {"profile": None, "sightings": []}
    profile = profiles[0]
    sightings = pg_rest(
        "auction_buyer_sightings",
        f"select=*&buyer_profile_id=eq.{profile['id']}&order=auction_date.asc&limit=500",
        timeout=30,
    )
    return {"profile": profile, "sightings": sightings}


# ---------------------------------------------------------------------------
# Source 3: Sunbiz (local table first, live cascade fallback)
# ---------------------------------------------------------------------------

def find_sunbiz_local(entity_name: str) -> dict | None:
    target = normalize(entity_name)
    rows = pg_rest(
        "sunbiz_entities",
        f"select=document_number,entity_name,status,principal_address_line1,principal_city,"
        f"registered_agent_name,registered_agent_address,officers&entity_name=ilike.{_esc_ilike(entity_name)}&limit=20",
        timeout=30,
    )
    for r in rows:
        if normalize(r["entity_name"]) == target:
            return r
    return None


def resolve_sunbiz(entity_name: str, run_live_cascade: bool = False) -> dict:
    """local sunbiz_entities bulk-sync table first (free, instant); falls
    back to the live Exa/mirror/Bright-Data/Playwright cascade
    (scripts/identity_cascade.py) only if run_live_cascade=True, since that
    leg costs real API calls and, per this session's live test against
    Bright Data 2026-08-28, search.sunbiz.org is now blocked by Bright
    Data's own residential-proxy policy (government-site classification) --
    a regression versus the 2026-08-25 issue's "verified live" claim for
    that same leg, worth flagging to whoever owns that cascade next."""
    local = find_sunbiz_local(entity_name)
    if local:
        return {"resolved": True, "source_step": "sunbiz_entities_local", "principal_name": None,
                "officers": local.get("officers") or [], "registered_agent_name": local.get("registered_agent_name"),
                "doc_number": local.get("document_number"), "raw": local}
    if not run_live_cascade:
        return {"resolved": False, "source_step": None, "tag": "not checked (run_live_cascade=False)"}
    return resolve_identity(entity_name)


# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------

def tier_for_property(linked_via: str, corroborated: bool) -> str:
    if linked_via == "exact_name":
        return TIER_VERIFIED_PRIMARY
    if linked_via == "affiliate_own_addr":
        return TIER_VERIFIED_CROSS_CHECKED if corroborated else TIER_UNCONFIRMED
    if linked_via == "shared_principal":
        return TIER_LIKELY_SINGLE_SOURCE
    return TIER_NOT_AVAILABLE


# ---------------------------------------------------------------------------
# Acquisition velocity
# ---------------------------------------------------------------------------

def acquisition_velocity(sightings: list[dict]) -> dict:
    dates = sorted(s["auction_date"] for s in sightings if s.get("auction_date"))
    if len(dates) < 2:
        return {"wins_on_file": len(dates), "velocity_per_year": None,
                "note": "insufficient history (<2 wins on file) to compute a rate"}
    from datetime import date
    d0 = date.fromisoformat(dates[0])
    d1 = date.fromisoformat(dates[-1])
    span_days = max((d1 - d0).days, 1)
    rate = (len(dates) - 1) / span_days * 365.0
    return {"wins_on_file": len(dates), "first_win": dates[0], "last_win": dates[-1],
            "span_days": span_days, "velocity_per_year": round(rate, 2)}


# ---------------------------------------------------------------------------
# Top-level resolver
# ---------------------------------------------------------------------------

def resolve_entity_portfolio(entity_name: str, run_live_cascade: bool = False) -> dict:
    owner_key = normalize(entity_name)
    anchor_rows = find_zw_parcels_exact(entity_name)
    buyer_graph = find_auction_buyer_graph(entity_name)
    sunbiz = resolve_sunbiz(entity_name, run_live_cascade=run_live_cascade)

    properties = [{**r, "linked_via": "exact_name", "source": "zw_parcels",
                   "confidence_tier": tier_for_property("exact_name", True)} for r in anchor_rows]

    # affiliate-by-address, gated by shared-principal corroboration exactly
    # like scripts/skiptrace_20260825_portfolio_batch.py's part2_portfolio
    claimed = {owner_key}
    anchor_principals = set()
    if sunbiz.get("resolved"):
        anchor_principals = {normalize(o["name"]) for o in sunbiz.get("officers", []) if o.get("name")}
        if sunbiz.get("principal_name"):
            anchor_principals.add(normalize(sunbiz["principal_name"]))
        if sunbiz.get("registered_agent_name"):
            anchor_principals.add(normalize(sunbiz["registered_agent_name"]))

    unconfirmed_candidates = []
    seen_addrs = {(r["owner_addr1"], r["owner_city"]) for r in anchor_rows if r.get("owner_addr1")}
    for addr, city in seen_addrs:
        for cand in find_zw_parcels_affiliate_by_addr(addr, city, claimed):
            cand_name = cand["owner_name"]
            cand_sunbiz = resolve_sunbiz(cand_name, run_live_cascade=False)  # local-only per candidate; never spawns a live cascade fan-out
            cand_principals = {normalize(o["name"]) for o in cand_sunbiz.get("officers", []) if o.get("name")} if cand_sunbiz.get("resolved") else set()
            shared = anchor_principals & cand_principals
            if shared and anchor_principals:
                claimed.add(normalize(cand_name))
                properties.append({**cand, "linked_via": "affiliate_own_addr",
                                    "source": "zw_parcels", "confidence_tier": tier_for_property("affiliate_own_addr", True),
                                    "linked_via_detail": f"shared_principal={sorted(shared)[0]}; addr={addr}"})
            else:
                unconfirmed_candidates.append({"owner_name": cand_name, "addr": addr, "city": city,
                                                "confidence_tier": TIER_UNCONFIRMED,
                                                "reason": "shared mailing address only; no corroborating shared Sunbiz principal -- not merged per no-strangers-merge rule"})

    # source 2: auction wins not already covered by a zw_parcels row (a fresh
    # win frequently predates that county's next zw_parcels refresh)
    anchor_pins = {r["pin_clean"] for r in anchor_rows}
    sighting_only = []
    for s in buyer_graph["sightings"]:
        if s.get("case_number") and not any(p.get("case_number") == s["case_number"] for p in properties):
            sighting_only.append({
                "case_number": s["case_number"], "county": s["county"], "site_addr": s.get("property_address"),
                "sold_amount": s.get("sold_amount"), "auction_date": s.get("auction_date"),
                "linked_via": "exact_name", "source": "auction_buyer_sightings",
                "confidence_tier": tier_for_property("exact_name", True),
            })

    # zw_parcels.county and auction_buyer_sightings.county are stored with
    # inconsistent casing across rows (confirmed live: 'Polk' and 'polk' both
    # occur for the same county) -- normalize before dedup or county_spread
    # silently over-counts.
    all_counties = sorted({p["county"].strip().title() for p in properties if p.get("county")} |
                           {s["county"].strip().title() for s in sighting_only if s.get("county")})
    total_assessed = sum(float(p.get("val_assessed") or 0) for p in properties)
    total_market = sum(float(p.get("val_market") or 0) for p in properties)

    return {
        "owner_key": owner_key,
        "entity_name": entity_name,
        "properties_from_ownership_records": properties,
        "auction_wins_not_yet_crosswalked": sighting_only,
        "unconfirmed_affiliate_candidates": unconfirmed_candidates,
        "sunbiz": sunbiz,
        "kpi": {
            "total_properties": len(properties) + len(sighting_only),
            "total_assessed_value": total_assessed,
            "total_market_value": total_market,
            "counties": all_counties,
            "county_spread": len(all_counties),
            "acquisition_velocity": acquisition_velocity(buyer_graph["sightings"]),
            "confidence_summary": {
                tier: sum(1 for p in properties if p["confidence_tier"] == tier) + sum(1 for s in sighting_only if s["confidence_tier"] == tier)
                for tier in (TIER_VERIFIED_PRIMARY, TIER_VERIFIED_CROSS_CHECKED, TIER_LIKELY_SINGLE_SOURCE, TIER_UNCONFIRMED)
            },
        },
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("entity_names", nargs="+")
    ap.add_argument("--live-sunbiz-cascade", action="store_true", help="Run the paid Exa/Bright Data/Playwright Sunbiz cascade for names not in the local sunbiz_entities bulk sync")
    args = ap.parse_args()
    print(json.dumps(reachable_backends(), indent=2))
    for name in args.entity_names:
        print(json.dumps(resolve_entity_portfolio(name, run_live_cascade=args.live_sunbiz_cascade), indent=2, default=str))
