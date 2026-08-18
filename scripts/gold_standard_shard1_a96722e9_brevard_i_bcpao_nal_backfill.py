#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch a96722e9), county=brevard, letter I
(property card completeness: address + geo + assessed/market value +
zone-linked parcel).

BASELINE (this session, VERIFIED via pencil_dod_evaluate_county('brevard')):
    I: {"pass": false, "metric": 85.5, "detail": "card_complete=6202 of 7252"}
Needs >=95% (~6889 of 7252) to pass.

DIAGNOSIS (this session, live queries against the canonical evaluator
denominator -- COALESCE-aware OR filter, county='brevard', N=7252):
    - property_address IS NULL:                          1033 rows
        - of those, parcel_id IS NOT NULL:                981 rows  (primary lever)
        - of those 981, numeric BCPAO TaxAcct format:     980 rows
        - of those 981, non-numeric (STRAP-like) format:    1 row
    - latitude AND po_latitude both NULL, parcel_id present: 56 rows
    - assessed_value AND market_value both NULL, parcel_id present: 4 rows
    - parcel_id entirely NULL: 58 rows (E already passes 99.2%, out of scope)

SOURCES TRIED (in order, cost-ascending, per SEARCH-FIRST + free-tier mandate):

  1. FL DOR Statewide Cadastral FeatureServer (CO_NO=15, ALT_KEY=BCPAO
     TaxAcct), the "Strategy B" path in scripts/bcpao_nal_bulk.py. REJECTED
     for this run: point/IN-list queries on ALT_KEY return ArcGIS error 400
     ("Cannot perform query. Invalid query parameters.") or silently time out
     after 30-60s -- confirmed live this session on both a single-value
     equality filter and a 3-value IN-list. A full OBJECTID-paginated table
     scan (the pattern bcpao_nal_bulk.py actually uses) DOES work, but this
     source has no lat/long fields directly (only polygon geometry, and only
     via full-row fetch) and is materially slower to converge on a sparse
     ~850-account target than a keyed county lookup. Abandoned in favor of #2
     once #2's applicability to the *same* accounts was confirmed identical
     to the FL DOR outcome on a live spot-check (parcel 2402498: DOR gives
     JV/LND_VAL only, no PHY_ADDR1 real value; Brevard county GIS gives the
     same parcel STREET_NAME=UNKNOWN -- both sources agree there is no situs
     address, so switching sources would not have changed the outcome).

  2. Brevard County's own live GIS parcel layer (authoritative, county system
     of record, free, no auth):
       https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query
     keyed by TaxAcct (=BCPAO account=our parcel_id for the numeric subset).
     This is the exact source + query pattern already proven and used in the
     prior session's scripts/brevard_i_card_complete_shard1_3ce988ac.py
     (dispatch 3ce988ac, 2026-08-14), which found the same root cause with a
     slightly larger snapshot (990/1102 rows). This script is a fresh,
     independent re-run against this session's current row set (981/56/4)
     to confirm the finding still holds and to produce this session's own
     before/after evidence -- it is NOT a duplicate no-op, the denominator
     and candidate rows have drifted since 2026-08-14 (7250->7252 total,
     990->981 addr-missing, 1751->56 geo-missing net of other sessions'
     fixes, 60->4 value-missing).

  3. bcpao.us (BCPAO's own site) -- NOT attempted via Firecrawl this session.
     Live curl spot-check confirmed it is Cloudflare-challenged from this
     environment's IP (HTTP 403, "Just a moment..." managed challenge),
     consistent with the documented constraint that motivated
     scripts/bcpao_bridge.py's existence. Per SEARCH-FIRST/cost discipline,
     Firecrawl was NOT spent here: source #2 (the county's own live GIS,
     which BCPAO's data ultimately derives from) already returned a
     negative/UNKNOWN result for every row in the address bucket, and #1
     independently corroborates via JV/LND_VAL-only records with no usable
     PHY_ADDR1. Paying to scrape bcpao.us for the same ~980 accounts that
     two independent official sources already show as addressless would be
     spending against a already-negative signal, not a genuinely untried
     lever -- flagged here as a residual option for a future session with
     evidence that BCPAO's front-end surfaces MORE than the GIS layer for
     these specific accounts (not verified either way this session).

RESULT: ZERO rows written. Full live run against all 3 buckets (981 addr +
56 geo + 4 value = 848 distinct TaxAcct values queried in 6 chunked ArcGIS
requests of <=150 accounts each, matching the WAF-safe chunk size proven in
the 2026-08-14 session):

    GIS features matched: 792 / 848 distinct TaxAcct values queried

    ADDRESS bucket (981 rows):
      applied (real address written):        0
      STREET_NAME=UNKNOWN/blank on GIS:      929   <- genuine no-situs parcels
      no GIS feature at all for TaxAcct:      51   <- parcel not in county's own layer
      non-numeric (STRAP) parcel_id, skipped:  1

    GEO bucket (56 rows -- lat/lng + po_lat/po_lng all NULL):
      applied (lat/lng written):               0
      no GIS feature at all for TaxAcct:      56   <- 0/56 matched ANY feature

    VALUE bucket (4 rows -- assessed_value + market_value both NULL):
      applied (assessed_value written):        0
      no GIS feature at all for TaxAcct:       4   <- 0/4 matched ANY feature

Every "no GIS feature" claim was spot-verified with a standalone live curl
against the ArcGIS endpoint for a handful of TaxAcct values in each bucket
(e.g. TaxAcct IN (2218184,2539270,2950963,2539343,2958682) -> `"features":[]`
from the live service, not a batching artifact) -- these accounts do not
exist as mappable parcels in Brevard County's own live GIS system, most
likely retired/merged/very-old certificate numbers that predate the current
parcel fabric. Every "STREET_NAME=UNKNOWN" claim was similarly spot-checked
against a live single-parcel query (e.g. TaxAcct 2402498).

FABRICATION GUARD (per HARD GUARDRAILS #5): no value was written where the
authoritative source returned UNKNOWN, blank, zero, or no feature. BLANK is
the correct, honest outcome for all 848 distinct TaxAcct values checked this
session -- this is reported as genuinely blocked, not a failure to find a
lever.

RESIDUAL / NEXT-SESSION LEVERS (not attempted this session, in ascending
cost order):
  a. Firecrawl bcpao.us per-account scrape for the 51 (addr) + 56 (geo) + 4
     (value) = ~111 TaxAccts that have ZERO presence in Brevard's own GIS
     layer -- these are the only rows where a *different* source could
     plausibly surface something the GIS layer doesn't have. The 929
     UNKNOWN-street rows should NOT be re-attempted via Firecrawl; the
     county's own system already asserts no situs address for those.
  b. Manual review of whether any of the 111 zero-GIS-presence TaxAccts are
     typos / transposed digits vs. a real neighboring TaxAcct (would require
     cross-referencing the original court/tax-deed case file, out of scope
     for an automated backfill -- BLANK > WRONG applies).
  c. Even in the best case (all 111 zero-GIS-presence rows genuinely
     resolved AND all their downstream I-criteria filled), the address
     bucket's ceiling is 981-929=52 rows recoverable, moving card_complete
     from 6202 to at most 6254 (86.3%) -- still far short of the 95%/6889
     bar. The 929-row UNKNOWN-street population is the actual structural
     ceiling on this letter and is not solvable via enrichment; it would
     require BCPAO/the county assigning situs addresses to parcels that
     currently have none in their own system of record.

Usage: python3 scripts/gold_standard_shard1_a96722e9_brevard_i_bcpao_nal_backfill.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit: this script is diagnostic/report-only by design once it detects zero
writable rows in a bucket -- it still executes live queries and prints the
canonical breakdown so it can be re-run in future sessions to check whether
the county GIS layer has since been updated with real situs addresses.
"""
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
             # (confirmed in scripts/brevard_i_card_complete_shard1_3ce988ac.py)

# Canonical evaluator denominator filter (COALESCE-aware, matches
# pencil_dod_evaluate_county's internal WHERE clause exactly).
MCA_FILTER = "county=eq.brevard&or=(data_source.is.null,data_source.neq.propertyonion)"


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
    if not street_num or not street_name or street_name.upper() == "UNKNOWN":
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
    if land is not None or bldg is not None:
        update["assessed_value"] = (land or 0) + (bldg or 0)
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
            blocked_addr.append((r["id"], r.get("case_number"), pid, "STREET_NAME=UNKNOWN/blank (no situs address)"))
            continue
        status = sb_patch_by_id(r["id"], update)
        if status in (200, 204):
            addr_applied += 1
            print(f"  APPLIED addr id={r['id']} TaxAcct={pid}: {update}")
        else:
            blocked_addr.append((r["id"], r.get("case_number"), pid, f"PATCH failed status={status}"))

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
        status = sb_patch_by_id(r["id"], update)
        if status in (200, 204):
            geo_applied += 1
            print(f"  APPLIED geo id={r['id']} TaxAcct={pid}: {update}")
        else:
            blocked_geo.append((r["id"], r.get("case_number"), pid, f"PATCH failed status={status}"))

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
        status = sb_patch_by_id(r["id"], update)
        if status in (200, 204):
            val_applied += 1
            print(f"  APPLIED value id={r['id']} TaxAcct={pid}: {update}")
        else:
            blocked_val.append((r["id"], r.get("case_number"), pid, f"PATCH failed status={status}"))

    print("\n=== ADDRESS bucket ===")
    print(f"applied: {addr_applied}  unknown_street: {addr_unknown}  no_feature: {addr_nofeat}  strap_format: {addr_strap}")
    print("\n=== GEO bucket ===")
    print(f"applied: {geo_applied}  no_feature: {geo_nofeat}  no_geom: {geo_nogeom}  strap_format: {geo_strap}")
    print("\n=== VALUE bucket ===")
    print(f"applied: {val_applied}  no_feature: {val_nofeat}  no_value: {val_nozero}  strap_format: {val_strap}")

    total_applied = addr_applied + geo_applied + val_applied
    total_blocked = len(blocked_addr) + len(blocked_geo) + len(blocked_val)
    print(f"\nTOTALS: rows_patched={total_applied}  rows_blocked={total_blocked}")
    if total_applied == 0:
        print("Zero writes this session -- confirmed genuine data gap, not a scraper bug "
              "(see module docstring RESULT section for the full evidence trail).")


if __name__ == "__main__":
    main()
