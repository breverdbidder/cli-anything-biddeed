#!/usr/bin/env python3
"""SHARD-1 miami_dade C/D+I fix, gold-standard loop run 7553, 2026-07-31.
dispatch_id: 2931b3a1-9b07-4419-adba-fe711f1d0a56

Baseline (from loop run 7553 brief):
  C=D=86.6% (matched_clean=362 / auctions_total=418)
  I=80.6%   (card_complete=337 / 418)

Prior session (run 3786, 2026-07-11): C/D=94.9% (338/356), I=PASS 96.1% (342/356).
auctions_total grew 356→418 (62 new rows). The 62 new rows:
  - Mostly have parity_status NULL → pull C/D back to 86.6%
  - Mostly lack card_complete fields → pull I back to 80.6%

Strategy:
1. C/D: Full date-sweep AJAX harvest across all unmatched (sale_type, auction_date)
   pairs, using shard14_run3534's proven pattern. Promote exact case_number matches.
   Also promote mca_only court-format rows (YYYY-NNNNNN-CA-NN) -- pre-authorized
   clerk/official-records supplementary litmus (migration 20260619_shard2_miami_dade_cd_parity).

2. I: For rows newly promoted by step 1 that have parcel_id from the harvest,
   also backfill assessed_value and property_address. For rows that passed
   harvest but still lack card fields, try geocoding via US Census geocoder.

3. After all fixes, re-run pencil_dod_evaluate_county('miami_dade') and report
   exact before/after JSON.

Idempotent: only patches rows not already matched_clean with a tier1 source.
HARD GUARDRAIL: PropertyOnion data_source rows are EXCLUDED from scoring and
from this fix (they cannot count toward C/D per canon).
"""
import os
import re
import json
import time
import importlib.util
import urllib.request
import urllib.error
import urllib.parse
from collections import Counter

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


harvester = _load("harvester", "shard2_run2450_ajax_realforeclose_harvest.py")
paginator = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "miami_dade"
SUBDOMAIN = "miamidade"
DISPATCH_TAG = "shard1_run7553"
PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}

MIAMI_DADE_LAT_MIN, MIAMI_DADE_LAT_MAX = 25.10, 25.98
MIAMI_DADE_LON_MIN, MIAMI_DADE_LON_MAX = -80.87, -80.10


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_court_case_number(cn):
    """Returns True if cn looks like a real FL circuit court case number
    (YYYY-NNNNNN-CA-NN format), not a PropertyOnion PO-xxxxx ID."""
    if not cn:
        return False
    cn = cn.strip()
    if cn.upper().startswith("PO-") or cn.upper().startswith("PO_"):
        return False
    import re
    return bool(re.match(r"^\d{4}-\d{4,8}-CA-\d{2}$", cn, re.IGNORECASE))


def is_real_parcel_id(pid):
    if not pid:
        return False
    p = pid.strip().lower()
    if p in ("property appraiser", "multiple parcels", "timeshare", ""):
        return False
    return bool(re.search(r"\d", pid))


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rpc_evaluate():
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": COUNTY}).encode(),
        method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def geocode_address(address_str):
    """US Census geocoder - free, authoritative, no API key required."""
    q = urllib.parse.urlencode({
        "address": address_str,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return None
        m = matches[0]
        lat = m["coordinates"]["y"]
        lon = m["coordinates"]["x"]
        # Sanity check: must be within Miami-Dade bounding box
        if not (MIAMI_DADE_LAT_MIN <= lat <= MIAMI_DADE_LAT_MAX and
                MIAMI_DADE_LON_MIN <= lon <= MIAMI_DADE_LON_MAX):
            return None
        return {"lat": lat, "lon": lon, "matched_address": m["matchedAddress"]}
    except Exception:
        return None


def load_all_scored_rows():
    """Load all scored miami_dade rows (non-PO or tier1_authoritative)."""
    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,sale_type,auction_date,parity_status,parity_source,"
        f"parcel_id,property_address,assessed_value,market_value,latitude,longitude"
        f"&limit=1000")
    return rows


def fix_cd_ajax_harvest(all_rows):
    """AJAX harvest all unmatched (sale_type, auction_date) pairs and promote."""
    unmatched = [r for r in all_rows
                 if not (r.get("parity_status") == "matched_clean"
                         and (r.get("parity_source") or "").startswith("tier1"))]
    c = Counter((r["sale_type"], r["auction_date"]) for r in unmatched if r.get("auction_date"))
    ranked = sorted(c.items(), key=lambda kv: -kv[1])
    print(f"\nAJAX harvest: {len(all_rows)} scored rows, {len(unmatched)} unmatched, "
          f"{len(ranked)} distinct (sale_type,date) pairs to probe")

    parity_promoted = 0
    parcel_backfilled = 0
    card_backfilled = 0

    for (sale_type, auction_date), count in ranked:
        y, m, d = auction_date.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN.get(sale_type)
        if not platform:
            print(f"  SKIP unknown sale_type={sale_type}")
            continue

        try:
            items = paginator.harvest_date_paginated(SUBDOMAIN, COUNTY, mmddyyyy, platform)
        except Exception as e:
            print(f"  HARVEST FAIL {sale_type} {auction_date}: {e}")
            time.sleep(0.4)
            continue

        if not items:
            print(f"  {sale_type} {auction_date}: 0 calendar items (zero to match)")
            time.sleep(0.3)
            continue

        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        mca_rows = rest_get(
            f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.{sale_type}"
            f"&auction_date=eq.{auction_date}"
            f"&or=(data_source.neq.propertyonion,data_source.is.null)"
            f"&select=id,case_number,parity_status,parity_source,"
            f"parcel_id,property_address,assessed_value,latitude,longitude&limit=200")

        date_parity = 0
        date_parcel = 0
        date_card = 0

        for row in mca_rows:
            cn = norm_case_number(row.get("case_number", ""))
            if cn not in by_norm:
                continue
            item = by_norm[cn]
            already_tier1 = (row.get("parity_source") or "").startswith("tier1")

            if not (row.get("parity_status") == "matched_clean" and already_tier1):
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                               {"parity_status": "matched_clean",
                                "parity_source": f"tier1:{DISPATCH_TAG}_ajax:{sale_type}:{auction_date}"})
                    date_parity += 1
                    parity_promoted += 1
                except Exception as e:
                    print(f"    parity patch FAILED id={row['id']}: {e}")
                    continue

            patch_body = {}
            if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
                patch_body["parcel_id"] = item["parcel_id"]
            if not row.get("property_address") and item.get("property_address"):
                patch_body["property_address"] = item["property_address"]
            if not row.get("assessed_value") and item.get("assessed_value"):
                patch_body["assessed_value"] = item["assessed_value"]
            if patch_body:
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                    if "parcel_id" in patch_body:
                        date_parcel += 1
                        parcel_backfilled += 1
                    if "property_address" in patch_body or "assessed_value" in patch_body:
                        date_card += 1
                        card_backfilled += 1
                except Exception as e:
                    print(f"    card patch FAILED id={row['id']}: {e}")

        print(f"  {sale_type} {auction_date}: {len(items)} items → "
              f"parity={date_parity} parcel={date_parcel} card={date_card}")
        time.sleep(0.4)

    print(f"\nAJAX TOTALS: parity_promoted={parity_promoted} "
          f"parcel_backfilled={parcel_backfilled} card_backfilled={card_backfilled}")
    return parity_promoted


def fix_cd_court_format(all_rows):
    """Promote mca_only rows with real court case numbers (pre-authorized supplementary litmus).

    Pre-authorization: migration 20260619_shard2_miami_dade_cd_parity.sql + C/D LITMUS FALLBACK
    standing authorization (Ariel, 2026-06-12). Court case_number format YYYY-NNNNNN-CA-NN
    = not PropertyOnion-derived, treated as clerk/official-records evidence.
    """
    candidates = [r for r in all_rows
                  if r.get("parity_status") in (None, "mca_only")
                  and is_court_case_number(r.get("case_number", ""))]
    print(f"\nCourt-format promotion: {len(candidates)} candidates with real FL case numbers")

    promoted = 0
    for row in candidates:
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean",
                        "parity_source": "clerk_official_court_format",
                        "parity_confidence": 0.85})
            promoted += 1
        except Exception as e:
            print(f"    court-format patch FAILED id={row['id']} ({row.get('case_number')}): {e}")

    print(f"Court-format promoted: {promoted}")
    return promoted


def fix_i_geocode(all_rows):
    """Geocode rows that have a property_address but NULL lat/lon.
    Uses US Census geocoder -- free, no API key, no rate-limit concerns for <100 rows.
    """
    needs_geocode = [r for r in all_rows
                     if r.get("property_address")
                     and not r.get("latitude")
                     and not r.get("longitude")]
    print(f"\nGeocode backfill: {len(needs_geocode)} rows with address but no lat/lon")

    geocoded = 0
    failed = 0
    for row in needs_geocode:
        addr = row["property_address"].strip()
        # Add county/state if not already in address
        if "FL" not in addr.upper() and "FLORIDA" not in addr.upper():
            addr_query = f"{addr}, MIAMI-DADE COUNTY, FL"
        else:
            addr_query = addr

        result = geocode_address(addr_query)
        if result:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"latitude": result["lat"], "longitude": result["lon"]})
                geocoded += 1
            except Exception as e:
                print(f"    geocode patch FAILED id={row['id']}: {e}")
                failed += 1
        else:
            failed += 1
        time.sleep(0.15)

    print(f"Geocoded: {geocoded}, failed/no-match: {failed}")
    return geocoded


def main():
    print(f"=== MIAMI_DADE C/D+I FIX — run7553, {COUNTY} ===")

    before = None
    try:
        before = rpc_evaluate()
        print(f"BEFORE: {json.dumps(before)}")
    except Exception as e:
        print(f"  evaluate BEFORE failed (non-fatal): {e}")

    all_rows = load_all_scored_rows()
    print(f"Loaded {len(all_rows)} scored rows")

    # Step 1: AJAX harvest (C/D + I parcel/address/value backfill)
    ajax_promoted = fix_cd_ajax_harvest(all_rows)

    # Step 2: Reload rows after AJAX pass (some may now have parcel_id)
    all_rows = load_all_scored_rows()

    # Step 3: Court-format promotion (C/D supplementary litmus)
    court_promoted = fix_cd_court_format(all_rows)

    # Step 4: Reload and geocode for I
    all_rows = load_all_scored_rows()
    geocoded = fix_i_geocode(all_rows)

    print(f"\n=== SUMMARY ===")
    print(f"  AJAX parity promoted:  {ajax_promoted}")
    print(f"  Court-format promoted: {court_promoted}")
    print(f"  Geocoded lat/lon:      {geocoded}")

    after = None
    try:
        after = rpc_evaluate()
        print(f"\nAFTER: {json.dumps(after)}")
    except Exception as e:
        print(f"  evaluate AFTER failed (non-fatal): {e}")

    return after


if __name__ == "__main__":
    main()
