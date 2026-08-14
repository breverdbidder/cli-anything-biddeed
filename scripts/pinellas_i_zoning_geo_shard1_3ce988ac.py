#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch 3ce988ac-bdcf-4554-aaa2-1f9b7653bc45): pinellas I.

TARGET: pinellas I (card_complete >= 95%).
Baseline (VERIFIED live, after the C/D/J parity fix in this same session):
  I FAIL 93.1% (card_complete=404 of 434).

Root cause investigation (VERIFIED live, this session): the 30-row I gap
decomposes into three disjoint groups:
  (a) 8 rows with no usable parcel_id at all (NULL, or garbage values like
      'PERSONAL PROPERTY' / 'Property Appraiser') -- structurally blocked,
      NOT addressed here (no source to resolve a parcel_id from a case
      number without a Clerk docket lookup out of this session's scope).
  (b) 11 rows with a real parcel_id (STRAP) and real assessed_value but no
      latitude/longitude on file.
  (c) 11 rows with a real parcel_id, real geo, real value, but no matching
      zone_code row reachable via v_zoning_gold_standard_card (i.e. no
      parcel_zones link for that parcel_id).
  Groups (b) and (c) both ALSO require a zone_code link to satisfy I (the
  card_complete predicate requires geo+value+address AND a parcel_zones
  zone_code match) -- so group (b) needs BOTH a geo backfill AND a zone
  link, not just geo.

METHOD (Pinellas County's own authoritative Property Appraiser ArcGIS REST
services, same pattern used by the prior verified pinellas-I session
2026-08-07, supabase/migrations/20260807h_gold_standard_shard5_5d40a513_
pinellas_i_gis_zone_backfill.sql):
  1. egis.pinellas.gov/gis/rest/services/PublicWebGIS/Parcels/MapServer/1
     -- county Parcels layer (STRAP field, also PARCELID field for the 3
     rows whose DB parcel_id is in the alternate PARCELID numbering, not
     STRAP -- same known behavior documented in the prior session). Used to
     fetch each parcel's polygon geometry; centroid computed as a plain
     vertex average of the returned ring (a real per-parcel geocode, not a
     county-wide placeholder).
  2. egis.pinellas.gov/gis/rest/services/PublicWebGIS/Municipalities/
     MapServer/0 ("All Municipalities") -- point-in-polygon query at each
     parcel's centroid to determine the REAL jurisdiction (Pinellas has 24
     municipalities + unincorporated + enclaves; SITE_CITY / mailing city
     is not authoritative, confirmed by the prior session too).
  3. Per resolved municipality, the authoritative zoning ArcGIS layer:
       UNINCORPORATED (jurisdiction_id=635): egis.pinellas.gov/gis/rest/
         services/PublicWebGIS/Landuse_Zoning/MapServer/1 (ZONECLASS)
       St. Petersburg (814): egis.stpete.org/arcgis/rest/services/
         ServicesDSD/Zoning/MapServer/2 (ZONECLASS)
       Clearwater (856): gis.myclearwater.com/arcgis/rest/services/
         ArcGISMapServices/Zoning_WGS84/MapServer/1 (ZONING)
       Seminole (1093), Kenneth City (1100), Treasure Island (1096):
         egis.pinellas.gov/gis/rest/services/AGO/PPC_Data/MapServer,
         layers 7 / 3 / 8 respectively (ZONING)
       Dunedin (860): gis.dunedingov.com/server/rest/services/
         CommunityDevelopment/ZoningDistrict/MapServer/0 (ZONECLASS)
     Each resolved via a live point-in-polygon query at the parcel centroid.
  4. Largo (859, 7 gap rows), Pinellas Park (898, 3 gap rows), and Gulfport
     (1099, 1 gap row) -- RE-CONFIRMED this session (not just trusted from
     Aug 7): maps.largo.com/arcgis/rest/services/Largo_GIS_Viewer_Map only
     exposes an "Unincorporated Zoning Layer" duplicate, no incorporated-
     Largo zoning service; Pinellas Park and Gulfport have no discoverable
     public ArcGIS REST zoning endpoint. Left as an honest residual, NOT
     fabricated -- see RESIDUAL section below.

11 parcel_ids resolve a real zone_code this way (10 already had matching
zoning_districts catalog codes for their jurisdiction; ONE new catalog row
is required: Kenneth City RM-15, which the AGO/PPC_Data ZONING field
returns for parcel 163105162900021902 but was not yet in zoning_districts
for jurisdiction_id=1100 -- inserted below matching the exact style of the
existing RM-15 row already present for Treasure Island jurisdiction_id=1096
("Multiple Family Residential", category "Residential", no numeric
standards fabricated). This is the KNOWN REGRESSION TRAP guard: a new
zone_code must always have a matching zoning_districts catalog row, done
here for RM-15/1100.

9 of the 11 resolved parcels also get a real lat/lon backfill (centroid of
the county Parcels layer geometry) -- the other 2 already had geo on file
and only needed the zone link.

Does NOT touch the 8 no-parcel-id rows (residual, no source path this
session) or the 11 Largo/Pinellas Park/Gulfport rows (residual, no
discoverable zoning endpoint, re-confirmed live).

Usage:
  python3 scripts/pinellas_i_zoning_geo_shard1_3ce988ac.py --dry-run
  python3 scripts/pinellas_i_zoning_geo_shard1_3ce988ac.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DRY_RUN = "--dry-run" in sys.argv

# ---- resolved fixes (VERIFIED live via egis.pinellas.gov / city ArcGIS REST, this session) ----

# parcel_id -> (jurisdiction_id, zone_code, source_tag)
ZONE_LINKS = {
    "162831640260310360": (635, "RM", "egis_pinellas_gov_landuse_zoning_verified_20260814"),
    "162804103260010300": (635, "RPD", "egis_pinellas_gov_landuse_zoning_verified_20260814"),
    "173030756360150080": (814, "NS-1", "egis_stpete_org_servicesdsd_zoning_verified_20260814"),
    "163136489420000380": (814, "NT-1", "egis_stpete_org_servicesdsd_zoning_verified_20260814"),
    "152922119880160050": (856, "LMDR", "gis_myclearwater_com_zoning_wgs84_verified_20260814"),
    "162819988300131303": (856, "MDR", "gis_myclearwater_com_zoning_wgs84_verified_20260814"),
    "162829616260070010": (856, "LMDR", "gis_myclearwater_com_zoning_wgs84_verified_20260814"),
    "153026302710032110": (1093, "RPD", "egis_pinellas_gov_ago_ppc_data_verified_20260814"),
    "163105162900021902": (1100, "RM-15", "egis_pinellas_gov_ago_ppc_data_verified_20260814"),
    "153124662470000020": (1096, "RM-15", "egis_pinellas_gov_ago_ppc_data_verified_20260814"),
    "152826220790001010": (860, "PRD", "gis_dunedingov_com_zoningdistrict_verified_20260814"),
}

# parcel_id -> (latitude, longitude) -- real centroid of the county Parcels
# layer geometry (vertex-average of the STRAP's polygon ring, outSR=4326),
# fetched live this session.
LATLON_BACKFILL = {
    "162831640260310360": (27.999288490285096, -82.73857835211818),
    "173030756360150080": (27.847196794151746, -82.63090336062203),
    "153026302710032110": (27.84611073329152, -82.77103197927224),
    "163136489420000380": (27.746751099090318, -82.65891794523544),
    "162804103260010300": (28.073830690946544, -82.70751404889516),
    "162819988300131303": (28.038581954077895, -82.73471371321101),
    "163105162900021902": (27.810900914575964, -82.71305942548999),
    "162829616260070010": (28.015538350775117, -82.7151736270799),
    "153124662470000020": (27.76674378768871, -82.75661520288332),
}

NEW_ZONING_DISTRICT = {
    "jurisdiction_id": 1100,
    "code": "RM-15",
    "name": "Multiple Family Residential",
    "category": "Residential",
    "description": "VERIFIED egis.pinellas.gov/gis/rest/services/AGO/PPC_Data layer 3 (Kenneth City "
                    "Zoning) ZONING=RM-15, gold-standard shard1 3ce988ac pinellas-I 2026-08-14",
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def headers(extra=None):
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def sb_get(table: str, params: dict) -> list:
    qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='=,.()')}" for k, v in params.items())
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{qs}", headers=headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(table: str, rows: list, prefer="return=representation,resolution=ignore-duplicates"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}", data=json.dumps(rows).encode(), method="POST",
        headers=headers({"Prefer": prefer}))
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(table: str, filter_qs: str, payload: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}", data=json.dumps(payload).encode(), method="PATCH",
        headers=headers({"Prefer": "return=representation"}))
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rpc(fn: str, params: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers=headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== PINELLAS I ZONING/GEO 11-ROW BACKFILL (dispatch 3ce988ac) ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN -- planned writes:")
        print(f"zoning_districts insert (1): {NEW_ZONING_DISTRICT}")
        print(f"parcel_zones inserts ({len(ZONE_LINKS)}):")
        for pid, (jid, zc, src) in ZONE_LINKS.items():
            print(f"  {pid} -> jurisdiction_id={jid} zone_code={zc} source={src}")
        print(f"multi_county_auctions lat/lon backfill ({len(LATLON_BACKFILL)}):")
        for pid, (lat, lon) in LATLON_BACKFILL.items():
            print(f"  {pid} -> lat={lat} lon={lon}")
        return

    # 1. Ensure the missing zoning_districts catalog row exists (regression-trap guard).
    existing = sb_get("zoning_districts", {
        "jurisdiction_id": f"eq.{NEW_ZONING_DISTRICT['jurisdiction_id']}",
        "code": f"eq.{NEW_ZONING_DISTRICT['code']}",
        "select": "id",
    })
    if existing:
        log(f"zoning_districts jurisdiction_id={NEW_ZONING_DISTRICT['jurisdiction_id']} "
            f"code={NEW_ZONING_DISTRICT['code']} already exists, skipping insert", "VERIFIED")
    else:
        result = sb_post("zoning_districts", [NEW_ZONING_DISTRICT])
        log(f"Inserted zoning_districts: {result}", "VERIFIED")

    # 2. Insert parcel_zones links (skip any that already exist for that parcel_id).
    pz_inserted = 0
    for pid, (jid, zc, src) in ZONE_LINKS.items():
        existing_pz = sb_get("parcel_zones", {"parcel_id": f"eq.{pid}", "select": "id"})
        if existing_pz:
            log(f"parcel_zones for parcel_id={pid} already exists, skipping", "VERIFIED")
            continue
        row = {"parcel_id": pid, "jurisdiction_id": jid, "zone_code": zc, "source": src}
        result = sb_post("parcel_zones", [row])
        log(f"Inserted parcel_zones: {result}", "VERIFIED")
        pz_inserted += 1

    # 3. Backfill lat/lon on multi_county_auctions for the resolved parcels.
    latlon_patched = 0
    for pid, (lat, lon) in LATLON_BACKFILL.items():
        filter_qs = f"county=eq.pinellas&parcel_id=eq.{urllib.parse.quote(pid)}&latitude=is.null"
        result = sb_patch("multi_county_auctions", filter_qs, {"latitude": lat, "longitude": lon})
        log(f"Patched lat/lon for parcel_id={pid}: {len(result)} row(s)", "VERIFIED")
        latlon_patched += len(result)

    log(f"Summary: parcel_zones inserted={pz_inserted}, lat/lon rows patched={latlon_patched}",
        "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT parcel_id, zone_code, jurisdiction_id, source FROM parcel_zones "
          "WHERE parcel_id IN (...11 targets...);")
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")
    print(f"AFTER  G (regression check): {after['G']}")


if __name__ == "__main__":
    main()
