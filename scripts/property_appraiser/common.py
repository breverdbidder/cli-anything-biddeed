#!/usr/bin/env python3
"""Shared helpers for property-appraiser cross-verification scrapers.

Writes results to public.parity_audit (existing BidDeed/PropertyOnion litmus
table, reused per dispatch brief). field_name in
{parcel_id, address, owner_of_record, just_value}. verdict in
{pass, fail, flag} per the brief's parity KPI classification:
  - parcel_id / address / legal description  -> blocking (fail = wrong parcel)
  - just_value / land sqft / living area     -> informational only, never fail
  - owner_of_record                          -> flag, never fail (tax-roll lag)
"""
import os
import re
import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

BLOCKING_FIELDS = {"parcel_id", "address", "legal_description"}
INFORMATIONAL_FIELDS = {"just_value", "land_sqft", "living_area"}
FLAG_FIELDS = {"owner_of_record"}


def _norm_text(s):
    if s is None:
        return ""
    s = re.sub(r"[^A-Z0-9]", "", str(s).upper())
    return s


_STREET_SUFFIXES = {
    "AVENUE": "AVE", "STREET": "ST", "DRIVE": "DR", "ROAD": "RD",
    "BOULEVARD": "BLVD", "LANE": "LN", "COURT": "CT", "CIRCLE": "CIR",
    "TERRACE": "TER", "PLACE": "PL", "PARKWAY": "PKWY", "HIGHWAY": "HWY",
    "TRAIL": "TRL",
}


def _addr_tokens(s):
    """Token set, not a squashed string -- a strict substring/containment
    check breaks whenever one side inserts a unit/apt number mid-address
    (e.g. '...OCEAN DR HOLLYWOOD' vs '...OCEAN DR #404 HOLLYWOOD'), which is
    common since our FF address field frequently omits condo unit numbers
    that the county appraiser record includes."""
    if s is None:
        return set()
    s = str(s).upper()
    s = re.sub(r"(\d{5})-\d{4}", r"\1", s)  # zip+4 -> zip5
    for full, abbr in _STREET_SUFFIXES.items():
        s = re.sub(rf"\b{full}\b", abbr, s)
    s = re.sub(r"[^A-Z0-9]", " ", s)
    tokens = {t for t in s.split() if t not in ("UNIT", "APT", "STE", "#")}
    return tokens


def classify_verdict(field_name, ff_value, appraiser_value):
    """Returns (verdict, note) per brief's pass/fail/flag classification."""
    if appraiser_value in (None, ""):
        return "unverified", "appraiser site returned no value for this field"

    if field_name in BLOCKING_FIELDS:
        if field_name == "address":
            a, b = _addr_tokens(ff_value), _addr_tokens(appraiser_value)
            # bidirectional subset: appraiser sites inconsistently include
            # state/zip (Marion omits both) or unit numbers (condos), so
            # neither side is reliably the "fuller" set to check against
            match = bool(a) and bool(b) and (a <= b or b <= a)
        else:
            match = _norm_text(ff_value) == _norm_text(appraiser_value)
        return ("pass", "blocking field matched") if match else ("fail", "BLOCKING mismatch — wrong parcel or bad linkage, do not ship FF")

    if field_name in FLAG_FIELDS:
        match = _norm_text(ff_value) == _norm_text(appraiser_value)
        if match:
            return "pass", "owner of record matches"
        return "flag", "owner of record differs from FF buyer name — expected/routine tax-roll lag (30-90 days); confirm via Clerk deed record before binding, do not reject FF"

    if field_name in INFORMATIONAL_FIELDS:
        return "informational", "value delta only — reassessment/homestead/valuation-date differences are legitimate, never blocks FF"

    return "informational", "unclassified field, treated as informational"


def write_parity_row(case_number, county, field_name, ff_value=None,
                      appraiser_value=None, biddeed_value=None,
                      competitor_value=None, verdict=None, note=None,
                      competitor_name="county_appraiser"):
    if verdict is None:
        verdict, note = classify_verdict(field_name, ff_value, appraiser_value)
    row = {
        "case_number": case_number,
        "county": county,
        "field_name": field_name,
        "competitor_name": competitor_name,
        "ff_value": None if ff_value is None else str(ff_value),
        "appraiser_value": None if appraiser_value is None else str(appraiser_value),
        "verdict": verdict,
        "verdict_note": note,
    }
    if biddeed_value is not None:
        row["biddeed_value"] = biddeed_value
    if competitor_value is not None:
        row["competitor_value"] = competitor_value
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/parity_audit", headers=HEADERS, json=row, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"parity_audit insert failed {r.status_code}: {r.text} | row={row}")
    return r.json()[0]


def load_batch_parcels(county):
    """Load this session's Winner Data intake fixtures for one county."""
    import json
    import glob
    out = []
    for path in glob.glob("summitleads/intake/*.json"):
        d = json.load(open(path))
        prop = d.get("property", {})
        if (prop.get("county", {}).get("value") or "").lower() != county:
            continue
        out.append({
            "id": d["id"],
            "case_number": (d.get("purchase", {}).get("case_number") or {}).get("value") or d["id"],
            "parcel_id": prop.get("parcel_id", {}).get("value"),
            "address": prop.get("address", {}).get("value"),
            "owner": d.get("applicant", {}).get("entity_name", {}).get("value"),
            "just_value": prop.get("just_value", {}).get("value"),
        })
    return out
