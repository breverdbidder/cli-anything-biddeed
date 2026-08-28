#!/usr/bin/env python3
"""Gold Standard shard-3, dispatch 0c873526-996a-4f5d-9123-99836d1d585f (continuation),
county=bay, letter I. Session 2026-08-28.

DIAGNOSIS (replicated the exact I-formula from the live pencil_dod_evaluate_county
definition in supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_
cd_recognition.sql, lines 89-100 -- card_complete requires property_address NOT
NULL, COALESCE(latitude,po_latitude) NOT NULL, COALESCE(longitude,po_longitude)
NOT NULL, COALESCE(assessed_value,market_value) NOT NULL, AND parcel_id present
in v_zoning_gold_standard_card (parcel_id or tax_account match, zone_code NOT
NULL) -- i.e. a real parcel_zones linkage, not just a raw parcel_id string).

Live evaluator BEFORE (2026-08-28): card_complete=260 of 274, metric=94.9, FAIL
(need >=95% i.e. >=261/274).

Replicating the exact SQL in Python against a live PostgREST pull of all 274
scoped bay rows (WHERE lower(county)='bay' AND (data_source<>'propertyonion' OR
tier1_authoritative=true), matching auctions_total=274 exactly) plus the live
v_zoning_gold_standard_card for bay (261 zone_code-not-null rows, 260 distinct
parcel_ids + 93 distinct tax_accounts) found exactly 14 failing rows, broken
down by which field fails first:

  address (11): 25000412CA, 23001239CA, 26000161CA, 25001176CA, 25001126CA,
                24000347CA, 25000819CA, 25001129CA, 25000552CA, 25001131CA,
                23001288CA
  geo only (1):   26000070CC (has address, missing lat/long/parcel/value)
  zone_link (2): 25001135CA, 25000656CA (already have address/geo/value, only
                 missing a parcel_zones row)

RESEARCH (live fetches this session):
  1. bay.realforeclose.com AJAX PREVIEW calendar (index.cfm?zaction=AUCTION&
     Zmethod=PREVIEW&AUCTIONDATE=MM/DD/YYYY), same method as
     bay_gsd3_0c873526_i_fc_tail_ajax_backfill.py / shard2_bay_nassau_run
     14cdfac9_e_backfill.py. Fetched the 10 distinct auction dates for the 12
     address/geo-missing case numbers. Result:
       - 2 cases (25000412CA, 25001176CA) show Parcel ID anchor text literally
         "TIMESHARE" -- these are timeshare-interest foreclosures with no
         standard real-property parcel on the county's own PREVIEW card. This
         is the documented legitimate-exclusion pattern flagged in the task
         brief. Left NULL (not a data gap, a genuine non-parcel case type).
       - 5 cases (23001239CA, 26000161CA, 26000070CC, 25000819CA, 25001131CA)
         show Parcel ID anchor text literally "Property Appraiser" -- the
         documented fleet-wide RealForeclose parser-gap pattern (the county's
         own displayed record has no real parcel_id link, same as 23001288CA
         was in the PRIOR session before its auction date came into the
         PREVIEW-publish window). Left NULL (BLANK > WRONG, not fabricated).
       - 5 cases (25001126CA, 24000347CA, 25001129CA, 25000552CA, 23001288CA)
         NOW carry full real cards on the live PREVIEW calendar (parcel_id +
         property_address + assessed_value) that did not exist at the time of
         the prior session's script (23001288CA specifically was previously
         documented-blocked; its auction date has since moved into the
         PREVIEW-publish window and the county has since posted a real card).
  2. US Census geocoder (geocoding.geo.census.gov/geocoder/locations/
     onelineaddress, same proven method as shard14_bay_geocode_backfill.py) --
     all 5 newly-recovered addresses plus 26000070CC's existing address
     geocoded to an exact single unique match. Applied lat/long for the 5
     patchable rows.
  3. gis.baycountyfl.gov Land_Use_Planning MapServer/1 point-in-polygon zoning
     query (same proven method as bay_gsd3_0c873526_i_fc_tail_geo_zone.py /
     bay_gsd3_0c873526_i_td_tail_zonepoint.py) at each new centroid -- all 6
     parcels needing zone linkage (5 newly-addressed + 2 pre-existing
     zone_link-only rows) resolved to a single unambiguous ZONING code.
     JURISDICTION_ID map corroborated live via the jurisdictions table (same
     map as both prior scripts: 1=1332 Unincorporated, 2=983 Callaway,
     5=884 Panama City).

26000070CC ("263 NELLIE STREET, PANAMA CITY , FL- 32404") is a GENUINE DATA
CEILING, not fabricated and not left alone out of laziness: gis.baycountyfl.gov
TEST_Parcels/MapServer/1 (Bay County Property Appraiser's own parcel layer)
shows ~70 distinct condo/townhome units all sharing the exact street address
"263 NELLE ST" (note: county spells it NELLE, RealForeclose spells it NELLIE)
with different unit numbers and different real assessed values ($61,000 for
most units, $1,384,435 for one, $1 [placeholder] for a common-area parcel).
The RealForeclose PREVIEW card for this case gives no unit number, and the
county's own RE_LABEL (parcel_id) field is blank across all ~70 features in
this GIS layer -- a genuine upstream data-quality gap, not something scrapable
from any live source checked this session. Writing any single one of the 70
parcel_ids/assessed_values would be a fabrication (BLANK > WRONG). Left fully
NULL and documented here.

GUARDRAILS APPLIED:
  - Only NULL fields patched; zero overwrites of existing real data (checked
    live before every PATCH).
  - No PropertyOnion data used or referenced anywhere in this fix.
  - No values invented; every write traces to a live curl/fetch response
    captured in this session (see per-row comments below).
  - parcel_zones inserts only after confirming zero existing row for that
    (jurisdiction_id, parcel_id) pair (idempotent).

Usage: python3 scripts/bay_gsd3_0c873526_i_final_14row_gap_close.py
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ZONING_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1/query"
BUFFERS = (0.00005, 0.0001, 0.0002, 0.0004)
JURISDICTION_ID = {1: 1332, 2: 983, 3: 873, 4: 985, 5: 884, 6: 907}

# (mca_id, case_number, parcel_id, property_address, assessed_value, lat, lon)
# parcel_id/property_address/assessed_value: live bay.realforeclose.com AJAX
#   PREVIEW calendar, fetched this session (2026-08-28).
# lat/lon: US Census geocoder onelineaddress, exact single match, this session.
FIXES = [
    ("b1ea5dfb-dc3f-4f3e-9304-a5105cd486e1", "25001126CA", "30167-296-000",
     "806 WHITE OAK CT, PANAMA CITY BEACH, FL- 32408", 335324.0,
     30.165621146636, -85.770716733413),
    ("972d5151-9f57-4f55-a0e9-5dc793d0e701", "24000347CA", "05227-002-000",
     "5930 PITTI LN, YOUNGSTOWN, FL- 32466", 64662.0,
     30.333390221306, -85.552739894253),
    ("b8c45663-95a0-4225-8f83-c40fcf47a0fd", "25001129CA", "32053-000-000",
     "5701 SOUTH LAGOON DR, PANAMA CITY BEACH, FL- 32408", 431073.0,
     30.149304292159, -85.756195086377),
    ("ddbde9e2-a60f-4173-94a1-1cfd354b4c07", "25000552CA", "30167-928-000",
     "2117 BENT OAK CT, PANAMA CITY BEACH, FL- 32408", 120869.0,
     30.166408447816, -85.760793733298),
    ("bad06dfc-9ad4-4013-9cea-319da6972d95", "23001288CA", "16885-000-000",
     "1202 LOUISIANA AVE, PANAMA CITY, FL- 32401", 146363.0,
     30.169723964396, -85.651240922614),
]

# Rows that already had real address/geo/value; only need zone linkage
# (mca_id, case_number, parcel_id, lat, lon) -- lat/lon read live from DB, not
# re-fetched.
ZONE_ONLY = [
    ("b850caf0-96f1-4c80-b2ea-2206337b6a97", "25001135CA", "12989-078-000",
     30.196311, -85.66614),
    ("678ad39d-e9ac-499b-a8b1-16497894fe34", "25000656CA", "06513-213-000",
     30.148999, -85.560388),
]

# TIMESHARE placeholder cases -- RealForeclose's own PREVIEW card carries
# Parcel ID anchor text literally "TIMESHARE" (no standard real-property
# parcel exists for a timeshare-interest foreclosure). Legitimate exclusion,
# not a data gap. parcel_id='TIMESHARE' was already present pre-session for
# 25001176CA; 25000412CA had no parcel_id at all -- confirmed live this
# session and intentionally left NULL for both (no address/geo/value exists
# on the county's own record either).
TIMESHARE_BLOCKED = {
    "6a0458de-7340-4623-b453-31a7692054ea":
        "25000412CA: live RealForeclose PREVIEW calendar (2026-03-24) Parcel "
        "ID anchor text = 'TIMESHARE' -- timeshare-interest foreclosure, no "
        "standard parcel exists. Left NULL (legitimate exclusion, not gap).",
    "31903804-2fa3-4507-bdd1-c9b856766a5c":
        "25001176CA: live RealForeclose PREVIEW calendar (2026-07-30) Parcel "
        "ID anchor text = 'TIMESHARE'. Same as above. Left NULL.",
}

# RealForeclose parser-gap cases -- Parcel ID anchor text literally "Property
# Appraiser" (the county's own PREVIEW card carries no real parcel link).
# Documented fleet-wide pattern (see bay_gsd3_0c873526_i_fc_tail_ajax_
# backfill.py for the prior instance, 23001288CA, which has since resolved
# itself as the auction date moved into the publish window -- see FIXES
# above). These 5 remain unresolved as of this session; left NULL.
PARSER_GAP_BLOCKED = {
    "be86e9d3-3a95-4521-baf0-b463a7416e28":
        "23001239CA: live PREVIEW calendar (2026-05-26) Parcel ID anchor "
        "text = 'Property Appraiser'. No real parcel/address/value on the "
        "county's own record. Left NULL.",
    "9d89d9e2-4951-42f9-9f30-9f3269701657":
        "26000161CA: live PREVIEW calendar (2026-07-30) Parcel ID anchor "
        "text = 'Property Appraiser'. Left NULL.",
    "6ec87d0d-5df7-4ffe-8286-50f3dd379361":
        "25000819CA: live PREVIEW calendar (2026-09-29) Parcel ID anchor "
        "text = 'Property Appraiser'. Left NULL.",
    "d57f5ca4-fae8-4455-a2e6-640ec3fb5abb":
        "25001131CA: live PREVIEW calendar (2026-10-05) Parcel ID anchor "
        "text = 'Property Appraiser'. Left NULL.",
}

# 26000070CC: genuine data ceiling. See module docstring for full evidence.
# gis.baycountyfl.gov TEST_Parcels/MapServer/1 (BCPAO's own parcel layer)
# shows ~70 distinct condo units all sharing the identical street address
# "263 NELLE ST" (RealForeclose spells it "263 NELLIE STREET") with no unit
# number on the RealForeclose card and a blank RE_LABEL (parcel_id) field
# across every one of the ~70 GIS features. No live source checked this
# session disambiguates which unit this case pertains to. Left fully NULL
# (parcel_id, assessed_value, latitude, longitude all remain NULL --
# geocoding only the street-level building would not satisfy the I formula
# and would misleadingly imply unit-level precision that doesn't exist).
AMBIGUOUS_BLOCKED = {
    "f0f64424-045e-49bf-8aaf-af08f6b625da":
        "26000070CC: 263 NELLIE STREET / 263 NELLE ST resolves to ~70 "
        "distinct condo/townhome parcels in gis.baycountyfl.gov TEST_Parcels "
        "(BCPAO parcel layer) with no unit number on the RealForeclose "
        "PREVIEW card and blank RE_LABEL across all ~70 GIS features. "
        "Genuine unresolvable ambiguity -- left NULL, not fabricated.",
}


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def lookup_zoning_by_point(lat, lon):
    for buf in BUFFERS:
        time.sleep(1.0)
        env = f"{lon - buf},{lat - buf},{lon + buf},{lat + buf}"
        params = {
            "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "ZONING,SUB_ZONING,Label",
            "returnGeometry": "false", "f": "json",
        }
        req = urllib.request.Request(f"{ZONING_URL}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        feats = data.get("features", [])
        if not feats:
            continue
        codes = {f["attributes"].get("ZONING") for f in feats}
        subs = {f["attributes"].get("SUB_ZONING") for f in feats}
        label = next(iter({f["attributes"].get("Label") for f in feats}))
        if len(codes) != 1:
            return None, None, len(codes), label
        zone_code = next(iter(codes))
        jur_id = JURISDICTION_ID.get(next(iter(subs))) if len(subs) == 1 else None
        return zone_code, jur_id, 1, label
    return None, None, 0, None


def zone_link(pid, lat, lon, cn):
    zone_code, jur_id, n, label = lookup_zoning_by_point(lat, lon)
    if n != 1 or not zone_code or not jur_id:
        print(f"    {cn} zoning: SKIP n={n} zone_code={zone_code} jur_id={jur_id} label={label} -- left alone (BLANK>WRONG)")
        return False
    existing = rest_get(f"parcel_zones?jurisdiction_id=eq.{jur_id}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
    if existing:
        print(f"    {cn} zoning: parcel_zones row already exists, skip insert")
        return True
    rest_post("parcel_zones", {
        "jurisdiction_id": jur_id, "parcel_id": pid, "zone_code": zone_code,
        "zone_name": label,
        "source": "gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, "
                   "gold-standard-shard3 dispatch 0c873526 continuation, bay I 14-row gap close)",
    })
    print(f"    {cn} zoning: zoned {zone_code} (jur={jur_id}, label={label})")
    return True


def main():
    patched = 0
    zoned = 0

    print("=== FIXES: address+value+geo backfill, then zone linkage ===")
    for mca_id, cn, parcel_id, addr, val, lat, lon in FIXES:
        existing = rest_get(f"multi_county_auctions?id=eq.{mca_id}&select=parcel_id,property_address,assessed_value,latitude,longitude")
        if not existing:
            print(f"  {cn}: row not found, skip")
            continue
        row = existing[0]
        body = {}
        if not row.get("parcel_id"):
            body["parcel_id"] = parcel_id
        if not row.get("property_address"):
            body["property_address"] = addr
        if not row.get("assessed_value"):
            body["assessed_value"] = val
        if row.get("latitude") is None:
            body["latitude"] = lat
        if row.get("longitude") is None:
            body["longitude"] = lon
        if body:
            result = rest_patch(f"multi_county_auctions?id=eq.{mca_id}", body)
            if not result:
                raise RuntimeError(f"PATCH returned 0 rows for {cn} -- fail-loud, not silent no-op")
            patched += 1
            print(f"  PATCHED {cn}: {json.dumps(body)}")
        else:
            print(f"  {cn}: already complete, skip field patch")

        if zone_link(parcel_id, lat, lon, cn):
            zoned += 1

    print("\n=== ZONE_ONLY: rows with full address/geo/value, missing zone linkage ===")
    for mca_id, cn, parcel_id, lat, lon in ZONE_ONLY:
        if zone_link(parcel_id, lat, lon, cn):
            zoned += 1

    print(f"\nTOTAL field-patched: {patched} of {len(FIXES)}")
    print(f"TOTAL zone-linked: {zoned} of {len(FIXES) + len(ZONE_ONLY)}")

    all_blocked = {**TIMESHARE_BLOCKED, **PARSER_GAP_BLOCKED, **AMBIGUOUS_BLOCKED}
    print(f"\nBLOCKED (evidence, no fabrication): {len(all_blocked)} rows")
    for row_id, reason in all_blocked.items():
        print(f"  {row_id}: {reason}")

    if patched == 0 and zoned == 0:
        raise RuntimeError("Fail-loud: expected work but 0 rows patched and 0 zoned")


if __name__ == "__main__":
    main()
