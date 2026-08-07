#!/usr/bin/env python3
"""Gold Standard shard-4, hendry E/I fix (key=hendry-root-cause diagnosis follow-up).

Prior step in this session (scripts/shard11_run3534_hendry_cd_harvest.py, reused
unmodified) matched all 21 previously-unlinked hendry tax_deed rows (auction_date
2026-08-13) against the live hendry.realtaxdeed.com AJAX calendar, moving
C/D/E to 100% (parity_status='matched_clean', parcel_id + assessed_value
backfilled from the real RealTaxDeed source).

This script closes the remaining I (card_complete) gap for those same 21 rows,
which needs two more real-sourced fields the harvester does not provide:
  1. latitude/longitude -- from the Hendry County Property Appraiser's own
     ArcGIS FeatureServer (Parcels_Feb2024, LAT/LON fields, WGS84).
  2. a real zoning link (parcel_zones row) -- from Hendry County's own ArcGIS
     "Zoning" FeatureServer (Current_Zo field), matched by the exact
     RealTaxDeed-sourced PARCELNO.

Both ArcGIS sources are live, county-government-owned (services7.arcgis.com/
8l7Qq5t0CPLAJwJK, owner smccormick@hendryfla.net -- Hendry County Property
Appraiser), and were queried directly by PARCELNO -- no address-matching
inference needed since the harvester already gave us authoritative parcel_ids.

20 of the 21 parcels resolve to a real zone code already present in
zoning_districts for jurisdiction_id=1399 (Hendry County Unincorporated):
RR-F (Montura Ranches, 4 parcels) or RG-3 (Port LaBelle / Banyan Village, 16
parcels). Zero new zoning_districts rows are needed -- these codes/records
already existed before this session.

1 of the 21 (case 25-98, 506 DR M L KING JR BLVD, parcel 2 29 43 02 670
000A-001.1) is inside LaBelle city limits. Hendry's own Zoning FeatureServer
returns Current_Zo='LABELLE' for this parcel -- which is the same kind of
non-specific "deferred to municipal zoning authority" placeholder already seen
for Clewiston parcels (zoning_districts code 'CLEWISTON-CITY-ZONED'), not a
real zone code. No equivalent LaBelle placeholder convention exists yet in
zoning_districts (checked live: jurisdiction_id=872 has only A-1/R-1 codes +
municode chapter placeholders, no city-deferred stub). Writing a fabricated
LaBelle zone code would violate the fabrication guardrail, so this ONE row is
deliberately left without a zoning link -- it will keep I as 20/21 instead of
21/21 for the newly-linked cohort, i.e. hendry I moves from 38/59 to 58/59
(98.3%), not 59/59 (100%). This is a genuine, disclosed residual gap, not
a bug in this script.

Only currently-NULL multi_county_auctions fields are patched (never overwrites
existing non-null data -- assessed_value is already populated by the prior
harvest step and is NOT touched here). parcel_zones inserts are check-then-
insert (idempotent).

Usage: python3 scripts/gold_shard4_hendry_e_i_arcgis_fix.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

PARCELS_URL = ("https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/"
               "Parcels_Feb2024/FeatureServer/0/query")
ZONING_URL = ("https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/arcgis/rest/services/"
              "Zoning/FeatureServer/1/query")

JURISDICTION_ID = 1399  # Hendry County (Unincorporated) -- confirmed live via SELECT

# case_number -> parcel_id, as backfilled live this session by
# scripts/shard11_run3534_hendry_cd_harvest.py from hendry.realtaxdeed.com.
TARGET_CASES = {
    "23-70": "1 33 44 31 A00 0180.0000",
    "25-65": "1 32 44 25 A00 0207.0000",
    "25-66": "1 32 44 26 A00 0047.0100",
    "25-72": "1 32 44 36 A00 0074.0000",
    "25-73": "4 29 43 10 010 2023-020.0",
    "25-74": "4 29 43 10 010 2031-025.0",
    "25-75": "4 29 43 10 020 2041-032.0",
    "25-77": "4 29 43 10 030 2095-017.0",
    "25-78": "4 29 43 10 030 2124-030.0",
    "25-79": "4 29 43 10 030 2137-010.0",
    "25-85": "4 29 43 10 130 2542-010.0",
    "25-87": "4 29 43 10 080 2283-015.0",
    "25-89": "4 29 43 10 100 2354-009.0",
    "25-90": "4 29 43 10 100 2354-014.0",
    "25-91": "4 29 43 10 100 2358-024.0",
    "25-93": "4 29 43 10 100 2364-008.0",
    "25-94": "4 29 43 10 100 2365-004.0",
    "25-95": "4 29 43 10 110 2456-039.0",
    "25-96": "4 29 43 10 130 2523-001.0",
    "25-97": "4 29 43 10 130 2534-009.0",
    "25-98": "2 29 43 02 670 000A-001.1",  # LaBelle -- excluded from zoning link, see docstring
}

LABELLE_EXCLUDED_PARCEL = "2 29 43 02 670 000A-001.1"


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_post_ignore_dupes(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates,return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body_txt = r.read()
        return json.loads(body_txt) if body_txt else []


def arcgis_query(url, parcel_ids, out_fields):
    where = " OR ".join(f"PARCELNO='{p}'" for p in parcel_ids)
    params = {"where": where, "outFields": out_fields, "f": "json"}
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    return {f["attributes"]["PARCELNO"]: f["attributes"] for f in data.get("features", [])}


def main():
    parcel_ids = list(TARGET_CASES.values())

    print("=== Querying Hendry Parcels_Feb2024 (LAT/LON) ===")
    parcels_gis = arcgis_query(PARCELS_URL, parcel_ids, "PARCELNO,LAT,LON")
    print(f"  matched {len(parcels_gis)} of {len(parcel_ids)}")

    print("=== Querying Hendry Zoning FeatureServer (Current_Zo) ===")
    zoning_gis = arcgis_query(ZONING_URL, parcel_ids, "PARCELNO,Current_Zo")
    print(f"  matched {len(zoning_gis)} of {len(parcel_ids)}")

    counters = {"mca_patched": 0, "parcel_zones_inserted": 0, "skipped_zoning": []}

    for case_number, pid in TARGET_CASES.items():
        rows = rest_get(
            f"multi_county_auctions?county=eq.hendry&case_number=eq.{urllib.parse.quote(case_number)}"
            f"&select=id,case_number,parcel_id,latitude,longitude")
        if not rows:
            raise SystemExit(f"FAIL-LOUD: row not found live for case_number={case_number}")
        row = rows[0]
        if row.get("parcel_id") != pid:
            raise SystemExit(
                f"FAIL-LOUD: live parcel_id mismatch for {case_number}: "
                f"expected {pid}, got {row.get('parcel_id')} -- diagnosis stale, aborting")

        # --- lat/lon backfill (only if currently NULL) ---
        gis = parcels_gis.get(pid)
        if gis is None:
            raise SystemExit(f"FAIL-LOUD: Hendry Parcels_Feb2024 returned no feature for {pid} ({case_number})")
        if row.get("latitude") is None and row.get("longitude") is None:
            patch = {"latitude": gis["LAT"], "longitude": gis["LON"]}
            result = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
            if not result:
                raise SystemExit(f"FAIL-LOUD: PATCH for {case_number} (id={row['id']}) returned 0 rows updated!")
            counters["mca_patched"] += 1
            print(f"  PATCHED {case_number} ({pid}): lat={gis['LAT']} lon={gis['LON']} "
                  f"(Hendry Parcels_Feb2024 ArcGIS, WGS84)")
        else:
            print(f"  {case_number} ({pid}): lat/lon already set, not overwritten")

        # --- zoning link (skip the one LaBelle placeholder-only parcel) ---
        if pid == LABELLE_EXCLUDED_PARCEL:
            counters["skipped_zoning"].append(
                {"case_number": case_number, "reason": "Current_Zo='LABELLE' is a city-deferred "
                                                         "placeholder, not a real zone code -- no "
                                                         "equivalent LaBelle stub exists in zoning_districts"})
            print(f"  {case_number} ({pid}): SKIP zoning link -- LaBelle placeholder only (see docstring)")
            continue

        zone_code = zoning_gis.get(pid, {}).get("Current_Zo")
        if not zone_code:
            counters["skipped_zoning"].append({"case_number": case_number, "reason": "no Current_Zo on file"})
            print(f"  {case_number} ({pid}): SKIP zoning link -- no Current_Zo on file")
            continue

        existing_zd = rest_get(
            f"zoning_districts?jurisdiction_id=eq.{JURISDICTION_ID}&code=eq.{urllib.parse.quote(zone_code)}&select=id")
        if not existing_zd:
            raise SystemExit(
                f"FAIL-LOUD: expected pre-existing zoning_districts row for "
                f"(jurisdiction_id={JURISDICTION_ID}, code={zone_code}) not found -- "
                f"diagnosis assumed this already exists, aborting rather than guessing name/category")

        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if existing_pz:
            print(f"  {case_number} ({pid}): parcel_zones already exists -- zoning link satisfied")
            continue

        source = (f"{ZONING_URL.split('?')[0]} (PARCELNO={pid}, Current_Zo={zone_code})")
        pz_body = [{
            "parcel_id": pid,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code,
            "zone_name": existing_zd[0].get("id") and zone_code,  # placeholder overwritten below
            "source": source,
        }]
        # use the real zoning_districts.name for zone_name (fetch it, don't guess)
        zd_full = rest_get(f"zoning_districts?id=eq.{existing_zd[0]['id']}&select=name")
        pz_body[0]["zone_name"] = zd_full[0]["name"] if zd_full else zone_code
        inserted = rest_post_ignore_dupes("parcel_zones", pz_body)
        if inserted:
            counters["parcel_zones_inserted"] += 1
            print(f"    INSERTED parcel_zones (parcel_id={pid}, zone_code={zone_code})")
        else:
            raise SystemExit(f"FAIL-LOUD: parcel_zones insert for {pid} returned 0 rows")

    print("\n=== SUMMARY ===")
    print(json.dumps(counters, indent=2, default=str))


if __name__ == "__main__":
    main()
