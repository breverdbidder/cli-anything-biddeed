#!/usr/bin/env python3
"""Gold Standard escambia I zone-linkage fix, 2026-08-28.

TARGET: escambia I (card_complete >= 95%, i.e. >= 475 of 499).
Baseline (VERIFIED live, this session): I FAIL 94.8% (card_complete=473 of 499).

Root cause (matches the issue brief -- re-verified live this session): 25
case_numbers have a parcel_id and (mostly) full address/value on
multi_county_auctions, but their parcel_id does NOT appear in
public.parcel_zones with a non-null zone_code, so
v_zoning_gold_standard_card cannot mark their card complete.

Live re-verification this session (all 25 confirmed still missing a
parcel_zones row -- zero pre-existing rows found for any of the 25 parcel_ids
before this script runs):
  - 2 rows have a genuinely unusable parcel_id and were NOT resolved:
      2025 CA 001702  -- parcel_id is NULL on multi_county_auctions
      2024 CA 001572  -- parcel_id is the literal junk value "MULTIPLE PARCELS"
    Neither has a property_address to search by either. Left blank (residual).
  - 1 additional row could not be resolved despite having a real-looking
    parcel_id:
      2024 TD 003802, parcel_id 502S306061130002 -- this REFERENCE does not
      exist in the Escambia_County/MapServer/0 Parcels layer (exact match,
      LIKE '502S30606113%', and LIKE '%3061130002' all returned zero
      features). The stored property_address is a bare "WINGATE ST 32507"
      with no house number. A visually similar nearby parcel exists
      (502S306061180002 @ 802 WINGATE ST) but there is no independent
      evidence that is the SAME parcel as our 502S306061130002 -- guessing
      would violate BLANK > WRONG. Left blank (residual).
  - 1 additional row could not be resolved:
      2025 CA 000781, parcel_id "3077268" -- auction_status is
      canceled_per_county, property_address is NULL, and "3077268" is not a
      STRAP-format Escambia reference number (does not match REFERENCE,
      REFNUM, or CONTROLNO in the county Parcels layer under any field).
      No address to independently cross-check. Left blank (residual).
  - The remaining 21 rows ARE resolved live this session (see ZONE_LINKS).

METHOD (Escambia County's and City of Pensacola's own authoritative GIS,
discovered fresh this session -- the URL in the issue brief,
gis.escambiacountyfl.gov, does not resolve/DNS-fails; that endpoint is dead):

  1. Jurisdiction routing (point-in-polygon, NOT mailing-city inference --
     per the known trap documented in the issue brief):
       https://gismaps.myescambia.com/arcgis/rest/services/
         Individual_Layers/lucity_incorporated_areas/MapServer/0/query
       Field: ADMIN_AREA ("CITY OF PENSACOLA" / "TOWN OF CENTURY").
       No feature returned at a point => unincorporated Escambia County
       (jurisdiction_id=1151). Century (877) did not appear for any of the
       25 targets (none are near Century).

  2. Parcel geometry / true centroid (used instead of the DB's stored
     lat/lon, which for 3 rows sits just outside the zoning polygon's edge
     -- the DB centroid and the GIS parcel polygon are not perfectly
     co-registered):
       https://gismaps.myescambia.com/arcgis/rest/services/
         Escambia_County/MapServer/0/query  (field REFERENCE = STRAP)
     Vertex-average of the returned polygon ring (outSR=4326), same method
     as the pinellas-I precedent script.

  3a. Unincorporated Escambia County zoning (18 of 21 resolved rows):
       https://gismaps.myescambia.com/arcgis/rest/services/
         Individual_Layers/Zoning/MapServer/0/query
       ("Escambia County Florida Zoning", field ZONING). Point-in-polygon
       at the true parcel centroid from step 2.
       NOTE: field metadata was verified live (layer 0 = "Current Zoning",
       fields OBJECTID/CASE_NUMBER/Shape/ZONING) before assuming ZONING —
       per the issue brief's instruction to confirm field names, not guess.

  3b. City of Pensacola zoning (3 of 21 resolved rows -- the county's own
      Zoning layer does not cover incorporated Pensacola parcels, confirmed
      live: point-in-polygon against it returned no feature for all 3
      Pensacola-jurisdiction targets even after using the true parcel
      centroid):
       https://maps.cityofpensacola.com/arcgis/rest/services/
         Zoning_WebMap_MIL1/MapServer/16/query
       (layer 16 = "Zoning", field ZONING). Discovered by listing the root
       ArcGIS REST catalog at maps.cityofpensacola.com (200 OK; the
       previously-guessed gis.cityofpensacola.com is a dead/403 host).

  Escambia's authoritative "Current Zoning" layer only covers unincorporated
  county land (confirmed: it returned polygons for 18 targets and, for the
  3 Pensacola-jurisdiction targets, only nearby-but-non-covering polygons
  existed within a small search buffer -- consistent with a jurisdictional
  boundary gap in that layer's coverage, not a data error).

REGRESSION-TRAP GUARD: one resolved zone_code, RMU (Residential Mixed-Use),
does not yet exist in zoning_districts for jurisdiction_id=1151. It IS a
real, live value returned by the county's own Zoning MapServer (confirmed
via a direct where=ZONING='RMU' query returning matching features, not
just present in the renderer legend). A new zoning_districts catalog row is
inserted for it below, matching the exact style of the existing null-
ordinance_section rows in that jurisdiction (R-1 Shard9 synthetic row is
NOT used as a style template since it is explicitly synthetic; Agr/LDR/MDR/
HDR/HDMU/Com/HC-LI all cite "Sec. 3-2.x" LDC sections that were NOT
independently verified for RMU this session, so ordinance_section is left
NULL rather than guessed -- consistent with the two other null-section
patterns already present in this catalog for other jurisdictions).

All 3 zone codes needed for the City of Pensacola rows (R-1AAA, R-1AA,
R-1A) already exist in the zoning_districts catalog for jurisdiction_id=972
-- no new catalog rows needed there.

HARD GUARDRAILS:
  - PropertyOnion = litmus ONLY, never a source for this fix.
  - Only inserted for parcel_ids confirmed (live, this session) to have ZERO
    existing parcel_zones row -- idempotent, no overwrite of any existing
    non-null classification.
  - No fabricated zone_code, jurisdiction, or ordinance data anywhere below.

Usage:
  python3 scripts/escambia_i_zoning_geo_shard_20260828.py --dry-run
  python3 scripts/escambia_i_zoning_geo_shard_20260828.py
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

# parcel_id -> (jurisdiction_id, zone_code, source_tag)
# All confirmed live via point-in-polygon query against the true parcel
# centroid (Escambia_County/MapServer/0 REFERENCE geometry), this session.
TODAY = "20260828"
ESC_SRC = f"gis_myescambia_com_zoning_verified_{TODAY}"
PCOLA_SRC = f"gis_cityofpensacola_com_zoning_webmap_verified_{TODAY}"

ZONE_LINKS: dict[str, tuple[int, str, str]] = {
    # -- Unincorporated Escambia County (jurisdiction_id=1151) --
    "332S313300070002": (1151, "MDR", ESC_SRC),   # 2022 CA 000662
    "101S303600008003": (1151, "MDR", ESC_SRC),   # 2023 CA 001649
    "252S312400070001": (1151, "MDR", ESC_SRC),   # 2025 CA 000894
    "211N304500069002": (1151, "MDR", ESC_SRC),   # 2025 CA 001079
    "132S304400019008": (1151, "MDR", ESC_SRC),   # 2025 CA 001354
    "192N314200022001": (1151, "RMU", ESC_SRC),   # 2025 CA 001415
    "461S301100007008": (1151, "MDR", ESC_SRC),   # 2025 CA 001460
    "461S302001009053": (1151, "MDR", ESC_SRC),   # 2025 CA 001769
    "141N316000130019": (1151, "LDR", ESC_SRC),   # 2025 CA 001880
    "352N313302018002": (1151, "LDR", ESC_SRC),   # 2025 CA 001964
    "011S324500014002": (1151, "MDR", ESC_SRC),   # 2025 CA 001976
    "092S300700462002": (1151, "HDMU", ESC_SRC),  # 2026 CA 000047
    "202S311399003003": (1151, "LDR", ESC_SRC),   # 2026 CA 000155
    "272N314500014004": (1151, "LDR", ESC_SRC),   # 2026 CC 001962
    "233S312050010003": (1151, "HDR", ESC_SRC),   # 2026 CC 002930
    "162S304800000039": (1151, "HDR", ESC_SRC),   # 2025 CA 000118 (true-centroid re-query; DB lat/lon sits off-polygon)
    "351S307500000007": (1151, "HDMU", ESC_SRC),  # 2025 CA 001297 (true-centroid re-query)
    "231N302200000040": (1151, "LDR", ESC_SRC),   # 2025 CA 001403 (true-centroid re-query)
    # -- City of Pensacola (jurisdiction_id=972) --
    "111S291001004023": (972, "R-1AAA", PCOLA_SRC),  # 2025 CA 001180
    "042S302050024004": (972, "R-1AA", PCOLA_SRC),   # 2025 CA 001221
    "000S009020020055": (972, "R-1A", PCOLA_SRC),    # 2025 CA 001672
}

# case_number -> reason, for the residual (unresolved) rows.
RESIDUAL = {
    "2025 CA 001702": "parcel_id is NULL on multi_county_auctions; no property_address either -- no source to resolve a parcel_id from the case number alone this session.",
    "2024 CA 001572": "parcel_id is the literal junk value 'MULTIPLE PARCELS'; no property_address to search by -- same structural blocker as documented in the issue brief.",
    "2024 TD 003802": "parcel_id 502S306061130002 does not exist in Escambia_County/MapServer/0 (exact, LIKE-prefix, and LIKE-suffix queries all returned zero features). Stored address 'WINGATE ST 32507' has no house number. A visually similar nearby parcel (502S306061180002 @ 802 WINGATE ST) exists but there is no independent evidence it is the same parcel -- guessing would violate BLANK > WRONG.",
    "2025 CA 000781": "parcel_id '3077268' is not a STRAP-format Escambia reference (no match on REFERENCE/REFNUM/CONTROLNO); auction_status=canceled_per_county and property_address is NULL, so there is no independent way to cross-check or resolve it this session.",
}

NEW_ZONING_DISTRICT = {
    "jurisdiction_id": 1151,
    "code": "RMU",
    "name": "Residential Mixed-Use district",
    "category": "mixed-use",
    "description": "VERIFIED live via gismaps.myescambia.com/arcgis/rest/services/Individual_Layers/Zoning "
                    "(Escambia County Florida Zoning, 'Current Zoning' layer, field ZONING='RMU') -- "
                    f"escambia I zone-linkage fix {TODAY}. Ordinance section not independently verified "
                    "this session; left NULL rather than guessed.",
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


def rpc(fn: str, params: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers=headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== ESCAMBIA I ZONING LINKAGE FIX (25-row gap, 21 resolved) ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "escambia"})
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN -- planned writes:")
        print(f"zoning_districts insert (1): {NEW_ZONING_DISTRICT}")
        print(f"parcel_zones inserts ({len(ZONE_LINKS)}):")
        for pid, (jid, zc, src) in ZONE_LINKS.items():
            print(f"  {pid} -> jurisdiction_id={jid} zone_code={zc} source={src}")
        print(f"\nResidual (left blank, {len(RESIDUAL)}):")
        for cn, reason in RESIDUAL.items():
            print(f"  {cn}: {reason}")
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

    # 2. Insert parcel_zones links (skip any that already exist for that parcel_id -- idempotent).
    pz_inserted = 0
    pz_skipped = 0
    for pid, (jid, zc, src) in ZONE_LINKS.items():
        existing_pz = sb_get("parcel_zones", {"parcel_id": f"eq.{pid}", "select": "id"})
        if existing_pz:
            log(f"parcel_zones for parcel_id={pid} already exists, skipping (idempotent)", "VERIFIED")
            pz_skipped += 1
            continue
        row = {"parcel_id": pid, "jurisdiction_id": jid, "zone_code": zc, "source": src}
        result = sb_post("parcel_zones", [row])
        log(f"Inserted parcel_zones: {result}", "VERIFIED")
        pz_inserted += 1

    log(f"Summary: parcel_zones inserted={pz_inserted}, skipped(existing)={pz_skipped}, "
        f"residual(left blank)={len(RESIDUAL)}", "VERIFIED")

    if pz_inserted == 0 and pz_skipped == 0:
        log("FAIL-LOUD: expected to insert or find rows for all 21 targets but got neither -- "
            "check ZONE_LINKS / table state", "ERROR")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "escambia"})
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT parcel_id, zone_code, jurisdiction_id, source FROM parcel_zones "
          f"WHERE parcel_id IN ({', '.join(repr(p) for p in ZONE_LINKS)});")
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")
    print(f"AFTER  C (regression check): {after['C']}")
    print(f"AFTER  D (regression check): {after['D']}")
    print(f"AFTER  G (regression check): {after['G']}")


if __name__ == "__main__":
    main()
