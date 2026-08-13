#!/usr/bin/env python3
"""
Manatee G (density sub-metric): fix the 2 concrete, real-ordinance-backed gaps
found via live diagnosis of pencil_dod_evaluate_county('manatee') (baseline
G=94.4%, "density=94.4 far=100.0 pk1000=100.0" -- density is the sole binder).

Diagnosis method: joined manatee's live parcel_zones (154 distinct auction
parcels) to zoning_districts by (jurisdiction_id, zone_code), then to
zone_standards, restricted to districts where density_regulated IS DISTINCT
FROM false (True or NULL both count as "applicable" per the exact predicate
in refresh_zoning_applicability_evidence(), migrations/
20260721_gold_standard_shard6_run5361_sarasota_g_far_guard_allowlist.sql).
Found exactly 3 gap districts actually used by manatee auction parcels:

  1. GC   (jurisdiction_id=1257, Unincorporated Manatee, zoning_districts.id=10894)
       -- General Commercial. density_regulated=NULL, zone_standards row exists
          (max_far=0.5) but max_density_du_acre=NULL. 1 auction parcel (5397800003).
       -- REAL FIX: Manatee County LDC Chapter 4 (official mymanatee.org PDF,
          "ldc-ch4-zoning-v64-comments.pdf", doc page 4-15 / PDF page 44) states
          verbatim: "In the NC, GC and HC zoning districts, single family and
          duplex dwellings may be allowed subject to the following criteria: ...
          3. Shall not violate the maximum gross density requirement of nine (9)
          dwelling units per acre". This is a real, quotable, county-sourced cap
          -> max_density_du_acre = 9.0, confidence 0.65 (draft/comments-version
          LDC PDF, single document, but explicit verbatim figure with citable
          section; corroborated contextually by the county's own Comprehensive
          Plan using the same "9 dwelling units per acre" figure for
          activity-node / affordable-housing bonus density elsewhere).

  2. VIL  (jurisdiction_id=1257, Unincorporated Manatee, zoning_districts.id=11248)
       -- Village district (Myakka City, Parrish, Rubonia). density_regulated=NULL,
          NO zone_standards row at all. 3 distinct auction parcels (2104000050,
          413100209, 2091900007).
       -- REAL FINDING (not a fillable number): same LDC Chapter 4 PDF, doc page
          4-2 (PDF page 3) cross-references VIL against THREE different Future
          Land Use categories simultaneously -- RES-3 (3 DU/GA), RES-6 (6 DU/GA),
          AND RES-9 (9 DU/GA) all list VIL as a compatible zoning district. PDF
          page 44 states explicitly for the analogous PR district: "The underlying
          Future Land Use Category shall determine the maximum density on each
          site" -- i.e. VIL has NO single fixed district-level max_density_du_acre;
          it is FLU-driven per parcel, exactly like the PD-R/PD-MU planned-
          development districts already correctly marked density_regulated=false
          in this same jurisdiction. Filling a single number here would be
          fabrication (Honesty Protocol CRITICAL). Correct fix: density_regulated
          = false, matching the PD-R/PD-MU precedent already in the DB.

  NOT FIXED (left honestly unresolved): BR_T4-R (jurisdiction_id=888, City of
  Bradenton, zoning_districts.id=11258, Form-Based Code "T4-R" / General Urban
  Restricted). 2 auction parcels (4324500000, 4401300001). WebSearch + WebFetch
  this session found only indirect/conflicting density figures (60 du/ac
  "by right" city-wide floor, 200 du/ac Urban Core cap subject to council
  approval, 15-20 du/ac "High Density Residential" FLU bonus) -- none of them
  a verified T4-R-specific base density from Bradenton's actual Form-Based Code
  document (not fetchable this session: totalcommercial.com's "FBC T4-R
  Development Standards" PDF turned out to be a zoning atlas street map with no
  standards table; Municode returns 403 on direct fetch for Bradenton's
  code_of_ordinances). Left NULL/density_regulated=NULL rather than guessed --
  same "ordinance section unconfirmed" flag already present in this row's
  `name` column from a prior session (shard_manatee_i_zoning.py).

dispatch_id: 7bcb4434-c068-4a5d-b140-0dcf65c8c87f (pair manatee-G)
"""
import os
import sys

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

GC_DISTRICT_ID = 10894
VIL_DISTRICT_ID = 11248

GC_SOURCE = (
    "Manatee County LDC Chapter 4 Zoning (official mymanatee.org PDF "
    "'ldc-ch4-zoning-v64-comments.pdf'), doc p.4-15: 'In the NC, GC and HC "
    "zoning districts, single family and duplex dwellings may be allowed "
    "subject to the following criteria: ... Shall not violate the maximum "
    "gross density requirement of nine (9) dwelling units per acre.'"
)


def main():
    with httpx.Client(timeout=30) as client:
        # 1. GC: insert zone_standards row with real max_density_du_acre=9.0,
        #    preserving the existing far/parking values already on file.
        r = client.get(
            f"{BASE}/zone_standards",
            headers=HEADERS,
            params={"zoning_district_id": f"eq.{GC_DISTRICT_ID}", "select": "*"},
        )
        r.raise_for_status()
        existing = r.json()
        if not existing:
            print("FAIL: expected an existing zone_standards row for GC (id=10894), found none. Aborting.")
            sys.exit(1)
        row = existing[0]
        if row.get("max_density_du_acre") is not None:
            print(f"SKIP: GC zone_standards.max_density_du_acre already set to {row['max_density_du_acre']}, not overwriting.")
        else:
            patch = {
                "max_density_du_acre": 9.0,
                "source_url": "https://www.mymanatee.org/media/docs/default-source/development-services-department-documents/development-services-department-documents/land-development-regulations/ldc-ch4-zoning-v64-comments.pdf",
                "ordinance_section": "LDC Ch.4 p.4-15, note on NC/GC/HC residential density cap",
                "confidence_score": 0.65,
            }
            pr = client.patch(
                f"{BASE}/zone_standards",
                headers=HEADERS,
                params={"zoning_district_id": f"eq.{GC_DISTRICT_ID}"},
                json=patch,
            )
            pr.raise_for_status()
            print(f"GC zone_standards PATCH -> {pr.status_code}, {len(pr.json())} row(s) updated: {pr.json()}")

        # 2. VIL: mark density_regulated=false (FLU-driven, no single fixed
        #    district value per LDC text -- matches PD-R/PD-MU precedent).
        vr = client.get(
            f"{BASE}/zoning_districts",
            headers=HEADERS,
            params={"id": f"eq.{VIL_DISTRICT_ID}", "select": "id,code,density_regulated"},
        )
        vr.raise_for_status()
        vil_rows = vr.json()
        if not vil_rows:
            print("FAIL: expected zoning_districts row id=11248 (VIL), found none. Aborting.")
            sys.exit(1)
        if vil_rows[0]["density_regulated"] is False:
            print("SKIP: VIL density_regulated already false.")
        else:
            vp = client.patch(
                f"{BASE}/zoning_districts",
                headers=HEADERS,
                params={"id": f"eq.{VIL_DISTRICT_ID}"},
                json={"density_regulated": False},
            )
            vp.raise_for_status()
            print(f"VIL zoning_districts PATCH -> {vp.status_code}, {len(vp.json())} row(s) updated: {vp.json()}")

        # 3. Verify live via pencil_dod_evaluate_county
        er = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"p_county": "manatee"},
        )
        er.raise_for_status()
        print("\nLIVE VERIFY pencil_dod_evaluate_county(manatee):")
        print(er.json())


if __name__ == "__main__":
    main()
