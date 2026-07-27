#!/usr/bin/env python3
"""
GOLD STANDARD shard-10 run 6796 — Hamilton C (parity_clean) / D (parity_any) fix.

Baseline (VERIFIED via pencil_dod_evaluate_county before this script ran):
  C=38.1% D=38.1% (matched_clean=8 of 21)

13 unmatched rows fall into three groups. This script writes ONLY what is
independently re-verified in this session. It does NOT guess statuses.

GROUP 1 (5 rows) — tier1_tax_deed_outcome wiring gap.
  These 5 tax_deed rows already have an INDEPENDENT verified outcome in
  public.tax_deed_outcomes sourced from the clerk's own results PDF
  (hamiltonclerk.com/wp-content/uploads/LIST-OF-PROPERTIES-07-24-2025-RESULTS.pdf),
  and multi_county_auctions.sold_amount already matches tax_deed_outcomes.winning_bid
  exactly. parity_status was simply never set. Confirmed independently in this
  session by (a) re-querying tax_deed_outcomes via REST, and (b) re-downloading
  and reading the actual PDF page-by-page (3-page PDF, read via Read tool),
  which shows for every one of these 5 certs a "Purchaser ... Purchase Amount"
  line matching the DB values exactly:
    Cert 2   (parcel 1005-130): Purchase Amount $10,300.00 -> mca.sold_amount 10300.0  MATCH
    Cert 300 (parcel 3478-450): Purchase Amount $17,000.00 -> mca.sold_amount 17000.0  MATCH
    Cert 539 (parcel 4421-000): Purchase Amount $17,000.00 -> mca.sold_amount 17000.0  MATCH
    Cert 540 (parcel 4427-000): Purchase Amount $18,100.00 -> mca.sold_amount 18100.0  MATCH
    Cert 585 (parcel 4680-000): Purchase Amount $14,000.00 -> mca.sold_amount 14000.0  MATCH
  Action: PATCH parity_status='matched_clean', parity_source='tier1_tax_deed_outcome'
  scoped by county=eq.hamilton AND case_number=eq.<x> (never bulk).

GROUP 2 (3 rows) — HAM-TD-CERT-597 (4837-048), HAM-TD-CERT-379 (3729-650),
  HAM-TD-CERT-599 (4837-067). mca says auction_status='upcoming', auction_date
  2025-12-04 (already passed relative to today). Checked hamiltonclerk.com/tax-deeds/
  live HTML directly (not just the WebFetch summarizer) on 2026-07-27: the page's
  current heading is "TAX DEED SALE - THURSDAY, DECEMBER 4, 2025" and lists 10
  certs for that date. 7 of the 10 (99, 230, 344, 467, 557, 559, 688 -- all
  already matched_clean in our DB) carry an explicit red "REDEEMED <date>"
  annotation inline in the HTML. Certs 597, 379, 599 carry NO such annotation --
  no REDEEMED, no SOLD, no purchaser, no purchase amount. Also checked
  hamiltonclerk.com/list-of-lands-available-for-taxes/ (would show unsold/
  no-bidder properties) -- "No available properties at this time", these 3
  certs are not there either. No December-2025 results PDF exists at any
  guessed URL (all 404). CONCLUSION: genuinely UNRESOLVED on the public site,
  not a stale-page artifact (sibling certs on the identical page/date ARE
  annotated). This is UNTESTED, not a guess -- do NOT write any outcome.
  Action: NO WRITE. Documented here and in final report.

GROUP 3 (5 rows) — foreclosures 2024-CA-19, 2023-CA-41, 2025-CA-37, 2025-CA-66,
  2021-CA-46 (all parity_status='mca_only'). Checked hamiltonclerk.com/foreclosures/
  raw HTML directly on 2026-07-27. The ENTIRE live foreclosure calendar content
  (verified via grep on the raw HTML, not summarizer) lists exactly 4 cases,
  total, on the whole page: 2025-CA-66, 2025-CA-92, 2025-CA-46, 2025-CA-28.
  grep for "2024-CA", "2023-CA", "2021-CA" returns ZERO hits in the raw HTML.
  Site search (?s=<case>) for 2024-CA-19 / 2023-CA-41 / 2025-CA-37 / 2021-CA-46
  each returns "Nothing Found" (confirmed the only place the query string
  appears in the response is the echoed search box value, not a result).
  2025-CA-66 DOES appear on the live calendar, but with sale date
  "JULY 22, 2026" -- this does NOT match mca's stored auction_date of
  2026-08-05 for that case. A mismatched date is not a clean match; writing
  matched_clean here would misrepresent a real discrepancy as a confirmation.
  CONCLUSION: 4 of 5 cases (2024-CA-19, 2023-CA-41, 2025-CA-37, 2021-CA-46) are
  not found on the live site at all. The 5th (2025-CA-66) is found but with a
  conflicting sale date that needs reconciliation, not a rubber-stamp match.
  Action: NO WRITE for any of the 5. Documented here and in final report as
  UNTESTED (not-found) / date-conflict (2025-CA-66) respectively.

Idempotent: re-running only re-verifies Group 1 against tax_deed_outcomes and
re-applies the same PATCH (safe no-op if already applied).
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "hamilton"

# GROUP 1 — case_number -> expected winning_bid (must match tax_deed_outcomes AND mca.sold_amount)
GROUP1 = {
    "HAM-TD-CERT-2": 10300.0,
    "HAM-TD-CERT-300": 17000.0,
    "HAM-TD-CERT-539": 17000.0,
    "HAM-TD-CERT-540": 18100.0,
    "HAM-TD-CERT-585": 14000.0,
}

PARITY_SOURCE = "tier1_tax_deed_outcome"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def sb_get(table: str, params: str) -> list:
    url = f"{BASE}/{table}?{params}"
    req = urllib.request.Request(url, headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"GET {table} HTTP {e.code}: {e.read()[:300]}", "ERROR")
        return []
    except Exception as e:
        log(f"GET {table} failed: {e}", "ERROR")
        return []


def sb_patch(table: str, filters: str, data: dict) -> tuple:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, method="PATCH",
        headers=sb_headers({"Prefer": "return=representation"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_text = e.read()
        log(f"PATCH {table}?{filters} HTTP {e.code}: {body_text[:300]}", "ERROR")
        return e.code, body_text
    except Exception as e:
        log(f"PATCH {table}?{filters} failed: {e}", "ERROR")
        return 0, str(e)


def main() -> int:
    log(f"=== GOLD STANDARD shard10 run6796 hamilton C/D fix START ===")
    fixed = 0
    errors = 0

    for case_number, expected_bid in GROUP1.items():
        cn_enc = urllib.parse.quote(case_number, safe="")

        # 1) Independently re-verify tax_deed_outcomes
        tdo_rows = sb_get(
            "tax_deed_outcomes",
            f"case_number=eq.{cn_enc}&select=case_number,winning_bid,data_source,outcome,county",
        )
        if not tdo_rows:
            log(f"{case_number}: NO tax_deed_outcomes row found -- SKIP (fail loud, not silent)", "ERROR")
            errors += 1
            continue
        tdo = tdo_rows[0]
        log(f"{case_number}: tax_deed_outcomes = {json.dumps(tdo)}", "VERIFIED")

        if tdo.get("winning_bid") is None or float(tdo["winning_bid"]) != expected_bid:
            log(
                f"{case_number}: winning_bid mismatch! expected={expected_bid} "
                f"got={tdo.get('winning_bid')} -- SKIP, do not write",
                "ERROR",
            )
            errors += 1
            continue

        # 2) Independently re-verify mca.sold_amount matches
        mca_rows = sb_get(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{cn_enc}&select=id,case_number,sold_amount,parity_status,parity_source",
        )
        if not mca_rows:
            log(f"{case_number}: NO multi_county_auctions row found -- SKIP", "ERROR")
            errors += 1
            continue
        mca = mca_rows[0]
        log(f"{case_number}: multi_county_auctions (before) = {json.dumps(mca)}", "VERIFIED")

        if mca.get("sold_amount") is None or float(mca["sold_amount"]) != expected_bid:
            log(
                f"{case_number}: mca.sold_amount does not match expected {expected_bid} "
                f"(got {mca.get('sold_amount')}) -- SKIP, do not write",
                "ERROR",
            )
            errors += 1
            continue

        if mca.get("parity_status") == "matched_clean":
            log(f"{case_number}: already matched_clean -- no-op (idempotent)", "INFO")
            fixed += 1
            continue

        # 3) PATCH — pinned by county + case_number, never a bulk update
        status, resp = sb_patch(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{cn_enc}",
            {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE},
        )
        if status not in (200, 201, 204):
            log(f"{case_number}: PATCH FAILED status={status} resp={resp}", "ERROR")
            errors += 1
            continue

        # 4) Re-GET to confirm write landed
        after_rows = sb_get(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{cn_enc}&select=id,case_number,sold_amount,parity_status,parity_source",
        )
        if not after_rows:
            log(f"{case_number}: re-GET after PATCH returned nothing -- FAIL LOUD", "ERROR")
            errors += 1
            continue
        after = after_rows[0]
        log(f"{case_number}: multi_county_auctions (AFTER) = {json.dumps(after)}", "VERIFIED")

        if after.get("parity_status") != "matched_clean":
            log(f"{case_number}: PATCH did not stick! after={after}", "ERROR")
            errors += 1
            continue

        fixed += 1
        log(f"{case_number}: FIXED (parity_status=matched_clean, parity_source={PARITY_SOURCE})", "VERIFIED")

    log(
        f"GROUP 2 (597/379/599): NO WRITE — confirmed UNTESTED on live "
        f"hamiltonclerk.com/tax-deeds/ (no REDEEMED/SOLD annotation on these "
        f"3 certs while 7 sibling certs on same sale date ARE annotated; no "
        f"lands-available listing; no Dec-2025 results PDF found).",
        "UNTESTED",
    )
    log(
        f"GROUP 3 (2024-CA-19/2023-CA-41/2025-CA-37/2021-CA-46): NO WRITE — "
        f"confirmed not present on live hamiltonclerk.com/foreclosures/ calendar "
        f"(raw HTML grep + site search both empty).",
        "UNTESTED",
    )
    log(
        f"GROUP 3 (2025-CA-66): NO WRITE — IS present on live foreclosure "
        f"calendar but with sale date JULY 22, 2026 vs mca.auction_date "
        f"2026-08-05 -- date conflict, not a clean match. Needs human/next-"
        f"session reconciliation, not a rubber-stamp matched_clean.",
        "UNTESTED",
    )

    log(f"=== DONE: fixed={fixed} errors={errors} (Group1 only; Group2/3 no-op by design) ===")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
