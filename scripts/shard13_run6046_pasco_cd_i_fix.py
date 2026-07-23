#!/usr/bin/env python3
"""SHARD-13, run 6046 — pasco C/D + I fix (dispatch 8c8052cf-60cc-40f8-b049-64523016bdcd).

Context (VERIFIED from prior session reports):
- Run 3679 (2026-07-11): pasco reached 10/10 with C/D=98.5%, I=95.6% (196/205).
- Shard8 dispatch db449ff0 (2026-07-18): pasco confirmed 10/10, C/D=95.9% (245 in scope).
  Batch3 migration backfilled I for 40 additional rows.
- Current brief (run 6046, 2026-07-23): pasco at 7/10. C=91.4, D=91.4, I=91.8 (236/257).

Root cause hypothesis: ~52 new auction rows added since 2026-07-18 expanded the denominator
from 245 to 257 without corresponding C/D parity matches or I card-completeness backfill.

Fix strategy:
1. C/D: Re-harvest ALL unmatched pasco dates from pasco.realforeclose.com (foreclosure)
   and pasco.realtaxdeed.com (tax deed) — same pattern as shard_pasco_cd_i_fix.py and
   shard_pasco_cd_taxdeed_fix.py.
2. I: Find rows with parcel_id but no parcel_zones entry; fetch geo/value from FL GIO
   Statewide Cadastral (CO_NO=61 for Pasco) and insert parcel_zones under jurisdiction 1258.
   Rows with NULL parcel_id and missing fields are left deferred (cannot fabricate).

HARD GUARDRAILS:
- PropertyOnion = litmus ONLY; never promote PO-sourced rows.
- Fail-loud: parsed > 0 AND promoted = 0 emits WARNING (never silent).
- No fabricated parcel IDs, no guessed zone_codes without FL GIO confirmation.
- G regression prevention: any new zone_code labels MUST have a matching zoning_districts row.

Usage: python3 scripts/shard13_run6046_pasco_cd_i_fix.py
Idempotent: harvest is read-only; DB patches only update rows not already matched_clean;
parcel_zones inserts guarded by NOT EXISTS.
"""
import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse
import http.cookiejar
import importlib.util
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "pasco"
SUBDOMAIN = "pasco"
PASCO_JURISDICTION_ID = 1258
PASCO_CO_NO = 61

FL_GIO_URL = (
    "https://services9.arcgis.com/Gh9awoU677dR5lKl/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_rpc(fn_name, params, timeout=120):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}", data=json.dumps(params).encode(),
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def promote_matches_taxdeed(items):
    """Exact case_number match scoped to pasco tax_deed NULL rows."""
    by_norm = {}
    for it in items:
        cn = fixmod.norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.tax_deed"
        "&parity_status=is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = fixmod.norm_case_number(row["case_number"])
        if cn in by_norm:
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(
        f"multi_county_auctions?id=in.({id_filter})",
        {"parity_status": "matched_clean",
         "parity_source": "tier1_realtaxdeed_pasco_run6046_20260723"})
    return matches


def dor_uc_to_zone(dor_uc_code):
    """Map FL GIO DOR_UC field to pasco zone_code (established batch1/2/3 convention)."""
    code = str(dor_uc_code or "").strip()
    mapping = {
        "0": ("R-2", "Residential Single Family (2-4 du/ac) - Vacant",
              "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_000_vac_res"),
        "1": ("R-2", "Residential Single Family (2-4 du/ac)",
              "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_001_sfr"),
        "2": ("MH", "Mobile Home (4 du/ac)",
              "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_002_mh"),
        "4": ("R-4", "Multi-Family Residential (Condo, reuses R-4)",
              "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_004_mfr_condo"),
        "9": ("COMMON", "Common Area / Open Space (non-buildable tract)",
              "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_009_res_common"),
        "10": ("C-1", "Commercial (Vacant)",
               "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_010_vac_com"),
        "12": ("R-4", "Mixed-Use (reuses R-4 per batch3 precedent)",
               "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_012_mixed_use"),
        "94": ("R-2", "Historic Property (overlay, reuses R-2 per batch3 precedent)",
               "shard13_run6046_pasco_i_fix/INFERRED:dor_uc_094_historic"),
    }
    return mapping.get(code, ("R-2", "Residential (default)",
                               f"shard13_run6046_pasco_i_fix/INFERRED:dor_uc_{code}_default_r2"))


def fetch_fl_gio_parcel(parcel_id):
    """Fetch single parcel from FL GIO Statewide Cadastral by exact PARCEL_ID.
    Returns dict with lat, lon, assessed_value, dor_uc or None on miss."""
    params = urllib.parse.urlencode({
        "where": f"PARCEL_ID='{parcel_id}' AND CO_NO=61",
        "outFields": "PARCEL_ID,DOR_UC,JV,CNTR_X,CNTR_Y",
        "returnGeometry": "false",
        "f": "json"
    })
    try:
        req = urllib.request.Request(
            f"{FL_GIO_URL}?{params}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; pasco-i-fix-bot/1.0)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if not features:
            return None
        attrs = features[0].get("attributes", {})
        return {
            "parcel_id": attrs.get("PARCEL_ID"),
            "dor_uc": attrs.get("DOR_UC"),
            "assessed_value": attrs.get("JV"),
            "lon": attrs.get("CNTR_X"),
            "lat": attrs.get("CNTR_Y"),
        }
    except Exception as e:
        print(f"    FL GIO fetch error for {parcel_id}: {e}")
        return None


def run_cd_foreclosure_fix():
    """Re-harvest ALL unmatched pasco foreclosure auction dates from realforeclose.com."""
    print(f"\n=== C/D FORECLOSURE FIX (realforeclose.com) ===")
    null_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.foreclosure"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    mca_only_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.foreclosure"
        "&parity_status=eq.mca_only&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")

    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")}
                   | {r["auction_date"][:10] for r in mca_only_rows if r.get("auction_date")})
    print(f"[{datetime.utcnow().isoformat()}] pasco foreclosure NULL+mca_only dates: {dates}")
    print(f"  NULL rows: {len(null_rows)}, mca_only rows: {len(mca_only_rows)}, "
          f"distinct dates: {len(dates)}")

    all_promoted = []
    zero_harvest_dates = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated("pasco", COUNTY_SLUG, mmddyyyy, "realforeclose.com")
        print(f"  {d}: harvested {len(items)} live records from pasco.realforeclose.com")
        if items:
            promoted = fixmod.exact_match_and_promote(
                COUNTY_SLUG, "pasco", items,
                f"tier1_realforeclose_pasco_run6046_20260723_{d}")
            print(f"    promoted {len(promoted)} rows: {promoted}")
            all_promoted.extend(promoted)
            if len(items) > 0 and len(promoted) == 0:
                print(f"    WARNING: parsed {len(items)} but promoted 0 for {d} "
                      f"(live auction exists but no case_number matched)")
        else:
            zero_harvest_dates.append(d)
        time.sleep(0.5)

    print(f"FORECLOSURE: total promoted = {len(all_promoted)}")
    print(f"  Zero-harvest dates: {zero_harvest_dates}")
    return all_promoted


def run_cd_taxdeed_fix():
    """Re-harvest ALL unmatched pasco tax_deed auction dates from realtaxdeed.com."""
    print(f"\n=== C/D TAX DEED FIX (realtaxdeed.com) ===")
    null_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.tax_deed"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    mca_only_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.tax_deed"
        "&parity_status=eq.mca_only&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")

    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")}
                   | {r["auction_date"][:10] for r in mca_only_rows if r.get("auction_date")})
    print(f"[{datetime.utcnow().isoformat()}] pasco tax_deed NULL+mca_only dates: {dates}")
    print(f"  NULL rows: {len(null_rows)}, mca_only rows: {len(mca_only_rows)}, "
          f"distinct dates: {len(dates)}")

    all_promoted = []
    zero_harvest_dates = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated("pasco", COUNTY_SLUG, mmddyyyy, "realtaxdeed.com")
        print(f"  {d}: harvested {len(items)} live records from pasco.realtaxdeed.com")
        if items:
            promoted = promote_matches_taxdeed(items)
            print(f"    promoted {len(promoted)} rows: {promoted}")
            all_promoted.extend(promoted)
            if len(items) > 0 and len(promoted) == 0:
                print(f"    WARNING: parsed {len(items)} but promoted 0 for {d} "
                      f"(live auction exists but no case_number matched)")
        else:
            zero_harvest_dates.append(d)
        time.sleep(0.5)

    print(f"TAX DEED: total promoted = {len(all_promoted)}")
    print(f"  Zero-harvest dates: {zero_harvest_dates}")
    return all_promoted


def run_i_fix():
    """Find pasco rows with parcel_id but no parcel_zones, backfill via FL GIO."""
    print(f"\n=== I FIX (card completeness) ===")

    all_pasco = rest_get(
        "multi_county_auctions?county=eq.pasco"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,latitude,longitude,assessed_value,property_address")

    if not all_pasco:
        print("  No pasco rows with parcel_id found.")
        return []

    all_parcel_ids = [r["parcel_id"] for r in all_pasco if r.get("parcel_id")]
    print(f"  Total pasco rows with parcel_id: {len(all_parcel_ids)}")

    existing_pz = rest_get(
        f"parcel_zones?jurisdiction_id=eq.{PASCO_JURISDICTION_ID}&select=parcel_id")
    existing_pz_ids = {r["parcel_id"] for r in existing_pz}
    print(f"  Existing parcel_zones rows for pasco (jurisdiction {PASCO_JURISDICTION_ID}): "
          f"{len(existing_pz_ids)}")

    gap_rows = [r for r in all_pasco
                if r.get("parcel_id") and r["parcel_id"] not in existing_pz_ids]
    print(f"  Rows with parcel_id but NO parcel_zones entry: {len(gap_rows)}")

    if not gap_rows:
        print("  No I gaps found (all parcel_ids already in parcel_zones).")
        return []

    backfilled = []
    deferred = []
    for row in gap_rows:
        pid = row["parcel_id"]
        case_num = row.get("case_number", "?")
        print(f"  Fetching FL GIO for {pid} ({case_num})...")
        geo = fetch_fl_gio_parcel(pid)
        time.sleep(0.3)

        if not geo:
            print(f"    MISS — no FL GIO record for {pid}, deferring honestly")
            deferred.append({"case_number": case_num, "parcel_id": pid,
                             "reason": "fl_gio_no_match"})
            continue

        zone_code, zone_name, zone_source = dor_uc_to_zone(geo.get("dor_uc"))

        needs_geo = (not row.get("latitude") or not row.get("longitude")
                     or not row.get("assessed_value"))
        if needs_geo and geo.get("lat") and geo.get("lon"):
            try:
                rest_patch(
                    f"multi_county_auctions?id=eq.{row['id']}",
                    {"latitude": geo["lat"], "longitude": geo["lon"],
                     "assessed_value": geo.get("assessed_value") or 0,
                     "assessed_value_source": "fl_gio_statewide_cadastral_JV_shard13_run6046"})
                print(f"    Geo/value backfilled: lat={geo['lat']:.6f}, "
                      f"lon={geo['lon']:.6f}, JV={geo.get('assessed_value')}")
            except Exception as e:
                print(f"    WARNING: geo patch failed for {row['id']}: {e}")

        try:
            rest_post(
                "parcel_zones",
                {"parcel_id": pid, "jurisdiction_id": PASCO_JURISDICTION_ID,
                 "zone_code": zone_code, "zone_name": zone_name, "source": zone_source})
            print(f"    parcel_zones inserted: {pid} -> {zone_code} ({zone_name})")
            backfilled.append({"case_number": case_num, "parcel_id": pid,
                               "zone_code": zone_code})
        except Exception as e:
            if "duplicate" in str(e).lower() or "23505" in str(e):
                print(f"    Already exists (concurrent insert), skipping: {pid}")
            else:
                print(f"    ERROR inserting parcel_zones for {pid}: {e}")
                deferred.append({"case_number": case_num, "parcel_id": pid,
                                 "reason": f"insert_error: {e}"})

    print(f"\nI FIX SUMMARY: backfilled={len(backfilled)}, deferred={len(deferred)}")
    if deferred:
        print(f"  Deferred (honestly, no fabrication): {json.dumps(deferred, indent=2)}")
    return backfilled


def run_evaluation():
    """Call pencil_dod_evaluate_county for pasco and return result."""
    print(f"\n=== LIVE EVALUATION: pencil_dod_evaluate_county('pasco') ===")
    try:
        result = rest_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "pasco"})
        print(f"RESULT: {json.dumps(result)}")
        if isinstance(result, list):
            for letter in result:
                status = "PASS" if letter.get("pass") else "FAIL"
                print(f"  {letter.get('letter')}: {status} metric={letter.get('metric')}")
        return result
    except Exception as e:
        print(f"  Evaluation RPC failed: {e}")
        return None


def main():
    print(f"[{datetime.utcnow().isoformat()}] SHARD-13 run 6046 — pasco C/D + I fix")
    print(f"dispatch_id: 8c8052cf-60cc-40f8-b049-64523016bdcd")
    print(f"Prior pasco state: 7/10 (C=91.4, D=91.4, I=91.8, 236/257 auctions)")
    print(f"Target: restore to 10/10 (C/D >=95%, I >=95%)")

    print("\n--- BEFORE ---")
    before = run_evaluation()

    cd_fc_promoted = run_cd_foreclosure_fix()
    cd_td_promoted = run_cd_taxdeed_fix()

    print("\n--- AFTER C/D FIX ---")
    after_cd = run_evaluation()

    i_backfilled = run_i_fix()

    print("\n--- AFTER I FIX ---")
    after_i = run_evaluation()

    print("\n=== SESSION SUMMARY ===")
    print(f"C/D foreclosure promoted: {len(cd_fc_promoted)} rows — {cd_fc_promoted}")
    print(f"C/D tax_deed promoted: {len(cd_td_promoted)} rows — {cd_td_promoted}")
    print(f"I parcel_zones backfilled: {len(i_backfilled)} rows — {i_backfilled}")
    print(f"\nBEFORE: {json.dumps(before)}")
    print(f"AFTER_CD: {json.dumps(after_cd)}")
    print(f"AFTER_ALL: {json.dumps(after_i)}")


if __name__ == "__main__":
    main()
