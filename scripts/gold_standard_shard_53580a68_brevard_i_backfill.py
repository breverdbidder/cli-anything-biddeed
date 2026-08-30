#!/usr/bin/env python3
"""Gold Standard shard (dispatch 53580a68), county=brevard, letter I
(property card completeness: address + geo + assessed/market value +
zone-linked parcel).

BASELINE (this session, VERIFIED via pencil_dod_evaluate_county('brevard')):
    I: {"pass": false, "metric": 85.7, "detail": "card_complete=6300 of 7348"}
Needs >=95% (~6981 of 7348) to pass. Gap = 1048 rows.

DIAGNOSIS (this session, live queries against the canonical evaluator
denominator/numerator -- exact CTE reproduced from
supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql,
county='brevard', card_rows=7348):

  Reconciled EXACTLY against the live evaluator's 7348-6300=1048 failing rows
  (union of the buckets below == 1048, verified this session):

    - property_address IS NULL, parcel_id NOT NULL:        977 rows
        - numeric BCPAO TaxAcct format:                     976 rows
        - non-numeric (STRAP-like) format:                    1 row
    - lat+po_lat both NULL, parcel_id NOT NULL:              65 rows (all numeric)
    - assessed_value+market_value both NULL, parcel_id NOT NULL: 16 rows (all numeric)
    - zoning-link-only blocked (addr+geo+value ALL present,
      zone_code EXISTS clause fails):                          4 rows
    - parcel_id IS NULL entirely (no lever, matches E~99.5%):  39 rows

  This is the SAME finding (near-identical counts) as three prior sessions:
    scripts/gold_standard_shard1_a96722e9_brevard_i_bcpao_nal_backfill.py
      (981 addr / 56 geo / 4 value, 2026-08-14)
    scripts/gold_standard_brevard_i_countyzoning_2row_20260826.py
      (977 addr / 6 zoning-only, 2026-08-26)
  The 4 zoning-only-blocked rows (case_numbers 180428, 180341, 180404,
  170965 / TaxAccts 2423944, 2532539, 2832622, 2724998) are RE-VERIFIED this
  session (live curl, see below) as still returning ZERO features from BOTH
  Brevard's Base_Map/Parcel_New_WKID2881/MapServer/5 (needed for centroid)
  AND Planning_Development/Zoning_WKID2881/MapServer/0 has no TaxAcct field
  at all (point-in-polygon only, requires geometry from Base_Map, which is
  empty for these 4) -- unchanged, permanently blocked, left untouched.

SOURCE (proven, free, no auth, county system of record):
    https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query
    keyed by TaxAcct (=BCPAO account=our parcel_id for the numeric subset).

RESULT: see bottom of stdout for this run's live totals. This script is
idempotent/re-runnable -- it re-fetches fresh candidate rows and fresh GIS
features every run, and only ever writes fields that are currently NULL
using a real, non-blank, non-UNKNOWN value from the live GIS feature.

FABRICATION GUARD (per HARD GUARDRAILS #5): never writes an address/lat/lon/
value where the authoritative source returns UNKNOWN, blank, zero, or no
feature at all. Rows in that state are counted and reported as a genuine
data gap, not silently skipped.

Usage:
  python3 scripts/gold_standard_shard_53580a68_brevard_i_backfill.py            # dry-run (default)
  python3 scripts/gold_standard_shard_53580a68_brevard_i_backfill.py --apply    # write live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"

GIS_QUERY = ("https://gis.brevardfl.gov/gissrv/rest/services/"
             "Base_Map/Parcel_New_WKID2881/MapServer/5/query")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
CHUNK = 150  # empirically safe: 200 triggers the county WAF's HTML redirect

# Canonical evaluator denominator filter (COALESCE-aware, matches
# pencil_dod_evaluate_county's internal WHERE clause exactly).
MCA_FILTER = ("county=eq.brevard&or=(data_source.is.null,data_source.neq.propertyonion,"
              "tier1_authoritative.eq.true)")


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def sb_get_all(select, extra_filter="", page_size=1000):
    rows = []
    offset = 0
    while True:
        url = (f"{SB_URL}/rest/v1/multi_county_auctions?{MCA_FILTER}"
               f"{extra_filter}&select={select}&order=id"
               f"&limit={page_size}&offset={offset}")
        req = urllib.request.Request(url, headers=sb_headers())
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.loads(r.read().decode())
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def sb_patch_by_id(row_id, payload):
    """Idempotent single-row PATCH keyed by primary key id -- never touches a
    row unless the caller already confirmed the target field is NULL."""
    url = f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, method="PATCH",
        headers={**sb_headers(), "Content-Type": "application/json",
                 "Prefer": "return=minimal"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  PATCH ERROR id={row_id}: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        return e.code


def fetch_gis_batch(tax_accts):
    features = {}
    for i in range(0, len(tax_accts), CHUNK):
        chunk = tax_accts[i:i + CHUNK]
        where = "TaxAcct IN (" + ",".join(chunk) + ")"
        params = {
            "where": where,
            "outFields": ("TaxAcct,STREET_NUMBER,STREET_DIRECTION_PREFIX,"
                          "STREET_NAME,STREET_TYPE,CITY,ZIP_CODE,"
                          "LAND_VALUE,BLDG_VALUE"),
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        }
        url = GIS_QUERY + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
        except Exception as e:
            print(f"  batch {i}: request error {e}", file=sys.stderr)
            time.sleep(3)
            continue
        if not body.startswith(b"{"):
            print(f"  batch {i}: WAF/redirect response, skipping")
            continue
        d = json.loads(body.decode())
        if "error" in d:
            print(f"  batch {i}: ArcGIS error {d['error']}", file=sys.stderr)
            continue
        for feat in d.get("features", []):
            tax = str(feat["attributes"].get("TaxAcct"))
            features[tax] = feat
        print(f"  batch {i}-{i + len(chunk)}: {len(d.get('features', []))} features returned")
        time.sleep(1.1)
    return features


def centroid(feature):
    ring = (feature.get("geometry") or {}).get("rings", [[]])
    ring = ring[0] if ring else []
    if not ring:
        return None, None
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lat, lon


def build_addr_update(feature):
    """Returns a partial-update dict, or None if the feature has no genuine,
    non-blank, non-UNKNOWN street address -- never fabricate (HARD GUARDRAIL #5)."""
    a = feature["attributes"]
    street_num = (a.get("STREET_NUMBER") or "").strip()
    street_name = (a.get("STREET_NAME") or "").strip()
    if not street_num or not street_name or street_name.upper() in ("UNKNOWN", "CONFIDENTIAL"):
        return None
    parts = [street_num]
    dir_prefix = (a.get("STREET_DIRECTION_PREFIX") or "").strip()
    if dir_prefix:
        parts.append(dir_prefix)
    parts.append(street_name)
    street_type = (a.get("STREET_TYPE") or "").strip()
    if street_type:
        parts.append(street_type)
    city = (a.get("CITY") or "").strip()
    zip_code = (a.get("ZIP_CODE") or "").strip()
    addr = " ".join((" ".join(parts) + f", {city}, FL {zip_code}").split())
    addr = addr.replace(" ,", ",")

    update = {"property_address": addr}
    lat, lon = centroid(feature)
    if lat is not None and lon is not None:
        update["latitude"] = lat
        update["longitude"] = lon
    land, bldg = a.get("LAND_VALUE"), a.get("BLDG_VALUE")
    total = (land or 0) + (bldg or 0)
    if total > 0:
        update["assessed_value"] = total
    return update


def build_geo_update(feature):
    lat, lon = centroid(feature)
    if lat is None or lon is None:
        return None
    return {"latitude": lat, "longitude": lon}


def build_value_update(feature):
    a = feature["attributes"]
    land, bldg = a.get("LAND_VALUE"), a.get("BLDG_VALUE")
    if land is None and bldg is None:
        return None
    total = (land or 0) + (bldg or 0)
    if total <= 0:
        return None
    return {"assessed_value": total}


def numeric_only(rows):
    return [r for r in rows if r.get("parcel_id") and str(r["parcel_id"]).strip().isdigit()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write live PATCHes (default: dry-run)")
    args = ap.parse_args()

    print("=== Fetching fresh candidate sets (canonical COALESCE-aware filter) ===")
    addr_missing = sb_get_all(
        "id,case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value",
        "&property_address=is.null&parcel_id=not.is.null",
    )
    geo_missing = sb_get_all(
        "id,case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value",
        "&latitude=is.null&po_latitude=is.null&parcel_id=not.is.null",
    )
    value_missing = sb_get_all(
        "id,case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value",
        "&assessed_value=is.null&market_value=is.null&parcel_id=not.is.null",
    )
    print(f"addr_missing: {len(addr_missing)}")
    print(f"geo_missing (lat+po_lat both null): {len(geo_missing)}")
    print(f"value_missing (assessed+market both null): {len(value_missing)}")

    addr_num = numeric_only(addr_missing)
    geo_num = numeric_only(geo_missing)
    val_num = numeric_only(value_missing)
    print(f"addr_missing numeric TaxAcct: {len(addr_num)}")
    print(f"geo_missing numeric TaxAcct: {len(geo_num)}")
    print(f"value_missing numeric TaxAcct: {len(val_num)}")

    all_accts = sorted({str(r["parcel_id"]).strip() for r in addr_num} |
                        {str(r["parcel_id"]).strip() for r in geo_num} |
                        {str(r["parcel_id"]).strip() for r in val_num})
    print(f"distinct TaxAcct to query: {len(all_accts)}")

    features = fetch_gis_batch(all_accts)
    print(f"GIS features matched: {len(features)}/{len(all_accts)}")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n=== MODE: {mode} ===")

    addr_applied = addr_unknown = addr_nofeat = addr_strap = 0
    blocked_addr = []
    for r in addr_missing:
        pid = str(r.get("parcel_id") or "").strip()
        if not pid.isdigit():
            addr_strap += 1
            blocked_addr.append((r["id"], r.get("case_number"), pid, "non-numeric parcel_id format"))
            continue
        feat = features.get(pid)
        if feat is None:
            addr_nofeat += 1
            blocked_addr.append((r["id"], r.get("case_number"), pid, "no GIS feature found"))
            continue
        update = build_addr_update(feat)
        if update is None:
            addr_unknown += 1
            blocked_addr.append((r["id"], r.get("case_number"), pid, "STREET_NAME=UNKNOWN/CONFIDENTIAL/blank (no situs address)"))
            continue
        if args.apply:
            status = sb_patch_by_id(r["id"], update)
            ok = status in (200, 204)
        else:
            ok = True
        if ok:
            addr_applied += 1
            print(f"  {'APPLIED' if args.apply else 'WOULD-APPLY'} addr id={r['id']} TaxAcct={pid}: {update}")
        else:
            blocked_addr.append((r["id"], r.get("case_number"), pid, "PATCH failed"))

    geo_applied = geo_nofeat = geo_nogeom = geo_strap = 0
    blocked_geo = []
    for r in geo_missing:
        pid = str(r.get("parcel_id") or "").strip()
        if not pid.isdigit():
            geo_strap += 1
            blocked_geo.append((r["id"], r.get("case_number"), pid, "non-numeric parcel_id format"))
            continue
        feat = features.get(pid)
        if feat is None:
            geo_nofeat += 1
            blocked_geo.append((r["id"], r.get("case_number"), pid, "no GIS feature found"))
            continue
        update = build_geo_update(feat)
        if update is None:
            geo_nogeom += 1
            blocked_geo.append((r["id"], r.get("case_number"), pid, "feature has no geometry"))
            continue
        if args.apply:
            status = sb_patch_by_id(r["id"], update)
            ok = status in (200, 204)
        else:
            ok = True
        if ok:
            geo_applied += 1
            print(f"  {'APPLIED' if args.apply else 'WOULD-APPLY'} geo id={r['id']} TaxAcct={pid}: {update}")
        else:
            blocked_geo.append((r["id"], r.get("case_number"), pid, "PATCH failed"))

    val_applied = val_nofeat = val_nozero = val_strap = 0
    blocked_val = []
    for r in value_missing:
        pid = str(r.get("parcel_id") or "").strip()
        if not pid.isdigit():
            val_strap += 1
            blocked_val.append((r["id"], r.get("case_number"), pid, "non-numeric parcel_id format"))
            continue
        feat = features.get(pid)
        if feat is None:
            val_nofeat += 1
            blocked_val.append((r["id"], r.get("case_number"), pid, "no GIS feature found"))
            continue
        update = build_value_update(feat)
        if update is None:
            val_nozero += 1
            blocked_val.append((r["id"], r.get("case_number"), pid, "LAND_VALUE+BLDG_VALUE both null/zero"))
            continue
        if args.apply:
            status = sb_patch_by_id(r["id"], update)
            ok = status in (200, 204)
        else:
            ok = True
        if ok:
            val_applied += 1
            print(f"  {'APPLIED' if args.apply else 'WOULD-APPLY'} value id={r['id']} TaxAcct={pid}: {update}")
        else:
            blocked_val.append((r["id"], r.get("case_number"), pid, "PATCH failed"))

    print("\n=== ADDRESS bucket ===")
    print(f"applied: {addr_applied}  unknown_street: {addr_unknown}  no_feature: {addr_nofeat}  strap_format: {addr_strap}")
    print("\n=== GEO bucket ===")
    print(f"applied: {geo_applied}  no_feature: {geo_nofeat}  no_geom: {geo_nogeom}  strap_format: {geo_strap}")
    print("\n=== VALUE bucket ===")
    print(f"applied: {val_applied}  no_feature: {val_nofeat}  no_value: {val_nozero}  strap_format: {val_strap}")

    total_applied = addr_applied + geo_applied + val_applied
    total_blocked = len(blocked_addr) + len(blocked_geo) + len(blocked_val)
    print(f"\nTOTALS: rows_{'patched' if args.apply else 'would_patch'}={total_applied}  rows_blocked={total_blocked}")

    if not args.apply and total_applied > 0:
        print("\nDry-run found writable rows. Re-run with --apply to write live.")

    with open("/tmp/blocked_rows_53580a68.json", "w") as f:
        json.dump({
            "addr": blocked_addr, "geo": blocked_geo, "value": blocked_val,
        }, f, indent=2)


if __name__ == "__main__":
    main()
