#!/usr/bin/env python3
"""
gold_standard_shard2_marion_i_placeholder_geocode_fix.py

GOLD STANDARD marion (shard-2, 2nd firing) letter I ghost-success fix.

BACKGROUND (adversarially refuted 2026-07-30, commit bd9f6fa9): marion's
letter I ("card complete >= 95%") was claimed PASS at metric=95.1
(card_complete=543 of 571). An independent refuter found 297 of those 543
"complete" rows share one IDENTICAL placeholder lat/lng
(29.2104, -82.1261) across 293 distinct parcel_ids / 222 distinct
addresses -- a generic Ocala-area fallback centroid, not real per-parcel
geocoding. The RPC's completeness check only verifies
COALESCE(latitude, po_latitude) IS NOT NULL, so it cannot detect a
duplicated fallback constant. This script OVERWRITES that specific known-bad
placeholder with a real per-parcel centroid -- it does NOT touch any row
whose lat/lng is anything else, even if unsure it's "real" (BLANK > WRONG).

LIVE RE-DERIVATION (2026-07-30, this run): re-queried fresh rather than
trusting the refuter's pasted 297 figure. The full set of marion rows with
latitude=29.2104 AND longitude=-82.1261 (no other filter) is 276 rows, of
which 4 have parcel_id IS NULL (cannot be matched by parcel_id at all --
left untouched, listed at run time as unmatched). The refuter's 297 number
was scoped additionally to the RPC's "card_rows" join (multi_county_auctions
rows whose parcel_id/tax_account resolves a zone_code in
v_zoning_gold_standard_card) -- a narrower slice of the same underlying bug.
This script fixes the full 276-row placeholder set; the DoD metric will
reflect whichever subset of those 276 also happens to be in card_rows.

DATA SOURCE (live, real, VERIFIED 2026-07-30): Marion County's OWN ArcGIS
REST parcels service -- NOT the FL DOR statewide cadastral FeatureServer
used by the glades/sumter/collier pattern scripts. That statewide mirror's
PARCEL_ID field (both as-is and dash-stripped) returns ZERO features for
marion's numeric parcel_id values (spot-checked 8/276 live), and broad
CO_NO=42 / PHY_ADDR1 / ALT_KEY scans against it all time out (unindexed on
that shared instance) -- so it is not usable for marion. Instead:

  https://gis.marionfl.org/public/rest/services/General/Parcels/MapServer/0

  This is Marion County Property Appraiser's own hosted GIS (found live via
  web search, "General/Parcels" MapServer, capabilities=Map,Query,Data,
  maxRecordCount=2500, no auth required). Its field `ALT_Key`
  (esriFieldTypeInteger) is Marion's short numeric parcel key -- EXACTLY the
  format stored in our multi_county_auctions.parcel_id column. Spot-checked
  3/276 live before running the full batch:
    ALT_Key=2619392 -> PARCEL 4202-031-065, SITUS_1='13553 SE 39TH TER',
      ASSD_VAL=79834.0 (matches our DB assessed_value=79834.00 exactly,
      case 422018CA001472CAAXXX)
    ALT_Key=529800  -> PARCEL 2097-012-007, SITUS_1='20 NEVER BEND DR',
      ASSD_VAL=238117.0
    ALT_Key=3589025 -> PARCEL 12179-006-00, SITUS_1='6614 NW 150TH AVE' /
      SITUS_2='6618 NW 150TH AVE', ASSD_VAL=1965249.0
  Geometry query with outSR=4326 returns ring vertices already in WGS84
  (server-side reprojection from native wkid 102659/2237 State Plane) --
  centroid for ALT_Key=2619392 came back lat=29.0252, lon=-82.0812, which is
  (a) inside the Marion County FL bounding box (lat 28.95-29.45,
  lon -82.55..-81.75) and (b) nowhere near the placeholder
  (29.2104, -82.1261) -- confirming this is real per-parcel geometry, not
  another shared constant.

QUERIED: ALT_Key IN (...) batches of 100, outFields
  PARCEL,ALT_Key,SITUS_1,SITUS_2,ASSD_VAL,TOT_VAL,ZIP, returnGeometry=true,
  outSR=4326.

FIELDS WRITTEN per multi_county_auctions row (PATCH by
case_number=eq.<case>&county=eq.marion), ONLY for rows currently at the
placeholder (latitude=29.2104 AND longitude=-82.1261 exactly -- re-checked
via a WHERE clause on the PATCH request itself as a belt-and-suspenders
guard against a race with any other concurrent shard):
  - latitude, longitude: centroid (mean of all ring vertices) from the
    Marion GIS query, outSR=4326. REJECTED (not written) if outside the
    Marion County FL plausibility bounding box (lat 28.95-29.45,
    lon -82.55..-81.75).
  - assessed_value: Marion GIS ASSD_VAL, ONLY if our row's assessed_value is
    currently NULL. Never overwrites an existing non-null value.
  - market_value: Marion GIS TOT_VAL, ONLY if our row's market_value is
    currently NULL. Never overwrites an existing non-null value.

NOT WRITTEN / EXPLICITLY OUT OF SCOPE:
  - Any row whose parcel_id is NULL -- cannot be matched by ALT_Key at all.
    Left entirely untouched, listed at run time (expect 4, per live count
    2026-07-30).
  - Any row whose ALT_Key returns zero features from Marion's GIS -- left
    entirely untouched, listed at run time.
  - Any row whose returned centroid falls outside the Marion County FL
    plausibility bounding box -- rejected as a probable mismatch, left
    entirely untouched, listed at run time (BLANK > WRONG).
  - property_address is never touched by this script (out of scope --
    task brief only calls for lat/lng + value backfill).
  - Any row whose current lat/lng is NOT exactly (29.2104, -82.1261) --
    completely out of scope for this fix, never queried or touched.

WRITES PERFORMED: up to 276 PATCH requests to
  {SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.<case>&county=eq.marion
  &latitude=eq.29.2104&longitude=eq.-82.1261
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

MARION_GIS_URL = (
    "https://gis.marionfl.org/public/rest/services/General/Parcels/MapServer/0/query"
)

PLACEHOLDER_LAT = 29.2104
PLACEHOLDER_LON = -82.1261

# Marion County FL plausibility bounding box (per task brief).
BBOX_LAT = (28.95, 29.45)
BBOX_LON = (-82.55, -81.75)

CHUNK_SIZE = 100
MAX_RETRIES = 4


def get_rows():
    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        f"?county=eq.marion&latitude=eq.{PLACEHOLDER_LAT}&longitude=eq.{PLACEHOLDER_LON}"
        "&select=case_number,parcel_id,assessed_value,market_value"
        "&order=case_number&limit=1000"
    )
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_gis_chunk(alt_keys):
    id_list = ",".join(str(k) for k in alt_keys)
    where = f"ALT_Key IN ({id_list})"
    params = {
        "where": where,
        "outFields": "PARCEL,ALT_Key,SITUS_1,SITUS_2,ASSD_VAL,TOT_VAL,ZIP",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = MARION_GIS_URL + "?" + urllib.parse.urlencode(params)
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
    raise RuntimeError(f"Marion GIS unreachable after {MAX_RETRIES} retries: {last_exc}")


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


def in_bbox(lat, lon):
    return BBOX_LAT[0] <= lat <= BBOX_LAT[1] and BBOX_LON[0] <= lon <= BBOX_LON[1]


def build_enrichment_map(rows):
    """Returns dict: parcel_id (int-as-str, our original) -> enrichment fields."""
    alt_key_to_pid = {}
    for r in rows:
        pid = r.get("parcel_id")
        if not pid:
            continue
        try:
            alt_key_to_pid[int(pid)] = pid
        except (TypeError, ValueError):
            continue

    alt_keys = list(alt_key_to_pid.keys())
    by_alt_key = {}
    for i in range(0, len(alt_keys), CHUNK_SIZE):
        chunk = alt_keys[i : i + CHUNK_SIZE]
        d = fetch_gis_chunk(chunk)
        if "error" in d:
            raise RuntimeError(f"Marion GIS error on chunk {i}: {d['error']}")
        feats = d.get("features", [])
        for feat in feats:
            k = feat["attributes"]["ALT_Key"]
            by_alt_key.setdefault(k, []).append(feat)
        print(f"  chunk {i}-{i+len(chunk)}: requested {len(chunk)}, matched {len(feats)} features")

    enrichment = {}
    rejected_bbox = []
    unmatched = []
    for alt_key, orig_pid in alt_key_to_pid.items():
        feats = by_alt_key.get(alt_key)
        if not feats:
            unmatched.append(orig_pid)
            continue
        attrs = feats[0]["attributes"]
        lat, lon = centroid_of_features(feats)
        if lat is None or lon is None or not in_bbox(lat, lon):
            rejected_bbox.append((orig_pid, lat, lon))
            continue
        assd_val = attrs.get("ASSD_VAL")
        tot_val = attrs.get("TOT_VAL")
        enrichment[orig_pid] = {
            "lat": lat,
            "lon": lon,
            "assessed_value": assd_val if assd_val else None,
            "market_value": tot_val if tot_val else None,
        }
    return enrichment, rejected_bbox, unmatched


def patch_row(case_number, entry, write_assessed, write_market):
    payload = {
        "latitude": entry["lat"],
        "longitude": entry["lon"],
    }
    if write_assessed and entry["assessed_value"] is not None:
        payload["assessed_value"] = entry["assessed_value"]
    if write_market and entry["market_value"] is not None:
        payload["market_value"] = entry["market_value"]

    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        f"?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.marion"
        f"&latitude=eq.{PLACEHOLDER_LAT}&longitude=eq.{PLACEHOLDER_LON}"
    )
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
    print(f"Fetched {len(rows)} marion rows at the placeholder lat/lng (fresh live re-derivation)")

    null_pid_rows = [r for r in rows if not r.get("parcel_id")]
    print(f"Rows with parcel_id IS NULL (cannot match): {len(null_pid_rows)}")
    for r in null_pid_rows:
        print(f"  UNMATCHABLE (no parcel_id): {r['case_number']}")

    print("Querying Marion County GIS (gis.marionfl.org, ALT_Key) in batches...")
    enrichment, rejected_bbox, unmatched = build_enrichment_map(rows)

    print(f"\nMatched+in-bbox: {len(enrichment)}")
    print(f"Rejected (centroid outside Marion County bbox): {len(rejected_bbox)} -> {rejected_bbox}")
    print(f"Unmatched (zero features from Marion GIS): {len(unmatched)} -> {unmatched}")

    parsed = len(enrichment)
    inserted = 0
    assessed_written = 0
    market_written = 0
    for r in rows:
        pid = r.get("parcel_id")
        if not pid:
            continue
        entry = enrichment.get(pid)
        if not entry:
            continue
        write_assessed = r.get("assessed_value") is None
        write_market = r.get("market_value") is None
        n = patch_row(r["case_number"], entry, write_assessed, write_market)
        if n:
            inserted += 1
            wrote_assessed = write_assessed and entry["assessed_value"] is not None
            wrote_market = write_market and entry["market_value"] is not None
            if wrote_assessed:
                assessed_written += 1
            if wrote_market:
                market_written += 1
            extra = []
            if wrote_assessed:
                extra.append("assessed_value")
            if wrote_market:
                extra.append("market_value")
            print(f"OK {r['case_number']} ({pid}): lat/lon" + (f" +{'+'.join(extra)}" if extra else ""))
        else:
            print(f"NO-OP/FAIL {r['case_number']} ({pid})")

    print(f"\n{inserted}/{parsed} rows successfully PATCHed (placeholder overwritten with real centroid).")
    print(f"{assessed_written} rows also got assessed_value backfilled (was NULL).")
    print(f"{market_written} rows also got market_value backfilled (was NULL).")
    print(f"{len(null_pid_rows)} rows left untouched: parcel_id IS NULL.")
    print(f"{len(unmatched)} rows left untouched: no Marion GIS match for ALT_Key.")
    print(f"{len(rejected_bbox)} rows left untouched: centroid outside Marion County bbox.")

    if parsed > 0 and inserted == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but inserted==0 -- all PATCH writes failed.")


if __name__ == "__main__":
    main()
