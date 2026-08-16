#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch 6a9e3c3a): Brevard county, letter I
(property card completeness) -- investigation of the NEW lever named in this
dispatch: the SRID-corruption repair landed in commit d204c897
("fix: critical SRID corruption in backfill_geom_fdor.py + repair 182,726
rows"). That commit fixed scripts/backfill_geom_fdor.py, which backfills
zw_parcels.geom/centroid_lat/centroid_lon from the FDOR Statewide Cadastral
FeatureServer, keyed by zw_parcels.pin + co_no.

THIS IS A CONFIRMED DEAD END FOR BREVARD. Zero rows written this session.

Live evidence (2026-08-16, via PostgREST against $SUPABASE_URL):

1. zw_parcels (the table the SRID fix actually repaired) has co_no=5
   (Brevard) rows at all -- but only 82 of them, and EVERY ONE has
   geom IS NULL:
     curl "$SUPABASE_URL/rest/v1/zw_parcels?select=pin&co_no=eq.5" -> 82 rows
     curl "...&co_no=eq.5&geom=not.is.null" -> 0 rows
   Brevard (co_no=5) is NOT in backfill_geom_fdor.py's TARGET_COUNTIES list
   (see script) -- it was never in scope for the SRID-corrupted run OR its
   repair. The repair commit touched 11 specific counties (Pasco, Columbia,
   Washington, DeSoto, Dixie, Jefferson, Calhoun, Lafayette, Walton,
   Sarasota, Jackson) -- Brevard was never among them, corrupted or not.
   Conclusion: the exact lever named in the dispatch (repaired zw_parcels
   geometry) does not exist for Brevard. This is a hard, verifiable no-op --
   not a "maybe/rerun a different way" residual.

2. Checked every other geometry-bearing table reachable via PostgREST for a
   Brevard join, in case a *different* geometry table (not zw_parcels) could
   serve the same purpose:
     - fl_parcels (10.5M rows, keyed by co_no): 0 rows for co_no=5 (Brevard
       absent from this table entirely).
     - fl_parcel_centroid_progress: no co_no=5 row at all (Brevard was never
       run through this pipeline).
     - parcel_zones: no geometry column (zone_code/jurisdiction linkage
       table only, keyed by tax_account -- already exhausted by prior
       sessions' address lookups, not a new lever).
     - parcels (332,774 rows, ATTOM-style, keyed by apn): DOES have 4,525
       Brevard rows (county_name='brevard'/'Brevard' -- mixed casing found
       live), 3,766 of which have non-null latitude/longitude. This looked
       promising and was investigated in depth (step 3 below) -- ultimately
       also a dead end, for a DIFFERENT reason (provenance, not absence).

3. Reconstructed the exact I-gate denominator/gap live using the identical
   MCA_FILTER string from scripts/brevard_i_card_complete_shard1_3ce988ac.py
   (reused verbatim, not re-derived):
     county=eq.brevard&or=(data_source.is.null,data_source.neq.propertyonion,
     tier1_authoritative.eq.true)
   Live counts (2026-08-16):
     total in scope:            7252  (matches evaluator auctions_total)
     property_address IS NULL:  1033
     lat/lng missing (BOTH latitude AND po_latitude NULL): 112
     value missing (BOTH assessed_value AND market_value NULL): 62
     parcel_id IS NULL:          58
   card_complete=6202/7252 (85.5%) per the live evaluator run below.
   NOTE: the geo-missing bucket has shrunk to 112 from the 1751 reported in
   the 3ce988ac session report -- most of that prior gap has since been
   closed by other work (the address-missing GIS backfill also writes
   lat/lng as a side effect -- see build_update() in the 3ce988ac script).

   Of the 112 geo-missing rows, only 56 (54 distinct parcel_id values) also
   have a parcel_id at all -- the other 56 fail on parcel_id IS NULL too and
   would need a parcel-linkage fix first, out of scope for a geometry-only
   lever. These 54 distinct numeric TaxAcct-format parcel_ids are the
   candidate set for any centroid backfill.

4. Tested the `parcels` table (step 2's promising candidate) against all 54
   candidate parcel_ids via `apn=in.(...)`:
     23 of 54 matched a `parcels.apn` row at all
     22 of those 23 have non-null latitude/longitude
   Sample-verified 20+ of these before considering any write, per the task's
   instruction to test on a sample before bulk action. Findings that KILL
   this as a usable source:
     - EVERY one of the 22 matched rows carries `honesty_marker='INFERRED'`
       (this repo's own fabrication-risk tag, per HONESTY PROTOCOL in
       CLAUDE.md) with `geocode_source=NULL`, `scraped_at=NULL`,
       `source_url=NULL`, `address_line_1=NULL`. There is no cited source
       for these coordinates -- they are themselves an unverified guess
       already sitting in `parcels`, not a scrape from BCPAO/Brevard-GIS/
       FDOR. Compare to the OTHER ~4,500 Brevard `parcels` rows sampled
       (non-targeted), which are ~80% `geocode_source='fl_parcels_centroid'`
       and `honesty_marker='UNTESTED'` -- i.e. a real (if unverified-by-us)
       provenance chain. Our 22 candidates specifically are the exception:
       zero provenance, explicit INFERRED tag.
     - Cross-checked apn=2313502 (case_number 211090, a $630-assessed-value
       tax-deed row) directly against the live Brevard GIS ArcGIS layer used
       by every prior Brevard-I session
       (gis.brevardfl.gov/.../Parcel_New_WKID2881/MapServer/5/query,
       TaxAcct IN (...)): returned ZERO features for all 22 candidate
       TaxAccts. These are the same "retired/re-platted TaxAcct, no longer
       in the live GIS layer" residual bucket documented in
       gold_standard_shard1_35db0a28_brevard_i_gis_backfill.py (the "50 of
       897 zero-feature" bucket from that session) -- i.e. even the county's
       own live system of record cannot confirm these parcels' geometry
       today, which is consistent with `parcels.latitude/longitude` for
       these specific rows being an interpolation/guess rather than a
       genuine centroid.
   Writing these 22 INFERRED, unsourced coordinates into
   multi_county_auctions.latitude/longitude would launder an unverified
   guess into a field the I-gate evaluator treats as verified card-complete
   data -- exactly the fabrication this task's guard explicitly prohibits.
   NOT attempted.

CONCLUSION: the new lever named in this dispatch (SRID-repaired zw_parcels
geometry, commit d204c897) does not reach Brevard at all (Brevard was never
in TARGET_COUNTIES, corrupted or repaired). The one live geometry source
that DOES cover a meaningful slice of the current 54-row geo-missing/
parcel_id-present candidate set (`parcels.latitude/longitude`) is itself
tagged INFERRED with zero source provenance for exactly this candidate set,
and independently fails to resolve against the live Brevard GIS layer. This
is a genuine, confirmed dead end -- not a scrape gap, not a rerun-the-same-
lever mistake. ZERO writes made this session.

Usage: python scripts/gold_standard_shard1_6a9e3c3a_brevard_i_geom_centroid_backfill.py
  (diagnostic/reporting only -- reproduces the live counts above; makes no
  writes)
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"

# Exact denominator filter reused verbatim from
# scripts/brevard_i_card_complete_shard1_3ce988ac.py.
MCA_FILTER = (
    "county=eq.brevard&or=(data_source.is.null,data_source.neq.propertyonion,"
    "tier1_authoritative.eq.true)"
)


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def sb_count(extra_filter):
    url = (f"{SB_URL}/rest/v1/multi_county_auctions?{MCA_FILTER}{extra_filter}"
           f"&select=case_number")
    req = urllib.request.Request(url, headers={**sb_headers(), "Range": "0-0",
                                                "Prefer": "count=exact"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range", "")
    return int(cr.split("/")[-1]) if "/" in cr else None


def sb_get_all(path_and_query, page_size=1000):
    rows = []
    offset = 0
    while True:
        sep = "&" if "?" in path_and_query else "?"
        url = f"{SB_URL}/rest/v1/{path_and_query}{sep}limit={page_size}&offset={offset}"
        req = urllib.request.Request(url, headers=sb_headers())
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.loads(r.read().decode())
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def zw_parcels_check():
    url = f"{SB_URL}/rest/v1/zw_parcels?select=pin&co_no=eq.5"
    req = urllib.request.Request(url, headers={**sb_headers(), "Range": "0-0",
                                                "Prefer": "count=exact"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Range", "*/0").split("/")[-1])
    url2 = f"{SB_URL}/rest/v1/zw_parcels?select=pin&co_no=eq.5&geom=not.is.null"
    req2 = urllib.request.Request(url2, headers={**sb_headers(), "Range": "0-0",
                                                  "Prefer": "count=exact"})
    with urllib.request.urlopen(req2, timeout=60) as r:
        with_geom = int(r.headers.get("Content-Range", "*/0").split("/")[-1])
    return total, with_geom


def main():
    print("=== zw_parcels (the table commit d204c897 actually repaired) ===")
    total, with_geom = zw_parcels_check()
    print(f"co_no=5 (Brevard) rows: {total}, of which geom IS NOT NULL: {with_geom}")
    print("Brevard is absent from backfill_geom_fdor.py TARGET_COUNTIES -- "
          "never corrupted, never repaired, never populated. DEAD END.\n")

    print("=== live I-gate denominator/gap (MCA_FILTER reused verbatim) ===")
    total_scope = sb_count("")
    addr_missing = sb_count("&property_address=is.null")
    geo_missing = sb_count("&latitude=is.null&po_latitude=is.null")
    value_missing = sb_count("&assessed_value=is.null&market_value=is.null")
    pid_missing = sb_count("&parcel_id=is.null")
    print(f"total in scope: {total_scope}")
    print(f"property_address IS NULL: {addr_missing}")
    print(f"geo missing (lat+po_lat both NULL): {geo_missing}")
    print(f"value missing (assessed+market both NULL): {value_missing}")
    print(f"parcel_id IS NULL: {pid_missing}\n")

    print("=== geo-missing rows WITH a parcel_id (candidate set for a "
          "geometry-centroid lever) ===")
    geo_rows = sb_get_all(
        f"multi_county_auctions?{MCA_FILTER}&latitude=is.null&po_latitude=is.null"
        f"&select=case_number,parcel_id,property_address"
    )
    with_pid = [r for r in geo_rows if r.get("parcel_id")]
    print(f"geo-missing total: {len(geo_rows)}, with parcel_id: {len(with_pid)}")
    distinct_pids = sorted({r["parcel_id"].strip() for r in with_pid
                             if r["parcel_id"].strip().isdigit()})
    print(f"distinct numeric TaxAcct-format parcel_ids: {len(distinct_pids)}\n")

    if not distinct_pids:
        print("No candidates -- nothing further to check.")
        return

    print("=== testing `parcels` table (apn=TaxAcct) for these candidates ===")
    inlist = ",".join(distinct_pids)
    url = (f"{SB_URL}/rest/v1/parcels?select=apn,latitude,longitude,honesty_marker,"
           f"geocode_source&apn=in.({inlist})")
    req = urllib.request.Request(url, headers=sb_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        matched = json.loads(r.read().decode())
    with_geo = [m for m in matched if m.get("latitude") is not None]
    inferred = [m for m in with_geo if m.get("honesty_marker") == "INFERRED"]
    print(f"matched in parcels: {len(matched)}, with non-null lat/lng: {len(with_geo)}")
    print(f"of those, honesty_marker='INFERRED' (no cited source): {len(inferred)}")
    if with_geo and len(inferred) == len(with_geo):
        print("\n100% of the candidate geometry hits are INFERRED with "
              "geocode_source=NULL, scraped_at=NULL, source_url=NULL -- no "
              "provenance. Per HONESTY PROTOCOL, writing these into "
              "multi_county_auctions would fabricate verified-looking data.")
        print("CONFIRMED DEAD END. No writes performed.")
    else:
        print("Some candidates have a cited/verified source -- would need "
              "manual review before any write (not the case in this run).")


if __name__ == "__main__":
    main()
