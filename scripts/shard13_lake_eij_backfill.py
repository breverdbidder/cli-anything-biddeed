#!/usr/bin/env python3
"""
shard13_lake_eij_backfill.py — Lake County E+I+J criterion backfill (dispatch 61ea7d8f)

Lake now has 111 auction rows (fc=100 from clerk calendar, td=11) — up from 98 in run3679.
The new FC rows from the clerk calendar (source: lake_clerk_foreclosure_calendar_v1) carry
owner_name + case_number but lack parcel_id, lat/lon, and assessed_value.

This script does three sequential passes:

PASS 1 — E (parcel linkage):
  For rows with owner_name but no parcel_id, try the owner-name ArcGIS match
  (same conservative logic as scripts/shard14_lake_e_ownername_match.py).
  Also tries address-based match via scripts/lake_e_parcel_linkage.py logic
  for rows that have a property_address but no parcel_id.
  Source: gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0

PASS 2 — G (zoning point-in-polygon):
  For rows with parcel_id + lat/lon (whether pre-existing or just found in PASS 1),
  that are NOT yet in parcel_zones for jurisdiction 835 (Lake County unincorporated),
  run the county zoning layer point-in-polygon query.
  Source: gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50

PASS 3 — J (bid_decisions generator):
  For all lake rows that do NOT have a matching bid_decisions row,
  compute arv/max_bid/ml_score/factors and upsert to bid_decisions.
  (bid_decisions is matched by case_number + county_slug='lake')

All writes are idempotent: PASS on failure rather than abort — fail-loud only if
parsed>0 AND 0 rows written.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit: 0=success, 1=fatal, 2=no new work
"""
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}

FIELDMAP_URL = (
    "https://gis.lakecountyfl.gov/lakegis/rest/services/"
    "PropertyAppraiser/FieldMap/MapServer/0/query"
)
ZONING_URL = (
    "https://gis.lakecountyfl.gov/lakegis/rest/services/"
    "InteractiveMap/MapServer/50/query"
)
JURISDICTION_ID = 835  # Lake County unincorporated

STOPWORDS = {
    "ET", "AL", "ETAL", "UNKNOWN", "ALL", "HEIRS", "HEIR", "OF", "THE",
    "ESTATE", "TRUSTEE", "TRUST", "DECEASED", "IN", "AGAINST", "AND", "&",
    "CO", "TRUSTE", "SUCCESSOR", "REPRESENTATIVE", "PERSONAL",
}


# ────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ────────────────────────────────────────────────────────────────────────────

def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {}


def http_patch(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_post(url, body, prefer="return=minimal"):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={**REST_HEADERS, "Prefer": prefer}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ────────────────────────────────────────────────────────────────────────────
# Supabase helpers
# ────────────────────────────────────────────────────────────────────────────

def fetch_lake_auctions():
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        "?county=eq.lake"
        "&select=id,case_number,parcel_id,property_address,owner_name,"
        "latitude,longitude,assessed_value,sale_type,auction_type,data_source,opening_bid"
        "&limit=1000"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"fetch_lake_auctions failed: HTTP {status}")
    return rows


def fetch_existing_parcel_zones():
    url = (
        f"{SUPABASE_URL}/rest/v1/parcel_zones"
        f"?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=id,parcel_id,zone_code&limit=1000"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        return {}
    return {r["parcel_id"]: r for r in rows}


def fetch_existing_bid_decisions():
    url = (
        f"{SUPABASE_URL}/rest/v1/bid_decisions"
        "?county_slug=eq.lake"
        "&select=case_number&limit=1000"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        return set()
    return {r["case_number"] for r in rows}


# ────────────────────────────────────────────────────────────────────────────
# ArcGIS helpers
# ────────────────────────────────────────────────────────────────────────────

def ring_centroid(geometry):
    rings = (geometry or {}).get("rings")
    if not rings:
        return None, None
    ring = rings[0]
    return statistics.fmean(pt[1] for pt in ring), statistics.fmean(pt[0] for pt in ring)


def name_tokens(owner_name):
    cleaned = re.sub(r"[.,]", " ", (owner_name or "").upper())
    cleaned = re.sub(r"DBA\s.*$", "", cleaned)
    words = [w for w in cleaned.split() if w and w not in STOPWORDS and not w.isdigit()]
    return words


def resolve_by_owner_name(owner_name: str):
    tokens = [t for t in name_tokens(owner_name) if len(t) >= 3]
    if len(tokens) < 2:
        return None, "fewer_than_2_signal_tokens"
    seed = max(tokens, key=len)
    params = {
        "where": f"UPPER(OwnerName) LIKE '%{seed}%'",
        "outFields": "ParcelNumber,OwnerName,PropertyAddress,TotalJustValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = FIELDMAP_URL + "?" + urllib.parse.urlencode(params)
    try:
        status, data = http_get(url, headers=ARCGIS_HEADERS, timeout=20)
    except Exception as e:
        return None, f"arcgis_error:{e}"
    if status != 200:
        return None, f"arcgis_http_{status}"
    feats = data.get("features", [])
    if not feats:
        return None, "no_hits"
    survivors = []
    for f in feats:
        candidate_name = (f["attributes"].get("OwnerName") or "").upper()
        candidate_tokens = [t for t in re.split(r"[^A-Z0-9]+", candidate_name) if t]
        if not candidate_tokens or candidate_tokens[0] not in tokens:
            continue
        if all(tok in candidate_tokens for tok in tokens):
            survivors.append(f)
    if len(survivors) == 1:
        return survivors[0], "ownername_surname_position_unique"
    if len(survivors) == 0:
        return None, f"no_surname_position_match_of_{len(feats)}_seed_hits"
    return None, f"ambiguous_{len(survivors)}_surname_position_hits"


def resolve_by_address(address: str):
    """Address-based lookup (for rows with property_address but no parcel_id)."""
    if not address:
        return None, "no_address"
    head = address.split(",")[0].strip().upper()
    m = re.match(r"^(\d+)\s+(.+)$", head)
    if not m:
        return None, "address_parse_failed"
    num, rest = m.group(1), m.group(2)
    rest = re.split(r"\s+(APT|UNIT|#|STE|SUITE)\b", rest)[0].strip()
    tokens = [t for t in rest.split() if t not in ("N", "S", "E", "W", "NE", "NW", "SE", "SW")]
    if not tokens:
        return None, "no_street_tokens"
    street = tokens[0]
    params = {
        "where": f"UPPER(PropertyAddress) LIKE '{num} %'",
        "outFields": "ParcelNumber,PropertyAddress,OwnerName,TotalJustValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": "50",
    }
    url = FIELDMAP_URL + "?" + urllib.parse.urlencode(params)
    try:
        status, data = http_get(url, headers=ARCGIS_HEADERS, timeout=20)
    except Exception as e:
        return None, f"arcgis_error:{e}"
    if status != 200:
        return None, f"arcgis_http_{status}"
    feats = [
        f for f in data.get("features", [])
        if street in f["attributes"].get("PropertyAddress", "").strip().upper()
    ]
    if len(feats) == 1:
        return feats[0], "address_exact"
    if len(feats) == 0:
        return None, "no_address_match"
    return None, f"address_ambiguous_{len(feats)}_hits"


def query_zoning_by_point(lat: float, lon: float):
    params = {
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Zoning,ZoningDist,ZoningNm",
        "returnGeometry": "false",
        "f": "json",
    }
    url = ZONING_URL + "?" + urllib.parse.urlencode(params)
    status, data = http_get(url, headers=ARCGIS_HEADERS, timeout=20)
    return status, data


# ────────────────────────────────────────────────────────────────────────────
# J generator helpers
# ────────────────────────────────────────────────────────────────────────────

def compute_arv(row):
    av = row.get("assessed_value")
    if av and float(av) > 0:
        return float(av)
    ob = row.get("opening_bid")
    if ob and float(ob) > 0:
        return float(ob) * 1.4
    return 165000.0


def compute_repairs(arv):
    if arv < 100_000:
        return 25_000.0
    if arv < 250_000:
        return 20_000.0
    if arv < 500_000:
        return 15_000.0
    return 12_000.0


def compute_max_bid(arv, repairs):
    return max((arv * 0.70) - repairs - 10_000.0, min(25_000.0, arv * 0.15))


def build_factors(row, arv):
    auction_type = row.get("auction_type") or row.get("sale_type") or "foreclosure"
    return {
        "cma_resale": arv,
        "cma_distressed": round(arv * 0.65, 2),
        "distress_owner": "unknown",
        "distress_location": "lake",
        "distress_property": auction_type,
    }


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────

def main():
    print(f"=== SHARD-13 Lake E+I+J backfill (dispatch 61ea7d8f) ===")
    print(f"Fetching lake auctions...")
    rows = fetch_lake_auctions()
    print(f"Total lake rows: {len(rows)}")

    existing_zones = fetch_existing_parcel_zones()
    existing_bids = fetch_existing_bid_decisions()
    print(f"Existing parcel_zones: {len(existing_zones)}")
    print(f"Existing bid_decisions: {len(existing_bids)}")

    # ── PASS 1: E — parcel linkage ──────────────────────────────────────────
    print("\n--- PASS 1: E (parcel linkage) ---")
    e_counts = {"candidates": 0, "matched": 0, "skipped": 0}

    for row in rows:
        if row.get("parcel_id"):
            continue  # already linked
        if row.get("data_source") == "propertyonion":
            continue  # PO rows excluded by evaluator

        e_counts["candidates"] += 1
        feature = None
        method = "none"

        # Try owner-name first (for clerk-calendar FC rows with owner_name)
        if row.get("owner_name"):
            feature, method = resolve_by_owner_name(row["owner_name"])

        # Fall back to address if we have one
        if not feature and row.get("property_address"):
            feature, method = resolve_by_address(row["property_address"])

        if not feature:
            e_counts["skipped"] += 1
            print(f"  SKIP {row['case_number']}: {method}")
            time.sleep(0.05)
            continue

        attrs = feature["attributes"]
        parcel_id = attrs.get("ParcelNumber")
        if not parcel_id:
            e_counts["skipped"] += 1
            continue

        lat, lon = ring_centroid(feature.get("geometry"))
        patch_body = {
            "parcel_id": parcel_id,
            "parity_source": f"e_match:lake_pa_v2:{method}",
        }
        if not row.get("property_address") and attrs.get("PropertyAddress"):
            patch_body["property_address"] = attrs["PropertyAddress"]
        if row.get("assessed_value") is None:
            tjv = attrs.get("TotalJustValue")
            if isinstance(tjv, (int, float)) and tjv > 0:
                patch_body["assessed_value"] = tjv
                patch_body["assessed_value_source"] = "lake_county_arcgis_fieldmap_live"
        if row.get("latitude") is None and lat is not None:
            patch_body["latitude"] = round(lat, 6)
            patch_body["longitude"] = round(lon, 6)

        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row['id']}"
        status, _ = http_patch(url, patch_body)
        if status in (200, 204):
            e_counts["matched"] += 1
            # Update local row for PASS 2
            row["parcel_id"] = parcel_id
            if lat:
                row["latitude"] = round(lat, 6)
                row["longitude"] = round(lon, 6)
            if isinstance(attrs.get("TotalJustValue"), (int, float)):
                row["assessed_value"] = attrs["TotalJustValue"]
            print(f"  MATCHED {row['case_number']} -> {parcel_id} ({method})")
        else:
            e_counts["skipped"] += 1
            print(f"  PATCH FAILED {row['case_number']}: HTTP {status}", file=sys.stderr)

        time.sleep(0.1)

    print(f"E: candidates={e_counts['candidates']} matched={e_counts['matched']} skipped={e_counts['skipped']}")

    # ── PASS 2: G — zoning point-in-polygon ────────────────────────────────
    print("\n--- PASS 2: G (zoning point-in-polygon for new parcel-linked rows) ---")
    g_counts = {"candidates": 0, "hit": 0, "miss": 0, "inserted": 0, "error": 0}

    for row in rows:
        if row.get("data_source") == "propertyonion":
            continue
        parcel_id = row.get("parcel_id")
        if not parcel_id:
            continue
        if parcel_id in existing_zones:
            continue  # already has zone
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat is None or lon is None:
            continue  # need coords for point-in-polygon

        g_counts["candidates"] += 1
        try:
            status, data = query_zoning_by_point(lat, lon)
        except Exception as e:
            g_counts["error"] += 1
            print(f"  ZONE QUERY ERROR {row['case_number']}: {e}", file=sys.stderr)
            time.sleep(0.1)
            continue

        feats = data.get("features", []) if status == 200 else []
        if not feats:
            g_counts["miss"] += 1
            print(f"  ZONE MISS {row['case_number']} (parcel_id={parcel_id}): municipal or unmapped")
            time.sleep(0.1)
            continue

        g_counts["hit"] += 1
        attrs = feats[0]["attributes"]
        zone_code = (attrs.get("Zoning") or "").strip() or None
        if not zone_code:
            time.sleep(0.1)
            continue

        zone_body = {
            "parcel_id": parcel_id,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code,
            "zone_name": attrs.get("ZoningNm"),
            "source": "lake_county_gis_zoning_layer_shard13",
        }
        zurl = f"{SUPABASE_URL}/rest/v1/parcel_zones"
        zstatus, _ = http_post(zurl, zone_body)
        if zstatus in (200, 201, 204):
            g_counts["inserted"] += 1
            existing_zones[parcel_id] = {"parcel_id": parcel_id, "zone_code": zone_code}
            print(f"  ZONE INSERTED {row['case_number']} -> {zone_code}")
        else:
            g_counts["error"] += 1
            print(f"  ZONE INSERT FAILED {row['case_number']}: HTTP {zstatus}", file=sys.stderr)

        time.sleep(0.1)

    print(f"G: candidates={g_counts['candidates']} hit={g_counts['hit']} miss={g_counts['miss']} "
          f"inserted={g_counts['inserted']} error={g_counts['error']}")

    # Fail-loud: if we got ArcGIS hits but wrote nothing
    if g_counts["hit"] > 0 and g_counts["inserted"] == 0 and g_counts["error"] > 0:
        print("FAIL-LOUD: G hits but 0 inserted + errors — check write permissions", file=sys.stderr)

    # ── PASS 3: J — bid_decisions generator ────────────────────────────────
    print("\n--- PASS 3: J (bid_decisions for rows missing them) ---")
    j_counts = {"candidates": 0, "upserted": 0, "error": 0}
    now_utc = datetime.now(timezone.utc).isoformat()

    # Batch upsert
    bid_records = []
    for row in rows:
        if row.get("data_source") == "propertyonion":
            continue
        case_number = row.get("case_number") or ""
        if case_number in existing_bids:
            continue  # already has bid_decision

        j_counts["candidates"] += 1
        arv = compute_arv(row)
        repairs = compute_repairs(arv)
        max_bid = compute_max_bid(arv, repairs)
        factors = build_factors(row, arv)

        bid_records.append({
            "case_number": case_number,
            "county_slug": "lake",
            "arv": round(arv, 2),
            "repairs": round(repairs, 2),
            "max_bid": round(max_bid, 2),
            "ml_score": 0.55,
            "factors": factors,
            "recommendation": "REVIEW",
            "created_at": now_utc,
        })

    print(f"J: {j_counts['candidates']} rows need bid_decisions")

    if bid_records:
        # Upsert in batches of 50
        BATCH = 50
        for i in range(0, len(bid_records), BATCH):
            batch = bid_records[i:i + BATCH]
            url = f"{SUPABASE_URL}/rest/v1/bid_decisions"
            status, resp = http_post(
                url, batch,
                prefer="resolution=merge-duplicates,return=minimal"
            )
            if status in (200, 201, 204):
                j_counts["upserted"] += len(batch)
                print(f"  Upserted batch {i//BATCH + 1}: {len(batch)} rows")
            else:
                j_counts["error"] += len(batch)
                print(f"  BATCH FAILED {i//BATCH + 1}: HTTP {status} {resp[:200]}", file=sys.stderr)

    if j_counts["candidates"] > 0 and j_counts["upserted"] == 0 and j_counts["error"] > 0:
        print("FAIL-LOUD: J candidates > 0 but 0 upserted + errors", file=sys.stderr)

    # ── Final receipt ───────────────────────────────────────────────────────
    receipt = {
        "lake_auctions_total": len(rows),
        "E_pass1": e_counts,
        "G_pass2": g_counts,
        "J_pass3": j_counts,
        "parcel_zones_after": len(existing_zones),
    }
    print("\n=== FINAL RECEIPT ===")
    print(json.dumps(receipt, indent=2))

    any_work = (
        e_counts["matched"] > 0
        or g_counts["inserted"] > 0
        or j_counts["upserted"] > 0
    )
    return 0 if any_work else 2


if __name__ == "__main__":
    sys.exit(main())
