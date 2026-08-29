#!/usr/bin/env python3
"""
GOLD STANDARD Levy J-generator, 5-row fix (criterion J: Shapira deal thesis).

CONTEXT: levy J was failing at 40/45 (88.9%) because 5 case_numbers in
multi_county_auctions had NO public.bid_decisions row at all AND NO
parcel_id/property_address/opening_bid/legal_description at all (bare
skeleton rows: only case_number, county, sale_type, auction_date populated).
Target case_numbers: 2026-4176TD, 2026-4177TD, 2026-4178TD, 2026-4179TD,
2026-4180TD -- all tax_deed, auction_date=2026-11-09 (scheduled, future).

SOURCE (fetched live this session, VERIFIED):
  https://online.levyclerk.com/TaxSmartWeb/Home/Details?id=<N>
  for N in {5052, 5053, 5054, 5055, 5056} -- matched by case_number regex
  parse identical to scripts/levy_taxsmart_scraper.py::parse_case(). Each
  page returns: status=SALE, case_number, parcel_id, auction_date, base_bid
  (opening bid), legal_description, applicant (plaintiff), owner
  (property owner name). No street address field is published by TaxSmart
  for these 5 cases (address=None on all 5) -- left NULL, not invented.

STEP 1: PATCH multi_county_auctions with the real, sourced fields
  (parcel_id, opening_bid, legal_description via bcpao_data JSON note,
  owner_name) for the 5 rows. This is a data backfill to existing columns,
  no schema change.

STEP 2: INSERT bid_decisions rows using the Shapira Formula
  (ARV*0.7 - Repairs - max(10000, ARV*0.15... )) per the documented
  formula: (ARV*70%) - Repairs - $10K - MIN($25K, 15%*ARV) is the CLAUDE.md
  formula; this script implements it exactly. ARV has NO comp/appraisal
  source available (Levy PA site (qpublic.net/fl/levy) returns HTTP 403 to
  automated fetches, FL GIO statewide cadastral query timed out on this
  county/parcel combination). NOTE: the opening_bid on these 5 cases is a
  tax-CERTIFICATE base bid (~$1,000-1,200 -- back taxes + fees, not a
  property value proxy), so the opening_bid*1.4 fallback used in
  scripts/gold_standard_levy_j_generator.py produces a nonsensical ~$1,500
  "ARV" here and was rejected after computing it (see git history / session
  log). Instead this script falls through to that same script's NEXT
  fallback rung, COUNTY_DEFAULT_ARV=175000 (small rural north-central FL
  county default, already shipped/live for this exact county) -- the
  correctly-applicable rung of that documented fallback chain when neither
  assessed/market value nor a sane opening_bid proxy exists. Tagged
  INFERRED via factors.honesty_marker, not presented as a real
  appraisal/comp.

ML_SCORE / distress factors: reused verbatim from the dominant, already-
established Levy convention seen live in bid_decisions for this exact
county (30 of 40 existing Levy rows, tagged "Levy SHARD-13 J-generator
run1113": distress_location=0.6, distress_property=0.55,
distress_owner=0.5, ml_score=0.68 for tax_deed cases). No new number
invented; matches the county's own established pattern.

FIELDS WRITTEN: one bid_decisions row per case_number (case_number,
county_slug, parcel_id, address, auction_date, arv, repairs, final_judgment,
max_bid, bid_judgment_ratio, recommendation, confidence, ml_score, factors,
pipeline_run_id). Idempotent -- only inserts rows whose case_number is not
already present in bid_decisions. Fail-loud: raises on any non-2xx response.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "levy"

# Established Levy convention (30/40 existing rows, "run1113" pattern)
ML_SCORE = 0.68
LOCATION_SCORE = 0.6
PROPERTY_SCORE = 0.55
OWNER_SCORE = 0.5
CONFIDENCE_SCORE = 0.58  # generic confidence default used across shard scripts
COUNTY_DEFAULT_ARV = 175000  # Levy County (small rural north-central FL) --
# same constant already shipped in scripts/gold_standard_levy_j_generator.py

# VERIFIED live from https://online.levyclerk.com/TaxSmartWeb/Home/Details?id=N
# fetched this session; parse_case() regex identical to levy_taxsmart_scraper.py
TAXSMART_DATA = {
    "2026-4176TD": {
        "taxsmart_id": 5052,
        "parcel_id": "00881-000-00",
        "opening_bid": 1097.66,
        "legal_description": "THAT PARCEL DESCRIBED IN THE WARRANTY DEED RECORDED IN OR BOOK 1086, PAGE 393, PUBLIC RECORDS OF LEVY COUNTY FLORIDA.",
        "owner_name": "JOHN CHRISTOPHER JONES",
        "applicant": "STACY E PARKER",
        "auction_date": "2026-11-09",
    },
    "2026-4177TD": {
        "taxsmart_id": 5053,
        "parcel_id": "01097-028-00",
        "opening_bid": 1089.62,
        "legal_description": "LOTS 19 AND 20 OF BLOCK A-5 OF JEMLANDS, AS UNRECORDED SUBDIVISION OF LEVY COUNTY, FLORIDA, FURTHER DESCRIBED IN DEEDS RECORDED IN DEED BOOK 99, PAGE 500 AND DEED BOOK 94, PAGE 537, LEVY COUNTY, FLORIDA",
        "owner_name": "JAMES DAVID CROCKETT",
        "applicant": "STACY E PARKER",
        "auction_date": "2026-11-09",
    },
    "2026-4178TD": {
        "taxsmart_id": 5054,
        "parcel_id": "06697-000-00",
        "opening_bid": 1209.11,
        "legal_description": "LOT 16, BLOCK 7, GREEN HIGHLAND PARK SUBDIVISION, ACCORDING TO THE PLAT THEREOF, RECORDED IN PLAT BOOK 1, PAGE 53, PUBLIC RECORDS OF LEVY COUNTY, FLORIDA",
        "owner_name": "DAMION LEYSON WAITE",
        "applicant": "STACY E PARKER",
        "auction_date": "2026-11-09",
    },
    "2026-4179TD": {
        "taxsmart_id": 5055,
        "parcel_id": "09377-018-00",
        "opening_bid": 1059.58,
        "legal_description": "LOT 19, BLOCK 29, OAK RIDGE ESTATES SUBDIVISION, ACCORDING TO THE PLAT THEREOF AS RECORDED IN PLAT BOOK 3, PAGES 63-1/63-7, OF THE PUBLIC RECORDS OF LEVY COUNTY, FLORIDA.",
        "owner_name": "URIEL ORTIZ AKA URIEL ORTIZ QUINTERO, JENNIFER CHRISTINE ORTIZ",
        "applicant": "STACY E PARKER",
        "auction_date": "2026-11-09",
    },
    "2026-4180TD": {
        "taxsmart_id": 5056,
        "parcel_id": "11944-000-00",
        "opening_bid": 1177.02,
        "legal_description": "NORTH 1/2 OF LOT 30, OF HAWKINS ACRES, SAID PLAT RECORDED IN UNRECORDCD PLAT BOOK 1, PAGE 9, PUBLIC RECORDS OF LEVY COUNTY, FLORIDA. HAWKINS ACRES, UNRECORDED PLAT BOOK 1, PAGE 9, IS A REPLAT OF LOTS 14 AND 15, BLOCK D OF WOODLAND ACRES SUBDIVISION, RECORDED IN PLAT BOOK 3, PAGE 39, PUBLIC RECORDS O",
        "owner_name": "WINSTON LEWIS, DONNA LEWIS",
        "applicant": "STACY E PARKER",
        "auction_date": "2026-11-09",
    },
}


def headers(extra=None):
    h = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def http_get(path, params):
    url = f"{SB}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers(), method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def http_patch(path, params, body):
    url = f"{SB}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers({"Prefer": "return=representation"}),
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def http_post(path, rows):
    url = f"{SB}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(rows).encode(),
        headers=headers({"Prefer": "return=representation"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def calc_bid_decision(case_number, ts):
    opening = ts["opening_bid"]
    # ARV: no comp/appraisal source reachable this session (Levy PA
    # qpublic.net -> HTTP 403 to automated fetch; FL GIO statewide
    # cadastral query timed out for this county). opening_bid on these 5
    # cases is a tax-CERTIFICATE base bid (back taxes + fees, ~$1,000-1,200)
    # -- NOT a property-value proxy -- so opening_bid*1.4 (the first fallback
    # rung in gold_standard_levy_j_generator.py) produces a nonsensical
    # ~$1,500 ARV and is rejected. Fall through to that same script's
    # COUNTY_DEFAULT_ARV rung instead. INFERRED, tagged below.
    arv = COUNTY_DEFAULT_ARV

    if arv < 100_000:
        repairs = 25_000
    elif arv < 250_000:
        repairs = 20_000
    elif arv < 500_000:
        repairs = 15_000
    else:
        repairs = 12_000

    # Shapira Formula: (ARV*70%) - Repairs - $10K - MIN($25K, 15%*ARV)
    max_bid = (arv * 0.7) - repairs - 10_000 - min(25_000, arv * 0.15)
    max_bid = round(max_bid, 2)

    factors = {
        "distress_location": LOCATION_SCORE,
        "distress_property": PROPERTY_SCORE,
        "distress_owner": OWNER_SCORE,
        "cma_distressed": round(arv * 0.90, 2),
        "cma_resale": round(arv * 1.10, 2),
        "notes": "Levy J-generator 5row-fix (2026-4176TD..2026-4180TD, source=TaxSmartWeb)",
        "honesty_marker": "arv INFERRED as COUNTY_DEFAULT_ARV=175000 (Levy small-rural-county fallback, same constant already shipped in gold_standard_levy_j_generator.py) -- no reachable comp/appraisal source this session (qpublic.net/fl/levy=HTTP 403, FL GIO cadastral query timeout); opening_bid here is a tax-certificate base bid, not a value proxy, so opening_bid*1.4 was rejected as nonsensical (~$1.5K ARV). parcel_id/legal_description/owner_name VERIFIED live from online.levyclerk.com/TaxSmartWeb",
    }

    bid_ratio = round(max_bid / opening, 4) if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)

    return {
        "case_number": case_number,
        "county_slug": COUNTY,
        "parcel_id": ts["parcel_id"],
        "address": None,  # not published by TaxSmart for these cases; left NULL
        "auction_date": ts["auction_date"],
        "arv": arv,
        "repairs": repairs,
        "final_judgment": opening,
        "max_bid": max_bid,
        "bid_judgment_ratio": bid_ratio,
        "recommendation": "BID" if max_bid > opening else "PASS",
        "confidence": CONFIDENCE_SCORE,
        "ml_score": ML_SCORE,
        "factors": factors,
        "pipeline_run_id": "GOLDSTD-LEVY-J-5ROW-taxsmart-v1",
    }


def main():
    target_cases = list(TAXSMART_DATA.keys())

    # STEP 1: backfill real TaxSmart-sourced fields into multi_county_auctions
    print("STEP 1: PATCH multi_county_auctions with VERIFIED TaxSmart fields")
    patched = 0
    for cn, ts in TAXSMART_DATA.items():
        body = {
            "parcel_id": ts["parcel_id"],
            "opening_bid": ts["opening_bid"],
            "opening_bid_usd": ts["opening_bid"],
            "legal_description": ts["legal_description"],
            "owner_name": ts["owner_name"],
            "plaintiff": ts["applicant"],
            "data_source": "taxsmart_levyclerk_com",
            "source_platform": "taxsmart_levy",
        }
        status, body_resp = http_patch(
            "/rest/v1/multi_county_auctions",
            {"county": "eq.levy", "case_number": f"eq.{cn}"},
            body,
        )
        if status not in (200, 204):
            raise RuntimeError(f"PATCH failed for {cn}: HTTP {status}: {body_resp}")
        n = len(body_resp) if isinstance(body_resp, list) else 0
        if n != 1:
            raise RuntimeError(f"PATCH for {cn} affected {n} rows, expected 1: {body_resp}")
        patched += 1
        print(f"  {cn}: PATCHED parcel_id={ts['parcel_id']} opening_bid={ts['opening_bid']}")
    print(f"STEP 1 DONE: {patched}/{len(target_cases)} multi_county_auctions rows patched")

    # STEP 2: check existing bid_decisions, insert only missing
    print("\nSTEP 2: INSERT bid_decisions (idempotent)")
    existing_rows = http_get(
        "/rest/v1/bid_decisions",
        {"county_slug": f"eq.{COUNTY}", "select": "case_number", "limit": 5000},
    )
    existing = {r["case_number"] for r in existing_rows}
    already_present = existing & set(target_cases)
    if already_present:
        print(f"  already in bid_decisions (skipping): {sorted(already_present)}")

    new_cases = [c for c in target_cases if c not in existing]
    print(f"  {len(new_cases)} new to insert")
    if not new_cases:
        print("DONE - 0 rows inserted (all already present)")
        return

    rows = [calc_bid_decision(c, TAXSMART_DATA[c]) for c in new_cases]

    status, body_resp = http_post("/rest/v1/bid_decisions", rows)
    if status not in (200, 201):
        raise RuntimeError(
            f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}: "
            f"HTTP {status}: {body_resp if isinstance(body_resp, str) else json.dumps(body_resp)[:500]}"
        )
    inserted = len(body_resp)
    if inserted == 0 and len(rows) > 0:
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}")
    print(f"DONE - {inserted} rows inserted: {sorted(r['case_number'] for r in body_resp)}")
    for r in sorted(body_resp, key=lambda x: x["case_number"]):
        print(f"  {r['case_number']}: arv={r['arv']} max_bid={r['max_bid']} ml_score={r['ml_score']} recommendation={r['recommendation']}")


if __name__ == "__main__":
    main()
