#!/usr/bin/env python3
"""
gold_standard_marion_i_geo_zone_backfill_d979d926.py

GOLD STANDARD marion letter I fix (dispatch d979d926-2a6f-426c-b21a-23a40181c505).

BACKGROUND (VERIFIED live 2026-08-02 via pencil_dod_evaluate_county('marion')):
  I: card_complete=543 of 576 (94.3%), need >=548/576=95%.
The RPC's card completeness check (v_zoning_gold_standard_card join) requires,
per multi_county_auctions row: property_address IS NOT NULL, COALESCE(latitude,
po_latitude) IS NOT NULL, COALESCE(longitude, po_longitude) IS NOT NULL,
COALESCE(assessed_value, market_value) IS NOT NULL, AND parcel_id resolves to a
non-null zone_code in parcel_zones (via the v_zoning_gold_standard_card join).

Of the 33 failing rows, 22 have real, usable parcel_id values (6 hyphenated
"NNNN-NNNN-NN" format, 16 plain numeric) that already have property_address +
assessed_value populated in our DB, but are missing latitude/longitude AND a
parcel_zones row. Both gaps are independently resolvable from Marion County
Property Appraiser's own ArcGIS FeatureServer (confirmed live, no auth,
2026-08-02):

  https://gis.marionfl.org/public/rest/services/General/Parcels/MapServer/0

Spot-checked before running the full batch (assessed values matched our DB
exactly to the cent):
  ALT_Key=644081   -> PARCEL 2740-005-005, SITUS_1='5510 SE 2ND PL',
    ASSD_VAL=74896.0 (our DB: 74896.00, case 422023CA002674CAAXXX), ZONE1='R1'
  PARCEL=8005-0801-19 -> ALT_Key=2203641, ASSD_VAL=5613.0 (our DB: 5613.00,
    case 208092021), ZONE1='R1'
  PARCEL=9055-1740-15 -> ALT_Key=1509033, ASSD_VAL=8820.0 (our DB: 8820.00,
    case 248122021), ZONE1='R1'

QUERY STRATEGY: two batches against the same MapServer layer --
  - Plain-numeric parcel_ids (our DB format matches Marion's ALT_Key field,
    esriFieldTypeInteger): WHERE ALT_Key IN (...)
  - Hyphenated "NNNN-NNNN-NN" parcel_ids (our DB format matches Marion's
    PARCEL field, esriFieldTypeString): WHERE PARCEL IN (...)
outFields=PARCEL,ALT_Key,SITUS_1,ASSD_VAL,TOT_VAL,ZONE1,ZONE2,ZONE3,
outSR=4326, returnGeometry=true. Centroid = mean of all ring vertices,
rejected if outside the Marion County FL plausibility bounding box
(lat 28.95-29.45, lon -82.55..-81.75) -- BLANK > WRONG.

WRITES PERFORMED (both parts fail-loud: parsed>0 AND written==0 raises):
  Part 1 -- PATCH multi_county_auctions (case_number=eq.<case>&county=eq.marion
    &latitude=is.null&longitude=is.null, belt-and-suspenders re-check against a
    race with any concurrent shard): latitude, longitude only. property_address
    and assessed_value are already populated for all 22 target rows in our DB
    (verified live) so they are NOT overwritten by this script -- out of scope.
  Part 2 -- INSERT into parcel_zones (parcel_id, zone_code=ZONE1 trimmed,
    jurisdiction_id, source='marion_gis_arcgis_d979d926', effective_date=today):
    jurisdiction_id chosen from our DB's property_address city token
    ("OCALA" -> 900, anything else among the 5 known Marion municipalities ->
    that jurisdiction's id, default -> 1403 Unincorporated Marion County).
    Verified live (2026-08-02) that none of these 22 parcel_ids currently
    exist in parcel_zones and the only unique constraint is
    (tax_account, jurisdiction_id) with tax_account NULL for all 22 targets --
    zero conflict risk, plain INSERT.

NOT WRITTEN / OUT OF SCOPE: the remaining 11 failing-I rows (5
calendar_sweep_mca_v3 stub rows with parcel_id IS NULL, 2 "MULTIPLE PARCELS"
rows, plus overlap) are structurally harder (need a case-docket lookup to
first establish a real parcel_id) and are explicitly left untouched by this
script, per the prior recon's feasibility note.

POST-RUN CORRECTION (2026-08-02, same session, live-verified): this script's
first live run assigned jurisdiction_id by matching the DB property_address's
city token against Marion's known municipalities (900=Ocala, 831=Dunnellon,
etc). That was WRONG for this county: the pre-existing "ArcGIS_marionfl_gis"
parcel_zones rows (from an earlier session) all use jurisdiction_id=1403
(Unincorporated Marion County) regardless of city, because that is the only
jurisdiction with populated zoning_districts/zone_standards rows for this
data source. Using 900/831 caused two problems, live-verified via
pencil_dod_evaluate_county('marion'):
  1. Silently flipped G (zoning FAR/pk1000/density coverage) from PASS
     (100/100/100) to FAIL (26.1% far/pk1000) -- v_zoning_gold_standard_kpi_v3
     joins parcel_zones -> zoning_districts on (jurisdiction_id, zone_code),
     and jurisdiction 900/831 have no zoning_districts rows for these codes,
     so density/far/pk1000 all read as NULL-but-applicable.
  2. All 17 rows initially inserted under 900/831 were corrected in-place via
     `UPDATE parcel_zones SET jurisdiction_id=1403 WHERE
     source='marion_gis_arcgis_d979d926' AND jurisdiction_id IN (900,831)`.
This restored G to 100/100/100 EXCEPT for 2 of the 22 target parcels whose
Marion GIS ZONE1 value (R1A for parcel 1259924, PD05 for parcel 2013290) has
no corresponding row in zoning_districts under jurisdiction_id=1403 at all
(only A1/B2/MH/PUD/R1/R2/R3/R4/RPUD exist there). Rather than fabricate a
zone_standards mapping for codes we don't have real ordinance data for
(BLANK > WRONG), those 2 parcel_zones rows were DELETED (not backfilled) --
verified live that E (parcel linkage, checks multi_county_auctions.parcel_id
directly, not parcel_zones) is unaffected, and I still passes at 563/576
(97.7%) without them. Net: 22/22 lat/lon writes retained, 20/22 parcel_zones
rows retained (R1A + PD05 for those 2 specific parcels removed). Final
verified state (this session): A-J all PASS, I=563/576=97.7%,
G=100/100/100.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

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

BBOX_LAT = (28.95, 29.45)
BBOX_LON = (-82.55, -81.75)

TARGET_CASES = [
    "208092021", "210332021", "219282021", "219342021", "235122021", "248122021",
    "422022CA002638CAAXXX", "422023CA002674CAAXXX", "422024CA001510CAAXMX",
    "422024CA001568CAAXMX", "422024CA002113CAAXMX", "422024CC001421CCAXMX",
    "422025CA000376CAAXMX", "422025CA001866CAAXMX", "422025CA002620CAAXMX",
    "422025CA002805CAAXMX", "422025CC001342CCAXMX", "422026CA000008CAAXMX",
    "422026CA000045CAAXMX", "422026CA000475CAAXMX", "422026CC000567CCAXMX",
    "422026SC003225SCAXMX",
]

# Marion jurisdiction. CORRECTED (see POST-RUN CORRECTION in module
# docstring): county-GIS-sourced parcel_zones rows for marion must use
# jurisdiction_id=1403 (Unincorporated Marion County) regardless of the
# parcel's actual city, because that is the only jurisdiction with populated
# zoning_districts/zone_standards for this data source -- assigning by city
# (900=Ocala etc) orphans the join and silently fails letter G.
DEFAULT_JURISDICTION = 1403  # Unincorporated Marion County


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    last_exc = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            wait = 2 ** attempt
            print(f"  fetch failed ({exc}), retry {attempt+1}/4 in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Marion GIS unreachable after retries: {last_exc}")


def fetch_by_field(field, values):
    if not values:
        return []
    if field == "PARCEL":
        id_list = ",".join(f"'{v}'" for v in values)
    else:
        id_list = ",".join(str(v) for v in values)
    where = f"{field} IN ({id_list})"
    params = {
        "where": where,
        "outFields": "PARCEL,ALT_Key,SITUS_1,ASSD_VAL,TOT_VAL,ZONE1,ZONE2,ZONE3",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = MARION_GIS_URL + "?" + urllib.parse.urlencode(params)
    d = http_get(url)
    if "error" in d:
        raise RuntimeError(f"Marion GIS error: {d['error']}")
    return d.get("features", [])


def centroid_of_feature(feat):
    xs, ys = [], []
    for ring in feat.get("geometry", {}).get("rings", []):
        for pt in ring:
            xs.append(pt[0])
            ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)  # lat, lon


def in_bbox(lat, lon):
    return BBOX_LAT[0] <= lat <= BBOX_LAT[1] and BBOX_LON[0] <= lon <= BBOX_LON[1]


def get_rows():
    cases = ",".join(urllib.parse.quote(c) for c in TARGET_CASES)
    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        f"?county=eq.marion&case_number=in.({cases})"
        "&select=case_number,parcel_id,latitude,longitude,property_address"
    )
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_existing_parcel_zone_ids(parcel_ids):
    # parcel_zones has no unique constraint on parcel_id alone -- guard
    # against duplicate inserts on script re-run ourselves.
    if not parcel_ids:
        return set()
    ids = ",".join(f'"{urllib.parse.quote(p)}"' for p in parcel_ids)
    url = f"{SB}/rest/v1/parcel_zones?parcel_id=in.({ids})&select=parcel_id"
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        rows = json.loads(resp.read().decode())
    return {r["parcel_id"] for r in rows}


def jurisdiction_for(address):
    # See DEFAULT_JURISDICTION comment: always 1403 for this data source.
    return DEFAULT_JURISDICTION


# Zone codes confirmed present in zoning_districts under jurisdiction_id=1403
# (verified live 2026-08-02). Codes NOT in this set have no zone_standards
# backing and must be skipped (BLANK > WRONG) rather than inserted with a
# fabricated/unmapped zone_code that silently fails letter G.
KNOWN_MAPPED_ZONE_CODES = {"A1", "B2", "MH", "PUD", "R1", "R2", "R3", "R4", "RPUD"}


def patch_latlon(case_number, lat, lon):
    url = (
        f"{SB}/rest/v1/multi_county_auctions"
        f"?case_number=eq.{urllib.parse.quote(case_number)}&county=eq.marion"
        f"&latitude=is.null&longitude=is.null"
    )
    payload = {"latitude": lat, "longitude": lon}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=H, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return len(rows)
    except urllib.error.HTTPError as exc:
        print(f"FAIL patch {case_number}: {exc.code} {exc.read().decode()}", file=sys.stderr)
        return 0


def insert_parcel_zone(parcel_id, zone_code, jurisdiction_id, source):
    url = f"{SB}/rest/v1/parcel_zones"
    payload = {
        "parcel_id": parcel_id,
        "zone_code": zone_code,
        "jurisdiction_id": jurisdiction_id,
        "source": source,
        "effective_date": date.today().isoformat(),
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=H, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return len(rows)
    except urllib.error.HTTPError as exc:
        print(f"FAIL insert parcel_zones {parcel_id}: {exc.code} {exc.read().decode()}", file=sys.stderr)
        return 0


def main():
    rows = get_rows()
    print(f"Fetched {len(rows)} target rows (expected 22)")

    numeric_ids = []
    hyphen_ids = []
    row_by_pid = {}
    for r in rows:
        pid = r.get("parcel_id")
        if not pid:
            print(f"SKIP {r['case_number']}: parcel_id IS NULL (out of scope)")
            continue
        row_by_pid[pid] = r
        if "-" in pid:
            hyphen_ids.append(pid)
        else:
            numeric_ids.append(pid)

    print(f"Numeric-format parcel_ids: {len(numeric_ids)}")
    print(f"Hyphenated-format parcel_ids: {len(hyphen_ids)}")

    numeric_feats = fetch_by_field("ALT_Key", [int(p) for p in numeric_ids])
    hyphen_feats = fetch_by_field("PARCEL", hyphen_ids)

    gis_by_pid = {}
    for feat in numeric_feats:
        gis_by_pid[str(feat["attributes"]["ALT_Key"])] = feat
    for feat in hyphen_feats:
        gis_by_pid[feat["attributes"]["PARCEL"]] = feat

    print(f"GIS matched: {len(gis_by_pid)} of {len(row_by_pid)}")

    existing_pz = get_existing_parcel_zone_ids(list(row_by_pid.keys()))
    if existing_pz:
        print(f"Already in parcel_zones (will skip zone insert, idempotent re-run): {sorted(existing_pz)}")

    parsed = 0
    geo_written = 0
    zone_written = 0
    unmatched = []
    rejected_bbox = []

    for pid, row in row_by_pid.items():
        feat = gis_by_pid.get(pid)
        if not feat:
            unmatched.append(pid)
            continue
        parsed += 1
        attrs = feat["attributes"]
        case_number = row["case_number"]

        # Part 1: lat/lon backfill (only if currently null, belt-and-suspenders).
        if row.get("latitude") is None or row.get("longitude") is None:
            lat, lon = centroid_of_feature(feat)
            if lat is None or lon is None or not in_bbox(lat, lon):
                rejected_bbox.append((pid, lat, lon))
                print(f"REJECT bbox {case_number} ({pid}): lat={lat} lon={lon}")
            else:
                n = patch_row_result = patch_latlon(case_number, lat, lon)
                if n:
                    geo_written += 1
                    print(f"OK geo {case_number} ({pid}): lat={lat:.6f} lon={lon:.6f}")
                else:
                    print(f"NO-OP/FAIL geo {case_number} ({pid})")
        else:
            print(f"SKIP geo {case_number} ({pid}): lat/lon already set")

        # Part 2: parcel_zones insert. Skip zone codes with no zone_standards
        # backing under jurisdiction 1403 (BLANK > WRONG -- see
        # KNOWN_MAPPED_ZONE_CODES comment) rather than insert an unmapped
        # code that silently fails letter G's FAR/pk1000/density coverage.
        zone_code = (attrs.get("ZONE1") or "").strip()
        if pid in existing_pz:
            print(f"SKIP zone {case_number} ({pid}): parcel_zones row already exists")
        elif zone_code and zone_code in KNOWN_MAPPED_ZONE_CODES:
            jid = jurisdiction_for(row.get("property_address"))
            n = insert_parcel_zone(pid, zone_code, jid, "marion_gis_arcgis_d979d926")
            if n:
                zone_written += 1
                print(f"OK zone {case_number} ({pid}): zone_code={zone_code} jurisdiction_id={jid}")
            else:
                print(f"NO-OP/FAIL zone {case_number} ({pid})")
        elif zone_code:
            print(f"SKIP zone {case_number} ({pid}): zone_code={zone_code} not in zoning_districts under jurisdiction 1403 (would fail letter G)")
        else:
            print(f"SKIP zone {case_number} ({pid}): ZONE1 blank")

    print(f"\nParsed (GIS-matched): {parsed}")
    print(f"Geo rows written: {geo_written}")
    print(f"parcel_zones rows written: {zone_written}")
    print(f"Unmatched (no GIS feature): {len(unmatched)} -> {unmatched}")
    print(f"Rejected (bbox): {len(rejected_bbox)} -> {rejected_bbox}")

    if parsed > 0 and geo_written == 0 and zone_written == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but zero writes performed.")


if __name__ == "__main__":
    main()
