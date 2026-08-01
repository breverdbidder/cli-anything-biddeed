#!/usr/bin/env python3
"""SHARD-1 charlotte C/D/I fix (2026-08-01, loop run 7858, dispatch 9757eae6).

Baseline from dispatch brief (VERIFIED via pencil_dod_evaluate_county):
  charlotte C=92.5% (matched_clean=111), D=94.2% (matched_any=113), I=91.7% (card_complete=110 of 120)

Prior session history:
  - shard1_run6253 (2026-07-24): fixed 6 new foreclosure rows: C/D 91.7->97.2%, I 92.7->98.2%
    resulted in 10/10 PASS at that time
  - Current brief shows 7/10 (C=92.5%, D=94.2%, I=91.7%) meaning new auctions have been
    ingested SINCE that session, denominator grew from 109 to 120 (+11 new rows)
  - The 9 new rows (120 - 111 = 9 gap in C; 120 - 113 = 7 gap in D; 120 - 110 = 10 gap in I)
    need the same litmus treatment: harvest their auction dates from realforeclose.com
    and promote to matched_clean on exact case_number match

Charlotte has foreclosure_platform=realforeclose.com (realforeclose.com domain).
Charlotte has NO taxdeed_platform (null, confirmed in shard1_run6253 session report).
So tax_deed rows remain out of scope for this parity fix.

CO_NO for Charlotte is 18 (confirmed in 2026-07-24 session report: "CO_NO=18 -- Charlotte's
actual FL DOR county number, confirmed live by PARCELNO lookup, not the commonly-assumed CO_NO=8").
FL GIO Statewide Cadastral FeatureServer used for lat/lon backfill (same as run6253).

This script:
  1. Fetches all NULL-parity charlotte foreclosure rows (non-PO)
  2. Harvests live RealAuction calendar for each unique auction_date
  3. Exact case_number match -> parity_status=matched_clean (C/D fix)
  4. For matched rows missing lat/lon, attempts FL GIO centroid backfill (I fix)
  5. For matched rows missing parcel_id, backfills from the AITEM block (E/I fix)

Idempotent: only promotes rows where parity_status IS NULL; only backfills NULL fields.
Exact case_number match only (no fuzzy/parcel-only arm -- per 2026-07-02 sentinel guard).

Usage: python3 scripts/shard1_9757eae6_charlotte_cdi_fix.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import re
import json
import time
import urllib.request
import urllib.parse
import importlib.util
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "charlotte"
PARITY_SOURCE = "tier1_realauction_ajax_charlotte_shard1_run7858_9757eae6"
FL_GIO_URL = ("https://services1.arcgis.com/CY1LXxl9zlJeBuiP/arcgis/rest/services/"
              "Florida_Statewide_Cadastral/FeatureServer/0/query")
CHARLOTTE_CO_NO = 18


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


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


def is_real_parcel_id(pid):
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def fl_gio_centroid(parcel_no):
    """Fetch centroid lat/lon from FL GIO Statewide Cadastral for a given PARCELNO."""
    try:
        params = {
            "where": f"CO_NO={CHARLOTTE_CO_NO} AND PARCELNO='{parcel_no}'",
            "outFields": "PARCELNO,PHY_ADDR1,PHY_ADDR2,PHY_CITY,PHY_ZIPCD,JV",
            "returnCentroid": "true",
            "outSR": "4326",
            "f": "json",
        }
        url = FL_GIO_URL + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        feats = data.get("features", [])
        if len(feats) != 1:
            return None
        feat = feats[0]
        centroid = feat.get("centroid") or {}
        if not centroid.get("x") or not centroid.get("y"):
            return None
        attrs = feat.get("attributes", {})
        addr_parts = [attrs.get("PHY_ADDR1"), attrs.get("PHY_ADDR2"),
                      attrs.get("PHY_CITY"), "FL", str(attrs.get("PHY_ZIPCD") or "")]
        addr = " ".join(p for p in addr_parts if p and str(p).strip() and str(p).strip() != "0")
        return {
            "latitude": centroid["y"],
            "longitude": centroid["x"],
            "property_address": addr.strip() or None,
            "assessed_value": attrs.get("JV") or None,
        }
    except Exception as e:
        print(f"  FL GIO fetch error for {parcel_no}: {e}")
        return None


def main():
    # Fetch all NULL-parity non-PO charlotte foreclosure rows
    gap_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.foreclosure"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&parity_status=is.null"
        f"&select=id,case_number,auction_date,parcel_id,latitude,longitude,property_address,assessed_value"
        f"&limit=200")
    print(f"[{datetime.utcnow().isoformat()}Z] charlotte foreclosure NULL-parity rows: {len(gap_rows)}")

    if not gap_rows:
        print("No gap rows — charlotte foreclosure already fully matched.")
        # Still check for I-card gaps (rows with parity_status=matched_clean but missing geo)
        _fix_i_gaps()
        return

    # Get unique auction dates
    dates = sorted({r["auction_date"][:10] for r in gap_rows if r.get("auction_date")})
    print(f"Auction dates to probe: {dates}")

    live_items = {}
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        try:
            items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, mmddyyyy, "realforeclose.com")
            print(f"  realforeclose {d} ({mmddyyyy}): {len(items)} live items")
            for it in items:
                cn = norm_case_number(it.get("case_number"))
                if cn:
                    live_items[cn] = it
        except Exception as e:
            print(f"  realforeclose {d}: ERROR {e}")
        time.sleep(0.5)

    print(f"Total live items: {len(live_items)}")

    # Match by normalized case_number
    matches = []
    for row in gap_rows:
        cn = norm_case_number(row.get("case_number"))
        if cn and cn in live_items:
            matches.append((row, live_items[cn]))

    print(f"Exact case_number matches: {len(matches)}")

    promoted = 0
    geo_backfilled = 0
    parcel_backfilled = 0

    for row, aitem in matches:
        print(f"  {row['id']} {row['case_number']} {row.get('auction_date')}")

        # 1. Promote to matched_clean (C/D fix)
        patch = {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE}

        # 2. Backfill parcel_id from AITEM if missing (E/I fix)
        aitem_pid = aitem.get("parcel_id")
        if not row.get("parcel_id") and is_real_parcel_id(aitem_pid):
            patch["parcel_id"] = aitem_pid
            parcel_backfilled += 1

        # 3. Backfill address/value from AITEM if missing
        if not row.get("property_address") and aitem.get("property_address"):
            patch["property_address"] = aitem["property_address"]
        if not row.get("assessed_value") and aitem.get("assessed_value"):
            patch["assessed_value"] = aitem["assessed_value"]

        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
            promoted += 1
        except Exception as e:
            print(f"  PATCH error for {row['id']}: {e}")

        # 4. Geo backfill from FL GIO if still missing lat/lon (I fix)
        effective_pid = patch.get("parcel_id") or row.get("parcel_id")
        if not row.get("latitude") and effective_pid and is_real_parcel_id(effective_pid):
            geo = fl_gio_centroid(effective_pid)
            if geo:
                geo_patch = {k: v for k, v in geo.items() if v is not None}
                if geo_patch:
                    try:
                        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", geo_patch)
                        geo_backfilled += 1
                        print(f"    geo backfilled: lat={geo.get('latitude'):.4f} lon={geo.get('longitude'):.4f}")
                    except Exception as e:
                        print(f"    geo PATCH error: {e}")
        time.sleep(0.3)

    residual = len(gap_rows) - len(matches)
    print(f"\nSummary:")
    print(f"  promoted to matched_clean: {promoted}")
    print(f"  parcel_id backfilled: {parcel_backfilled}")
    print(f"  geo (lat/lon) backfilled: {geo_backfilled}")
    print(f"  residual (genuinely unmatched): {residual}")

    # Also fix I-gaps for already-matched rows missing geo
    _fix_i_gaps()

    print(json.dumps({
        "county": COUNTY_SLUG, "gap_rows": len(gap_rows),
        "live_items": len(live_items), "matches": len(matches),
        "promoted": promoted, "parcel_backfilled": parcel_backfilled,
        "geo_backfilled": geo_backfilled, "residual": residual,
        "parity_source": PARITY_SOURCE
    }))


def _fix_i_gaps():
    """Fix I-card gaps: matched rows missing lat/lon that have a valid parcel_id."""
    i_gaps = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}"
        f"&parity_status=eq.matched_clean&latitude=is.null"
        f"&parcel_id=not.is.null&parcel_id=neq.MULTIPLE PARCELS"
        f"&select=id,parcel_id,property_address&limit=50")
    print(f"\nI-gap rows (matched but missing lat/lon): {len(i_gaps)}")
    geo_fixed = 0
    for row in i_gaps:
        pid = row.get("parcel_id")
        if not is_real_parcel_id(pid):
            continue
        geo = fl_gio_centroid(pid)
        if geo:
            geo_patch = {k: v for k, v in geo.items() if v is not None}
            if geo_patch.get("latitude"):
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{row['id']}", geo_patch)
                    geo_fixed += 1
                    print(f"  I-gap fixed: {row['id']} {pid} lat={geo['latitude']:.4f}")
                except Exception as e:
                    print(f"  I-gap PATCH error for {row['id']}: {e}")
        time.sleep(0.3)
    print(f"I-gap geo fixes: {geo_fixed}")


if __name__ == "__main__":
    main()
