#!/usr/bin/env python3
"""Gold Standard shard-5 (dispatch 5d40a513, loop run 9630): pinellas I zone-linkage backfill.

TARGET: pinellas I (card_complete >= 95%, i.e. >= 443 of 466).
Baseline (VERIFIED live, this session, 2026-08-28): I FAIL 93.3% (card_complete=435 of 466).

31 named case_numbers lack a zone_code link in public.parcel_zones. This session
re-verified all 31 live and decomposed them:

  (a) 7 rows with NULL or junk parcel_id on multi_county_auctions itself
      ('PERSONAL PROPERTY', 'MULTIPLE PARCELS', or NULL with no address):
      522019CA002273XXCICI, 522023CA006219XXCICI, 522024CC007590XXCOCO,
      522025CA000532XXCICI, 522025CA002564XXCICI, 522025CA003843XXCICI,
      522025CA006625XXCICI.
      Attempted PCPAO resolution this session -- see RESIDUAL section. NOT
      addressed (no safe source to derive a real parcel_id from a bare case
      number / no-address row without a Clerk docket lookup out of scope).

  (b) 24 rows WITH a real parcel_id (STRAP or PARCELID numbering -- 3 of the
      24 use the alternate PARCELID numbering on multi_county_auctions, same
      known behavior as the prior pinellas-I session). Point-in-polygon
      against egis.pinellas.gov Municipalities layer resolved the REAL
      jurisdiction for all 24 (mailing SITE_CITY is NOT authoritative --
      confirmed again this session, matches prior finding):
        Largo:          11 parcels -- NO official City of Largo zoning-
                        district feature service exists (exhaustively
                        re-checked: maps.largo.com/arcgis/rest/services has
                        no zoning layer beyond the Unincorporated dupe; full
                        AGOL search of all 148 CityOfLargo-owned items shows
                        Future-Land-Use and Community-Standards-Zones layers
                        only, never a zoning-classification layer). GENUINE
                        RESIDUAL, matches prior session's finding exactly.
        Tarpon Springs:  2 parcels -- RESOLVED via gis.ctsfl.us (City of
                        Tarpon Springs) Hosted/Zoning_2025 FeatureServer
                        layer 3, direct spatial point-in-polygon query.
        Unincorporated:  3 parcels -- RESOLVED via egis.pinellas.gov
                        PublicWebGIS/Landuse_Zoning/MapServer/1 (ZONECLASS),
                        same layer as prior session.
        St. Petersburg:  3 parcels -- RESOLVED via egis.stpete.org
                        ServicesDSD/Zoning/MapServer/2 (ZONECLASS), same
                        layer as prior session.
        Madeira Beach:   1 parcel  -- RESOLVED via egis.pinellas.gov
                        AGO/PPC_Data/MapServer layer 4 "Madeira Beach
                        Zoning" (ZONING field) -- newly discovered this
                        session (not used in prior pinellas-I session).
        Gulfport:        2 parcels -- RESOLVED via a City of Gulfport-hosted
                        ArcGIS Online FeatureServer ("Energov1", owner
                        kanderson_mygulfport, services1.arcgis.com/
                        PzyKnm4YvKQg5oLs) layer 4 "GP_Zoning" (CODE field) --
                        newly discovered this session; prior session found
                        no Gulfport endpoint, this is a genuinely new lever.
        Pinellas Park:   2 parcels -- RESOLVED via the City of Pinellas Park
                        official zoning FeatureServer already used in a
                        PRIOR pinellas session (services6.arcgis.com/
                        fH2ZwfxOgb5eaBS4/.../Zoning__Pinellas_Park_03122025),
                        direct STRAP match for one, STRAP/PARCELID cross-
                        match + spatial confirmation for the other.

  13 of the 24 real-parcel_id rows resolve a live, verifiable zone_code this
  session (2 Tarpon Springs + 3 unincorporated + 3 St. Petersburg + 1 Madeira
  Beach + 2 Gulfport + 2 Pinellas Park). 11 (all Largo) are a genuine,
  re-confirmed residual.

  New zoning_districts catalog rows required (regression-trap guard -- a new
  zone_code must always have a matching catalog row):
    Tarpon Springs (896): R-60, R-100 -- names taken directly from the
      gis.ctsfl.us curr_zone field ("One and Two Family Residential
      District", "Single Family District"); NOT fabricated, read live from
      the same query that resolved the zone_code.
    Gulfport (1099): PUD, R-1A -- the GP_Zoning FeatureServer exposes only a
      CODE field and a numeric ZONING_ id, no name/description field anywhere
      in the service. Per NEVER-LIE (no fabricated names), catalog "name" is
      set to the code itself, matching the existing "code-echo" pattern
      already present in this table for other bare-code entries.

RESIDUAL -- 7 no-parcel-id rows (group a): attempted live resolution via
  PCPAO (pcpao.gov) this session. Left BLANK per BLANK > WRONG -- 4 of the 7
  have no case-identifying address/owner on multi_county_auctions to search
  by (parcel_id NULL AND property_address NULL AND owner_name NULL), and the
  other 3 (junk 'PERSONAL PROPERTY' / 'MULTIPLE PARCELS' values) require a
  Clerk-of-Court docket read to determine which specific parcel(s) are
  actually being foreclosed, out of this session's scope. NOT fabricated.

RESIDUAL -- 11 Largo rows (group b): no official City of Largo zoning-
  classification ArcGIS service exists (re-confirmed exhaustively this
  session across maps.largo.com and the full CityOfLargo AGOL org). NOT
  fabricated.

Usage:
  python3 scripts/pinellas_i_zoning_geo_shard5_5d40a513.py --dry-run
  python3 scripts/pinellas_i_zoning_geo_shard5_5d40a513.py
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

# ---- resolved fixes (VERIFIED live via city/county ArcGIS REST, this session, 2026-08-28) ----

# parcel_id -> (jurisdiction_id, zone_code, source_tag)
ZONE_LINKS = {
    # Tarpon Springs -- gis.ctsfl.us Hosted/Zoning_2025 FeatureServer layer 3
    "152712899820430402": (896, "R-60", "gis_ctsfl_us_hosted_zoning_2025_verified_20260828"),
    "152703723820000260": (896, "R-100", "gis_ctsfl_us_hosted_zoning_2025_verified_20260828"),
    # Unincorporated -- egis.pinellas.gov PublicWebGIS/Landuse_Zoning/MapServer/1
    "162734900090000650": (635, "RPD-W", "egis_pinellas_gov_landuse_zoning_verified_20260828"),
    "162732941060270030": (635, "RPD", "egis_pinellas_gov_landuse_zoning_verified_20260828"),
    "163001167850001813": (635, "RPD", "egis_pinellas_gov_landuse_zoning_verified_20260828"),
    # St. Petersburg -- egis.stpete.org ServicesDSD/Zoning/MapServer/2
    "173104817020010010": (814, "NS-1", "egis_stpete_org_servicesdsd_zoning_verified_20260828"),
    "163110511560010080": (814, "NS-1", "egis_stpete_org_servicesdsd_zoning_verified_20260828"),
    "163036568800760150": (814, "NS-1", "egis_stpete_org_servicesdsd_zoning_verified_20260828"),
    # Madeira Beach -- egis.pinellas.gov AGO/PPC_Data/MapServer layer 4 (Madeira Beach Zoning)
    "153115653040040050": (1095, "R-2", "egis_pinellas_gov_ago_ppc_data_madeira_beach_verified_20260828"),
    # Gulfport -- Energov1 FeatureServer layer 4 (GP_Zoning), City of Gulfport AGOL org
    "163132682050000150": (1099, "PUD", "services1_arcgis_com_gulfport_energov1_gp_zoning_verified_20260828"),
    "163129670500380120": (1099, "R-1A", "services1_arcgis_com_gulfport_energov1_gp_zoning_verified_20260828"),
    # Pinellas Park -- Zoning__Pinellas_Park_03122025 FeatureServer/0 (official city layer)
    "163019164380000850": (898, "T-2", "services6_arcgis_com_pinellas_park_zoning_verified_20260828"),
    "073016690580000490": (898, "RPUD", "services6_arcgis_com_pinellas_park_zoning_verified_20260828"),
}

NEW_ZONING_DISTRICTS = [
    {
        "jurisdiction_id": 896,
        "code": "R-60",
        "name": "One and Two Family Residential District",
        "category": "Residential",
        "description": "VERIFIED gis.ctsfl.us/arcgis/rest/services/Hosted/Zoning_2025 FeatureServer "
                        "layer 3, curr_code=R-60 curr_zone='One and Two Family Residential District', "
                        "gold-standard shard5 5d40a513 pinellas-I 2026-08-28",
    },
    {
        "jurisdiction_id": 896,
        "code": "R-100",
        "name": "Single Family District",
        "category": "Residential",
        "description": "VERIFIED gis.ctsfl.us/arcgis/rest/services/Hosted/Zoning_2025 FeatureServer "
                        "layer 3, curr_code=R-100 curr_zone='Single Family District', "
                        "gold-standard shard5 5d40a513 pinellas-I 2026-08-28",
    },
    {
        "jurisdiction_id": 1099,
        "code": "PUD",
        "name": "PUD",
        "category": "Uncategorized",
        "description": "VERIFIED services1.arcgis.com/PzyKnm4YvKQg5oLs/arcgis/rest/services/Energov1 "
                        "FeatureServer layer 4 (GP_Zoning), CODE=PUD -- no name/description field "
                        "exists in the source service, name left as the code itself (no fabrication), "
                        "gold-standard shard5 5d40a513 pinellas-I 2026-08-28",
    },
    {
        "jurisdiction_id": 1099,
        "code": "R-1A",
        "name": "R-1A",
        "category": "Uncategorized",
        "description": "VERIFIED services1.arcgis.com/PzyKnm4YvKQg5oLs/arcgis/rest/services/Energov1 "
                        "FeatureServer layer 4 (GP_Zoning), CODE=R-1A -- no name/description field "
                        "exists in the source service, name left as the code itself (no fabrication), "
                        "gold-standard shard5 5d40a513 pinellas-I 2026-08-28",
    },
]


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


def rpc(fn: str, params: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers=headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== PINELLAS I ZONING LINKAGE 13-ROW BACKFILL (dispatch 5d40a513, shard5) ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN -- planned writes:")
        print(f"zoning_districts inserts ({len(NEW_ZONING_DISTRICTS)}):")
        for d in NEW_ZONING_DISTRICTS:
            print(f"  {d['jurisdiction_id']} {d['code']} -> {d['name']}")
        print(f"parcel_zones inserts ({len(ZONE_LINKS)}):")
        for pid, (jid, zc, src) in ZONE_LINKS.items():
            print(f"  {pid} -> jurisdiction_id={jid} zone_code={zc} source={src}")
        return

    # 1. Ensure missing zoning_districts catalog rows exist (regression-trap guard).
    for d in NEW_ZONING_DISTRICTS:
        existing = sb_get("zoning_districts", {
            "jurisdiction_id": f"eq.{d['jurisdiction_id']}",
            "code": f"eq.{d['code']}",
            "select": "id",
        })
        if existing:
            log(f"zoning_districts jurisdiction_id={d['jurisdiction_id']} code={d['code']} "
                f"already exists, skipping insert", "VERIFIED")
        else:
            result = sb_post("zoning_districts", [d])
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

    log(f"Summary: parcel_zones inserted={pz_inserted}", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT parcel_id, zone_code, jurisdiction_id, source FROM parcel_zones "
          f"WHERE parcel_id IN ({', '.join(repr(p) for p in ZONE_LINKS)});")
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")
    print(f"AFTER  G (regression check): {after['G']}")


if __name__ == "__main__":
    main()
