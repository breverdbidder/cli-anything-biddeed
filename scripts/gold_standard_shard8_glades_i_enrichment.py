#!/usr/bin/env python3
"""
gold_standard_shard8_glades_i_enrichment.py

GOLD STANDARD shard-8 (glades) criterion I (card_complete) fix, step 1:
property_address / latitude / longitude / assessed_value / market_value
backfill for glades' 70 multi_county_auctions rows
(data_source='municode_munidocs:GLADES-TD-V1'). All 70 rows have a real
Glades Section-Township-Range-style parcel_id (e.g.
'S02-42-32-001-0009-0090', 'A22-42-32-U02-0000-005A') and 66/70 already have
a real property_address parsed from the source Municode PDFs; ZERO have
latitude/longitude/assessed_value/market_value (VERIFIED live 2026-07-11).

DATA SOURCE (live, real, cross-verified 2026-07-11):
  https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
    Florida_Statewide_Cadastral/FeatureServer/0
  Same FL DOR statewide cadastral FeatureServer mirror already used and
  documented for Sumter (scripts/shard9_run3645_sumter_i_parcel_enrichment.py)
  and Collier (scripts/gold_standard_shard1_collier_i_enrichment.py).
  Queried in 60-id batches by PARCEL_ID IN (...).

  PARCEL_ID FORMAT QUIRK (VERIFIED live, a NEW quirk distinct from Collier's
  CO_NO-remap and Sumter's CO_NO=70 mislabel): a direct string match of our
  glades parcel_id against this mirror's PARCEL_ID field returns ZERO
  features (tested for 'S02-42-32-001-0009-0090' and
  'A22-42-32-U02-0000-005A' -- both return 0 rows verbatim). The mirror
  stores the SAME parcel key with all internal dashes stripped:
  'S02-42-32-001-0009-0090' -> 'S02423200100090090' (19 chars) and
  'A22-42-32-U02-0000-005A' -> 'A224232U020000005A' (19 chars). Stripping
  '-' from our parcel_id and querying PARCEL_ID = <stripped> returns exactly
  1 feature per id, every time tested (spot-checked 7 of 70 live before
  running the full batch: S02423200100090090 -> 1033 GREEN ST, MOORE HAVEN;
  A224232U020000005A -> 1203 HICPOCHEE LN, MOORE HAVEN; S11423200301680110
  -> 1505 TOBIAS AVE, MOORE HAVEN; plus the 4 no-address rows -- JERDIK DR
  Moore Haven, VENUS LOOP/SOLAR RD/JABARA CIR LaBelle -- all CO_NO=32).
  Unlike Collier/Sumter, CO_NO=32 on this mirror IS glades' real FL DOR
  county number (matches the task brief's CO_NO=32) -- no county remap here,
  just dash-stripping.

  CROSS-VALIDATION: every match is additionally checked against a PHY_CITY
  allowlist of real Glades cities/communities (per task brief: Moore Haven,
  Buckhead Ridge, Lakeport, Palmdale, Ortona, Muse, LaBelle/Okeechobee for
  legitimate near-county-line mailing addresses) AND against CO_NO=32. Any
  match whose PHY_CITY is not on this list, or whose CO_NO != 32, is NOT
  enriched (BLANK > WRONG).

FIELDS WRITTEN per multi_county_auctions row (PATCH by
case_number=eq.<case>&county=eq.glades):
  - latitude, longitude: centroid (mean of all ring vertices) from the
    FeatureServer query with outSR=4326.
  - market_value: cadastral JV (just value) field, when JV > 0.
  - assessed_value: cadastral AV_SD (assessed value, school district)
    field, when AV_SD > 0.
  - property_address: "{PHY_ADDR1}, {PHY_CITY}, FL {PHY_ZIPCD}" ONLY for the
    4 rows currently missing property_address AND only where PHY_ADDR1 is
    non-blank. The 66 rows that already have a property_address (scraped
    from the Municode PDFs) are left untouched -- not overwritten -- to
    avoid clobbering a real, independently-sourced value with a
    differently-formatted (but not necessarily better) one.

NOT WRITTEN / EXPLICITLY OUT OF SCOPE:
  - Any row whose PARCEL_ID (dash-stripped) returns zero features from the
    FeatureServer -- left entirely NULL, listed at run time.
  - Any match whose PHY_CITY is not on the Glades allowlist or whose
    CO_NO != 32 -- left entirely NULL (BLANK > WRONG), listed at run time.
  - JV/AV_SD of exactly 0 or missing are NOT written as 0.
  - The v_zoning_gold_standard_card join (zone_code) required for I to PASS
    is a separate downstream step (another shard's scope per task brief) --
    I is expected to remain FAIL/card_complete=0 after this script alone.

WRITES PERFORMED: up to 70 PATCH requests to
  {SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.<case>&county=eq.glades
See stdout at run time for exact per-row and summary counts (fail-loud: if
parsed>0 and inserted==0 this script raises, per repo guardrails).
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

# Real Glades County cities/communities (per task brief) + legitimate
# near-county-line mailing addresses that share ZIP/postal service areas.
GLADES_CITY_ALLOWLIST = {
    "MOORE HAVEN", "BUCKHEAD RIDGE", "LAKEPORT", "PALMDALE", "ORTONA",
    "MUSE", "LABELLE", "OKEECHOBEE",
}
GLADES_CO_NO = 32

CHUNK_SIZE = 60
MAX_RETRIES = 4


def get_rows():
    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        "?county=eq.glades&select=case_number,parcel_id,property_address"
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
    """Returns dict: parcel_id (our original, dashed) -> enrichment fields."""
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
    print(f"Fetched {len(rows)} glades multi_county_auctions rows")
    if len(rows) != 70:
        print(f"WARNING: expected 70 rows, got {len(rows)}", file=sys.stderr)

    print("Querying FL DOR statewide cadastral FeatureServer in batches (dash-stripped PARCEL_ID)...")
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
    print(f"{addr_written} rows also got a real property_address written (of the 4 that were missing one).")
    print(f"{len(unmatched)} rows left unenriched: no FeatureServer match for parcel_id.")
    print(f"{len(rejected)} rows left unenriched: PHY_CITY/CO_NO not on Glades allowlist.")

    if parsed > 0 and inserted == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but inserted==0 -- all PATCH writes failed.")


if __name__ == "__main__":
    main()
