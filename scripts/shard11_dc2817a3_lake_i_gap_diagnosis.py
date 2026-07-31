#!/usr/bin/env python3
"""
Shard-11 (dispatch dc2817a3): Lake county criterion-I (property card completeness)
gap diagnosis + honest-ceiling report. READ-ONLY EVIDENCE LOG — no matching logic,
no writes performed by this file. All writes attempted this session were done via
the PRE-EXISTING, already-live scripts/shard7_run3679_lake_i_real_zoning_backfill.py
(re-run fresh, unmodified) exactly as instructed.

FRESH BASELINE (pencil_dod_evaluate_county('lake'), fetched live at session start):
  I.metric=62.4%, card_complete=68 of 109
  E.metric=73.4%, parcel_linked=80

EXACT FORMULA (from live migration
supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql,
lines 94-151):
  card_rows  = count(*) FROM multi_county_auctions WHERE county=lake AND
               (data_source <> 'propertyonion' OR tier1_authoritative)   -> 109 rows (all of scope)
  card_complete = count(*) FILTER WHERE
               property_address IS NOT NULL
               AND COALESCE(latitude, po_latitude) IS NOT NULL
               AND COALESCE(longitude, po_longitude) IS NOT NULL
               AND COALESCE(assessed_value, market_value) IS NOT NULL
               AND parcel_id resolves to a v_zoning_gold_standard_card row (county=lake,
                   zone_code IS NOT NULL) via parcel_id OR tax_account match

INDEPENDENT REPLICATION (this session, via REST):
  Fetched all 109 in-scope multi_county_auctions rows (address/geo/value/parcel_id/
  data_source/tier1_authoritative) + all 67 v_zoning_gold_standard_card rows for
  county=lake with zone_code IS NOT NULL (parcel_id, tax_account).
  Computed card_complete locally: 68 of 109 -- EXACT MATCH to the live RPC, confirming
  the diagnosis logic below is correct.

  Breakdown of the 41 incomplete rows:
    - 29 rows: parcel_id IS NULL (missing address+geo+value+zone all at once). These
      are the SAME 29 unlinked rows the parallel E-task (this session) already
      diagnosed as a confirmed real ceiling (0/29 resolve to a unique ArcGIS OwnerName
      match). Out of scope for I until E moves; not re-attempted here per "don't
      duplicate another task's already-diagnosed ceiling" discipline.
    - 12 rows: parcel_id present, address+geo+value ALL already populated, ONLY
      "zone" missing (no matching parcel_zones row with a real zone_code for that
      parcel_id/jurisdiction). THIS is the genuine I-specific gap attacked this
      session. Case numbers: 2025CA001608, 2022CA001313, 2025CA002672, 2025CA002732,
      2023CA002430, 2025CA002707, 2020CA001954, 2025CA002532, 2025CA000481,
      2025CA002647, 2025CC004659, 2025CA000634.

ACTION TAKEN ON THE 12-ROW ZONE GAP:
  1. Re-ran scripts/shard7_run3679_lake_i_real_zoning_backfill.py fresh (unmodified),
     which point-in-polygon queries ALL 80 parcel-linked lake rows (not just these 12)
     against Lake County's own unincorporated-zoning layer
     (gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50).
     Result: arcgis_hit=38 (all "already_correct", 0 new inserts/updates -- this
     layer's coverage was already fully applied in a prior session), arcgis_miss=42
     (points fall inside incorporated municipal boundaries, which this
     unincorporated-only layer never covers -- by the script's own documented design,
     not a bug). All 12 of my gap parcels are inside this 42-row miss bucket.
  2. Point-in-polygon check against Lake County GIS "City Limits In" layer
     (InteractiveMap/MapServer/26) to identify which municipality each of the 12
     falls in: 8x EUSTIS, 2x CLERMONT, 1x LEESBURG, 1x EUSTIS (confirmed 9 Eustis +
     2 Clermont + 1 Leesburg = 12).
  3. Searched for and found a real, live, additional Lake County GIS service that
     compiles SEVERAL (not all) incorporated-city zoning layers:
     gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer
     Layers present: Astatula(0), Clermont(1), Fruitland Park(2), Groveland(3),
     Mount Dora(4), Tavares(5), Umatilla(6), Mascotte(7), Minneola(8),
     Howey-in-the-Hills(9), Montverde(10). NO Eustis layer, NO Leesburg layer in this
     service -- confirmed via live MapServer?f=json layer listing, not assumed.
  4. Queried CityZoning/MapServer/1 (Clermont) live for the 2 Clermont-city-limits
     candidate points (082326050200001800 @ 28.510456,-81.727966 and
     062326040000001800 @ 28.516863,-81.746841): both returned empty features[]
     (zero polygon coverage at those exact coordinates). Sanity-checked the query
     mechanism itself against a known-good Clermont City Hall coordinate
     (28.5494,-81.7729) on the SAME layer -- got a real hit
     ("R-1 SINGLE FAMILY MEDIUM DENSITY RESIDENTIAL DISTRICT"), proving the miss on
     the 2 target parcels is a genuine coverage gap in Lake County's Clermont zoning
     polygon dataset (edge-of-city / recently-annexed parcels likely not yet
     digitized), not a malformed request.
  5. Searched for Eustis- and Leesburg-specific ArcGIS REST endpoints
     (map.leesburgflorida.gov/arcgis/rest/services/CommunityDevelopment/
     Planning_and_Zoning/MapServer -- found via web search, real published URL).
     Attempted live connection 3x (default UA, Mozilla UA, HTTP/1.1 forced): all 3
     failed at the TCP/TLS layer ("Connection reset by peer" / curl exit 000,
     0-byte response) from this sandbox's network egress -- NOT a 404 or auth wall,
     a network-level connectivity failure to that specific host. Other Lake-area
     hosts (gis.lakecountyfl.gov, www.eustis.org) resolve and respond normally from
     the same sandbox in the same session, so this is host-specific, not a general
     outbound block.
  6. Checked Eustis's own published GIS entry point (eustis.org Planning page) --
     it links only to the same Lake County ArcGIS Web AppBuilder viewer built on top
     of the CityZoning/CityFLU services already queried above (no independent Eustis
     zoning REST endpoint discoverable). Checked LocalGov/CityFLU (Future Land Use,
     confirmed live via service metadata) -- explicitly NOT used to fill zone_code:
     FLU and zoning are different regulatory fields: writing an FLU code into
     zone_code would be a category-mismatch fabrication and was not done.

HONEST CONCLUSION: the 12-row zone gap is a real, current ceiling for county=lake
under the "no fabrication" constraint:
  - 9 parcels (8 confirmed Eustis + 1 further Eustis) sit in a municipality with no
    reachable live zoning GIS REST endpoint from this environment.
  - 1 parcel sits in Leesburg, whose real, published ArcGIS REST service exists but
    is unreachable from this sandbox (network-level connection reset, verified 3x).
  - 2 parcels sit in Clermont, whose zoning layer IS reachable and IS queried
    correctly (proven via a known-good sanity point), but has no polygon covering
    these 2 exact parcel coordinates.
No zone_code was written for any of the 12. No parcel_zones row was inserted or
updated as a result of this diagnosis (the one live write attempt, via the
pre-existing backfill script, produced 0 inserts/0 updates/38 already-correct/42
honest misses, matching its own documented behavior).

VERIFICATION: pencil_dod_evaluate_county('lake') re-fetched fresh immediately after
all of the above: I.metric=62.4%, card_complete=68 of 109 -- byte-identical to the
pre-session baseline, confirming zero DB writes landed and the reported 62.4% is the
honest, verified live ceiling for this session under the given data-source
constraints.
"""

DIAGNOSIS = {
    "county": "lake",
    "letter": "I",
    "baseline_metric": 62.4,
    "baseline_detail": "card_complete=68 of 109",
    "post_session_metric": 62.4,
    "post_session_detail": "card_complete=68 of 109",
    "gap_rows_total": 41,
    "gap_rows_unlinked_parcel_null": 29,  # owned by parallel E task this session, confirmed ceiling
    "gap_rows_zone_missing_only": 12,
    "zone_gap_case_numbers": [
        "2025CA001608", "2022CA001313", "2025CA002672", "2025CA002732",
        "2023CA002430", "2025CA002707", "2020CA001954", "2025CA002532",
        "2025CA000481", "2025CA002647", "2025CC004659", "2025CA000634",
    ],
    "zone_gap_municipalities": {
        "eustis": 9,
        "clermont": 2,
        "leesburg": 1,
    },
    "sources_attempted": [
        "gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50 (unincorporated zoning) -- all 12 fall outside coverage by design (municipal land)",
        "gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityZoning/MapServer (multi-city compilation) -- no Eustis/Leesburg layer; Clermont layer live but empty at these 2 exact points (sanity-checked against known-good Clermont point, real hit confirmed)",
        "map.leesburgflorida.gov/arcgis/rest/services/CommunityDevelopment/Planning_and_Zoning/MapServer -- real published endpoint, unreachable from sandbox (TCP/TLS connection reset, 3 attempts)",
        "eustis.org Planning page + LocalGov/CityFLU -- no independent Eustis zoning REST endpoint found; CityFLU is Future Land Use (different field), not used to avoid category-mismatch fabrication",
    ],
    "writes_performed": 0,
    "fabrication": False,
}

if __name__ == "__main__":
    import json
    print(json.dumps(DIAGNOSIS, indent=2))
