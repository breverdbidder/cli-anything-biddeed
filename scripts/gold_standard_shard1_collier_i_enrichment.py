#!/usr/bin/env python3
"""
gold_standard_shard1_collier_i_enrichment.py

GOLD STANDARD shard-1 (collier) criterion I (card_complete) fix, step 1:
property_address / latitude / longitude / assessed_value / market_value
backfill for collier's 212 multi_county_auctions rows
(data_source='collier_clerk_laserfiche'). All 212 rows had a real 11-digit
Collier folio number in parcel_id but zero enrichment fields populated
(VERIFIED live 2026-07-11).

DATA SOURCE (live, real, cross-verified 2026-07-11):
  https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
    Florida_Statewide_Cadastral/FeatureServer/0
  Same FL DOR statewide cadastral FeatureServer mirror already used and
  documented for Sumter in
  scripts/shard9_run3645_sumter_i_parcel_enrichment.py. Queried in
  60-id batches by PARCEL_ID IN (...).

  CO_NO QUIRK (same class as Sumter's CO_NO=70 quirk, re-confirmed live for
  Collier specifically): this mirror returns CO_NO=21 for genuine Collier
  folios, not Collier's real FL DOR co_no=11. We do NOT filter on CO_NO.
  Instead every match is cross-validated against a PHY_CITY allowlist of
  real Collier cities/communities: NAPLES, MARCO ISLAND, EVERGLADES CITY,
  IMMOKALEE, AVE MARIA, GOLDEN GATE, GOLDEN GATE CITY, GOLDEN GATE ESTATES,
  OCHOPEE, COPELAND, CHOKOLOSKEE, PLANTATION ISLAND. (GOLDEN GATE CITY was
  observed live and added to the allowlist verbatim -- it is a real,
  well-known unincorporated Collier community, not a fabricated addition.)
  Any match whose PHY_CITY is not on this list is NOT enriched (BLANK >
  WRONG) -- none were observed in this run (all 204 matched features
  resolved to NAPLES/IMMOKALEE/MARCO ISLAND/GOLDEN GATE CITY/EVERGLADES
  CITY), but the guard is left in place for reproducibility.

  MULTI-FEATURE FOLIOS: 8 of the 212 requested PARCEL_IDs returned more than
  one feature (identical PHY_ADDR1/PHY_CITY/PHY_ZIPCD/JV/AV_SD attributes,
  different geometry rings -- e.g. condo/mobile-home-park parcels recorded
  as multiple polygon parts under one folio). For these, latitude/longitude
  is the centroid of ALL returned rings combined (still real geometry, not
  fabricated), and the (identical) attribute values are used once.

  UNMATCHED FOLIOS: 8 of the 212 requested PARCEL_IDs returned ZERO features
  from this FeatureServer (00992000008, 01155640000, 01160000004,
  01160400002, 0745160001, 3480006, 37870600108, 78698105 -- several are
  shorter/differently-formatted folio strings, likely an older format or a
  parcel not present in this particular cached mirror). These are left
  completely unenriched -- no value fabricated -- and are a documented
  residual (see NOT WRITTEN section below).

FIELDS WRITTEN per multi_county_auctions row (PATCH by
case_number=eq.<case>&county=eq.collier):
  - latitude, longitude: centroid (mean of all ring vertices across all
    matched features for that PARCEL_ID) from the FeatureServer query with
    outSR=4326.
  - market_value: cadastral JV (just value) field, when JV > 0.
  - assessed_value: cadastral AV_SD (assessed value, school district)
    field, when AV_SD > 0.
  - property_address: "{PHY_ADDR1}, {PHY_CITY}, FL {PHY_ZIPCD}" ONLY where
    PHY_ADDR1.strip() is non-blank (109 of 204 matched rows have a blank
    " " PHY_ADDR1 -- vacant/unimproved tax-deed parcels with no DOR-recorded
    situs address; left NULL, not fabricated, matching the Sumter
    precedent).

NOT WRITTEN / EXPLICITLY OUT OF SCOPE:
  - The 8 folios with zero FeatureServer matches (listed above) -- no live
    source found within this run's scope. Left entirely NULL.
  - JV/AV_SD of exactly 0 or missing are NOT written as 0 (0 is not a
    believable market/assessed value for a real property and would read as
    fabricated precision) -- left NULL if absent/zero, and property_address
    is still written independently if PHY_ADDR1 is present.

WRITES PERFORMED: up to 204 PATCH requests to
  {SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.<case>&county=eq.collier
See stdout at run time for exact per-row and summary counts (fail-loud: if
parsed>0 and inserted==0 this script raises, per repo guardrails).
"""
import json
import os
import sys
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

COLLIER_CITY_ALLOWLIST = {
    "NAPLES", "MARCO ISLAND", "EVERGLADES CITY", "IMMOKALEE", "AVE MARIA",
    "GOLDEN GATE", "GOLDEN GATE CITY", "GOLDEN GATE ESTATES", "OCHOPEE",
    "COPELAND", "CHOKOLOSKEE", "PLANTATION ISLAND",
}

CHUNK_SIZE = 60


def get_rows():
    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        "?county=eq.collier&select=case_number,parcel_id,opening_bid&order=case_number&limit=300"
    )
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_dor_chunk(parcel_ids):
    id_list = ",".join(f"'{i}'" for i in parcel_ids)
    where = f"PARCEL_ID IN ({id_list})"
    params = {
        "where": where,
        "outFields": "PARCEL_ID,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def centroid_of_features(features):
    """Mean of all ring vertices across ALL rings of ALL features (real
    geometry only, no fabrication)."""
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
    """Returns dict: parcel_id -> enrichment fields (or None if rejected)."""
    parcel_ids = [r["parcel_id"] for r in rows]
    by_parcel = {}
    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i : i + CHUNK_SIZE]
        d = fetch_dor_chunk(chunk)
        if "error" in d:
            raise RuntimeError(f"FL DOR FeatureServer error on chunk {i}: {d['error']}")
        for feat in d.get("features", []):
            pid = feat["attributes"]["PARCEL_ID"]
            by_parcel.setdefault(pid, []).append(feat)
        print(f"  chunk {i}-{i+len(chunk)}: requested {len(chunk)}, matched {len(d.get('features', []))} features")

    enrichment = {}
    rejected_city = []
    unmatched = []
    for pid in parcel_ids:
        feats = by_parcel.get(pid)
        if not feats:
            unmatched.append(pid)
            continue
        attrs = feats[0]["attributes"]
        city = (attrs.get("PHY_CITY") or "").strip().upper()
        if city not in COLLIER_CITY_ALLOWLIST:
            rejected_city.append((pid, city))
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
        enrichment[pid] = entry
    return enrichment, rejected_city, unmatched


def patch_row(case_number, entry):
    payload = {}
    if entry["lat"] is not None:
        payload["latitude"] = entry["lat"]
    if entry["lon"] is not None:
        payload["longitude"] = entry["lon"]
    if entry["market_value"] is not None:
        payload["market_value"] = entry["market_value"]
    if entry["assessed_value"] is not None:
        payload["assessed_value"] = entry["assessed_value"]
    if entry["property_address"] is not None:
        payload["property_address"] = entry["property_address"]

    if not payload:
        return None  # nothing to write

    url = f"{SB}/rest/v1/multi_county_auctions?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.collier"
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
    print(f"Fetched {len(rows)} collier multi_county_auctions rows")
    if len(rows) != 212:
        print(f"WARNING: expected 212 rows, got {len(rows)}", file=sys.stderr)

    print("Querying FL DOR statewide cadastral FeatureServer in batches...")
    enrichment, rejected_city, unmatched = build_enrichment_map(rows)

    print(f"\nMatched+allowlisted: {len(enrichment)}")
    print(f"Rejected (city not on allowlist): {len(rejected_city)} -> {rejected_city}")
    print(f"Unmatched (zero features from FeatureServer): {len(unmatched)} -> {unmatched}")

    parsed = len(enrichment)
    inserted = 0
    addr_written = 0
    for r in rows:
        pid = r["parcel_id"]
        entry = enrichment.get(pid)
        if not entry:
            continue
        n = patch_row(r["case_number"], entry)
        if n:
            inserted += 1
            if entry["property_address"]:
                addr_written += 1
            print(f"OK {r['case_number']} ({pid}): lat/lon/value" + (" +address" if entry["property_address"] else ""))
        else:
            print(f"NO-OP/FAIL {r['case_number']} ({pid})")

    print(f"\n{inserted}/{parsed} rows successfully enriched via PATCH.")
    print(f"{addr_written}/{inserted} of those also got a real property_address.")
    print(f"{len(unmatched)} rows left unenriched: no FeatureServer match for folio.")
    print(f"{len(rejected_city)} rows left unenriched: PHY_CITY not on Collier allowlist.")

    if parsed > 0 and inserted == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but inserted==0 -- all PATCH writes failed.")


if __name__ == "__main__":
    main()
