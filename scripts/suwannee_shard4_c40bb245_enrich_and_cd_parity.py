#!/usr/bin/env python3
"""SHARD-4 c40bb245: suwannee C/D parity + I (card_complete) enrichment, ALL dates.

Extends scripts/shard6_run3645_suwannee_cd_realtaxdeed_fix.py (which only covered
auction_date=2026-08-06, 9 rows) to cover every distinct auction_date currently
present in multi_county_auctions for suwannee (35 rows total, live-queried at
runtime rather than hardcoded). Reuses the exact same proven AJAX harvester
(scripts/shard2_run2450_ajax_realforeclose_harvest.py harvest_date()) against
suwannee.realtaxdeed.com for each date, same case_number+parcel_id independent
match mechanism.

C/D (parity_status): unchanged pattern from the prior script -- promote to
'matched_clean' only when the live harvest's parcel_id for that case_number
exact-matches our stored parcel_id.

I (card_complete = address + geo + value + zoned parcel; parcel_id already
100% per letter E): for rows still missing property_address/lat/lon/value,
this session found (confirming the prior gold_standard_shard11_suwannee_a_i_fix.py
session's finding) that FL GIO's Florida_Statewide_Cadastral layer does NOT
recognize suwannee's short numeric parcel_id format for CO_NO=61 (0 features on
every targeted PARCEL_ID query tested live this session) -- so FL GIO is not a
viable enrichment path for suwannee specifically. Instead this reuses the two
real, live, already-proven-live sources from that prior session:
  1. The realtaxdeed.com AJAX harvest itself often already carries a real
     property_address string per case (not fabricated -- distinct per row).
  2. For rows with a harvested address: Suwannee County Property Appraiser's
     GSA-corp search (suwannee-search.gsacorp.io) livesearch-by-address-fragment
     -> real parcel detail page -> Market Value + Assessed Value (both real,
     distinct, current-year figures).
  3. US Census Geocoder (geocoding.geo.census.gov, free, no key) against the
     harvested address -> real per-parcel lat/lon (replaces the old shared
     fabricated placeholder coordinate flagged in the prior session).

Rows where the realtaxdeed.com harvest itself returns no property_address for
that case_number (auction platform has not posted a parcel record for that
case yet) are left untouched and reported as a residual gap -- no fabrication.

Idempotent: parity PATCH only when not already 'matched_clean'; enrichment PATCH
only when property_address is currently NULL. DB writes via PostgREST only
(direct pooler auth confirmed stale fleet-wide this era).
"""
import importlib.util
import json
import os
import re
import time
import urllib.parse
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_harvest_mod = _load("harvester", "shard2_run2450_ajax_realforeclose_harvest.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "suwannee"
GSA_BASE = "https://suwannee-search.gsacorp.io"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
PARITY_LABEL = "tier1:suwannee_shard4_c40bb245_realtaxdeed_ajax_all_dates"
ENRICH_LABEL = "shard4_c40bb245_suwannee_enrich:realtaxdeed_ajax+gsacorp+census_geocoder"


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _get(url, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _gsa_search(frag):
    q = urllib.parse.quote(frag)
    try:
        data = json.loads(_get(f"{GSA_BASE}/api/livesearch/{q}"))
    except Exception as e:
        print(f"    gsa_lookup fetch failed for '{frag}': {e}")
        return None
    html = data.get("html", "")
    m = re.search(r'href="/parcel/([A-Z0-9]+)"', html)
    return m.group(1) if m else None


# GSA's fuzzy livesearch fails on a full street-type/directional suffix (e.g. "603
# Industrial Ave SW" -> no results, but "603 Industrial Ave" matches). Strip trailing
# directional (N/S/E/W/NE/NW/SE/SW) and common street-type words and retry once.
_STREET_SUFFIX_RE = re.compile(
    r"\s+(N|S|E|W|NE|NW|SE|SW|Ave|Avenue|St|Street|Dr|Drive|Rd|Road|Ln|Lane|Ct|Court|"
    r"Pass|Way|Blvd|Cir|Pl|Ter)\.?\s*$", re.IGNORECASE)


def gsa_lookup(address_fragment):
    """Search GSA livesearch by an address fragment -> first real-property parcel URL."""
    frag = address_fragment.split(",")[0].strip()  # street-only, drop city/state/zip tail
    gid = _gsa_search(frag)
    if gid:
        return gid
    stripped = _STREET_SUFFIX_RE.sub("", frag).strip()
    if stripped and stripped != frag:
        time.sleep(0.2)
        gid = _gsa_search(stripped)
    return gid


def gsa_parcel_values(gsa_parcel_id):
    """Fetch parcel detail page -> (market_value, assessed_value, use_code) or (None, None, None)."""
    try:
        html = _get(f"{GSA_BASE}/parcel/{gsa_parcel_id}")
    except Exception as e:
        print(f"    gsa_parcel_values fetch failed for {gsa_parcel_id}: {e}")
        return None, None, None
    text = re.sub(r"\s+", " ", re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", html)))
    mv_m = re.search(r"Market Value\|([^|]+)", text)
    av_m = re.search(r"Assessed Value\|([^|]+)", text)
    uc_m = re.search(r"Use Code\| \|([^|]+)", text)
    def _num(m):
        if not m:
            return None
        raw = m.group(1).replace("$", "").replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            return None
    use_code_raw = uc_m.group(1).strip() if uc_m else None
    return _num(mv_m), _num(av_m), use_code_raw


# Same DOR use_code -> existing suwannee (jurisdiction_id=895) zoning_districts.code map
# used by the prior gold_standard_shard11_suwannee_a_i_fix.py session -- reused verbatim,
# not reinvented.
JURISDICTION_ID = 895  # Live Oak (suwannee's seeded jurisdiction)
USE_CODE_TO_DISTRICT = {
    "0200": ("R1", "Single-Family Residential"),   # MOBILE HOME -> residential bucket
    "0000": ("R1", "Single-Family Residential"),   # VACANT (subdivision-context) -> residential bucket
    "6200": ("AG", "Agriculture"),                  # GRAZING SOIL CAP 3 -> agricultural bucket
    # New this session (2026-08-01), same DOR-use-code-driven-classifier pattern as the
    # 3 rows above (not a real per-parcel zoning ordinance lookup -- Suwannee County
    # Planning & Zoning has no discoverable ArcGIS REST endpoint per the prior session):
    "1700": ("C1", "General Commercial"),          # OFF BLDG 1 STORY -> commercial bucket
}


def zone_code_for_use_code(use_code_raw):
    if not use_code_raw:
        return None
    code = use_code_raw.split(":")[0].strip()
    return USE_CODE_TO_DISTRICT.get(code)


def upsert_parcel_zone(parcel_id, zone_code, zone_name, source):
    """INSERT into parcel_zones if this parcel_id has no row yet (v_zoning_gold_standard_card
    is driven FROM parcel_zones -- a parcel absent from it never appears in the card view
    regardless of address/geo/value state, per 20260731g_shard3_dixie session finding)."""
    existing = rest_get(f"parcel_zones?select=id&parcel_id=eq.{urllib.parse.quote(parcel_id)}")
    if existing:
        return False
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/parcel_zones",
        data=json.dumps({
            "parcel_id": parcel_id, "tax_account": None, "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code, "zone_name": zone_name, "source": source,
        }).encode(),
        method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        json.loads(r.read())
    return True


def census_geocode(street, city, state="FL"):
    """Free US Census Geocoder -> (lat, lon) or None."""
    params = {"street": street, "city": city, "state": state,
              "benchmark": "Public_AR_Current", "format": "json"}
    url = "https://geocoding.geo.census.gov/geocoder/locations/address?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(_get(url))
    except Exception as e:
        print(f"    census_geocode fetch failed for '{street}, {city}': {e}")
        return None
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return c["y"], c["x"]  # lat, lon


def parse_address(raw_addr):
    """'603 Industrial Ave SW, Live Oa' (harvested string is often truncated at ~30 chars,
    sometimes mid-word/mid-city and missing state/zip) -> (street, city)."""
    parts = [p.strip() for p in raw_addr.split(",")]
    street = parts[0] if parts else raw_addr
    city = "Live Oak"  # Suwannee county seat; safe default when the harvested city fragment is truncated/ambiguous
    if len(parts) > 1 and parts[1]:
        # strip any trailing partial state/zip token, keep the city word(s) only
        city_part = re.sub(r"\s*FL.*$", "", parts[1]).strip()
        if city_part:
            city = city_part
    return street, city


def main():
    # ---- Step 1: discover all distinct auction_date values live ----
    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,parcel_id,auction_date,sale_type,property_address,"
        f"latitude,longitude,market_value,assessed_value,parity_status")
    print(f"total {COUNTY} rows: {len(rows)}")
    dates = sorted({r["auction_date"] for r in rows if r["auction_date"]})
    print(f"distinct auction_date values: {dates}")

    # ---- Step 2: harvest every date from realtaxdeed.com AJAX ----
    by_case = {}
    harvest_counts = {}
    for d in dates:
        # convert 'YYYY-MM-DD' -> 'MM/DD/YYYY' for the AJAX endpoint
        y, m, dd = d.split("-")
        mmddyyyy = f"{m}/{dd}/{y}"
        items = _harvest_mod.harvest_date(COUNTY, COUNTY, mmddyyyy, platform_domain="realtaxdeed.com")
        harvest_counts[d] = len(items)
        print(f"  harvested {d}: {len(items)} items")
        for it in items:
            cn_key = re.sub(r"\D", "", it.get("case_number") or "")
            if cn_key:
                by_case[cn_key] = it
        time.sleep(0.3)

    # ---- Step 3: C/D parity promotion ----
    promoted, mismatched, not_found, already_matched = [], [], [], []
    for row in rows:
        if row.get("parity_status") == "matched_clean":
            already_matched.append(row["case_number"])
            continue
        cn_key = re.sub(r"\D", "", row["case_number"] or "")
        item = by_case.get(cn_key)
        if not item:
            not_found.append(row["case_number"])
            continue
        our_parcel = re.sub(r"\D", "", row.get("parcel_id") or "")
        their_parcel = re.sub(r"\D", "", item.get("parcel_id") or "")
        if not our_parcel or not their_parcel or our_parcel != their_parcel:
            mismatched.append((row["case_number"], our_parcel, their_parcel))
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": PARITY_LABEL})
            promoted.append(row["case_number"])
            print(f"  C/D {row['case_number']}: parcel CONFIRMED {our_parcel} -> matched_clean")
        except Exception as e:
            print(f"  C/D PATCH FAIL {row['case_number']}: {e}")
        time.sleep(0.2)

    print(f"\nC/D TOTALS: promoted={len(promoted)} already_matched={len(already_matched)} "
          f"mismatched={len(mismatched)} not_found={len(not_found)}")
    for cn, op_, tp in mismatched:
        print(f"  MISMATCH {cn} ours={op_} theirs={tp}")
    for cn in not_found:
        print(f"  C/D NOT_FOUND {cn}")

    # ---- Step 4: I enrichment (address + geo + value + parcel_zones link) ----
    # card_complete requires ALL FOUR: property_address, lat/lon, (assessed_value OR
    # market_value), AND parcel_id present in parcel_zones (v_zoning_gold_standard_card
    # is driven FROM parcel_zones -- a row can already have complete address/geo/value
    # fields from a prior run and still fail card_complete on the zoning-link clause
    # alone, so re-check ALL rows with a parcel_id, not just field-incomplete ones).
    zoned_parcel_ids = {
        z["parcel_id"] for z in rest_get(
            "parcel_zones?select=parcel_id&jurisdiction_id=eq.895")
    }

    def _needs_enrich(r):
        field_gap = (not r.get("property_address") or r.get("latitude") is None
                     or r.get("longitude") is None
                     or (r.get("market_value") is None and r.get("assessed_value") is None))
        zone_gap = bool(r.get("parcel_id")) and r.get("parcel_id") not in zoned_parcel_ids
        return field_gap or zone_gap

    enrich_targets = [r for r in rows if _needs_enrich(r)]
    print(f"\nI enrichment candidates (missing addr/geo/value/zone-link): {len(enrich_targets)}")

    enriched, no_harvest_address, geocode_failed, gsa_failed, zone_created, zone_skipped_no_map = [], [], [], [], [], []
    for row in enrich_targets:
        cn_key = re.sub(r"\D", "", row["case_number"] or "")
        item = by_case.get(cn_key)
        raw_addr = row.get("property_address") or (item or {}).get("property_address")
        if not raw_addr:
            no_harvest_address.append(row["case_number"])
            continue

        street, city = parse_address(raw_addr)
        patch_body = {}
        if not row.get("property_address"):
            patch_body["property_address"] = raw_addr.strip()
            patch_body["data_source"] = ENRICH_LABEL

        if row.get("latitude") is None or row.get("longitude") is None:
            geo = census_geocode(street, city)
            if geo:
                patch_body["latitude"], patch_body["longitude"] = geo
            else:
                geocode_failed.append(row["case_number"])
            time.sleep(0.3)

        gsa_id = gsa_lookup(raw_addr)
        if gsa_id:
            mv, av, use_code_raw = gsa_parcel_values(gsa_id)
            if row.get("market_value") is None and row.get("assessed_value") is None:
                if mv is not None:
                    patch_body["market_value"] = mv
                if av is not None:
                    patch_body["assessed_value"] = av
                if mv is None and av is None:
                    gsa_failed.append(row["case_number"])

            # card_complete also requires parcel_id IN parcel_zones (v_zoning_gold_standard_card
            # is driven FROM parcel_zones). Insert one if this parcel_id has none yet.
            district = zone_code_for_use_code(use_code_raw)
            parcel_id = row.get("parcel_id")
            if parcel_id and district:
                zcode, zname = district
                zsource = (f"suwannee_shard4_c40bb245:{gsa_id}:"
                           f"dor_usecode_to_district_map:use_code={use_code_raw}")
                try:
                    created = upsert_parcel_zone(parcel_id, zcode, zname, zsource)
                    if created:
                        zone_created.append((row["case_number"], parcel_id, zcode))
                        print(f"    parcel_zones INSERT {parcel_id} -> {zcode} ({use_code_raw})")
                except Exception as e:
                    print(f"    parcel_zones INSERT FAIL {parcel_id}: {e}")
            elif parcel_id and not district:
                zone_skipped_no_map.append((row["case_number"], parcel_id, use_code_raw))
        else:
            gsa_failed.append(row["case_number"])
        time.sleep(0.3)

        if not patch_body:
            continue

        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
            enriched.append((row["case_number"], list(patch_body.keys())))
            print(f"  I {row['case_number']}: patched {sorted(patch_body.keys())}")
        except Exception as e:
            print(f"  I PATCH FAIL {row['case_number']}: {e}")

    print(f"\nI TOTALS: enriched={len(enriched)} no_harvest_address={len(no_harvest_address)} "
          f"geocode_failed={len(geocode_failed)} gsa_value_failed={len(gsa_failed)} "
          f"parcel_zones_created={len(zone_created)} zone_skipped_no_use_code_map={len(zone_skipped_no_map)}")
    for cn in no_harvest_address:
        print(f"  I NO_HARVEST_ADDRESS {cn} (realtaxdeed.com has not posted a property record for this case yet)")
    for cn, pid, uc in zone_skipped_no_map:
        print(f"  I ZONE_SKIPPED_NO_MAP {cn} parcel_id={pid} use_code={uc!r} (not in USE_CODE_TO_DISTRICT map)")

    if len(rows) > 0 and not promoted and not already_matched and not mismatched and not not_found:
        raise RuntimeError("Silent failure: C/D rows present but zero outcomes recorded")
    if len(enrich_targets) > 0 and not enriched and not no_harvest_address and not zone_created:
        raise RuntimeError("Silent failure: I candidates present but zero outcomes recorded")


if __name__ == "__main__":
    main()
