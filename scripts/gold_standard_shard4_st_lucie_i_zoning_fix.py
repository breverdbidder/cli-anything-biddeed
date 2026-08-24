#!/usr/bin/env python3
"""Gold Standard shard-4 st_lucie letter I (property card completeness) fix.

Dispatch 7d59c973-434c-4b8c-a699-e820f9093c39.

I (card_complete = address + geo + value + zoned-parcel) was 200/237=84.4%.
All 37 failing rows fail on the zoned_parcel join alone (address/geo/value
are NOT the bottleneck for any of them). This script closes two independently
confirmed sub-classes of the 37-row gap with real, verified data:

PART 1 -- format-normalization (10 rows, zero new scraping):
  10 multi_county_auctions.parcel_id values are stored with a trailing
  "-N" suffix (e.g. '1431-701-0266-000-1') while the matching
  public.parcel_zones row for the physically identical parcel is stored
  with a trailing "/N" suffix ('1431-701-0266-000/1'). Confirmed live for
  all 10 by exact string match after format conversion. This PATCHes
  multi_county_auctions.parcel_id to the slash format so the existing
  v_zoning_gold_standard_card join resolves -- no new source data, purely
  a representation fix of data already proven correct in this session.

PART 2 -- new spatial zoning lookups (4 of 6 candidate rows, live-confirmed):
  4 of the 6 "no-zoning-row-yet" foreclosure rows resolve to a real,
  unambiguous zone via point-in-polygon spatial query (parcel centroid,
  geo_source='parcel_centroid', geo_ambiguity=1 -- i.e. NOT a shared/
  condo-complex centroid) against the same 3 St Lucie-area ArcGIS
  FeatureServers the 2026-08-15 migration already used and cited:
    - St Lucie County unincorporated: slcgis.stlucieco.gov LandUse/Zoning
    - Fort Pierce: services1.arcgis.com/oDRzuf2MGmdEHAbQ CityZoning
    - Port St Lucie: services1.arcgis.com/YdUP5V6WwzeG8T8r Zoning
  The other 2 candidates are deliberately EXCLUDED as ghost-success risks:
    - 2025CA002566 (parcel 189265) and 26-137 (parcel 2311-800-0031-000/3)
      both hit the St Lucie County layer on a "PID Gone" record with
      Zoned=NULL -- no real zone code exists to insert, would require
      fabricating a value.
    - 2025CC001010 (parcel 31371) is a unit within a larger condominium
      complex; its centroid intersects the OWNING complex's parent tax
      account (AccountNum 180147, a 29.6-acre parcel, different address)
      rather than its own unit -- inserting that zone would misattribute
      a different tax account's zoning to this parcel. geo_ambiguity=1 on
      the row does not guarantee unit-level disambiguation for condos; this
      is the same "condo-unit-not-disambiguable" class flagged unresolved
      in the prior E-fix session for this same case.

Fail-loud: raises if any expected row/insert count does not match.
"""
import os

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MCA_URL = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
PZ_URL = f"{SUPABASE_URL}/rest/v1/parcel_zones"
PG_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# PART 1: dash-format multi_county_auctions.parcel_id -> confirmed slash-format
# equivalent already present in parcel_zones (verified live this session).
DASH_TO_SLASH = {
    "26-072": ("1431-701-0266-000-1", "1431-701-0266-000/1"),
    "26-041": ("3420-620-0042-000-9", "3420-620-0042-000/9"),
    "26-068": ("2405-501-0170-000-9", "2405-501-0170-000/9"),
    "26-075": ("2404-516-0022-000-0", "2404-516-0022-000/0"),
    "26-018": ("3425-706-0193-000-0", "3425-706-0193-000/0"),
    "26-066": ("3420-695-1461-000-1", "3420-695-1461-000/1"),
    "26-071": ("2405-524-0007-000-7", "2405-524-0007-000/7"),
    "26-070": ("2404-716-0006-000-6", "2404-716-0006-000/6"),
    "26-085": ("2402-503-0089-000-1", "2402-503-0089-000/1"),
    "26-073": ("1432-807-0085-000-6", "1432-807-0085-000/6"),
}

# PART 2: new parcel_zones inserts. zone_code/description confirmed live this
# session via point-in-polygon query against the parcel's own centroid
# (geo_source=parcel_centroid, geo_ambiguity=1) at the cited FeatureServer.
NEW_ZONING = [
    # (parcel_id, jurisdiction_id, zone_code, zone_description, source)
    ("160173", 1400, "RS-4", None, "st_lucie_county_arcgis_landuse_zoning_20260824_session2"),
    ("27264", 971, "R-4", "Medium Density Residential Zone", "fort_pierce_arcgis_cityzoning_20260824_session2"),
    ("74172", 953, "RS-2", "SINGLE-FAMILY RESIDENTIAL", "port_st_lucie_arcgis_zoning_20260824_session2"),
    ("86303", 953, "RS-2", "SINGLE-FAMILY RESIDENTIAL", "port_st_lucie_arcgis_zoning_20260824_session2"),
]


def part1_normalize_format(client: httpx.Client) -> int:
    written = 0
    for case_number, (dash_pid, slash_pid) in DASH_TO_SLASH.items():
        # Verify the slash-format row exists in parcel_zones before patching
        # (avoid pointing multi_county_auctions.parcel_id at a value that
        # would not actually resolve zoning — fail loud if it's gone).
        resp = client.get(PZ_URL, params={"parcel_id": f"eq.{slash_pid}", "select": "parcel_id,zone_code"}, headers=PG_HEADERS)
        resp.raise_for_status()
        pz_rows = resp.json()
        if len(pz_rows) != 1 or not pz_rows[0].get("zone_code"):
            raise RuntimeError(f"st_lucie I fix: expected 1 zoned parcel_zones row for {slash_pid}, got {pz_rows}")

        # Verify current multi_county_auctions state matches expected dash format
        resp = client.get(MCA_URL, params={"county": "eq.st_lucie", "case_number": f"eq.{case_number}", "select": "case_number,parcel_id"}, headers=PG_HEADERS)
        resp.raise_for_status()
        mca_rows = resp.json()
        if len(mca_rows) != 1:
            raise RuntimeError(f"st_lucie I fix: expected 1 multi_county_auctions row for {case_number}, got {len(mca_rows)}")
        if mca_rows[0]["parcel_id"] != dash_pid:
            raise RuntimeError(f"st_lucie I fix: {case_number} parcel_id was {mca_rows[0]['parcel_id']!r}, expected {dash_pid!r} — refusing to overwrite unexpected state")

        resp = client.patch(
            MCA_URL,
            params={"county": "eq.st_lucie", "case_number": f"eq.{case_number}"},
            headers=PG_HEADERS,
            json={"parcel_id": slash_pid},
        )
        resp.raise_for_status()
        body = resp.json()
        if len(body) != 1 or body[0].get("parcel_id") != slash_pid:
            raise RuntimeError(f"st_lucie I fix: PATCH for {case_number} did not persist parcel_id={slash_pid}, got {body}")
        written += 1
        print(f"  [format] {case_number}: {dash_pid} -> {slash_pid} OK (zone={pz_rows[0]['zone_code']})")
    return written


def part2_insert_new_zoning(client: httpx.Client) -> int:
    written = 0
    for parcel_id, jurisdiction_id, zone_code, zone_desc, source in NEW_ZONING:
        # Idempotency: skip if a row for this parcel_id already exists.
        resp = client.get(PZ_URL, params={"parcel_id": f"eq.{parcel_id}", "select": "parcel_id"}, headers=PG_HEADERS)
        resp.raise_for_status()
        if resp.json():
            raise RuntimeError(f"st_lucie I fix: parcel_zones row for {parcel_id} already exists — refusing duplicate insert")

        payload = {
            "parcel_id": parcel_id,
            "jurisdiction_id": jurisdiction_id,
            "zone_code": zone_code,
            "zone_name": zone_desc,
            "source": source,
        }
        resp = client.post(PZ_URL, headers=PG_HEADERS, json=payload)
        resp.raise_for_status()
        body = resp.json()
        if len(body) != 1 or body[0].get("zone_code") != zone_code:
            raise RuntimeError(f"st_lucie I fix: INSERT for parcel {parcel_id} did not persist zone_code={zone_code}, got {body}")
        written += 1
        print(f"  [new-zoning] parcel {parcel_id} -> zone_code={zone_code} (jurisdiction={jurisdiction_id}) OK")
    return written


def main():
    with httpx.Client(timeout=30) as client:
        print("PART 1: format-normalize 10 dash->slash parcel_id rows")
        n1 = part1_normalize_format(client)

        print("\nPART 2: insert 4 new confirmed zoning rows")
        n2 = part2_insert_new_zoning(client)

    print(f"\nTotal: {n1} format-normalized (multi_county_auctions) + {n2} new zoning rows (parcel_zones)")
    if n1 != len(DASH_TO_SLASH):
        raise RuntimeError(f"st_lucie I fix: expected {len(DASH_TO_SLASH)} format fixes, got {n1}")
    if n2 != len(NEW_ZONING):
        raise RuntimeError(f"st_lucie I fix: expected {len(NEW_ZONING)} new zoning inserts, got {n2}")


if __name__ == "__main__":
    main()
