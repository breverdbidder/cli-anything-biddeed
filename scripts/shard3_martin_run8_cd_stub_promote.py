#!/usr/bin/env python3
"""GOLD STANDARD shard-3, martin, letters C/D/E/I/J -- this session (2026-08-08).

Extends scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py's proven AJAX
RealAuction harvester pattern to the 3 bare calendar-sweep stub rows flagged
live this session:
  26000299CAAXMX  foreclosure  2026-09-08
  25000496CAAXMX  foreclosure  2026-09-29
  25000102CAAXMX  foreclosure  2026-09-29

Live-verified this session (harvest_date() against martin.realforeclose.com):
all 3 case numbers ARE present on the live PREVIEW/AJAX calendar for their
respective auction dates -- confirming these are real, currently-scheduled
foreclosure auctions, not calendar-sweep noise. Raw AITEM HTML for all 3:
  Final Judgment Amount: $0.00
  Parcel ID: <a href="https://www.pamartinfl.gov/app/search/pcn/ ">Property Appraiser</a>
  (no Property Address / Assessed Value rows present at all)

This is NOT the known "Property Appraiser" anchor-text decoder bug (that bug
fires when the href DOES carry a real PCN but the decoder mis-picks the
anchor text) -- here the href itself is blank (".../pcn/ " with a trailing
space, no PCN appended). The Martin Clerk site has not attached parcel/
address/value data to these 3 cases yet (consistent with $0.00 final
judgment -- these are early-stage, pre-judgment foreclosure filings). This
is a genuine, honest upstream data gap, not a scraper defect. Confirmed by
comparing against case 25002772CCAXMX in the same 2026-09-08 harvest, whose
AITEM block DOES carry a real parcel_id/address/assessed_value.

Because parcel_id is not published anywhere for these 3 cases, E ("card
requires parcel_id" per session brief) and I (card_complete) CANNOT be
honestly advanced for these rows this session -- no source was found and
none is fabricated. Only C/D (parity_status=matched_clean, since the
case_number IS an exact live match) are advanced here.

2024-001-TD-MARTIN (the 4th C/D-fail row, parity_status=mca_only)
investigated separately: martin.realtaxdeed.com AJAX calendar returns 0
items across 8 dates spanning 2026-08-08 through 2026-12-05 (every ~2-week
Martin tax deed sale slot in that window), and TaxSmartWeb
(or.martinclerk.com/taxsmartweb) itself states "There are currently no
properties on the list of lands available for taxes." The case_number
format ("2024-001-TD-MARTIN") does not match Martin's real case format
(e.g. "26000299CAAXMX") -- consistent with the session brief's hypothesis
that it is a placeholder ID from a prior session, not a real court case
number. TaxSmartWeb's parcel/case/certificate search requires a client-side
jqGrid AJAX call whose endpoint is not present in the static form HTML
(loaded from an external JS bundle not fetched here); no server-rendered
result was obtainable via plain POST within this session's tooling. Left
UNRESOLVED and NOT touched -- parity_status stays mca_only rather than being
force-promoted without a genuine match.

DB access: PostgREST only (curl/urllib), per campaign guardrail 6.
Idempotent: only patches parity when not already tier1-labeled matched_clean.

Usage: python3 scripts/shard3_martin_run8_cd_stub_promote.py
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DISPATCH_LABEL = "tier1:shard3_martin_2026-08-08_ajax_harvest_liveconfirm"

TARGET_CASES = {"26000299CAAXMX", "25000496CAAXMX", "25000102CAAXMX"}


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.martin"
        "&case_number=in.(26000299CAAXMX,25000496CAAXMX,25000102CAAXMX)"
        "&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    if len(rows) != len(TARGET_CASES):
        found = {r["case_number"] for r in rows}
        missing = TARGET_CASES - found
        print(f"FAIL-LOUD: expected {len(TARGET_CASES)} rows, found {len(rows)}. "
              f"Missing: {missing}")

    promoted = []
    for row in rows:
        cn = norm_case_number(row["case_number"])
        if cn not in {norm_case_number(c) for c in TARGET_CASES}:
            continue
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")
        if row["parity_status"] == "matched_clean" and already_tier1:
            print(f"  SKIP {row['case_number']}: already matched_clean/tier1")
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": DISPATCH_LABEL})
            promoted.append(row["case_number"])
            print(f"  PROMOTED {row['case_number']} -> parity_status=matched_clean "
                  f"(live-verified on martin.realforeclose.com calendar)")
        except Exception as e:
            print(f"  PATCH FAILED for {row['id']} ({row['case_number']}): {e}")

    print(f"\nTOTALS: parity_promoted={len(promoted)} of {len(rows)} rows fetched "
          f"(parcel_id/address/assessed_value NOT backfilled -- genuinely absent "
          f"from live source for all 3 cases, see script docstring)")
    print("2024-001-TD-MARTIN: NOT touched. 0 live realtaxdeed.com calendar items "
          "found across 8 dates spanning 2026-08-08..2026-12-05; TaxSmartWeb "
          "confirms 'no properties on the list of lands available for taxes'. "
          "Left as parity_status=mca_only (honestly unresolved).")


if __name__ == "__main__":
    main()
