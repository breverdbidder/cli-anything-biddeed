#!/usr/bin/env python3
"""
gold_standard_shard2_glades_i_enrichment_run11435.py

GOLD STANDARD shard-2 (dispatch 5f3a88a5, loop run 11435), glades criterion I
(card_complete) fix, continuation of gold_standard_shard8_glades_i_enrichment.py.

CONTEXT (VERIFIED live this session via pencil_dod_evaluate_county('glades')):
  auctions_total grew from 70 (run6080 J-generator build) to 102 -- 32 new
  tax-deed rows landed 2026-08-13T14:41:25Z, all data_source=
  'municode_munidocs:GLADES-TD-V1' with real STR-style parcel_id (same format
  as the original 70: e.g. 'S11-42-32-003-0051-0070', 'A21-40-32-A00-004H-0000').
  card_complete=68 of 102 (66.7%) -- exactly the 68/70 originally enriched
  by the prior script PLUS 0 of the 32 new rows (all 32 lack lat/lon/value/
  zone-link; 1 of the 32, TD-2025-27-20260604, also lacks property_address
  entirely).

  The 2 old unmatched rows from the prior 70 (222025CA000139CAAXMX -- the lone
  foreclosure row, no parcel_id at all; TD-2024-4-20240808, parcel_id
  S31-42-30-102-0018-0070) were RE-CHECKED live this session against the FL
  DOR statewide cadastral FeatureServer and STILL return zero features for
  the dash-stripped PARCEL_ID -- confirmed still structurally unmatched, not
  retried further (BLANK > WRONG, no new evidence emerged).

DATA SOURCE (same proven mirror + dash-stripping quirk as the prior script):
  https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
    Florida_Statewide_Cadastral/FeatureServer/0
  PARCEL_ID field on this mirror strips all dashes from our parcel_id
  (e.g. 'S11-42-32-003-0051-0070' -> 'S11423200300510070', CO_NO=32 for
  glades -- confirmed, no county remap needed).

CROSS-VALIDATION: same PHY_CITY allowlist + CO_NO=32 check as the prior
  script -- any match whose PHY_CITY is not a real Glades-area city, or whose
  CO_NO != 32, is rejected and left NULL (BLANK > WRONG).

FIELDS WRITTEN per multi_county_auctions row (PATCH by
case_number=eq.<case>&county=eq.glades), ONLY for the 32 new rows:
  - latitude, longitude: centroid from FeatureServer geometry (outSR=4326).
  - market_value: cadastral JV field, when JV > 0.
  - assessed_value: cadastral AV_SD field, when AV_SD > 0.
  - property_address: ONLY for TD-2025-27-20260604 (the one row with no
    address at all currently) -- "{PHY_ADDR1}, {PHY_CITY}, FL {PHY_ZIPCD}",
    written only if PHY_ADDR1 is non-blank. The other 31 rows already have a
    real property_address scraped from the Municode PDFs -- left untouched.

NOT WRITTEN / OUT OF SCOPE (same discipline as the prior script):
  - Any row whose dash-stripped PARCEL_ID returns zero features -- left NULL.
  - Any match whose PHY_CITY/CO_NO fails the Glades allowlist check -- NULL.
  - JV/AV_SD of exactly 0 or missing are NOT written as 0.
  - zone_code / parcel_zones linkage (separate step, this script's sibling
    zoning-query script handles that against the live Glades zoning MapServer).

WRITES PERFORMED: up to 32 PATCH requests to
  {SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.<case>&county=eq.glades
Fail-loud: if parsed>0 and inserted==0, this script raises.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

FL_DOR_CADASTRAL_URL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)

GLADES_CITY_ALLOWLIST = {
    "MOORE HAVEN", "BUCKHEAD RIDGE", "LAKEPORT", "PALMDALE", "ORTONA",
    "MUSE", "LABELLE", "OKEECHOBEE",
    # VENUS added this session (run11435): parcel A06-41-29-A00-006A-0000
    # verified live via direct PARCEL_ID lookup on the FL DOR cadastral
    # FeatureServer -- CO_NO=32 (Glades, ground-truth authoritative field)
    # AND PHY_CITY='VENUS', PHY_ADDR1='COUNTY RD 74', PHY_ZIPCD=33960.
    # Venus is a real unincorporated community straddling the Glades/
    # Highlands county line; the DOR's own CO_NO assignment for this
    # specific parcel is the deciding signal, not the city allowlist
    # (which was always a secondary sanity check, not the primary gate).
    "VENUS",
}
GLADES_CO_NO = 32
CHUNK_SIZE = 60
MAX_RETRIES = 4

# The 32 new rows (created_at 2026-08-13T14:41:25Z), identified live this
# session via a gap query joining multi_county_auctions against
# v_zoning_gold_standard_card for county='glades'.
TARGET_CASES = [
    "TD-2025-24-20260604", "TD-2022-30-20260604", "TD-2022-44-20260604",
    "TD-2026-4-20260604", "TD-2025-32-20260604", "TD-2025-28-20260604",
    "TD-2025-33-20260604", "TD-2026-1-20260604", "TD-2025-39-20260604",
    "TD-2024-34-20260604", "TD-2025-26-20260604", "TD-2024-31-20260604",
    "TD-2024-35-20260604", "TD-2024-37-20260604", "TD-2024-29-20260604",
    "TD-2022-31-20260604", "TD-2025-29-20260604", "TD-2022-21-20260604",
    "TD-2022-47-20260604", "TD-2024-27-20260604", "TD-2024-25-20260604",
    "TD-2025-20-20260604", "TD-2024-36-20260604", "TD-2025-27-20260604",
    "TD-2025-31-20260604", "TD-2025-36-20260604", "TD-2026-2-20260604",
    "TD-2023-13-20260604", "TD-2024-33-20260604", "TD-2023-14-20260604",
    "TD-2025-35-20260604", "TD-2026-3-20260604",
]


def get_rows():
    ids = ",".join(TARGET_CASES)
    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        f"?county=eq.glades&case_number=in.({ids})"
        "&select=case_number,parcel_id,property_address"
        "&order=case_number&limit=200"
    )
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_dor_chunk(stripped_ids):
    id_list = ",".join(f"'{i}'" for i in stripped_ids)
    where = f"PARCEL_ID IN ({id_list})"
    params = {
        "where": where,
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            wait = 2 ** attempt
            print(f"  chunk fetch failed ({exc}), retry {attempt+1}/{MAX_RETRIES} in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"FL DOR FeatureServer unreachable after {MAX_RETRIES} retries: {last_exc}")


def centroid_of_features(features):
    xs, ys = [], []
    for feat in features:
        rings = feat.get("geometry", {}).get("rings", [])
        for ring in rings:
            for pt in ring:
                xs.append(pt[0])
                ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)  # lat, lon


def build_enrichment_map(rows):
    stripped_to_orig = {
        r["parcel_id"].replace("-", ""): r["parcel_id"]
        for r in rows
        if r.get("parcel_id")
    }
    stripped_ids = list(stripped_to_orig.keys())

    by_stripped = {}
    for i in range(0, len(stripped_ids), CHUNK_SIZE):
        chunk = stripped_ids[i : i + CHUNK_SIZE]
        d = fetch_dor_chunk(chunk)
        if "error" in d:
            raise RuntimeError(f"FL DOR FeatureServer error on chunk {i}: {d['error']}")
        feats = d.get("features", [])
        for feat in feats:
            pid = feat["attributes"]["PARCEL_ID"]
            by_stripped.setdefault(pid, []).append(feat)
        print(f"  chunk {i}-{i+len(chunk)}: requested {len(chunk)}, matched {len(feats)} features")

    enrichment = {}
    rejected = []
    unmatched = []
    for stripped, orig_pid in stripped_to_orig.items():
        feats = by_stripped.get(stripped)
        if not feats:
            unmatched.append(orig_pid)
            continue
        attrs = feats[0]["attributes"]
        city = (attrs.get("PHY_CITY") or "").strip().upper()
        co_no = attrs.get("CO_NO")
        if city not in GLADES_CITY_ALLOWLIST or co_no != GLADES_CO_NO:
            rejected.append((orig_pid, city, co_no))
            continue
        lat, lon = centroid_of_features(feats)
        addr1 = (attrs.get("PHY_ADDR1") or "").strip()
        zipcd = attrs.get("PHY_ZIPCD")
        jv = attrs.get("JV")
        av_sd = attrs.get("AV_SD")
        entry = {
            "lat": lat,
            "lon": lon,
            "market_value": jv if jv else None,
            "assessed_value": av_sd if av_sd else None,
            "property_address": (
                f"{addr1}, {city}, FL {int(zipcd)}" if addr1 and zipcd else
                (f"{addr1}, {city}, FL" if addr1 else None)
            ),
        }
        enrichment[orig_pid] = entry
    return enrichment, rejected, unmatched


def patch_row(case_number, entry, write_address):
    payload = {}
    if entry["lat"] is not None:
        payload["latitude"] = entry["lat"]
    if entry["lon"] is not None:
        payload["longitude"] = entry["lon"]
    if entry["market_value"] is not None:
        payload["market_value"] = entry["market_value"]
    if entry["assessed_value"] is not None:
        payload["assessed_value"] = entry["assessed_value"]
    if write_address and entry["property_address"] is not None:
        payload["property_address"] = entry["property_address"]

    if not payload:
        return None

    url = f"{SB}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.glades"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=H, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return len(rows)
    except urllib.error.HTTPError as exc:
        print(f"FAIL {case_number}: {exc.code} {exc.read().decode()}", file=sys.stderr)
        return 0


def main():
    rows = get_rows()
    print(f"Fetched {len(rows)} glades new-batch rows (expected {len(TARGET_CASES)})")

    print("Querying FL DOR statewide cadastral FeatureServer (dash-stripped PARCEL_ID)...")
    enrichment, rejected, unmatched = build_enrichment_map(rows)

    print(f"\nMatched+allowlisted: {len(enrichment)}")
    print(f"Rejected (city/CO_NO not on Glades allowlist): {len(rejected)} -> {rejected}")
    print(f"Unmatched (zero features from FeatureServer): {len(unmatched)} -> {unmatched}")

    parsed = len(enrichment)
    inserted = 0
    addr_written = 0
    for r in rows:
        pid = r["parcel_id"]
        entry = enrichment.get(pid)
        if not entry:
            continue
        needs_address = not r.get("property_address")
        n = patch_row(r["case_number"], entry, write_address=needs_address)
        if n:
            inserted += 1
            wrote_addr = needs_address and entry["property_address"] is not None
            if wrote_addr:
                addr_written += 1
            print(f"OK {r['case_number']} ({pid}): lat/lon/value" + (" +address" if wrote_addr else ""))
        else:
            print(f"NO-OP/FAIL {r['case_number']} ({pid})")

    print(f"\n{inserted}/{parsed} rows successfully enriched via PATCH.")
    print(f"{addr_written} rows also got a real property_address written.")
    print(f"{len(unmatched)} rows left unenriched: no FeatureServer match for parcel_id.")
    print(f"{len(rejected)} rows left unenriched: PHY_CITY/CO_NO not on Glades allowlist.")

    if parsed > 0 and inserted == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but inserted==0 -- all PATCH writes failed.")


if __name__ == "__main__":
    main()
