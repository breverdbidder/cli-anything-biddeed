#!/usr/bin/env python3
"""Gold Standard, county=santa_rosa, letter I (property card completeness).

DIAGNOSIS (live, this session, 2026-08-28):
  pencil_dod_evaluate_county('santa_rosa') baseline: I FAIL, card_complete=115 of 124,
  metric=92.7 (need >=95% i.e. >=118 of 124).

  Evaluator scope (verified against supabase/migrations/
  20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql, the current live
  definition of public.pencil_dod_evaluate_county):
    auctions_total = rows WHERE lower(county)='santa_rosa' AND
      (data_source <> 'propertyonion' OR tier1_authoritative = true)   -- 124 rows
    card_complete additionally requires property_address, latitude/longitude
    (or po_latitude/po_longitude), assessed_value (or market_value) ALL non-null,
    AND parcel_id present with a real zone_code match in
    v_zoning_gold_standard_card (county='santa rosa', note: SPACE not underscore
    in that view).

  Reconciled the exact 9-row gap (119 rows pass address+geo+value, minus 4 that
  fail zone-linkage = 115):

  (A) 5 rows failing on basic fields (address/geo/value):
    - 572022CA000671CAAXMX: property_address/parcel_id/assessed_value/lat/lon ALL NULL.
    - 572025CA000043CAAXMX, 572025CA000445CAAXMX: property_address is the placeholder
      string "Santa Rosa County FL (address pending)", parcel_id NULL,
      assessed_value=150000, lat/lon=30.6736/-87.0244 -- CONFIRMED this exact
      lat/lon/150000 combo is a documented, PRE-EXISTING fleet-wide generic
      county-centroid + "conservative FL average" placeholder pair, applied by
      migrations/20260619_shard5_i_card_fix.sql (CASE WHEN 'santa_rosa' THEN 30.6736
      / -87.0244, and COALESCE(NULLIF(po_market_value,0), 150000)), NOT this
      session's data and NOT real per-parcel values -- do not treat as ground truth,
      do not overwrite with a guess either.
    - 572025CA000489CAAXMX, 572025CA000604CAAXMX, 572025CA000900CAAXMX,
      572026CA000181CAAXMX: real property_address + parcel_id + assessed_value
      already present, ONLY latitude/longitude NULL.

  (B) 4 rows passing basic fields but failing zone-linkage (parcel_id not matched
      to a non-null zone_code in v_zoning_gold_standard_card):
    - 2026033 (parcel 41-5N-29-0000-04100-0000) -- address/geo/value already real
      (lat 30.9523086744775 / lon -87.1521537633799, NOT the placeholder pair).
    - 572025CA000567CAAXMX (parcel 30-2N-29-0403-00C00-0080) -- address/geo/value
      already real (lat 30.654139 / lon -87.184069, matches live GIS centroid to
      6 decimal places -- already accurate, not the placeholder).
    - 572025CA000043CAAXMX, 572025CA000445CAAXMX (see A above -- also NULL parcel_id
      so also fail zone-linkage).

METHOD (this script -- fixes group A's 4 lat/long-only rows ONLY):
  Santa Rosa County Property Appraiser (SRCPA) authoritative parcel GIS layer:
    https://services.arcgis.com/Eg4L1xEv2R3abuQd/ArcGIS/rest/services/ParcelsOpenData/FeatureServer/0
  Discovered live via web search (org id Eg4L1xEv2R3abuQd, service "ParcelsOpenData",
  serviceDescription "Parcels for Open Data, updated 7/22/2026"). Field PAR_NUM is
  the county STRAP with all dashes stripped (verified: our parcel_id
  "32-2N-28-2864-00A00-0340" -> dashes stripped -> "322N28286400A000340" -> exact
  hit, StrNum/StrName/City = "5998 RIDGEVIEW DR" / "MILTON", matching our existing
  DB property_address "5998 RIDGEVIEW DR, MILTON, FL- 32570" exactly).
  Query: WHERE PAR_NUM='<parcel_id with dashes stripped>', returnCentroid=true,
  outSR=4326 (WGS84 lat/lon) -- this is the parcel-specific centroid from the
  county's own authoritative cadastral layer, NOT a generic geocoder guess.
  All 4 target parcels matched exactly with address fields corroborating the
  existing DB property_address (street number + name + city all agree).

NOT FIXED / LEFT AS-IS (documented, not silently dropped):
  - 572022CA000671CAAXMX, 572025CA000043CAAXMX: live santarosa.realforeclose.com
    AJAX preview calendar (harvested this session for auction_date 2026-07-16 and
    2026-03-11 respectively) shows the county's OWN system displays
    Parcel ID: "MULTIPLE PARCELS" (verified in raw AJAX HTML: anchor
    href="http://srcpa.gov/Parcel/Index2?parcel=MULTIPLE PARCELS") -- this is a
    genuine multi-parcel foreclosure case with no single canonical parcel/address
    in the source system itself. Not extractable without inventing a "primary"
    parcel from a multi-parcel legal instrument, which would be a fabrication.
    Left NULL (BLANK > WRONG).
  - 572025CA000445CAAXMX: live AJAX preview for auction_date 2026-03-24 shows
    Parcel ID anchor href="http://srcpa.gov/Parcel/Index2?parcel=" (empty) with
    anchor text literally "Property Appraiser" -- the documented fleet-wide
    parser-gap pattern (same as bay case 23001288CA, see
    scripts/bay_gsd3_0c873526_i_fc_tail_ajax_backfill.py). The county's own page
    has no real Parcel ID for this case. Left NULL.
  - 2026033, 572025CA000567CAAXMX: property_address/parcel_id/assessed_value/
    lat/lon are ALL already real and correct (verified against SRCPA GIS
    centroid for 572025CA000567CAAXMX: DB lat/lon 30.654139/-87.184069 vs live
    GIS centroid 30.654139249778126/-87.18406878765782 -- match to 6 decimals).
    Their card-completeness failure is SOLELY zone-linkage: parcel_id has no
    matching non-null zone_code row in v_zoning_gold_standard_card. Fixing this
    requires spatial point-in-polygon zoning-district ingestion against the
    county's Zoning FeatureServer (https://services.arcgis.com/Eg4L1xEv2R3abuQd/
    ArcGIS/rest/services/Zoning/FeatureServer, a polygon-only layer with no
    PAR_NUM field) followed by insertion into zoning_districts/zoning_assignments
    -- out of scope for a multi_county_auctions field backfill and requires the
    established ordinance-sourcing methodology used elsewhere in the gold-standard
    campaign. Genuine data ceiling for THIS script; not touched, not fabricated.

Only patches fields that are currently NULL (idempotent, no overwrite of existing
real data). Does not touch parity_status, zoning tables, or the evaluator function.

Usage: python3 scripts/santa_rosa_i_gsd_srcpa_gis_centroid_geo_backfill.py
"""
import json
import os
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

SRCPA_PARCELS_URL = (
    "https://services.arcgis.com/Eg4L1xEv2R3abuQd/ArcGIS/rest/services/"
    "ParcelsOpenData/FeatureServer/0/query"
)

# (mca_id, case_number, parcel_id) -- rows with real address/parcel_id/assessed_value
# already present, only latitude/longitude missing. Centroid fetched live from SRCPA
# ParcelsOpenData FeatureServer (PAR_NUM = parcel_id with dashes stripped).
TARGETS = [
    ("98ae4820-7cb7-4d5a-977e-8f4f1f3ea638", "572025CA000489CAAXMX", "32-2N-28-2864-00A00-0340"),
    ("2b5de657-7678-4359-8613-9b8fc88beaf5", "572025CA000604CAAXMX", "09-2S-26-5515-00400-0010"),
    ("4ceed4fa-4363-40d7-a3eb-1afe0bc15795", "572025CA000900CAAXMX", "19-1N-28-0110-00000-1642"),
    ("9e34d71e-529f-4fcc-808f-9f308c3f6ae7", "572026CA000181CAAXMX", "43-1N-28-3397-00C00-0220"),
]

BLOCKED = {
    "572022CA000671CAAXMX":
        "Live santarosa.realforeclose.com AJAX preview (auction_date 2026-07-16) shows "
        "county's own Parcel ID field = 'MULTIPLE PARCELS' (href=...?parcel=MULTIPLE PARCELS). "
        "Genuine multi-parcel case, no single canonical parcel/address in source. Left NULL.",
    "572025CA000043CAAXMX":
        "Live santarosa.realforeclose.com AJAX preview (auction_date 2026-03-11) shows "
        "county's own Parcel ID field = 'MULTIPLE PARCELS'. Same pattern as above. "
        "Pre-existing placeholder address/value/geo (fleet-wide 30.6736/-87.0244 + 150000 "
        "pattern from migrations/20260619_shard5_i_card_fix.sql) left untouched -- not "
        "real data, but not overwritten with a guess either. Left NULL parcel_id.",
    "572025CA000445CAAXMX":
        "Live santarosa.realforeclose.com AJAX preview (auction_date 2026-03-24) shows "
        "county's own Parcel ID anchor href='...?parcel=' (empty), anchor text literally "
        "'Property Appraiser' -- documented fleet-wide parser-gap pattern (same as bay "
        "case 23001288CA). County's own page has no real parcel_id for this case. Left NULL.",
    "2026033":
        "Address/parcel_id/assessed_value/lat/lon all already real and correct. Card-"
        "completeness failure is solely zone-linkage (parcel_id 41-5N-29-0000-04100-0000 "
        "has no zone_code match in v_zoning_gold_standard_card) -- requires spatial "
        "zoning-district ingestion, out of scope for this mca-field backfill. Not touched.",
    "572025CA000567CAAXMX":
        "Address/parcel_id/assessed_value/lat/lon all already real and correct (lat/lon "
        "verified against live SRCPA GIS centroid to 6 decimal places). Card-completeness "
        "failure is solely zone-linkage (parcel_id 30-2N-29-0403-00C00-0080 has no zone_code "
        "match in v_zoning_gold_standard_card) -- out of scope for this mca-field backfill. "
        "Not touched.",
}


def srcpa_centroid(parcel_id):
    """Query SRCPA ParcelsOpenData FeatureServer for the parcel-specific centroid
    (WGS84 lat/lon), returned via returnCentroid=true, outSR=4326."""
    par_num = parcel_id.replace("-", "")
    params = {
        "where": f"PAR_NUM='{par_num}'",
        "outFields": "PAR_NUM,StrNum,StrName,StSuffix,City",
        "returnCentroid": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{SRCPA_PARCELS_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features", [])
    if not feats:
        return None
    f = feats[0]
    c = f.get("centroid")
    if not c:
        return None
    return {
        "lat": c["y"],
        "lon": c["x"],
        "addr": f"{f['attributes'].get('StrNum','').strip()} {f['attributes'].get('StrName','').strip()} {f['attributes'].get('StSuffix','').strip()}".strip(),
        "city": f["attributes"].get("City", "").strip(),
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


def main():
    patched = 0
    for mca_id, cn, parcel_id in TARGETS:
        existing = rest_get(f"multi_county_auctions?id=eq.{mca_id}&select=latitude,longitude,property_address")
        if not existing:
            print(f"  {cn}: row not found, skip")
            continue
        row = existing[0]
        if row.get("latitude") is not None and row.get("longitude") is not None:
            print(f"  {cn}: lat/lon already set, skip (idempotent)")
            continue

        centroid = srcpa_centroid(parcel_id)
        if not centroid:
            print(f"  {cn}: NO SRCPA GIS match for parcel {parcel_id} -- leaving NULL, not fabricating")
            continue

        # Sanity check: the GIS street number/name should appear in the existing
        # DB address (independent corroboration before trusting the centroid).
        db_addr = (row.get("property_address") or "").upper()
        gis_addr = centroid["addr"].upper()
        if gis_addr and gis_addr.split(" ")[0] not in db_addr:
            print(f"  {cn}: GIS address '{centroid['addr']}' does not corroborate DB "
                  f"address '{row.get('property_address')}' -- skipping to avoid mismatch, not fabricating")
            continue

        body = {"latitude": centroid["lat"], "longitude": centroid["lon"]}
        result = rest_patch(f"multi_county_auctions?id=eq.{mca_id}", body)
        if not result:
            raise RuntimeError(f"PATCH returned 0 rows for {cn} -- fail-loud, not silent no-op")
        patched += 1
        print(f"  PATCHED {cn}: lat={centroid['lat']} lon={centroid['lon']} "
              f"(SRCPA GIS parcel centroid, corroborated by address '{centroid['addr']} {centroid['city']}')")

    print(f"\nTOTAL PATCHED: {patched} of {len(TARGETS)}")
    print(f"\nBLOCKED / OUT-OF-SCOPE (evidence, no fabrication): {len(BLOCKED)} rows")
    for cn, reason in BLOCKED.items():
        print(f"  {cn}: {reason}")
    if patched == 0:
        raise RuntimeError("Fail-loud: TARGETS was non-empty but 0 rows patched")


if __name__ == "__main__":
    main()
