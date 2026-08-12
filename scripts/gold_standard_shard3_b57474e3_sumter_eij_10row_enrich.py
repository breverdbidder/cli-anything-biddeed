#!/usr/bin/env python3
"""
GOLD STANDARD shard-3 (dispatch b57474e3-1a2a-4938-bb03-a5e57905841e): sumter
E/I/J fix -- 10-row enrichment for auctions scraped since the prior 11-row
(10 real + D29A024) baseline.

ROOT CAUSE (verified live 2026-08-12): 10 NEW sumter multi_county_auctions rows
(3 foreclosure cases scraped 2026-08-10, 7 tax_deed cases scraped 2026-08-10)
had ONLY case_number populated -- no parcel_id, address, geo, or value. This
dragged E (parcel_linked), I (card_complete), and J (deal_complete) from
100% (11/11) down to 52.4% (11/21) each.

DATA SOURCES (all live, real, cross-verified same session -- see the companion
migration supabase/migrations/20260812_gold_standard_shard3_b57474e3_sumter_eij_10row_zoning_link.sql
for the parcel_zones/zoning_districts/zone_standards half of this fix):
  1. https://www.sumterclerk.com/courts/foreclosures/foreclosure-sales/ -- live
     HTML listing the 3 foreclosure cases with real address + judgment amount.
  2. https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/ -- live
     HTML page with embedded JSON listing the 7 tax_deed cases: parcel number,
     opening bid, cert holder, owner name.
  3. https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
     Sumter_Geocoder/GeocodeServer -- geocoded the 3 foreclosure addresses
     (parcel_id unknown until geocoded) to a lat/long point.
  4. https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
     Florida_Statewide_Cadastral/FeatureServer/0 -- FL DOR statewide cadastral.
     Tax-deed parcels queried by exact PARCEL_ID. Foreclosure parcels located
     by point-in-polygon spatial intersection at the geocoded address point
     (PARCEL_ID was unknown beforehand). OWN_NAME on every one of the 10
     returned features independently cross-matches the party/owner name
     already scraped from sumterclerk.com (e.g. G06H058 -> "NEWTON MARY
     ESTATE" matches cert 779's clerk-scraped owner "NEWTON, MARY ESTATE";
     J05-050 -> "ARNOLD ALMA JOY" matches case 2025-CA-000642's defendant
     "ALMA JOY ARNOLD"). No ambiguity.
  5. fl_parcels table (co_no=70, same FL DOR extract already loaded into
     Supabase) -- used for the J-criterion real-comps CMA (see below).

property_address left NULL for 4 of the 10 rows (J16C020/case 1078,
M06C003/case 1159, C27-268/case 104, G06H033/case 776) because FL DOR's own
PHY_ADDR1 field is blank for all 4 -- confirmed live, same class of genuine
"no situs address" gap as the already-documented D29A024 case. This is why I
(card_complete) settles at 81.0% (17/21) rather than 100% -- a real residual,
not a research gap (qpublic.schneidercorp.com, the only other candidate
source, returns HTTP 403 WAF block, the same dead end already documented for
D29A024 in the 2026-07-25 session).

J-CRITERION METHODOLOGY (two-arm real CMA, NOT flat-constant ghost data --
see scripts/gold_standard_shard2_13b31f39_sumter_j_ghostfix.py's docstring for
what NOT to repeat):
  For each of the 10 parcels, pulled REAL sold comps from fl_parcels
  (co_no=70, same zip + DOR use code bucket, sale_yr1>=2022, sale_prc1>1000).
  IMPORTANT DATA-QUALITY FIX discovered this session: FL DOR's sale_prc1 field
  records the SAME price on every parcel in a multi-parcel/subdivision bulk
  deed (confirmed live: 291 "sales" in zip 34785/dor_uc=000 collapsed to only
  60 unique prices, several repeated 7-35x, e.g. $4,875,000 x10, $1,995,000
  x27). Treating each repetition as an independent comp would fabricate wildly
  inflated ARVs (a naive first pass on G06H058 produced ARV=$1,995,000 for an
  $11,930-assessed vacant lot -- a 167x multiplier, rejected as implausible
  and not shipped). FIX: deduplicate by exact sale_prc1 before computing
  percentiles, and for vacant-land codes (dor_uc 000/076) also bound comps to
  0.4x-2.5x of the subject's own lnd_sqfoot to avoid pooling in unrelated
  commercial-scale parcels that happen to share the same zip/use-code. ARV =
  p75 of deduplicated comps, cma_distressed = p25, cma_resale = p75 (same
  percentile convention as scripts/shard4_17123_session_executor.py's
  fl_parcels comps methodology).
  ONE parcel (C27-268, DOR use code 076 = cemetery) had ZERO comps -- confirmed
  live that ALL 35 dor_uc=076 parcels in Sumter have sale_prc1=0 (cemetery
  land does not transact on the open market). Fell back to assessed_value
  proxy (JV=$11,780), honestly labeled honesty_marker="INFERRED_NO_COMPS" in
  factors, matching the existing fallback pattern already used by the passing
  TD-5054/TD-5056/TD-5058 rows.
  distress_owner/distress_property/distress_location all vary per-property
  (estate/trustee ownership, vacant-vs-improved DOR code, debt-to-assessed-
  value ratio) -- genuinely computed from real per-row data, not a repeated
  constant.

WRITES PERFORMED (all live, this session, verified via response row counts):
  1. 10 PATCH requests to multi_county_auctions (parcel_id, property_address
     where real, latitude, longitude, assessed_value, market_value).
  2. 10 POST rows to bid_decisions (arv, repairs, max_bid, ml_score, factors
     with the 5 required keys, confidence, recommendation).
  (parcel_zones / zoning_districts / zone_standards writes are in the
  companion SQL migration, applied live via PostgREST in the same session.)

RESULT (verified via pencil_dod_evaluate_county('sumter'), fresh call after
all writes): E 52.4%->100.0% PASS. J 52.4%->100.0% PASS. I 52.4%->81.0%,
still FAIL -- genuine residual (4 addressless vacant parcels), not fabricated.
G (explicitly out of scope) dipped 100.0%->72.7% mid-session as an UNINTENDED
side effect of inserting zoning_districts rows with no zone_standards density
value, then was restored to 100.0% by sourcing real Table 13-423A/13-414A
density standards for R4C/R6M/A10C from Sumter's own LDC (see migration file
docstring for full detail) -- confirmed zero net regression on any
previously-passing letter.
"""
import os
import json
import re
import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

FL_DOR_CADASTRAL_URL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)

# ── multi_county_auctions enrichment (real, live-sourced 2026-08-12) ─────────
MCA_UPDATES = {
    "2025-CA-000214": {
        "parcel_id": "D13L032", "property_address": "468 HILDALGO DR, THE VILLAGES, FL 32159",
        "latitude": 28.927214, "longitude": -81.966073,
        "assessed_value": 209120, "market_value": 209120,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "2025-CA-000642": {
        "parcel_id": "J05-050", "property_address": "1149 CR 464, LAKE PANASOFFKEE, FL 33538",
        "latitude": 28.777818, "longitude": -82.123111,
        "assessed_value": 62390, "market_value": 62390,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "2023-CA-000629": {
        "parcel_id": "N17G509", "property_address": "1691 CR 607C, BUSHNELL, FL 33513",
        "latitude": 28.655708, "longitude": -82.132279,
        "assessed_value": 141240, "market_value": 141240,
        "assessed_value_source": "fl_dor_statewide_cadastral_pip_geocoded",
    },
    "779": {
        "parcel_id": "G06H058", "property_address": "503 ORANGE ST, WILDWOOD, FL 34785",
        "latitude": 28.858984, "longitude": -82.046563,
        "assessed_value": 11930, "market_value": 11930,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
    "1078": {
        "parcel_id": "J16C020",
        "latitude": 28.755206, "longitude": -82.118845,
        "assessed_value": 11040, "market_value": 11040,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
    "1159": {
        "parcel_id": "M06C003",
        "latitude": 28.694554, "longitude": -82.244666,
        "assessed_value": 9890, "market_value": 9890,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
    "104": {
        "parcel_id": "C27-268",
        "latitude": 28.887301, "longitude": -82.087579,
        "assessed_value": 11780, "market_value": 11780,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
    "1400": {
        "parcel_id": "N33-021", "property_address": "349 C 478 W, WEBSTER, FL 33597",
        "latitude": 28.616703, "longitude": -82.110109,
        "assessed_value": 6900, "market_value": 6900,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
    "776": {
        "parcel_id": "G06H033",
        "latitude": 28.858752, "longitude": -82.046009,
        "assessed_value": 16900, "market_value": 16900,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
    "593": {
        "parcel_id": "F32Q059", "property_address": "1637 CR 435, LAKE PANASOFFKEE, FL 33538",
        "latitude": 28.793068, "longitude": -82.131623,
        "assessed_value": 20370, "market_value": 23650,
        "assessed_value_source": "fl_dor_statewide_cadastral",
    },
}
# Rows with no key: property_address are genuinely blank in FL DOR (PHY_ADDR1
# NULL) -- NOT written, per BLANK > WRONG (see docstring).

# ── J-criterion inputs: parcel/dor_uc/zip/value/owner per case ───────────────
J_ROWS = {
    "2025-CA-000214": {"parcel": "D13L032", "dor_uc": "001", "zip": "32159", "jv": 209120, "av_sd": 209120, "lnd": 3600, "own": "PARKS THOMAS L", "sale_type": "foreclosure", "judgment": 128701.08, "address": "468 HILDALGO DR", "auction_date": "2026-08-20"},
    "2025-CA-000642": {"parcel": "J05-050", "dor_uc": "001", "zip": "33538", "jv": 62390, "av_sd": 62390, "lnd": 18461, "own": "ARNOLD ALMA JOY", "sale_type": "foreclosure", "judgment": 249979.26, "address": "1149 CR 464", "auction_date": "2026-09-17"},
    "2023-CA-000629": {"parcel": "N17G509", "dor_uc": "001", "zip": "33513", "jv": 141240, "av_sd": 141240, "lnd": 9545, "own": "RYDER TERRI LYNNE", "sale_type": "foreclosure", "judgment": 311693.20, "address": "1691 CR 607C", "auction_date": "2026-10-01"},
    "779":  {"parcel": "G06H058", "dor_uc": "000", "zip": "34785", "jv": 11930, "av_sd": 11930, "lnd": 22950, "own": "NEWTON MARY ESTATE", "sale_type": "tax_deed", "opening_bid": 1970.65, "address": "503 ORANGE ST", "auction_date": "2026-09-10"},
    "1078": {"parcel": "J16C020", "dor_uc": "000", "zip": "0", "jv": 11040, "av_sd": 11040, "lnd": 20983, "own": "JACKSON MARTIN", "sale_type": "tax_deed", "opening_bid": 1607.28, "address": None, "auction_date": "2026-09-10"},
    "1159": {"parcel": "M06C003", "dor_uc": "000", "zip": "0", "jv": 9890, "av_sd": 9890, "lnd": 18750, "own": "CROMER BRENDA", "sale_type": "tax_deed", "opening_bid": 1452.45, "address": None, "auction_date": "2026-09-10"},
    "104":  {"parcel": "C27-268", "dor_uc": "076", "zip": "0", "jv": 11780, "av_sd": 11780, "lnd": 27007, "own": "TRUSTEES OF THE OAK HILL CEMETERY", "sale_type": "tax_deed", "opening_bid": 2266.86, "address": None, "auction_date": "2026-09-10"},
    "1400": {"parcel": "N33-021", "dor_uc": "000", "zip": "33597", "jv": 6900, "av_sd": 6900, "lnd": 13068, "own": "GRINER ANDREW & SEAN (JTWROS)", "sale_type": "tax_deed", "opening_bid": 1497.80, "address": "349 C 478 W", "auction_date": "2026-09-10"},
    "776":  {"parcel": "G06H033", "dor_uc": "000", "zip": "0", "jv": 16900, "av_sd": 16900, "lnd": 32500, "own": "JONES CARRIE MAE", "sale_type": "tax_deed", "opening_bid": 2289.21, "address": None, "auction_date": "2026-09-10"},
    "593":  {"parcel": "F32Q059", "dor_uc": "002", "zip": "33538", "jv": 23650, "av_sd": 20370, "lnd": 3980, "own": "WINCHELL JOHN M & LEE CINDY SMITH", "sale_type": "tax_deed", "opening_bid": 12222.58, "address": "1637 CR 435", "auction_date": "2026-09-10"},
}


def percentile(vals, p):
    if not vals:
        return None
    vals = sorted(float(v) for v in vals if v is not None)
    n = len(vals)
    idx = (n - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return vals[lo] + frac * (vals[hi] - vals[lo])


def get_comps_dedup(zip_, dor_uc, lnd_sqfoot=None):
    """Fetch real fl_parcels comps and dedupe by exact sale_prc1 -- FL DOR
    records the SAME deed price on every parcel in a multi-parcel bulk sale,
    which is not a real per-lot comp (see module docstring)."""
    params = {
        "co_no": "eq.70",
        "phy_zipcd": f"eq.{zip_}",
        "dor_uc": f"eq.{dor_uc}",
        "sale_yr1": "gte.2022",
        "sale_prc1": "gt.1000",
        "select": "sale_prc1,lnd_sqfoot",
        "limit": 1000,
    }
    if lnd_sqfoot:
        lo = int(lnd_sqfoot * 0.4)
        hi = int(lnd_sqfoot * 2.5)
        params["lnd_sqfoot"] = f"gte.{lo}"
        params["and"] = f"(lnd_sqfoot.lte.{hi})"
    r = requests.get(f"{SB}/rest/v1/fl_parcels", headers=H, params=params, timeout=30)
    r.raise_for_status()
    rows = r.json()
    seen, dedup = set(), []
    for row in rows:
        p = row.get("sale_prc1")
        if p and p not in seen:
            seen.add(p)
            dedup.append(p)
    return dedup, len(rows)


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


def compute_j_row(case, r):
    is_vacant = r["dor_uc"] in ("000", "076")
    prices, raw_n = get_comps_dedup(r["zip"], r["dor_uc"], lnd_sqfoot=r["lnd"] if is_vacant else None)
    n = len(prices)

    if n >= 3:
        p75, p25 = percentile(prices, 75), percentile(prices, 25)
        arv, cma_distressed, cma_resale = round(p75, 2), round(p25, 2), round(p75, 2)
        method = "fl_parcels_comps_p75_sizebound0.4-2.5x_dedup_bulk" if is_vacant else "fl_parcels_comps_p75_zip_dor_uc_dedup_bulk"
        arv_source = f"{method}_n{n}"
        note_common = f"{n} real deduplicated sold comps (fl_parcels, co_no=70, same zip+DOR use code" + \
            (", land sqft within 0.4x-2.5x tolerance" if is_vacant else "") + \
            ", sold since 2022, bulk/subdivision-deed duplicate prices collapsed)"
        honesty = "INFERRED"
    else:
        arv = max(r["jv"], r["av_sd"])
        cma_distressed, cma_resale = round(arv * 0.87, 2), round(arv * 1.12, 2)
        arv_source = f"assessed_value_proxy_n{n}_comps_insufficient"
        note_common = "assessed_value proxy (no qualifying comps found for this use code/zip)"
        honesty = "INFERRED_NO_COMPS"

    repairs = repairs_tier(arv)
    max_bid = round(shapira_max_bid(arv, repairs), 2)

    owner = r["own"].upper()
    is_estate = bool(re.search(r"\b(ESTATE|TRUST|HEIRS?|DECEASED|DECD)\b", owner))
    is_entity = bool(re.search(r"\b(LLC|INC|CORP|LP|HOLDING|PROPERTIES|REALTY|TRUSTEES)\b", owner))
    is_multi_owner = "&" in owner or " AND " in owner
    if is_estate:
        distress_owner = 0.62
    elif is_entity:
        distress_owner = 0.30
    elif is_multi_owner:
        distress_owner = 0.48
    else:
        distress_owner = 0.50

    distress_property = 0.55 if is_vacant else 0.40

    debt = r.get("judgment") or r.get("opening_bid") or 0
    av = max(r["jv"], r["av_sd"]) or 1
    debt_ratio = debt / av
    if debt_ratio > 2.0:
        distress_location = 0.55
    elif debt_ratio > 1.0:
        distress_location = 0.42
    elif debt_ratio > 0.3:
        distress_location = 0.30
    else:
        distress_location = 0.20

    spread = (cma_resale - cma_distressed) / cma_resale if cma_resale else 0.3
    ml_score = round(min(0.95, max(0.15, (distress_owner + distress_property + distress_location) / 3 * (1 - spread * 0.3) + 0.15)), 4)
    confidence = round(0.5 + (n / 500) * 0.3, 4) if n >= 3 else 0.35

    opening_bid = r.get("opening_bid")
    bid_ratio = round(min(max_bid / opening_bid, 9.99), 4) if opening_bid else None
    recommendation = "BID" if (opening_bid and max_bid > opening_bid) else ("REVIEW" if not opening_bid else "PASS")

    return {
        "case_number": case,
        "county_slug": "sumter",
        "parcel_id": r["parcel"],
        "address": r.get("address"),
        "auction_date": r.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": repairs,
        "final_judgment": round(debt, 2) if debt else None,
        "max_bid": max_bid,
        "bid_judgment_ratio": bid_ratio,
        "recommendation": recommendation,
        "confidence": confidence,
        "ml_score": ml_score,
        "factors": {
            "distress_location": distress_location,
            "distress_property": distress_property,
            "distress_owner": distress_owner,
            "cma_distressed": {"value": cma_distressed, "note": f"p25 percentile of {note_common}", "honesty_marker": honesty},
            "cma_resale": {"value": cma_resale, "note": f"p75 percentile of {note_common}", "honesty_marker": honesty},
        },
        "arv_source": arv_source,
        "pipeline_run_id": "GOLDSTANDARD-SHARD3-b57474e3-SUMTER-EIJ-v1",
        "pipeline_version": "gold_standard_shard3_b57474e3_sumter_eij_v1",
    }


def patch_mca():
    ok = 0
    for case_number, payload in MCA_UPDATES.items():
        url = f"{SB}/rest/v1/multi_county_auctions?case_number=eq.{case_number}&county=eq.sumter"
        resp = requests.patch(url, headers=H, data=json.dumps(payload), timeout=30)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Fail-loud: PATCH failed for {case_number}: {resp.status_code} {resp.text[:500]}")
        rows = resp.json()
        if len(rows) != 1:
            raise RuntimeError(f"Fail-loud: expected 1 row updated for {case_number}, got {len(rows)}")
        print(f"MCA OK {case_number}: parcel_id={rows[0]['parcel_id']} address={rows[0]['property_address']}")
        ok += 1
    print(f"multi_county_auctions: {ok}/{len(MCA_UPDATES)} rows updated.")


def insert_bid_decisions():
    rows = [compute_j_row(case, r) for case, r in J_ROWS.items()]
    resp = requests.post(f"{SB}/rest/v1/bid_decisions", headers=H, data=json.dumps(rows), timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0: {resp.status_code} {resp.text[:1000]}")
    inserted = resp.json()
    if len(inserted) != len(rows):
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted={len(inserted)}")
    for r in inserted:
        print(f"J OK {r['case_number']}: arv={r['arv']} max_bid={r['max_bid']} ml_score={r['ml_score']}")
    print(f"bid_decisions: {len(inserted)}/{len(rows)} rows inserted.")


if __name__ == "__main__":
    patch_mca()
    insert_bid_decisions()
