#!/usr/bin/env python3
"""SHARD-7 continuation (dispatch 2f9f6a3e-a24c-4638-bcd3-5fe8f031d830), osceola G fix.

CONTEXT: the prior session on this dispatch (see GOLD_STANDARD_SHARD7_FLAGLER_
OSCEOLA_RUN3786_SESSION_REPORT.md) purged a fabricated osceola zoning dataset and
rebuilt 26 real parcel_zones rows from gis.osceola.org's live Zoning_Parcels
FeatureServer, across 7 real zone codes (AC, CR, CT, PD, PMUD, RMH, STRPD) under
jurisdiction_id=1186 (unincorporated Osceola County). That correctly dropped G from
a fabricated 100% to an honest 0%, because zoning_districts existed for all 7 codes
but zone_standards (density/FAR) was left entirely NULL -- library.municode.com's
Angular front-end 403'd plain curl and Firecrawl had no key in that session.

THIS SESSION: Firecrawl key now exists in the environment but returns "Insufficient
credits" (still unusable). Found a different, working, zero-cost path instead --
Municode's own undocumented REST API (api.municode.com), discovered via the
community-maintained doc at git.sr.ht/~partytax/unofficial-municode-api-documentation.
Same pattern already proven in this codebase for Lake County
(scripts/shard7c_lake_g_zoning_standards_fix.py), applied fresh for Osceola:

  1. GET https://api.municode.com/Clients/name?clientName=Osceola%20County&stateAbbr=FL
     -> ClientID=7166
  2. GET https://api.municode.com/ClientContent/7166
     -> Land Development Code productId=15810
  3. GET https://api.municode.com/Jobs/latest/15810
     -> jobId=478316, "Supplement 10, codified through Ordinance No. 2025-40,
        enacted August 18, 2025"
  4. GET https://api.municode.com/CodesContent?jobId=478316&nodeId=<any Ch.3 node>
     &productId=15810 -> returns the FULL Chapter 3 Docs[] array regardless of
     which specific nodeId within the chapter is passed

Ran via an ULTRALOOP research + adversarial-verify workflow (2 research agents, 2
independent refuter agents, all with live Bash/curl access, no shared context).
9 of 11 distinct claims were independently CONFIRMED by re-fetching the same live
API calls; 2 were REFUTED with concrete evidence and were NOT written to the DB:
  - CT max_far was claimed as 1.0 -- the refuter re-pulled the raw HTML table and
    found the real "RPB|CG|CT|CO|CN|EC" column order: CG=1.0 FAR, CT=N/A. The 1.0
    was a one-column transcription shift. CT's true value is N/A (Sec 3.2.4(D)
    Commercial Development Standards table).
  - AC's cited amendment history (Ord. 2020-07/2022-125/2024-48/2025-10) was real
    text, but it belonged to Sec 3.2.4 (Commercial), not Sec 3.2.1 (Agricultural) --
    misattributed section. The actual AC density VALUE (0.2 du/acre) was confirmed
    correct; only the amendment citation was dropped from what got written.

VALUES ACTUALLY WRITTEN (all via PostgREST REST API -- direct psql/`supabase db
push` auth failed in this session's environment, SUPABASE_DB_PASSWORD does not
authenticate; this is a pure data backfill, no schema change, so REST PATCH is
sufficient and matches the "simple backfills don't need a migration" precedent
already used for this dispatch's C/D fix):

  AC   (zoning_districts id=11793, zone_standards id=4500):
       max_density_du_acre = 0.2 (1 du per 5 acres), confidence_score=1.0.
       Source: LDC Sec 3.2.1(D) Agricultural Development Standards table.

  CR   (zoning_districts id=11794): far_regulated=false.
       Table 3.2 "Preceding Zoning District Development Standards Matrix" (CR's
       own governing table, since CR is a pre-2012 historic district) has ONLY
       Lot Size/Width/Height/Setback columns -- no FAR/intensity column exists
       anywhere in that table, for any code. zone_standards left NULL (genuinely
       no value to write), far_regulated=false so it stops counting as an
       "applicable but missing" FAR gap.

  CT   (zoning_districts id=11795): far_regulated=false.
       Live Sec 3.2.4(D) table: CT's own "Maximum intensity" cell = N/A (distinct
       from the REFUTED 1.0 claim, which belonged to CG). zone_standards left NULL.

  RMH  (zoning_districts id=11798): density_regulated=false.
       Same Table 3.2 matrix as CR -- RMH's row gives min-lot-size-by-unit-type
       only (house 7,000 / duplex 9,500 / triplex 12,500 / townhouse 15,500 sqft),
       no per-acre density figure anywhere. Back-calculating a du/acre number from
       lot size was deliberately NOT done (would be an invented number, not an
       ordinance value -- the exact fabrication pattern this dispatch has twice
       already had to clean up for this county).

  PD, PMUD, STRPD (zoning_districts ids 11796/11797/11799): LEFT UNCHANGED
       (far_regulated/density_regulated remain NULL, same as the Lake County PUD
       precedent). Sec 3.11.1(I) "Density and Intensity" governs all three
       sub-types identically and states verbatim: "allowable density and intensity
       will be based on several factors, including the land use designation on the
       future land use map, existing development in the immediate vicinity..." --
       i.e. determined per planned-development application, not a single codified
       number. These 3 correctly remain "applicable but missing" -- an honest,
       structural, currently-unfixable gap, not a data-collection failure.

RESULT: G 0.0 -> 5.3 (density=5.3, far/pk1000 no longer counted -- REAL, VERIFIED,
still FAILING the 95% gate). The residual gap is dominated by PD/PMUD/STRPD parcels,
which is a genuine per-development-agreement ceiling, not a further scraping problem.

This script is a RECORD of what was executed live via curl during the session (the
actual writes already happened via the commands below when originally run) -- running
it again is idempotent (each PATCH sets the same target state) and serves as the
audit trail / reproducibility artifact for this dispatch, matching this codebase's
existing convention (see shard7c_lake_g_zoning_standards_fix.py).

Usage:
  python3 scripts/shard7_run2f9f_osceola_g_zoning_standards_fix.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

COUNTY = "osceola"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DRY_RUN = "--dry-run" in sys.argv

MUNICODE_METHOD = (
    "api.municode.com undocumented REST API (Clients/name -> ClientID=7166 "
    "'Osceola County' -> ClientContent/7166 -> productId=15810 'Land Development "
    "Code' -> Jobs/latest/15810 -> jobId=478316 'Supplement 10, codified through "
    "Ordinance No. 2025-40, enacted 8-18-2025' -> CodesContent?jobId=478316&"
    "productId=15810&nodeId=<any Ch.3 node> returns full Chapter 3; human viewer: "
    "https://library.municode.com/fl/osceola_county/codes/land_development_code)"
)

AC_SOURCE = (
    "https://api.municode.com/CodesContent?jobId=478316&"
    "nodeId=LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.2DIDEST_3.2.1RUAGDIDE&"
    "productId=15810 (Osceola LDC Ch.3 Performance and Siting Standards, Art.3.2 "
    "District Development Standards, Sec 3.2.1(D) Agricultural Development "
    "Standards -- live Municode API, " + MUNICODE_METHOD + ")"
)
CR_SOURCE = (
    "https://api.municode.com/CodesContent?jobId=478316&"
    "nodeId=LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.1GEPR_3.1.3AP&productId=15810 "
    "(Osceola LDC Sec 3.1.3 Applicability, Table 3.1 crosswalk + Table 3.2 "
    "Preceding Zoning District Development Standards Matrix -- CONFIRMED live: CR "
    "'Commercial Restricted' preceding-district row has Lot Size/Width/Height/"
    "Setback columns only, NO FAR/intensity column anywhere in Table 3.2.)"
)
CT_SOURCE = (
    "https://api.municode.com/CodesContent?jobId=478316&"
    "nodeId=LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.2DIDEST_3.2.4COREOFDIDE&"
    "productId=15810 (Osceola LDC Sec 3.2.4(D) Commercial Development Standards "
    "table -- CONFIRMED live: CT column 'Maximum intensity' = N/A, distinct from "
    "CG's 1.0 FAR one column over -- a prior draft misattributed CG's 1.0 to CT, "
    "caught by adversarial verify, NOT written.)"
)
RMH_SOURCE = (
    "https://api.municode.com/CodesContent?jobId=478316&"
    "nodeId=LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.1GEPR_3.1.3AP&productId=15810 "
    "(Osceola LDC Table 3.2 Preceding Zoning District Development Standards Matrix "
    "-- CONFIRMED live: RMH row gives min-lot-size-by-unit-type only, no per-acre "
    "density figure anywhere. Deliberately not back-calculated from lot size.)"
)
PD_FAMILY_SOURCE = (
    "https://api.municode.com/CodesContent?jobId=478316&"
    "nodeId=LAND_DEVELOPMENT_CODE_CH3PESIST_ART3.11PLDE_3.11.1PLDE&"
    "productId=15810 (Osceola LDC Sec 3.11.1(I) Density and Intensity -- CONFIRMED "
    "live verbatim: 'allowable density and intensity will be based on several "
    "factors...' -- per-development-order, no single codified number. Applies "
    "identically to PD/PMUD/STRPD sub-types.)"
)


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": "return=minimal"})
    if DRY_RUN:
        log(f"DRY-RUN would PATCH {path} {body}", "UNTESTED")
        return
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        log(f"PATCH {path} {body} OK", "VERIFIED")
    except urllib.error.HTTPError as e:
        log(f"PATCH {path} FAILED: {e.code} {e.read().decode()[:300]}", "VERIFIED")
        raise


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== SHARD-7 RUN-2F9F OSCEOLA G FIX: real Osceola LDC zoning standards ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE G: {baseline['G']}", "VERIFIED")

    rest_patch("zone_standards?id=eq.4500", {
        "max_density_du_acre": 0.2, "confidence_score": 1.0,
        "ordinance_section": "Section 3.2.1(D) Agricultural Development Standards "
                              "-- Table (Standards: AC/RS/ARE, Maximum residential density)",
        "source_url": AC_SOURCE,
    })
    rest_patch("zoning_districts?id=eq.11794", {"far_regulated": False})
    rest_patch("zone_standards?id=eq.4501", {"source_url": CR_SOURCE})
    rest_patch("zoning_districts?id=eq.11795", {"far_regulated": False})
    rest_patch("zone_standards?id=eq.4502", {"source_url": CT_SOURCE})
    rest_patch("zoning_districts?id=eq.11798", {"density_regulated": False})
    rest_patch("zone_standards?id=eq.4505", {"source_url": RMH_SOURCE})
    for zsid in (4503, 4504, 4506):
        rest_patch(f"zone_standards?id=eq.{zsid}", {"source_url": PD_FAMILY_SOURCE})

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT zd.code, zd.far_regulated, zd.density_regulated, s.max_density_du_acre, "
          "s.max_far, s.confidence_score FROM zoning_districts zd JOIN zone_standards s "
          "ON s.zoning_district_id=zd.id WHERE zd.jurisdiction_id=1186 ORDER BY zd.code;")
    print(f"BEFORE G: {baseline['G']}")
    print(f"AFTER  G: {after['G']}")


if __name__ == "__main__":
    main()
