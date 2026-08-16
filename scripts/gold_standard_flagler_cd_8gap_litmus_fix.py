#!/usr/bin/env python3
"""Gold Standard flagler C/D — litmus harvest for the 8 parity_status=NULL rows
that arrived after flagler's 2026-07-24 10/10 certification (denominator grew
148->159; see GOLD_STANDARD_SHARD7_DIXIE_FLAGLER_DISPATCH_EA6AF08A_4TH_PASS_SESSION_REPORT.md).

Reuses two already-proven flagler litmus sources verbatim (no new endpoint
discovery, per HARD GUARDRAILS #1 -- PropertyOnion is never ingested, only used
as an internal comparison target, never as the litmus source here):

  1. flagler.realtdm.com public case search (search_case(), lifted from
     scripts/shard6_run3645_flagler_realtdm_case_search.py) for the 4 tax_deed
     rows -- county clerk's own RealTDM portal, independent of PropertyOnion.
  2. RealForeclose AJAX calendar harvest_date() (imported from
     scripts/shard2_run2450_ajax_realforeclose_harvest.py, same import pattern
     as scripts/shard9_flagler_cd_ajax_harvest.py) for the 4 foreclosure rows --
     the county's own RealForeclose auction platform.

Matching rule (same standard used fleet-wide, e.g. shard6_run3645 and the
charlotte CD refuter-fix precedent for redeemed handling):
  - live source returns a card/item for the case number AND its own
    parcel/case field EXACT-matches (or exact prefix-matches, for the
    realtdm short-form IDs) our stored parcel_id
      -> case is ACTIVE/SOLD (not redeemed/cancelled): parity_status=matched_clean,
         parity_source='tier1:gold_standard_flagler_8gap_litmus:<source>'
      -> case is REDEEMED (paid off before sale, legitimate non-sale outcome,
         confirmed via the live independent source): parity_status=
         CLERK_SSOT_CANCELLED (counts for D/matched_any per the evaluator SQL's
         FILTER clause, correctly excluded from C/matched_clean since no sale
         occurred) -- NOT matched_divergent, since there is no sale-outcome
         field disagreement to diverge on, just a non-sale.
  - not found on live source: parity_status left NULL (no fabrication).

DB writes via PostgREST only (direct pooler confirmed stale, per every prior
shard session).
"""
import json
import os
import re
import sys
import time
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
import importlib.util

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "ajax_harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_ajax_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ajax_mod)

REALTDM_BASE = "https://flagler.realtdm.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

RUN_LABEL_REALTDM = "tier1:gold_standard_flagler_8gap_litmus:realtdm"
RUN_LABEL_AJAX = "tier1:gold_standard_flagler_8gap_litmus:realforeclose_ajax"

TAX_DEED_ROWS = [
    {"id": "4d6bf5d2-6aaf-42f2-b58e-7e8d080c0ef2", "case_number": "25-032 TDC", "parcel_id": "071131700300"},
    {"id": "891967a0-0ca1-4973-a6f3-3041563bf4af", "case_number": "25-031 TDC", "parcel_id": "071131706400"},
    {"id": "ba115d77-7924-4a85-b44c-648ab5f254cc", "case_number": "25-026 TDC", "parcel_id": "331229555000"},
    {"id": "148a2580-1294-477e-814b-6b8a0ea09a1a", "case_number": "26-076 TDC", "parcel_id": "0711317024000700120"},
]

FORECLOSURE_ROWS = [
    {"id": "fa706ae9-acca-4495-b0f4-8b06b0b8e309", "case_number": "2025 CA 000656", "auction_date": "2026-08-28",
     "parcel_id": "35-11-31-4075-00000-0220"},
    {"id": "7c6013d5-1130-4c29-a93b-8217c4a1cf33", "case_number": "2025 CA 000462", "auction_date": "2026-09-18",
     "parcel_id": "20-10-31-0300-00150-0000"},
    {"id": "2e7aef04-be0d-43c7-93cf-3d74ffedd3f6", "case_number": "2024 CC 000454", "auction_date": "2026-09-18",
     "parcel_id": "20-10-31-3050-00080-0050"},
    {"id": "a817ed79-5509-4108-b370-3d1c18408384", "case_number": "2025 CA 000505", "auction_date": "2026-09-18",
     "parcel_id": "07-11-31-0310-00020-0720"},
]


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def realtdm_search_case(op, case_number_short):
    data = urllib.parse.urlencode({
        "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
        "isPublic": "1", "filterCaseNumber": case_number_short,
    }).encode()
    req = urllib.request.Request(
        REALTDM_BASE + "/public/cases/list", data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": REALTDM_BASE + "/public/cases/list"})
    with op.open(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")
    cards = []
    for blk in html.split('data-caseid="')[1:]:
        case_m = re.search(r"CASE #([^<]+)<", blk)
        status_m = re.search(r'opacity-75">([^<]+)<', blk)
        parcel_m = re.search(r"Parcel Number</div>\s*<div class=\"data-value text-end\">([^<]*)<", blk)
        sale_m = re.search(r"Sale Date</div>\s*<div class=\"data-value text-end\">([^<]*)<", blk)
        if not case_m:
            continue
        cards.append({
            "case_number": case_m.group(1).strip(),
            "status": (status_m.group(1).strip() if status_m else ""),
            "parcel_number": re.sub(r"\D", "", parcel_m.group(1)) if parcel_m else "",
            "sale_date": sale_m.group(1).strip() if sale_m else "",
        })
    return cards


def norm_digits(s):
    return re.sub(r"\D", "", s or "")


def process_tax_deed(rows):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request(REALTDM_BASE + "/public/cases/list", headers={"User-Agent": UA}), timeout=30).read()

    results = []
    for row in rows:
        cn = row["case_number"]
        short = cn.split()[0]
        try:
            cards = realtdm_search_case(op, short)
        except Exception as e:
            print(f"  SEARCH FAIL {cn}: {e}")
            results.append((row, "search_fail", None, None))
            time.sleep(0.8)
            continue
        match = next((c for c in cards if c["case_number"] == cn), None)
        if not match:
            print(f"  {cn}: NOT FOUND on live realtdm case search")
            results.append((row, "not_found", None, None))
            time.sleep(0.8)
            continue

        our_parcel = norm_digits(row["parcel_id"])
        their_parcel = match["parcel_number"]
        parcel_ok = bool(our_parcel) and bool(their_parcel) and their_parcel.startswith(our_parcel)
        status_lower = match["status"].lower()

        if not parcel_ok:
            print(f"  {cn}: status={match['status']!r} parcel MISMATCH ours={our_parcel!r} theirs={their_parcel!r} -- NOT promoted")
            results.append((row, "parcel_mismatch", match["status"], their_parcel))
            time.sleep(0.8)
            continue

        if "redeem" in status_lower:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "CLERK_SSOT_CANCELLED", "parity_source": RUN_LABEL_REALTDM})
                print(f"  {cn}: status={match['status']!r} parcel CONFIRMED (prefix) -> CLERK_SSOT_CANCELLED (redeemed, D-only)")
                results.append((row, "clerk_ssot_cancelled", match["status"], their_parcel))
            except Exception as e:
                print(f"  PATCH FAIL {cn}: {e}")
                results.append((row, "patch_fail", match["status"], their_parcel))
            time.sleep(0.8)
            continue

        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": RUN_LABEL_REALTDM})
            print(f"  {cn}: status={match['status']!r} parcel CONFIRMED -> matched_clean")
            results.append((row, "matched_clean", match["status"], their_parcel))
        except Exception as e:
            print(f"  PATCH FAIL {cn}: {e}")
            results.append((row, "patch_fail", match["status"], their_parcel))
        time.sleep(0.8)
    return results


def process_foreclosure(rows):
    by_date = {}
    for row in rows:
        by_date.setdefault(row["auction_date"], []).append(row)

    results = []
    for ad, group in by_date.items():
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        try:
            items = _ajax_mod.harvest_date("flagler", "flagler", mmddyyyy, platform_domain="realforeclose.com")
        except Exception as e:
            print(f"  HARVEST FAIL flagler foreclosure {ad}: {e}")
            for row in group:
                results.append((row, "harvest_fail", None, None))
            continue

        by_cn = {(it.get("case_number") or "").strip(): it for it in items}
        for row in group:
            cn = row["case_number"]
            item = by_cn.get(cn)
            if not item:
                print(f"  {cn}: NOT FOUND on live realforeclose AJAX calendar for {ad}")
                results.append((row, "not_found", None, None))
                continue
            our_parcel = norm_digits(row["parcel_id"])
            their_parcel = norm_digits(item.get("parcel_id"))
            if not our_parcel or not their_parcel or our_parcel != their_parcel:
                print(f"  {cn}: parcel MISMATCH ours={row['parcel_id']!r} theirs={item.get('parcel_id')!r} -- NOT promoted")
                results.append((row, "parcel_mismatch", None, item.get("parcel_id")))
                continue
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": RUN_LABEL_AJAX})
                print(f"  {cn}: parcel EXACT match -> matched_clean")
                results.append((row, "matched_clean", None, item.get("parcel_id")))
            except Exception as e:
                print(f"  PATCH FAIL {cn}: {e}")
                results.append((row, "patch_fail", None, item.get("parcel_id")))
        time.sleep(0.6)
    return results


def main():
    print("=== tax_deed rows (realtdm) ===")
    td_results = process_tax_deed(TAX_DEED_ROWS)

    print("\n=== foreclosure rows (realforeclose AJAX) ===")
    fc_results = process_foreclosure(FORECLOSURE_ROWS)

    all_results = td_results + fc_results
    counts = {}
    for row, outcome, *_ in all_results:
        counts[outcome] = counts.get(outcome, 0) + 1

    print(f"\nTOTALS: {counts}")
    if len(all_results) != 8:
        raise RuntimeError(f"Expected 8 rows processed, got {len(all_results)} -- fail-loud")

    matched_clean = counts.get("matched_clean", 0)
    if matched_clean == 0 and counts.get("clerk_ssot_cancelled", 0) == 0:
        raise RuntimeError("Zero rows promoted (matched_clean or CLERK_SSOT_CANCELLED) -- silent failure, investigate")


if __name__ == "__main__":
    main()
