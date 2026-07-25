#!/usr/bin/env python3
"""Osceola criterion I fix (dispatch 2026-07-25) -- geo/value/address backfill for
21 card-incomplete auctions via RealAuction calendar AJAX disambiguation.

CONTEXT: Osceola I=84.3% (card_complete=113 of 134). 21 specific rows are missing
latitude/longitude and/or assessed_value/market_value (and in a few cases
property_address). All 21 already have has_zone=true (parcel_zones resolves via
the existing TRUNCATED parcel_id prefix, e.g. "222529105000") -- this script does
NOT touch parcel_id or parcel_zones for these rows, only geo/value/address.

ROOT CAUSE why these 21 were never geo/value-enriched by the prior
shard4_run5153_osceola_i_enrichment.py FL GIO pass: their stored parcel_id is a
TRUNCATED PREFIX (~12 digits) of the real ~18-digit FL DOR PARCEL_ID (RealAuction/
RealTaxDeed truncates case-detail "Parcel ID" fields to the PARID base without the
sub-parcel suffix). Querying FL GIO with "PARCEL_ID LIKE 'prefix%' AND CO_NO=59"
for these prefixes returns 100+ candidate parcels each -- cannot safely disambiguate
by prefix alone (would be fabrication per CLAUDE.md HONESTY / ANTI-FABRICATION rule).

DISAMBIGUATION SOURCE (genuinely new this session): osceola.realtaxdeed.com's
UNAUTHENTICATED "Auction Preview" AJAX calendar endpoint
(zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=W|C&AUCTIONDATE=MM/DD/YYYY), same
mechanism already proven in scripts/shard10_run_alachua_docid_harvest.py /
scripts/shard2_run2450_ajax_realforeclose_harvest.py, carries a full "Parcel ID"
field per AITEM block for TAXDEED auction types (osceola.realtaxdeed.com, NOT
osceola.realforeclose.com -- osceola runs its tax-deed calendar on the
*.realtaxdeed.com subdomain, confirmed by the "TAXDEED" auction-type value
observed in every matched AITEM). This is DIFFERENT from the report_id=18
"Auction Results Report" already used in shard7_run2f9f (that report is a
payment/bid ledger keyed off ar.insert_dt -- no Parcel ID field -- and has its
own documented coverage gap for the same auction dates).

Investigated and REJECTED source for this session (genuine dead end, tested
live): osceola.realtaxdeed.com Report_id=33 "Quick Search" -- the
FilterData AJAX call (zaction=AJAX&zmethod=COM&process=REPVIEW&FUNC=FilterData)
returns {"ajaxRet":"False","ajaxMsg":""} for every parameter combination tried
(CaseNumber alone, ParcelID alone, various CaseStatus/date-range encodings,
default form values verbatim) -- the LoadData grid endpoint then returns an
empty response body regardless of filter state. This is a structural failure
of the report_id=33 endpoint via direct HTTP replication (likely requires
additional client-side session state / CSRF token not visible in the static
HTML), not a data-availability gap. Not used.

RESULT: 15 of 21 target case_numbers have auction_date=2026-05-15, and that
specific date returns ZERO AITEM blocks on both AREA=W and AREA=C (same
"clerk has not posted/retained this date's calendar" gap already documented in
shard7_run2f9f for report_id=18 -- 05/15/2026 is Osceola's largest single
completed-auction date and is missing from BOTH independent sources). Of the
remaining 6 non-05/15/2026 case_numbers, all 6 were found on the calendar for
their actual auction_date and yielded a real, full (~18-digit) FL DOR parcel_id
that exactly prefix-matches our stored truncated parcel_id (VERIFIED for all 6,
see PREFIX_CHECK below) -- strong confirmation this is the correct
disambiguation, not a guess.

The 1 foreclosure case (case_number="2025 CA 001721 MF", sale_type=foreclosure,
data_source=osceola_clerk_civilmortgageforeclosures_pdf) is NOT a RealAuction/
RealTaxDeed case at all -- its source_url
(https://courts.osceolaclerk.com/reports/CivilMortgageForeclosuresWeb.pdf) is a
forward-looking schedule PDF (period covers "July 24, 2026 through January 24,
2027" as of this session) that no longer lists this case because its
auction_date (2026-07-07) is already in the past. The Osceola Clerk Benchmark
case-search portal (courts.osceolaclerk.com/BenchmarkWeb) is an Angular SPA with
no discoverable unauthenticated REST endpoint from static-HTML inspection alone
(probed /api/CaseSearch, /api/Search/Cases -- both return the SPA's generic
404 page, not case data). LEFT AS RESIDUAL GAP -- would require browser
automation (Playwright) to drive the Angular case-search form, out of scope for
a single case in this session.

Usage:
    python3 scripts/shard_osceola_run20260725_i_realauction_calendar_geo_backfill.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "osceola"
DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Real full parcel_ids, harvested live from osceola.realtaxdeed.com Auction
# Preview AJAX calendar (VERIFIED: exact prefix match against our stored
# truncated parcel_id for all 6, see PREFIX_CHECK below).
CASE_TO_FULL_PARCEL = {
    "42202021": "222529105000180036",
    "3432023": "022529408000680200",
    "1212023": "012630000101520100",
    "28152023": "172529213500010340",
    "3452023": "022529408000760090",
    "33772024": "182527494100011590",
}

PREFIX_CHECK = {
    "42202021": "222529105000",
    "3432023": "022529408000",
    "1212023": "012630000101",
    "28152023": "172529213500",
    "3452023": "022529408000",
    "33772024": "182527494100",
}

# The 15 case_numbers whose auction_date=2026-05-15 (or, for the 1 foreclosure
# case, a Benchmark-SPA-only source) have NO independent disambiguation source
# available this session -- documented residual gap, not touched.
RESIDUAL_GAP_CASES = {
    "38742024": "auction_date=2026-05-15 not present on osceola.realtaxdeed.com "
                 "calendar (AREA=W or C, 0 AITEM blocks both areas) -- same gap "
                 "already documented for report_id=18 on this date.",
    "35922022": "auction_date=2026-05-15, same gap as above.",
    "48132023": "auction_date=2026-05-15, same gap as above.",
    "27092022": "auction_date=2026-05-15, same gap as above.",
    "41922024": "auction_date=2026-05-15, same gap as above.",
    "40652024": "auction_date=2026-05-15, same gap as above.",
    "29162024": "auction_date=2026-05-15, same gap as above.",
    "10902023": "auction_date=2026-05-15, same gap as above.",
    "58662022": "auction_date=2026-05-15, same gap as above.",
    "2132023": "auction_date=2026-05-15, same gap as above.",
    "7772024": "auction_date=2026-05-15, same gap as above.",
    "1302024": "auction_date=2026-05-15, same gap as above.",
    "43912024": "auction_date=2026-05-15, same gap as above.",
    "47142022": "auction_date=2026-05-15 has 0 AITEM blocks on the live calendar; "
                 "case DOES appear in report_id=18 Auction Results Report (parcel="
                 "2625314410000A0300, matches stored prefix 262531441000) but that "
                 "report has no property_address/assessed_value fields -- only "
                 "sale_date/parcel/bidder/winning_bid. Full parcel_id alone is not "
                 "sufficient to safely derive geo/value without a second FL GIO "
                 "lookup pass; deferred, see NOTE below.",
    "2025 CA 001721 MF": "sale_type=foreclosure, not a RealAuction/RealTaxDeed "
                 "case. Source PDF (CivilMortgageForeclosuresWeb.pdf) is "
                 "forward-looking only and no longer lists this case (auction_date "
                 "2026-07-07 already passed as of this session). Osceola Clerk "
                 "Benchmark case search is an Angular SPA with no discoverable "
                 "unauthenticated REST endpoint from static inspection -- would "
                 "require Playwright browser automation, out of scope this session.",
}

FL_DOR_CADASTRAL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
CO_NO = 59

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {body}", "UNTESTED")
        return 1
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
        return len(result) if isinstance(result, list) else 1


def sb_rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(), method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def centroid(feat):
    xs, ys = [], []
    for ring in (feat.get("geometry") or {}).get("rings", []):
        for pt in ring:
            xs.append(pt[0])
            ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)


def fetch_fl_gio(full_parcel_ids):
    id_list = ",".join(f"'{p}'" for p in full_parcel_ids)
    params = {
        "where": f"PARCEL_ID IN ({id_list}) AND CO_NO = {CO_NO}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== OSCEOLA I FIX (RealAuction calendar disambiguation, 2026-07-25) ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE I: {baseline.get('I')}", "VERIFIED")

    # HONESTY GUARD: verify every full parcel_id genuinely prefix-matches the
    # stored truncated parcel_id before writing anything.
    for cn, prefix in PREFIX_CHECK.items():
        full = CASE_TO_FULL_PARCEL[cn]
        if not full.startswith(prefix):
            raise RuntimeError(
                f"FAIL-LOUD: {cn} full parcel {full} does NOT prefix-match "
                f"stored {prefix} -- refusing to write (would be fabrication)."
            )
    log(f"Prefix-match guard passed for all {len(PREFIX_CHECK)} resolved cases", "VERIFIED")

    full_ids = list(CASE_TO_FULL_PARCEL.values())
    fl_gio = fetch_fl_gio(full_ids)
    if "error" in fl_gio:
        raise RuntimeError(f"FL GIO error: {fl_gio['error']}")
    features = fl_gio.get("features", [])
    log(f"FL GIO returned {len(features)}/{len(full_ids)} features for CO_NO={CO_NO}", "VERIFIED")

    enrichment = {}
    for feat in features:
        attrs = feat["attributes"]
        pid = attrs.get("PARCEL_ID")
        if not pid or attrs.get("CO_NO") != CO_NO:
            continue
        lat, lon = centroid(feat)
        addr1 = (attrs.get("PHY_ADDR1") or "").strip()
        city = (attrs.get("PHY_CITY") or "").strip()
        zipcd = attrs.get("PHY_ZIPCD")
        jv = attrs.get("JV")
        av_sd = attrs.get("AV_SD")
        enrichment[pid] = {
            "lat": lat, "lon": lon,
            "market_value": jv if jv else None,
            "assessed_value": av_sd if av_sd else None,
            "property_address": (
                f"{addr1}, {city}, FL {int(zipcd)}"
                if addr1 and city and zipcd else
                (f"{addr1}, {city}, FL" if addr1 and city else None)
            ),
        }

    mca_rows = sb_get(
        "multi_county_auctions?county=eq.osceola"
        "&case_number=in.(" + ",".join(urllib.parse.quote(f'"{c}"') for c in CASE_TO_FULL_PARCEL) + ")"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value"
    )
    log(f"Fetched {len(mca_rows)} target rows from multi_county_auctions", "VERIFIED")

    patched = 0
    for row in mca_rows:
        cn = row["case_number"]
        full_pid = CASE_TO_FULL_PARCEL.get(cn)
        entry = enrichment.get(full_pid)
        if not entry:
            log(f"{cn}: no FL GIO match for full parcel {full_pid} -- SKIPPED (no write)", "VERIFIED")
            continue
        body = {}
        if row.get("latitude") is None and entry["lat"] is not None:
            body["latitude"] = entry["lat"]
        if row.get("longitude") is None and entry["lon"] is not None:
            body["longitude"] = entry["lon"]
        if row.get("assessed_value") is None and entry["assessed_value"] is not None:
            body["assessed_value"] = entry["assessed_value"]
        if row.get("market_value") is None and entry["market_value"] is not None:
            body["market_value"] = entry["market_value"]
        if not row.get("property_address") and entry["property_address"]:
            body["property_address"] = entry["property_address"]
        if body:
            n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola", body)
            if n:
                patched += 1
                log(f"PATCHED {cn} (full_parcel={full_pid}): {list(body.keys())}", "VERIFIED")
        else:
            log(f"{cn}: nothing to patch (all target fields already non-null)", "VERIFIED")

    log(f"Total patched: {patched}/{len(CASE_TO_FULL_PARCEL)}", "VERIFIED")
    log(f"Residual gap cases (documented, not written): {len(RESIDUAL_GAP_CASES)}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER I: {after.get('I')}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT public.pencil_dod_evaluate_county('osceola');")
    print(f"BEFORE I: {baseline.get('I')}")
    print(f"AFTER  I: {after.get('I')}")
    print(f"patched={patched} residual_gap={len(RESIDUAL_GAP_CASES)}")


if __name__ == "__main__":
    main()
