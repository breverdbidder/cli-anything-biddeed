#!/usr/bin/env python3
"""
GOLD STANDARD (issue #19807, shard-5 pasco/manatee/sumter): sumter E+I+J,
4th documented attempt on the persistent 3-row gap (074/129/448).

ROOT-CAUSE RECHECK (live 2026-09-03, before writing anything):
  - 2026-CA-000074 (RATLIFF) and 2026-CA-000129 (STRONG v YOUNG): re-fetched
    scripts/clerk_ssot/parsers/sumter.py's parse_foreclosure() live — both
    still carry ONLY case_title (plaintiff -vs- defendant) + sale_date, no
    address field, matching sumter_eij_3row_owner_address_dead_end_20260827.sql's
    finding verbatim. Also re-tried the sumter.realforeclose.com AJAX lane
    (harvest_date, same module manatee's fix below reuses) for their 3 sale
    dates live — 0 items returned for all 3, confirming Sumter foreclosures
    are NOT on RealForeclose (sumterclerk_foreclosure is the sole source, as
    already documented). CONFIRMED DEAD, 3rd/4th independent re-check, no new
    lever found this session either — NOT enriched, no write attempted.
  - 2024-CA-000448 (NATIONSTAR MORTGAGE LLC -V- TRENTIN PENLEY): NEW case
    (created_at 2026-09-03, this session's own scrape run), never attempted
    before. WebSearch surfaced a Sumter County government agenda document
    naming "Penley Trentin James & Botelho Megan Ann (JT)" as owner of
    3170 CR 421, Lake Panasoffkee FL 33538, parcel F30D019 — independently
    CONFIRMED against fl_parcels (co_no=70, parcel_id=F30D019, own_name=
    "PENLEY TRENTIN JAMES & BOTELHO", phy_addr1="3170 CR 421", exact address
    match, unusual first name "Trentin" = high-confidence unique match, not
    a common-name collision). RESOLVED.

ADDITIONAL I-ONLY GAP (address/geo/value already present, zone_code missing):
  - 2026-CA-000090 (D28E030, The Villages): the 2026-08-27 dead-end doc
    concluded "no genuine zone_code" after querying Sumter's
    DevelopmentServices/Development_Services MapServer layers 5/10 (WRONG
    endpoint for this check — those are FLU layers, and the working I-fix
    precedent in supabase/migrations/20260711_shard9_sumter_i_real_zoning_
    gis_wiring.sql actually uses Interactive/FLU_Zoning/FeatureServer/11/10).
    Queried FeatureServer/11 by exact Parcel=D28E030 match live this
    session: 1 feature, Zone_Type=RPUD. The 08-27 conclusion was wrong about
    which endpoint to use, not about the data itself — RESOLVED.
  - 2025-CA-000515 (G04N163): never checked. FeatureServer/11 (county layer)
    returned 0 features; FeatureServer/10 (Wildwood municipal, PIN-keyed)
    returned 1 feature, Zoning_Cur=CMU. Wildwood jurisdiction_id=950 (not
    1325/Sumter-County-unincorporated). RESOLVED.

Sources for zone codes (both real, live, exact-key GIS queries, no
inference/guessing):
  https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/
    FLU_Zoning/FeatureServer/11  (field: Parcel, attr: Zone_Type)
  https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/
    FLU_Zoning/FeatureServer/10  (field: PIN, attr: Zoning_Cur)

Geocode for F30D019 (fl_parcels has no centroid_lat/lng for this parcel):
  US Census Bureau public geocoder (geocoding.geo.census.gov, TIGER/Line,
  federal government service) — matched "3170 CR 421, Lake Panasoffkee, FL
  33538" exactly, benchmark Public_AR_Current.

Two of the three E/I/J-blocking rows remain genuinely blocked at the source
(no address exists on sumterclerk.com for 074/129, and no independent lever
reaches them — Turnstile-gated secondary sources unchanged from prior
sessions). E/I/J will improve but NOT reach the 95% gate this session
(31/33 = 93.9% for all three, need 32/33) — reported honestly, not silently
declared PASS.

dispatch_id: 33847d2f-ce63-400d-a68e-e2971b0c13bd
"""
import json
import os
import re

import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}


def patch_mca(case_number, payload):
    r = requests.patch(f"{SB}/rest/v1/multi_county_auctions", headers=H,
                        params={"case_number": f"eq.{case_number}", "county": "eq.sumter"},
                        data=json.dumps(payload), timeout=30)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"PATCH FAILED {case_number}: {r.status_code} {r.text[:300]}")
    body = r.json() if r.text else []
    if not body:
        raise RuntimeError(f"Fail-loud: PATCH {case_number} matched 0 rows")
    print(f"  MCA PATCH ok {case_number}: {list(payload.keys())}")


def insert_parcel_zone(parcel_id, jurisdiction_id, zone_code, source):
    existing = requests.get(f"{SB}/rest/v1/parcel_zones", headers=H,
                             params={"parcel_id": f"eq.{parcel_id}", "select": "id"}, timeout=30).json()
    if existing:
        print(f"  parcel_zones already has {parcel_id} (id={existing[0]['id']}) — skip (idempotent)")
        return
    row = {"parcel_id": parcel_id, "tax_account": parcel_id, "jurisdiction_id": jurisdiction_id,
           "zone_code": zone_code, "source": source}
    r = requests.post(f"{SB}/rest/v1/parcel_zones", headers=H, data=json.dumps([row]), timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Fail-loud: parcel_zones insert failed for {parcel_id}: {r.status_code} {r.text[:300]}")
    print(f"  parcel_zones inserted {parcel_id} -> zone_code={zone_code} jurisdiction={jurisdiction_id}")


def percentile(vals, p):
    if not vals:
        return None
    vals = sorted(float(v) for v in vals)
    n = len(vals)
    idx = (n - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return vals[lo] + frac * (vals[hi] - vals[lo])


def get_comps_dedup(zip_, dor_uc):
    params = {"co_no": "eq.70", "phy_zipcd": f"eq.{zip_}", "dor_uc": f"eq.{dor_uc}",
              "sale_yr1": "gte.2022", "sale_prc1": "gt.1000", "select": "sale_prc1", "limit": 1000}
    r = requests.get(f"{SB}/rest/v1/fl_parcels", headers=H, params=params, timeout=30)
    r.raise_for_status()
    seen, dedup = set(), []
    for row in r.json():
        p = row.get("sale_prc1")
        if p and p not in seen:
            seen.add(p)
            dedup.append(p)
    return dedup


def repairs_tier(arv):
    if arv < 100_000:
        return 25_000
    elif arv < 250_000:
        return 20_000
    elif arv < 500_000:
        return 15_000
    return 12_000


def shapira_max_bid(arv, repairs):
    profit_floor = min(25000.0, 0.15 * arv)
    return max(0.0, (arv * 0.70) - repairs - profit_floor)


def compute_j_row_448():
    zip_, dor_uc = "33538", "001"
    prices = get_comps_dedup(zip_, dor_uc)
    n = len(prices)
    jv, av_sd = 77590, 77590
    if n >= 3:
        p75, p25 = percentile(prices, 75), percentile(prices, 25)
        arv, cma_distressed, cma_resale = round(p75, 2), round(p25, 2), round(p75, 2)
        honesty = "INFERRED"
        note = f"{n} real deduplicated sold comps (fl_parcels, co_no=70, same zip+DOR use code, sold since 2022, bulk-deed duplicate prices collapsed)"
        arv_source = f"fl_parcels_comps_p75_zip_dor_uc_dedup_bulk_n{n}"
    else:
        arv = max(jv, av_sd)
        cma_distressed, cma_resale = round(arv * 0.87, 2), round(arv * 1.12, 2)
        honesty = "INFERRED_NO_COMPS"
        note = "assessed_value proxy (no qualifying comps found for this use code/zip)"
        arv_source = f"assessed_value_proxy_n{n}_comps_insufficient"

    repairs = repairs_tier(arv)
    max_bid = round(shapira_max_bid(arv, repairs), 2)

    owner = "PENLEY TRENTIN JAMES & BOTELHO"
    is_multi_owner = "&" in owner
    distress_owner = 0.48 if is_multi_owner else 0.50
    distress_property = 0.40  # improved residential, dor_uc=001

    # No judgment_amount scraped for this case (sumterclerk.com list carries
    # no dollar figure for foreclosures, only case_title/sale_date) — debt
    # ratio left at its most conservative (lowest-distress) bucket rather
    # than fabricating a judgment figure.
    distress_location = 0.20

    spread = (cma_resale - cma_distressed) / cma_resale if cma_resale else 0.3
    ml_score = round(min(0.95, max(0.15, (distress_owner + distress_property + distress_location) / 3 * (1 - spread * 0.3) + 0.15)), 4)
    confidence = round(0.5 + (n / 500) * 0.3, 4) if n >= 3 else 0.35

    return {
        "case_number": "2024-CA-000448",
        "county_slug": "sumter",
        "parcel_id": "F30D019",
        "address": "3170 CR 421, LAKE PANASOFFKEE, FL 33538",
        "auction_date": "2026-10-29",
        "arv": round(arv, 2),
        "repairs": repairs,
        "final_judgment": None,
        "max_bid": max_bid,
        "bid_judgment_ratio": None,
        "recommendation": "REVIEW",
        "confidence": confidence,
        "ml_score": ml_score,
        "factors": {
            "distress_location": distress_location,
            "distress_property": distress_property,
            "distress_owner": distress_owner,
            "cma_distressed": {"value": cma_distressed, "note": f"p25 percentile of {note}", "honesty_marker": honesty},
            "cma_resale": {"value": cma_resale, "note": f"p75 percentile of {note}", "honesty_marker": honesty},
        },
        "arv_source": arv_source,
        "pipeline_run_id": "GOLDSTANDARD-19807-SUMTER-EIJ-v1",
        "pipeline_version": "sumter_eij_run19807",
    }


def main():
    print("=== 2024-CA-000448 (PENLEY) — MCA enrichment ===")
    patch_mca("2024-CA-000448", {
        "property_address": "3170 CR 421, LAKE PANASOFFKEE, FL 33538",
        "city": "LAKE PANASOFFKEE",
        "zip": "33538",
        "parcel_id": "F30D019",
        "assessed_value": 77590,
        "market_value": 77590,
        "latitude": 28.802623418566,
        "longitude": -82.1405617233,
        "owner_name": "PENLEY TRENTIN JAMES & BOTELHO",
        "geo_source": "us_census_geocoder_TIGER_public_AR_current",
    })

    print("=== parcel_zones inserts (real GIS, exact Parcel/PIN match) ===")
    insert_parcel_zone("F30D019", 1325, "R6C",
                        "sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=F30D019:2026-09-03")
    insert_parcel_zone("D28E030", 1325, "RPUD",
                        "sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D28E030:2026-09-03")
    insert_parcel_zone("G04N163", 950, "CMU",
                        "sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=G04N163:2026-09-03")

    print("=== bid_decisions insert for 2024-CA-000448 (J) ===")
    row = compute_j_row_448()
    r = requests.post(f"{SB}/rest/v1/bid_decisions", headers=H, data=json.dumps([row]), timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Fail-loud: bid_decisions insert failed: {r.status_code} {r.text[:500]}")
    inserted = r.json()
    if len(inserted) != 1:
        raise RuntimeError(f"Fail-loud: parsed=1 inserted={len(inserted)}")
    print(f"  J OK 2024-CA-000448: arv={row['arv']} max_bid={row['max_bid']} ml_score={row['ml_score']}")

    print("\n2026-CA-000074 (RATLIFF) and 2026-CA-000129 (STRONG/YOUNG): "
          "CONFIRMED DEAD this session (re-verified, no write). See docstring.")


if __name__ == "__main__":
    main()
