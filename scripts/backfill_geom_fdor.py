#!/usr/bin/env python3
"""
ZoneWise GIS: backfill zw_parcels.geom from the FDOR Statewide Cadastral FeatureServer.

Root method (issue-spec) of filtering the FeatureServer by CO_NO is BROKEN:
the CO_NO field has no server-side attribute index (confirmed via layer /0
metadata "indexes": only OBJECTID, PARCEL_ID, Shape are indexed) and every
WHERE/CAST/GROUP BY/ORDER BY on CO_NO times out ~55s and returns a generic
400. PARCEL_ID *is* indexed and fast. So instead of pulling a whole county
by CO_NO, we look up our own known zw_parcels.pin values in batched
`PARCEL_ID IN (...)` POST queries (POST avoids the GET URL-length cap that a
2000-pin IN-list would blow through).

Usage:
  python backfill_geom_fdor.py --county 44                 # one county
  python backfill_geom_fdor.py --county 44 --dry-run        # fetch+match only, no write
  python backfill_geom_fdor.py --all                        # all TARGET_COUNTIES in order
"""
import json, os, sys, time, argparse
import urllib.request
import urllib.parse
import urllib.error

MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
FDOR_QUERY_URL = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"

BATCH_FETCH = 150    # pins per FeatureServer POST. Live-probed 2026-08-16: batches >=800
                      # reliably time out (45s+) under current FeatureServer load — this
                      # public Esri service is congested well below its documented
                      # maxRecordCount 2000. 150 w/ 2s spacing ran 8/8 clean in probing.
BATCH_UPDATE = 150   # rows per UPDATE VALUES batch (400 was timing out server-side -> Cloudflare 544)
SLEEP_BETWEEN = 2.0  # politeness delay between FeatureServer requests (was 0.25 — too
                      # aggressive for current server load, was triggering cascading
                      # retry/split storms that cost far more time than they saved)

# co_no -> name, smallest first so failures surface early/cheap
# NOTE: Lafayette (44) was missing from this list until 2026-08-16 -- it had been
# corrupted by the SRID bug (see git history) but the --all sweep never reached it,
# so it silently sat at a correctly-NULLed-but-unrepaired 0% between sessions.
TARGET_COUNTIES = [
    (42, "Jackson"), (17, "Calhoun"), (43, "Jefferson"), (25, "Dixie"),
    (24, "DeSoto"), (22, "Columbia"), (44, "Lafayette"), (77, "Washington"),
    (20, "Clay"), (67, "Santa Rosa"), (47, "Leon"), (64, "Putnam"), (76, "Walton"),
    (61, "Pasco"), (68, "Sarasota"), (19, "Citrus"), (59, "Osceola"),
    (45, "Lake"), (18, "Charlotte"), (58, "Orange"), (21, "Collier"),
    (63, "Polk"), (62, "Pinellas"), (60, "Palm Beach"), (16, "Broward"),
]


UA = "curl/8.5.0"  # Cloudflare WAF (error 1010) blocks default urllib/python UAs


def sql_exec(query, timeout=120, retries=5):
    """POST to the Supabase Management API SQL endpoint. Retries with backoff on
    transient HTTP errors (observed: bursts of back-to-back calls draw a 400
    that clears itself within seconds) instead of letting one flaky call crash
    the whole county."""
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        MGMT_API, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")[:500]
            last_err = f"HTTP {e.code}: {body_text}"
            if e.code in (401, 403, 404) or attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            last_err = str(e)
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"sql_exec exhausted retries: {last_err}")


def esc(s):
    return s.replace("'", "''")


def fetch_missing_pins(co_no):
    rows = sql_exec(f"SELECT pin FROM zw_parcels WHERE co_no={co_no} AND geom IS NULL;", timeout=180)
    return [r["pin"] for r in rows]


def round_coords(obj):
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(x, 2) for x in obj]
        return [round_coords(x) for x in obj]
    return obj


def fetch_geoms_batch(pins, retries=4):
    """POST to FeatureServer, PARCEL_ID IN (...), return list of (pin, co_no, geojson_geom_dict).
    Splits the batch in half and retries on transient error/timeout instead of
    silently dropping pins — a single flaky request must not read as a coverage gap."""
    inlist = ",".join(f"'{esc(p)}'" for p in pins)
    data = urllib.parse.urlencode({
        "where": f"PARCEL_ID IN ({inlist})",
        "outFields": "CO_NO,PARCEL_ID",
        "returnGeometry": "true",
        "resultRecordCount": "2000",
        "f": "geojson",
    }).encode()
    req = urllib.request.Request(FDOR_QUERY_URL, data=data, method="POST",
                                  headers={"User-Agent": UA})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
            if "error" in d:
                # ArcGIS returned HTTP 200 with an in-body error object — this is a
                # deterministic query rejection (e.g. one malformed PIN in the
                # IN-list), not a transient blip. Retrying identically wastes 4x
                # backoff for zero benefit; go straight to split-and-isolate.
                last_err = d["error"]
                break
            out = []
            for feat in d.get("features", []):
                props = feat.get("properties", {})
                geom = feat.get("geometry")
                pin = props.get("PARCEL_ID")
                co_no = props.get("CO_NO")
                if not pin or geom is None:
                    continue
                out.append((pin, co_no, round_coords(geom)))
            return out
        except Exception as e:
            last_err = str(e)
            time.sleep(2 * (attempt + 1))
    # exhausted retries at this batch size — split and recurse (isolates the bad
    # pin/payload instead of dropping the whole batch)
    if len(pins) > 25:
        mid = len(pins) // 2
        print(f"    FeatureServer error after {retries} retries on batch of {len(pins)} "
              f"({last_err}) — splitting", file=sys.stderr)
        return fetch_geoms_batch(pins[:mid], retries) + fetch_geoms_batch(pins[mid:], retries)
    print(f"    FeatureServer error after {retries} retries on small batch "
          f"({len(pins)} pins, {last_err}) — giving up on this batch", file=sys.stderr)
    return []


def apply_update_chunk(co_no, chunk):
    """Write one chunk. On a persistent timeout (Cloudflare 544 etc, i.e. the
    query itself is too heavy — large/complex geometries), halve and recurse
    instead of dropping the chunk, so a few oversized parcels don't sink an
    otherwise-healthy batch."""
    values = ",\n".join(
        f"('{esc(pin)}', '{esc(json.dumps(geom, separators=(',', ':')))}')"
        for pin, _, geom in chunk
    )
    # f=geojson responses from ArcGIS REST are always WGS84 (RFC 7946 / Esri spec),
    # regardless of the layer's native storage SRID (3086 for this FeatureServer).
    # Confirmed live 2026-08-16: a raw fetch returned (-85.63, 30.54) -- real lon/lat
    # for Washington County, FL -- and Find_SRID('public','zw_parcels','geom') = 4326.
    # A prior version of this script wrapped the already-4326 GeoJSON in
    # ST_SetSRID(...,3086) before transforming to 4326, which silently collapsed
    # every written geometry to a near-zero-area point next to the 3086 projection
    # origin (~23.94N,-87.93W -- open Gulf water, not Florida). That corrupted
    # 182,726 rows across 11 counties in prior sessions; see repair migration.
    query = f"""
WITH v(pin, gj) AS (VALUES
{values}
)
UPDATE zw_parcels z
SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(v.gj), 4326)),
    centroid_lat = ST_Y(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(v.gj), 4326))),
    centroid_lon = ST_X(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(v.gj), 4326)))
FROM v
WHERE z.pin = v.pin AND z.co_no = {co_no} AND z.geom IS NULL;
"""
    try:
        sql_exec(query, timeout=180)
        return len(chunk)
    except urllib.error.HTTPError as e:
        if len(chunk) <= 10:
            print(f"    UPDATE failed on minimal chunk ({len(chunk)} rows, "
                  f"pins={[c[0] for c in chunk]}, HTTP {e.code}) — giving up on this chunk",
                  file=sys.stderr)
            return 0
        mid = len(chunk) // 2
        print(f"    UPDATE chunk of {len(chunk)} failed (HTTP {e.code}) — splitting", file=sys.stderr)
        return apply_update_chunk(co_no, chunk[:mid]) + apply_update_chunk(co_no, chunk[mid:])


def apply_updates(co_no, matched):
    """matched: list of (pin, co_no_returned, geom_dict). Writes in BATCH_UPDATE chunks."""
    total = 0
    for i in range(0, len(matched), BATCH_UPDATE):
        chunk = matched[i:i + BATCH_UPDATE]
        total += apply_update_chunk(co_no, chunk)
    return total


def verify_county(co_no):
    rows = sql_exec(
        f"SELECT county, co_no, count(*) n, count(geom) has_geom, "
        f"round(100.0*count(geom)/count(*),2) pct FROM zw_parcels "
        f"WHERE co_no={co_no} GROUP BY county, co_no;"
    )
    return rows[0] if rows else None


def process_county(co_no, name, dry_run=False):
    start = verify_county(co_no)
    print(f"\n=== {name} (co_no={co_no}) — START pct_geom={start['pct']}% ({start['has_geom']}/{start['n']}) ===")

    pins = fetch_missing_pins(co_no)
    print(f"  {len(pins):,} pins missing geom")
    if not pins:
        print("  nothing to do")
        return start, start, 0, 0

    matched_total = 0
    fetched_total = 0
    for i in range(0, len(pins), BATCH_FETCH):
        batch = pins[i:i + BATCH_FETCH]
        matched = fetch_geoms_batch(batch)
        fetched_total += len(batch)
        matched_total += len(matched)
        if matched and not dry_run:
            apply_updates(co_no, matched)
        if (i // BATCH_FETCH) % 10 == 0:
            print(f"    progress: {fetched_total:,}/{len(pins):,} pins queried, {matched_total:,} matched")
        time.sleep(SLEEP_BETWEEN)

    end = verify_county(co_no)
    print(f"  matched {matched_total:,}/{len(pins):,} pins to FeatureServer geometry")
    print(f"=== {name} (co_no={co_no}) — END pct_geom={end['pct']}% ({end['has_geom']}/{end['n']}) ===")
    return start, end, len(pins), matched_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", type=int, help="single co_no to process")
    ap.add_argument("--all", action="store_true", help="process all TARGET_COUNTIES in order")
    ap.add_argument("--dry-run", action="store_true", help="fetch+match only, no DB write")
    args = ap.parse_args()

    if not ACCESS_TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    results = []
    if args.county:
        name = dict(TARGET_COUNTIES).get(args.county, str(args.county))
        results.append((name, args.county) + process_county(args.county, name, args.dry_run))
    elif args.all:
        for co_no, name in TARGET_COUNTIES:
            results.append((name, co_no) + process_county(co_no, name, args.dry_run))
    else:
        ap.print_help()
        return

    print("\n\n=== SUMMARY ===")
    for name, co_no, start, end, n_missing, n_matched in results:
        print(f"{name:12s} co_no={co_no:3d}  {start['pct']}% -> {end['pct']}%  "
              f"(missing {n_missing:,}, matched {n_matched:,})")


if __name__ == "__main__":
    main()
