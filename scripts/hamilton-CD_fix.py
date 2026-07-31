#!/usr/bin/env python3
"""
GOLD STANDARD hamilton C (parity_clean) / D (parity_any) — session re-verify,
2026-07-31. Follows the exact PostgREST GET/PATCH convention established by
scripts/gold_standard_shard10_hamilton_c_d_fix_run6796.py (2026-07-27).

Baseline (VERIFIED via pencil_dod_evaluate_county fresh this session):
  C: matched_clean=13 metric=61.9 FAIL (need 20/21 = 95%)
  D: matched_any=13   metric=61.9 FAIL
  auctions_total=21

This is the SAME 8-row gap Group 1/2/3 diagnosed on 2026-07-27. Group 1 (5 rows)
was already fixed by the prior script and remains matched_clean/
tier1_tax_deed_outcome (re-verified below as a defensive no-op check — this
script does NOT touch those 5 rows unless the re-check somehow fails).

The remaining 8 rows (Group 2 + Group 3) were re-investigated independently
today via 4 live public sources:
  1. hamiltonclerk.com/foreclosures/          (raw HTML, not summarizer)
  2. hamiltonclerk.com/tax-deeds/             (raw HTML, not summarizer)
  3. hamiltonclerk.com/list-of-lands-available-for-taxes/
  4. hamiltonclerk.com/court-search/ -> civitekflorida.com/ocrs/county/24/
     (NEW lever vs. 2026-07-27 script, which flagged this as "untried,
     requires session/JS interaction". This session drove the full flow:
     GET home -> POST "Public" access button (PrimeFaces ajax) -> redirect to
     disclaimer.xhtml -> POST "I Agree" -> redirect to app/search.xhtml. The
     resulting search form has ONLY name/DOB/business-name/SSN/court fields --
     NO case-number search field exists on this OCRS instance. This is a
     structural dead end, not an engineering gap: no amount of further
     session/cookie handling would surface a case-number lookup that the tool
     does not offer.

RESULT — GROUP 2 (HAM-TD-CERT-379/597/599, tax deed certs, parity_status=null):
  Re-fetched hamiltonclerk.com/tax-deeds/ raw HTML today. Cert 379 (parcel
  3729-650), cert 597 (parcel 4837-048), cert 599 (parcel 4837-067) each
  appear on the Dec 4, 2025 sale block with NO "REDEEMED"/"SOLD" annotation --
  identical to the 2026-07-27 finding. 7 sibling certs on the same sale date
  in the same document ARE annotated REDEEMED, confirming this is not a
  stale-page artifact. list-of-lands-available-for-taxes/ still shows "No
  available properties at this time" -- these 3 certs are not there either.
  No Dec-2025 results PDF found. CONCLUSION: genuinely UNRESOLVED at the
  source today. NO WRITE.

RESULT — GROUP 3a (2024-CA-19, 2023-CA-41, 2025-CA-37, 2021-CA-46,
  parity_status='mca_only'): Re-fetched hamiltonclerk.com/foreclosures/ raw
  HTML today. grep for 20[0-9]{2}-CA-[0-9]+ across the ENTIRE live page
  returns exactly 4 distinct cases: 2025-CA-28, 2025-CA-46, 2025-CA-66,
  2025-CA-92. None of 2024-CA-19 / 2023-CA-41 / 2025-CA-37 / 2021-CA-46
  appear anywhere on the page. Tried the new OCRS lever (see above) --
  structurally cannot search by case number, dead end. CONCLUSION: not
  published on any reachable public source today. NO WRITE.

RESULT — GROUP 3b (2025-CA-66, parity_status='mca_only'): DOES appear on the
  live foreclosures page today, confirming the 2026-07-27 finding persists
  (not a stale artifact): "DATE OF SALE - JULY 22, 2026 / Case No. 2025-CA-66;
  21st Mortgage Corp., vs. Ashley Victoria Steward-Ross / Judgment amount:
  $184,852.59." This matches mca.judgment_amount (184852.59) exactly, but the
  clerk's sale date (2026-07-22) does NOT match mca.auction_date (2026-08-05)
  -- and 2026-07-22 is now in the PAST relative to today (2026-07-31). The
  live page gives no SOLD/REDEEMED/CANCELLED annotation for this case, so
  there is no independently-verifiable sale OUTCOME to write, only a date
  discrepancy. Writing matched_clean here would misrepresent a genuine
  discrepancy (wrong auction_date in our own row) as a confirmed match --
  explicitly barred by the anti-fabrication guardrail. NO WRITE to
  parity_status. OCRS case-number lookup unavailable (see above), so the
  actual disposition of the 7/22 sale cannot be independently confirmed via
  any lever available this session.

NET: 0 of the 8 remaining rows are resolvable with real, independently-
verified data today. This is a genuine "clerk hasn't published it yet" /
"tool doesn't support this lookup" gap at the source, not a wiring or
pipeline bug. C/D cannot reach 95% (20/21) this session without fabricating
an outcome, which is prohibited. This script performs ONLY a defensive
re-verify of the already-fixed Group 1 rows (idempotent no-op if unchanged)
and fails loud if that re-verify ever regresses.
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

# Group 1 rows fixed by the 2026-07-27 script — defensive re-verify only.
GROUP1_EXPECTED = {
    "HAM-TD-CERT-2": {"parity_status": "matched_clean", "parity_source": "tier1_tax_deed_outcome"},
    "HAM-TD-CERT-300": {"parity_status": "matched_clean", "parity_source": "tier1_tax_deed_outcome"},
    "HAM-TD-CERT-539": {"parity_status": "matched_clean", "parity_source": "tier1_tax_deed_outcome"},
    "HAM-TD-CERT-540": {"parity_status": "matched_clean", "parity_source": "tier1_tax_deed_outcome"},
    "HAM-TD-CERT-585": {"parity_status": "matched_clean", "parity_source": "tier1_tax_deed_outcome"},
}

# Remaining 8 rows re-investigated this session — all NO WRITE, documented above.
GROUP2_NO_WRITE = ["HAM-TD-CERT-597", "HAM-TD-CERT-379", "HAM-TD-CERT-599"]
GROUP3_NO_WRITE = ["2024-CA-19", "2023-CA-41", "2025-CA-37", "2021-CA-46", "2025-CA-66"]


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


def main() -> int:
    log("=== hamilton C/D re-verify session (2026-07-31) START ===")
    regressions = 0
    confirmed = 0

    for case_number, expected in GROUP1_EXPECTED.items():
        cn_enc = urllib.parse.quote(case_number, safe="")
        rows = sb_get(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{cn_enc}&select=case_number,parity_status,parity_source",
        )
        if not rows:
            log(f"{case_number}: NO ROW FOUND -- FAIL LOUD (was previously fixed)", "ERROR")
            regressions += 1
            continue
        row = rows[0]
        if row.get("parity_status") != expected["parity_status"] or row.get("parity_source") != expected["parity_source"]:
            log(f"{case_number}: REGRESSION! expected={expected} got={row}", "ERROR")
            regressions += 1
            continue
        confirmed += 1
        log(f"{case_number}: still {row.get('parity_status')}/{row.get('parity_source')} -- OK", "VERIFIED")

    for case_number in GROUP2_NO_WRITE + GROUP3_NO_WRITE:
        log(
            f"{case_number}: NO WRITE this session -- re-verified live source "
            f"has no independently-confirmable disposition (see module docstring "
            f"for per-case evidence). Not a pipeline bug; source has not "
            f"published data or (2025-CA-66) has an unresolved date conflict "
            f"with no outcome annotation.",
            "UNTESTED",
        )

    log(
        f"=== DONE: group1_confirmed={confirmed}/5 regressions={regressions} "
        f"rows_written=0 (diagnosis reconfirmed, no new data available to write) ===",
        "INFO",
    )
    if regressions > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
