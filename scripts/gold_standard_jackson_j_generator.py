#!/usr/bin/env python3
"""
GOLD STANDARD Jackson-only J-generator (criterion J: Shapira deal thesis).

Same shape as scripts/gold_standard_alachua_j_generator.py (the canonical,
already-shipped Shapira Formula pattern used across ~20 counties). Uses
urllib.request instead of `requests` -- matches the stdlib-only convention.

CONTEXT: jackson J was failing at 129/145 (89.0%) because 16 case_numbers in
multi_county_auctions had NO public.bid_decisions row at all (VERIFIED this
session by diffing all 145 jackson auction case_numbers against all 175
distinct case_numbers present in bid_decisions for county_slug='jackson').

Of those 16:
  - 14 are tax_deed rows in a single "OF 2019" case-number series (1611-1952)
    for tiny platted vacant lots in the same section-township-range
    (02-2N-11-0083/0084/0086) in Marianna/Alford. All 14 have parcel_id +
    opening_bid but assessed_value AND market_value are both NULL in our DB.
    Three independent live lookups this session (WebFetch on
    qpublic.schneidercorp.com, brightdata scrape on the same + on
    jacksonclerk.com, WebFetch on jackson.realforeclose.com) all returned
    403/blocked -- consistent with the standing documented finding in
    GOLD_STANDARD_SHARD4_JACKSON_BRADFORD_UNION_HOLMES_ALACHUA_DISPATCH_49342BAB_SESSION_REPORT.md
    ("jacksonpa.com Cloudflare 403", "qpublic.schneidercorp.com" also dead).
    HOWEVER: jackson already has 8 CLOSED tax_deed sales in the exact same
    "OF 2019" series and exact same plat prefix (02-2N-11-00xx) with REAL
    assessed_value + sold_amount already in multi_county_auctions (case
    numbers 1616, 1679, 1680, 1681, 1694, 1705, 1707, 3505 OF 2019 --
    VERIFIED via live query this session). Mean assessed_value of those 8
    real comps = $3,795.25 (range $2,214-$6,000), mean sold_amount =
    $4,312.42. This is a genuine same-plat comp set, not an invented
    number -- used as the ARV basis for the 14 open lots via the same
    "county/plat median fallback" pattern already shipped in
    scripts/shard4_run3713_pinellas_i_j_fix.py (county_median_sold_fallback).
  - 1 is a foreclosure (322025CA000221CAAXMX) with real parcel_id +
    assessed_value=35501 + opening_bid=38807.88 already in our DB -- no
    fallback needed, straight formula application.
  - 1 is a foreclosure (322026CA000029CAAXMX) with parcel_id=NULL,
    property_address=NULL, and ONLY opening_bid=86499.29 populated. Live
    checks this session (WebFetch + brightdata on the auction_url
    jackson.realforeclose.com/...AID=1517659, and a targeted search for the
    case number) found NOTHING -- no address, no parcel, no comp anchor of
    any kind. This row is EXCLUDED from this generator and left unresolved
    per the no-fabrication mandate (cannot derive even a location-based
    proxy with zero geo/parcel data).

FIELDS WRITTEN: one bid_decisions row per new jackson case_number
(case_number, county_slug, parcel_id, address, auction_date, arv, repairs,
final_judgment, max_bid, bid_judgment_ratio, recommendation, confidence,
ml_score, factors, pipeline_run_id). Idempotent -- only inserts rows whose
case_number is not already present in bid_decisions. Fail-loud: raises on
any non-2xx POST response or on inserted=0 when rows were parsed.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "jackson"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58

# Real, live-verified same-plat (02-2N-11-00xx) closed tax_deed comps in the
# same "OF 2019" case-number series -- NOT an invented constant.
PLAT_COMP_ASSESSED_MEAN = 3795.25  # mean of 8 real assessed_value comps
PLAT_COMP_SOLD_MEAN = 4312.42      # mean of 8 real sold_amount comps

# Resolvable target case_numbers only. 322026CA000029CAAXMX is deliberately
# EXCLUDED -- zero parcel/address/comp anchor, see module docstring.
TARGET_CASE_NUMBERS = [
    "1611 OF 2019",
    "1612 of 2019",
    "1717 OF 2019",
    "1719 OF 2019",
    "1721 OF 2019",
    "1885 OF 2019",
    "1886 OF 2019",
    "1905 OF 2019",
    "1916 OF 2019",
    "1929 OF 2019",
    "1940 OF 2019",
    "1944 OF 2019",
    "1947 OF 2019",
    "1952 OF 2019",
    "322025CA000221CAAXMX",
]


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


def calc_bid_decision(row):
    assessed = row.get("assessed_value") or 0
    opening = row.get("opening_bid") or 0
    market = row.get("market_value") or 0

    if max(assessed, market) > 0:
        arv = max(assessed, market)
        arv_source = "assessed_or_market_value"
    else:
        # No assessed/market on this row (the 14 same-plat tax_deed lots).
        # Use the real same-plat closed-comp mean, floored by opening_bid so
        # the ARV is never below the actual tax certificate face amount.
        arv = max(PLAT_COMP_ASSESSED_MEAN, opening)
        arv_source = "plat_comp_mean_fallback_INFERRED"

    arv = min(arv, 5_000_000)

    if arv < 100_000:
        repairs = 25_000
    elif arv < 250_000:
        repairs = 20_000
    elif arv < 500_000:
        repairs = 15_000
    else:
        repairs = 12_000

    max_bid = max((arv * 0.7) - repairs - 10_000, min(25_000, arv * 0.15))

    factors = {
        "distress_location": LOCATION_SCORE,
        "distress_property": 0.50,
        "distress_owner": 0.55,
        "cma_distressed": {"value": round(arv * 0.87, 2), "sources": [arv_source]},
        "cma_resale": {
            "value": round(
                PLAT_COMP_SOLD_MEAN if arv_source.startswith("plat_comp") else arv * 1.12,
                2,
            ),
            "sources": ["plat_comp_sold_mean"] if arv_source.startswith("plat_comp") else ["market_value_proxy"],
        },
    }

    bid_ratio = max_bid / opening if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)

    return {
        "case_number": row["case_number"],
        "county_slug": COUNTY,
        "parcel_id": row.get("parcel_id"),
        "address": row.get("property_address"),
        "auction_date": row.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": round(repairs, 2),
        "final_judgment": round(opening, 2) if opening else None,
        "max_bid": round(max_bid, 2),
        "bid_judgment_ratio": round(bid_ratio, 4) if bid_ratio else None,
        "recommendation": "BID" if (opening > 0 and max_bid > opening) else "PASS",
        "confidence": CONFIDENCE_SCORE,
        "ml_score": ML_SCORE,
        "factors": factors,
        "pipeline_run_id": "GOLDSTD-JACKSON-J-15ROW-v1",
    }


def main():
    auctions = http_get(
        "/rest/v1/multi_county_auctions",
        {
            "county": f"eq.{COUNTY}",
            "case_number": f"in.({','.join(chr(34) + c + chr(34) for c in TARGET_CASE_NUMBERS)})",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value",
            "limit": 2000,
        },
    )
    print(f"{COUNTY}: {len(auctions)} target auctions fetched fresh")
    found = {a["case_number"] for a in auctions}
    missing = set(TARGET_CASE_NUMBERS) - found
    if missing:
        print(f"{COUNTY}: WARNING - {len(missing)} target case_numbers not found in multi_county_auctions: {sorted(missing)}")

    existing_rows = http_get(
        "/rest/v1/bid_decisions",
        {"county_slug": f"eq.{COUNTY}", "select": "case_number", "limit": 5000},
    )
    existing = {r["case_number"] for r in existing_rows}
    already_present = existing & found
    if already_present:
        print(f"{COUNTY}: {len(already_present)} target case_numbers already in bid_decisions (skipping): {sorted(already_present)}")

    new_auctions = [a for a in auctions if a["case_number"] not in existing]
    print(f"{COUNTY}: {len(new_auctions)} new to insert")

    if not new_auctions:
        print(f"{COUNTY}: DONE - 0 rows inserted (all already present)")
        return

    rows = [calc_bid_decision(a) for a in new_auctions]

    status, body = http_post("/rest/v1/bid_decisions", rows)
    if status not in (200, 201):
        raise RuntimeError(
            f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}: "
            f"HTTP {status}: {body if isinstance(body, str) else json.dumps(body)[:500]}"
        )
    inserted = len(body)
    if inserted == 0 and len(rows) > 0:
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}")
    print(f"{COUNTY}: DONE - {inserted} rows inserted: {sorted(r['case_number'] for r in body)}")


if __name__ == "__main__":
    main()
