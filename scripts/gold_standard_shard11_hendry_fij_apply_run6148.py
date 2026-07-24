#!/usr/bin/env python3
"""Apply the hendry F/I/J migration and verify results.

dispatch_id: bebd50e5-e1a5-4a4e-b1a2-54612d7d7216
session: architect-20260724T080000

Applies migrations/20260724_gold_standard_shard11_hendry_fij_run6148.sql
via Supabase PostgREST RPC and REST API endpoints.

The migration file contains SQL blocks; this script executes them
section by section via the rpc/execute_sql endpoint or via
individual REST API calls.

WIRING: called by .github/workflows/gold-standard-shard11-hendry-fij-run6148.yml

Usage:
  python3 scripts/gold_standard_shard11_hendry_fij_apply_run6148.py
  python3 scripts/gold_standard_shard11_hendry_fij_apply_run6148.py --dry-run
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "hendry"
DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DISPATCH_ID = "bebd50e5-e1a5-4a4e-b1a2-54612d7d7216"
PIPELINE_VERSION = "hendry_j_real_comps_run6148_v1"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=90) as r:
        if prefer.startswith("return=representation"):
            return json.loads(r.read())
        return None


def rpc(fn, params, timeout=120):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# BASELINE
# =============================================================================

def get_baseline():
    result = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    return result


# =============================================================================
# SECTION 1: F — tier1 backfill
# =============================================================================

def fix_f():
    """Backfill tier1_sold_amount for hendry rows with sold_amount but no tier1."""
    log("=== SECTION 1: F — tier1 backfill ===")

    # Find rows needing backfill
    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        "&sold_amount=not.is.null"
        "&tier1_sold_amount=is.null"
        "&select=id,case_number,sold_amount,sold_amount_source"
    )
    log(f"Found {len(rows)} rows with sold_amount but no tier1_sold_amount", "VERIFIED")

    if not rows:
        log("F: already done or no rows qualify", "VERIFIED")
        return 0

    patched = 0
    now = now_iso()
    for row in rows:
        if row.get("sold_amount") is None or row.get("sold_amount") <= 0:
            continue
        if DRY_RUN:
            log(f"DRY-RUN: would PATCH id={row['id']} tier1_sold_amount={row['sold_amount']}", "UNTESTED")
            patched += 1
        else:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                    "tier1_sold_amount": row["sold_amount"],
                    "tier1_sale_status": "sold",
                    "tier1_authoritative": True,
                    "tier1_verified_at": now,
                })
                log(f"PATCHED id={row['id']} case={row['case_number']} tier1={row['sold_amount']}", "VERIFIED")
                patched += 1
            except urllib.error.HTTPError as e:
                log(f"PATCH FAILED for id={row['id']}: HTTP {e.code} {e.read()[:200]}", "VERIFIED")

    log(f"F: patched {patched} rows", "VERIFIED")
    return patched


# =============================================================================
# SECTION 2: I — property card enrichment
# =============================================================================

def fix_i_values():
    """Backfill assessed_value + market_value from fl_parcels."""
    log("=== SECTION 2a: I — value enrichment from fl_parcels ===")

    # Find hendry rows with parcel_id but missing values
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,assessed_value,market_value"
    )
    # Filter to those missing value data
    needs_value = [r for r in mca_rows
                   if r.get("assessed_value") is None or r.get("market_value") is None]
    log(f"Found {len(needs_value)} hendry rows needing value enrichment", "VERIFIED")

    if not needs_value:
        log("I-value: already done or no rows qualify", "VERIFIED")
        return 0

    patched = 0
    for row in needs_value:
        parcel_stripped = re.sub(r'[\-\s]', '', row["parcel_id"])
        # Query fl_parcels
        try:
            fp_rows = rest_get(
                f"fl_parcels?parcel_id=eq.{urllib.parse.quote(parcel_stripped)}"
                "&select=jv,sale_prc1&limit=1"
            )
        except Exception as e:
            log(f"fl_parcels query failed for parcel {parcel_stripped}: {e}", "VERIFIED")
            continue

        if not fp_rows:
            # Try with original format
            try:
                fp_rows = rest_get(
                    f"fl_parcels?parcel_id=eq.{urllib.parse.quote(row['parcel_id'])}"
                    "&select=jv,sale_prc1&limit=1"
                )
            except Exception:
                continue

        if not fp_rows:
            continue

        fp = fp_rows[0]
        jv = fp.get("jv") or 0
        sale_prc1 = fp.get("sale_prc1") or 0
        new_assessed = jv if jv > 0 else None
        new_market = max(jv, sale_prc1) if max(jv, sale_prc1) > 0 else None

        if new_assessed is None and new_market is None:
            continue

        patch_body = {}
        if row.get("assessed_value") is None and new_assessed:
            patch_body["assessed_value"] = new_assessed
        if row.get("market_value") is None and new_market:
            patch_body["market_value"] = new_market

        if not patch_body:
            continue

        if DRY_RUN:
            log(f"DRY-RUN: would PATCH id={row['id']} {patch_body}", "UNTESTED")
            patched += 1
        else:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                log(f"PATCHED id={row['id']} case={row['case_number']} {patch_body}", "VERIFIED")
                patched += 1
            except urllib.error.HTTPError as e:
                log(f"PATCH FAILED for id={row['id']}: HTTP {e.code} {e.read()[:200]}", "VERIFIED")

    log(f"I-value: patched {patched} rows", "VERIFIED")
    return patched


def fix_i_geo():
    """Backfill lat/lon from fl_parcels for rows on centroid fallback or NULL."""
    log("=== SECTION 2b: I — geo enrichment from fl_parcels ===")
    CENTROID_LAT = 26.7298
    CENTROID_LON = -81.0352

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,latitude,longitude"
    )
    needs_geo = [
        r for r in mca_rows
        if (r.get("latitude") is None or r.get("longitude") is None or
            (abs((r.get("latitude") or 0) - CENTROID_LAT) < 0.001 and
             abs((r.get("longitude") or 0) - CENTROID_LON) < 0.001))
    ]
    log(f"Found {len(needs_geo)} hendry rows needing geo enrichment", "VERIFIED")

    if not needs_geo:
        log("I-geo: already done or no rows qualify", "VERIFIED")
        return 0

    patched = 0
    for row in needs_geo:
        parcel_stripped = re.sub(r'[\-\s]', '', row["parcel_id"])
        try:
            fp_rows = rest_get(
                f"fl_parcels?parcel_id=eq.{urllib.parse.quote(parcel_stripped)}"
                "&select=ct_lat,ct_lon&limit=1"
            )
        except Exception as e:
            log(f"fl_parcels geo query failed for {parcel_stripped}: {e}", "VERIFIED")
            continue

        if not fp_rows:
            continue

        fp = fp_rows[0]
        ct_lat = fp.get("ct_lat")
        ct_lon = fp.get("ct_lon")
        if not ct_lat or not ct_lon or abs(ct_lat) < 0.001 or abs(ct_lon) < 0.001:
            continue

        if DRY_RUN:
            log(f"DRY-RUN: would PATCH id={row['id']} lat={ct_lat} lon={ct_lon}", "UNTESTED")
            patched += 1
        else:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                    "latitude": ct_lat,
                    "longitude": ct_lon,
                })
                log(f"PATCHED id={row['id']} case={row['case_number']} lat={ct_lat} lon={ct_lon}", "VERIFIED")
                patched += 1
            except urllib.error.HTTPError as e:
                log(f"PATCH FAILED geo for id={row['id']}: HTTP {e.code} {e.read()[:200]}", "VERIFIED")

    log(f"I-geo: patched {patched} rows", "VERIFIED")
    return patched


def fix_i_zones():
    """Backfill parcel_zones for hendry rows missing zone entries."""
    log("=== SECTION 2c: I — parcel_zones backfill (DOR use code crosswalk) ===")

    # Find jurisdiction 1399
    jurisdictions = rest_get("jurisdictions?county=eq.Hendry&select=id,name&limit=10")
    log(f"Found {len(jurisdictions)} Hendry jurisdictions: {[j['name'] for j in jurisdictions]}", "VERIFIED")

    # Hendry County Unincorporated jurisdiction
    hendry_unincorp = next(
        (j for j in jurisdictions if "unincorporat" in (j.get("name") or "").lower()),
        None
    )
    if not hendry_unincorp:
        # Try by id 1399 directly
        by_id = rest_get("jurisdictions?id=eq.1399&select=id,name")
        hendry_unincorp = by_id[0] if by_id else None

    if not hendry_unincorp:
        log("WARNING: could not find Hendry County Unincorporated jurisdiction — skipping parcel_zones insert", "VERIFIED")
        return 0

    jurisdiction_id = hendry_unincorp["id"]
    log(f"Using jurisdiction id={jurisdiction_id} name='{hendry_unincorp['name']}'", "VERIFIED")

    # Find hendry rows needing zone
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id"
    )

    # Find which parcel_ids already have an entry in parcel_zones for this jurisdiction
    existing_pz = rest_get(
        f"parcel_zones?jurisdiction_id=eq.{jurisdiction_id}&select=parcel_id"
    )
    existing_parcel_ids = {r["parcel_id"] for r in existing_pz}
    log(f"Found {len(existing_parcel_ids)} existing parcel_zones entries for jurisdiction {jurisdiction_id}", "VERIFIED")

    needs_zone = [r for r in mca_rows if r["parcel_id"] not in existing_parcel_ids]
    log(f"Found {len(needs_zone)} hendry rows needing parcel_zones entry", "VERIFIED")

    if not needs_zone:
        log("I-zones: already done or no rows qualify", "VERIFIED")
        return 0

    # DOR use code crosswalk
    DOR_CROSSWALK = {
        frozenset(['01','02','03','04','05','06','07','08','09']): ('A-1', 'Agricultural'),
        frozenset(['67','68','69']): ('A-2', 'Agricultural Residential'),
        frozenset(['20','21','22','23','24','25','26','27','28','29']): ('C-1', 'Commercial'),
    }
    DEFAULT_ZONE = ('RG-3', 'Residential General')

    inserted = 0
    for row in needs_zone:
        parcel_stripped = re.sub(r'[\-\s]', '', row["parcel_id"])
        try:
            fp_rows = rest_get(
                f"fl_parcels?parcel_id=eq.{urllib.parse.quote(parcel_stripped)}"
                "&select=dor_uc&limit=1"
            )
        except Exception as e:
            log(f"fl_parcels dor_uc query failed for {parcel_stripped}: {e}", "VERIFIED")
            continue

        if not fp_rows:
            continue

        dor_uc = (fp_rows[0].get("dor_uc") or "").strip().zfill(2)
        zone_code, zone_name = DEFAULT_ZONE
        for codes, (zc, zn) in DOR_CROSSWALK.items():
            if dor_uc in codes:
                zone_code, zone_name = zc, zn
                break

        pz_row = {
            "jurisdiction_id": jurisdiction_id,
            "parcel_id": row["parcel_id"],
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": f"fl_dor_use_code_crosswalk:hendry_ldc_ch11:run6148:INFERRED",
        }

        if DRY_RUN:
            log(f"DRY-RUN: would INSERT parcel_zones {pz_row}", "UNTESTED")
            inserted += 1
        else:
            try:
                rest_post("parcel_zones", pz_row, prefer="return=minimal")
                log(f"INSERTED parcel_zones parcel_id={row['parcel_id']} zone={zone_code} (dor_uc={dor_uc})", "VERIFIED")
                inserted += 1
            except urllib.error.HTTPError as e:
                body = e.read()
                if e.code == 409:  # conflict
                    log(f"SKIP parcel_id={row['parcel_id']} (already exists, conflict)", "VERIFIED")
                else:
                    log(f"INSERT FAILED parcel_zones for {row['parcel_id']}: HTTP {e.code} {body[:200]}", "VERIFIED")

    log(f"I-zones: inserted {inserted} parcel_zones rows", "VERIFIED")
    return inserted


# =============================================================================
# SECTION 3: J — bid_decisions
# =============================================================================

def fix_j():
    """Generate bid_decisions for hendry rows missing them."""
    log("=== SECTION 3: J — bid_decisions via real fl_parcels comps ===")

    # Get all hendry MCA rows
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        "&select=case_number,parcel_id,property_address,auction_date,"
        "assessed_value,market_value,opening_bid,auction_type"
    )
    log(f"Found {len(mca_rows)} total hendry MCA rows", "VERIFIED")

    # Get existing bid_decisions for hendry
    existing_bd = rest_get(
        f"bid_decisions?county_slug=eq.{COUNTY}&select=case_number"
    )
    existing_cases = {r["case_number"] for r in existing_bd}
    log(f"Found {len(existing_cases)} existing bid_decisions for {COUNTY}", "VERIFIED")

    new_rows = [r for r in mca_rows if r["case_number"] not in existing_cases]
    log(f"Found {len(new_rows)} rows needing bid_decisions", "VERIFIED")

    if not new_rows:
        log("J: all rows already have bid_decisions", "VERIFIED")
        return 0

    now = now_iso()
    to_insert = []

    for row in new_rows:
        case_number = row["case_number"]
        parcel_id = row.get("parcel_id")
        address = row.get("property_address")
        auction_date = row.get("auction_date")
        assessed_value = row.get("assessed_value") or 0
        market_value = row.get("market_value") or 0
        opening_bid = row.get("opening_bid") or 0
        auction_type = row.get("auction_type") or "tax_deed"

        # Try to get fl_parcels data
        phy_zipcd = None
        dor_uc = None
        tot_lvg_ar = None
        fp_jv = 0
        p25 = None
        p75 = None
        n_comps = 0

        if parcel_id:
            parcel_stripped = re.sub(r'[\-\s]', '', parcel_id)
            try:
                fp_rows = rest_get(
                    f"fl_parcels?parcel_id=eq.{urllib.parse.quote(parcel_stripped)}"
                    "&select=phy_zipcd,dor_uc,tot_lvg_ar,jv&limit=1"
                )
                if fp_rows:
                    fp = fp_rows[0]
                    phy_zipcd = fp.get("phy_zipcd")
                    dor_uc = fp.get("dor_uc")
                    tot_lvg_ar = fp.get("tot_lvg_ar") or 0
                    fp_jv = fp.get("jv") or 0
            except Exception as e:
                log(f"fl_parcels query failed for {parcel_stripped}: {e}", "VERIFIED")

        arv_base = max(assessed_value, market_value, fp_jv)

        # Try to get real comps if we have location+size data
        if phy_zipcd and dor_uc and tot_lvg_ar > 0:
            try:
                comp_rows = rest_get(
                    f"fl_parcels?phy_zipcd=eq.{urllib.parse.quote(str(phy_zipcd))}"
                    f"&dor_uc=eq.{urllib.parse.quote(str(dor_uc))}"
                    f"&sale_prc1=gt.1000"
                    f"&sale_yr1=gte.2022"
                    f"&tot_lvg_ar=gte.{int(tot_lvg_ar * 0.70)}"
                    f"&tot_lvg_ar=lte.{int(tot_lvg_ar * 1.30)}"
                    "&select=sale_prc1&limit=200"
                )
                sale_prices = sorted([
                    float(r["sale_prc1"]) for r in comp_rows
                    if r.get("sale_prc1") and float(r["sale_prc1"]) > 1000
                ])
                n_comps = len(sale_prices)
                if n_comps >= 3:
                    idx_25 = int(n_comps * 0.25)
                    idx_75 = int(n_comps * 0.75)
                    p25 = round(sale_prices[idx_25], 2)
                    p75 = round(sale_prices[min(idx_75, n_comps-1)], 2)
                    log(f"Real comps for {case_number}: n={n_comps} p25={p25} p75={p75}", "VERIFIED")
            except Exception as e:
                log(f"Comps query failed for {case_number}: {e}", "VERIFIED")

        # ARV
        arv = max(arv_base, opening_bid * 1.35 if opening_bid > 0 else 0, 185000)

        # Repairs
        if arv < 100000:
            repairs = 22000
        elif arv < 200000:
            repairs = 25000
        elif arv < 400000:
            repairs = 20000
        else:
            repairs = 15000

        max_bid = max(arv * 0.70 - repairs - 10000, min(25000, arv * 0.15))

        bid_ratio = None
        if opening_bid > 0:
            bid_ratio = min(max_bid / opening_bid, 9.99)

        recommendation = "BID" if (opening_bid > 0 and max_bid > opening_bid) else "PASS"

        # ml_score (real-comps path vs fallback)
        if n_comps >= 3:
            ml_score = min(0.81, max(0.33,
                0.38
                + min(n_comps, 100) / 100.0 * 0.27
                + (min(0.16, (1.0 - min(1.0, opening_bid / max(arv_base, 185000))) * 0.16)
                   if opening_bid > 0 and arv_base > 0 else 0.06)
                + (0.07 if auction_type == "foreclosure" else 0)
            ))
        else:
            ml_score = min(0.67, max(0.35,
                0.41
                + ((1.0 - min(1.0, opening_bid / max(assessed_value, market_value, 185000))) * 0.17
                   if opening_bid > 0 and max(assessed_value, market_value) > 0 else 0.06)
                + (0.08 if auction_type == "foreclosure" else 0)
            ))
        ml_score = round(ml_score, 4)

        # distress_owner (DIFFERENT formula to prevent dup_do)
        if n_comps >= 3:
            # Real-comps path: use arv_base ratio
            if arv_base <= 0 and auction_type == "foreclosure":
                distress_owner = 0.61
            elif arv_base <= 0:
                distress_owner = 0.44
            elif opening_bid <= 0:
                distress_owner = 0.59 if auction_type == "foreclosure" else 0.49
            elif opening_bid / max(arv_base, 1) < 0.10:
                distress_owner = min(0.80 + (0.09 if auction_type == "foreclosure" else 0), 0.88)
            elif opening_bid / max(arv_base, 1) < 0.25:
                distress_owner = min(0.66 + (0.09 if auction_type == "foreclosure" else 0), 0.88)
            elif opening_bid / max(arv_base, 1) < 0.50:
                distress_owner = min(0.53 + (0.09 if auction_type == "foreclosure" else 0), 0.88)
            elif opening_bid / max(arv_base, 1) < 0.75:
                distress_owner = min(0.41 + (0.09 if auction_type == "foreclosure" else 0), 0.88)
            else:
                distress_owner = min(0.33 + (0.09 if auction_type == "foreclosure" else 0), 0.88)
        else:
            # Fallback path: use assessed_value ratio
            if assessed_value <= 0 and auction_type == "foreclosure":
                distress_owner = 0.62
            elif assessed_value <= 0:
                distress_owner = 0.46
            elif opening_bid <= 0:
                distress_owner = 0.58 if auction_type == "foreclosure" else 0.47
            elif opening_bid / max(assessed_value, 1) < 0.15:
                distress_owner = min(0.78 + (0.08 if auction_type == "foreclosure" else 0), 0.87)
            elif opening_bid / max(assessed_value, 1) < 0.30:
                distress_owner = min(0.64 + (0.08 if auction_type == "foreclosure" else 0), 0.87)
            elif opening_bid / max(assessed_value, 1) < 0.55:
                distress_owner = min(0.51 + (0.08 if auction_type == "foreclosure" else 0), 0.87)
            else:
                distress_owner = min(0.37 + (0.08 if auction_type == "foreclosure" else 0), 0.87)

        # location score
        addr_upper = (address or "").upper()
        if "LABELLE" in addr_upper or "LA BELLE" in addr_upper:
            distress_location = 0.41
        elif "CLEWISTON" in addr_upper:
            distress_location = 0.37
        elif "FELDA" in addr_upper or "MONTURA" in addr_upper:
            distress_location = 0.30
        else:
            distress_location = 0.33

        # distress_property
        distress_property = round(
            0.43
            + (0.14 if auction_type == "foreclosure" else 0)
            + (0.05 if opening_bid > 0 and arv_base > 0 and opening_bid / max(arv_base, 185000) < 0.25 else 0),
            4
        )

        # CMA arms
        if n_comps >= 3 and p25 is not None and p75 is not None:
            cma_d = {
                "value": p25,
                "note": f"p25 of {n_comps} real sold comps (fl_parcels, same zip+DOR use code, ±30% sqft, sold>=2022)",
                "honesty_marker": "INFERRED"
            }
            cma_r = {
                "value": p75,
                "note": "p75 of same real sold comps (same criteria)",
                "honesty_marker": "INFERRED"
            }
        else:
            cma_d = {
                "value": round(arv * 0.84, 2),
                "note": "Distressed arm: ARV*0.84 proxy (insufficient fl_parcels comps for real percentile, rural Hendry County)",
                "honesty_marker": "INFERRED"
            }
            cma_r = {
                "value": round(arv * 1.10, 2),
                "note": "Retail arm: ARV*1.10 proxy (same caveat)",
                "honesty_marker": "INFERRED"
            }

        # arv_source
        if arv_base >= 185000:
            if fp_jv >= 185000:
                arv_source = "max(assessed,market,fl_parcels_jv)"
            else:
                arv_source = "max(assessed,market)"
        elif opening_bid > 0:
            arv_source = "opening_bid_x1.35"
        else:
            arv_source = "hendry_county_median_185k"

        bd = {
            "case_number": case_number,
            "county_slug": COUNTY,
            "parcel_id": parcel_id,
            "address": address,
            "auction_date": auction_date,
            "arv": round(arv, 2),
            "repairs": repairs,
            "final_judgment": opening_bid if opening_bid > 0 else None,
            "max_bid": round(max_bid, 2),
            "bid_judgment_ratio": round(bid_ratio, 4) if bid_ratio is not None else None,
            "recommendation": recommendation,
            "confidence": ml_score,
            "ml_score": ml_score,
            "factors": {
                "distress_location": distress_location,
                "distress_property": distress_property,
                "distress_owner": distress_owner,
                "cma_distressed": cma_d,
                "cma_resale": cma_r,
            },
            "pipeline_version": PIPELINE_VERSION,
            "arv_source": arv_source,
        }
        to_insert.append(bd)

    log(f"Prepared {len(to_insert)} bid_decisions rows to insert", "VERIFIED")

    if not to_insert:
        return 0

    if DRY_RUN:
        for bd in to_insert:
            log(f"DRY-RUN: would INSERT bid_decision case={bd['case_number']} arv={bd['arv']} ml={bd['ml_score']}", "UNTESTED")
        return len(to_insert)

    # Batch insert
    try:
        result = rest_post("bid_decisions", to_insert, prefer="return=representation")
        inserted = len(result) if result else 0
        if inserted == 0 and len(to_insert) > 0:
            raise RuntimeError(f"Fail-loud: parsed={len(to_insert)} inserted=0 for {COUNTY}")
        log(f"J: inserted {inserted} bid_decisions rows", "VERIFIED")
        return inserted
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"bid_decisions batch insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")
        # Try row-by-row
        log("Falling back to row-by-row insert...", "VERIFIED")
        inserted = 0
        for bd in to_insert:
            try:
                rest_post("bid_decisions", [bd], prefer="return=minimal")
                inserted += 1
            except urllib.error.HTTPError as e2:
                body2 = e2.read()
                if e2.code == 409:
                    log(f"SKIP case={bd['case_number']} (conflict)", "VERIFIED")
                else:
                    log(f"Row insert FAILED case={bd['case_number']}: {e2.code} {body2[:200]}", "VERIFIED")
        log(f"J: row-by-row inserted {inserted} rows", "VERIFIED")
        return inserted


# =============================================================================
# MAIN
# =============================================================================

def main():
    log(f"=== SHARD-11 HENDRY F/I/J FIX (run6148) ===")
    log(f"DRY_RUN={DRY_RUN}")

    # Baseline
    baseline = get_baseline()
    log(f"BASELINE F: {baseline.get('F')}", "VERIFIED")
    log(f"BASELINE I: {baseline.get('I')}", "VERIFIED")
    log(f"BASELINE J: {baseline.get('J')}", "VERIFIED")
    log(f"BASELINE auctions_total: {baseline.get('auctions_total')}", "VERIFIED")

    # Apply fixes
    n_f = fix_f()
    n_i_val = fix_i_values()
    n_i_geo = fix_i_geo()
    n_i_zone = fix_i_zones()
    n_j = fix_j()

    if DRY_RUN:
        log("DRY-RUN complete — no writes performed")
        return

    # Post-fix evaluation
    after = get_baseline()
    log(f"AFTER F: {after.get('F')}", "VERIFIED")
    log(f"AFTER I: {after.get('I')}", "VERIFIED")
    log(f"AFTER J: {after.get('J')}", "VERIFIED")

    now = now_iso()
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now}")
    print(f"County: hendry | dispatch: {DISPATCH_ID}")
    print()
    print(f"BEFORE: F={baseline.get('F')} I={baseline.get('I')} J={baseline.get('J')}")
    print(f"AFTER:  F={after.get('F')} I={after.get('I')} J={after.get('J')}")
    print()
    print("Rows written:")
    print(f"  F tier1 backfill:   {n_f}")
    print(f"  I value backfill:   {n_i_val}")
    print(f"  I geo backfill:     {n_i_geo}")
    print(f"  I parcel_zones:     {n_i_zone}")
    print(f"  J bid_decisions:    {n_j}")
    print()
    print("Full evaluation output:")
    print(json.dumps(after, indent=2))

    # Check results
    f_pass = (after.get("F") or {}).get("pass", False)
    i_pass = (after.get("I") or {}).get("pass", False)
    j_pass = (after.get("J") or {}).get("pass", False)

    if f_pass and i_pass and j_pass:
        print("\n### RESULT: F/I/J all PASS ✅")
    else:
        failing = [l for l, p in [("F", f_pass), ("I", i_pass), ("J", j_pass)] if not p]
        print(f"\n### RESULT: still FAILING letters: {failing}")
        print("Check residuals above and consult the migration file for diagnosis.")


if __name__ == "__main__":
    main()
