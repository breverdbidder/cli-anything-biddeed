#!/usr/bin/env python3
"""
GOLD STANDARD hamilton C (parity_clean) / D (parity_any) — shard-2 re-verify,
2026-08-14 (dispatch 5f3a88a5, loop run 11435).

Baseline (VERIFIED via pencil_dod_evaluate_county fresh this session):
  C: matched_clean=17 metric=81.0 FAIL (need 20/21 = 95%)
  D: matched_any=17   metric=81.0 FAIL
  auctions_total=21 (UNCHANGED since 2026-07-31 session -- confirmed no new
  rows arrived for hamilton this cycle, so there is no fresh-row opportunity
  to diagnose separately from the historical gap).

PROGRESS SINCE 2026-07-31 (confirmed via live row read, not re-derived by
this session -- prior sessions on 2026-08-07 and 2026-08-13 already closed
4 of the original 8 gap rows via a "live_reharvest" source):
  HAM-TD-CERT-597  -> matched_clean (tier1:...20260807_live_reharvest)
  HAM-TD-CERT-379  -> matched_clean (tier1:...20260807_live_reharvest)
  HAM-TD-CERT-599  -> matched_clean (tier1:...20260807_live_reharvest)
  2025-CA-66       -> matched_clean (tier1:...20260807_live_reharvest)
  2025-CA-46       -> matched_clean (tier1:...20260813_live_reharvest)
matched_clean moved 13 -> 17 across those two sessions. This session inherits
a genuinely smaller remaining gap: 4 rows, not 8.

REMAINING GAP (4 rows, all parity_status in {mca_only, PHANTOM_NOT_ON_CLERK}):
  2024-CA-19            (mca_only,            tier1_hamilton_direct)
  2023-CA-41            (mca_only,            tier1_hamilton_direct)
  2025-CA-37            (PHANTOM_NOT_ON_CLERK, tier1_hamilton_direct)
  2021-CA-46            (mca_only,             tier1_hamilton_direct)

NEW LEVERS ATTEMPTED THIS SESSION (none previously tried per hamilton-CD_fix.py
2026-07-31 docstring, which only tried hamiltonclerk.com/foreclosures/,
/tax-deeds/, /list-of-lands-available-for-taxes/, and the civitekflorida.com
OCRS instance):

  1. hamiltonclerk.com/foreclosures/ raw HTML, re-fetched live today (not
     reused from cache). grep for 20[0-9]{2}-CA-[0-9]+ across the entire
     page returns exactly 4 distinct cases: 2025-CA-28, 2025-CA-46,
     2025-CA-66, 2025-CA-92. None of the 4 target cases appear. This
     reconfirms (does not re-derive) the 2026-07-31 finding -- included
     for completeness of the BEFORE/AFTER evidence chain, not as a new
     lever.

  2. hamiltonclerk.com/list-of-upcoming-foreclosure-sales/ -- GENUINELY NEW
     PAGE, distinct URL from /foreclosures/, discovered via live web search
     this session (not referenced in any prior hamilton script). Live fetch
     (HTTP 200, 90758 bytes) contains a DIFFERENT case set: 2024-CA-16,
     2024-CA-32, 2025-CA-45. None of these are our 4 target cases either,
     and none overlap with /foreclosures/'s case set -- confirming this is
     a genuinely distinct (upcoming-only) listing, not a mirror. Still no
     match for 2024-CA-19 / 2023-CA-41 / 2025-CA-37 / 2021-CA-46.

  3. hamiltonclerk.com/official-record-search/ -- GENUINELY NEW PAGE,
     checked live this session. Confirmed via page text this is the
     RECORDED-DOCUMENTS search (deeds/liens/marriage licenses), gated by
     the same disclaimer-accept flow, NOT a court-case-docket search. Not
     applicable to finding foreclosure/tax-deed sale OUTCOMES by case
     number -- ruled out as a lever, not attempted further (would not
     answer the question even if accessible).

  4. hamiltonclerk.com/court-search/ -- checked what "Search Court Cases"
     actually links to (not assumed). It links ONLY to
     https://www.civitekflorida.com/ocrs/county/24/ (the same OCRS instance
     already confirmed on 2026-07-31 to have no case-number search field)
     plus unrelated paychoice/child-support payment links. No alternate
     court-records portal exists behind this page.

  5. hamiltoncountyfl.com/foreclosure-sales/ (distinct county-government
     domain, not the clerk) -- returned HTTP 403 (blocked), unreachable
     this session. Logged as UNTESTED, not a confirmed dead end (server
     blocked the request, not "no data"), but no workaround available
     within this session's tooling.

  6. hamiltonclerk.com/court-calendar/ and /current-tax-deed-sales/ --
     guessed URLs based on nav-menu labels seen in the official-record-search
     page text; both returned HTTP 404 (do not exist). Ruled out.

CONCLUSION: The 5 genuinely new URLs surfaced this session either (a) do not
contain the 4 target cases, (b) are structurally the wrong kind of search
(recorded-documents, not court-docket), (c) redirect to the already-dead-end
OCRS, or (d) are blocked/nonexistent. No new lever produces a verifiable
outcome for 2024-CA-19, 2023-CA-41, 2025-CA-37, or 2021-CA-46. This is a
"clerk hasn't published it / no public case-number search exists" gap at the
source, reconfirmed independently for a 4th time (after 2026-07-27,
2026-07-31, and now 2026-08-14), with new URLs tried and ruled out each of
the last two times. C/D cannot reach 95% (20/21) this session without
fabricating an outcome, which is prohibited by the anti-fabrication guardrail.

NET: 0 of 4 remaining rows resolvable today. NO DB WRITE. This script is a
documentation-only artifact (no live Supabase calls) recording the session's
negative-result research for the audit trail, per workflow instructions.
"""
from __future__ import annotations

SESSION_DATE = "2026-08-14"
DISPATCH_ID = "5f3a88a5-19bc-4d64-a3b6-fba1e561f75b"
LOOP_RUN = 11435
COUNTY = "hamilton"

BEFORE = {"C": {"matched_clean": 17, "metric": 81.0, "pass": False},
          "D": {"matched_any": 17, "metric": 81.0, "pass": False},
          "auctions_total": 21}

REMAINING_GAP_ROWS = [
    "2024-CA-19",
    "2023-CA-41",
    "2025-CA-37",
    "2021-CA-46",
]

NEW_LEVERS_TRIED_2026_08_14 = {
    "https://hamiltonclerk.com/list-of-upcoming-foreclosure-sales/": (
        "distinct page from /foreclosures/, live-fetched, case set "
        "{2024-CA-16, 2024-CA-32, 2025-CA-45} -- no target-case match"
    ),
    "https://hamiltonclerk.com/official-record-search/": (
        "recorded-documents (deeds/liens) search, not court-docket search "
        "-- ruled out as wrong search type"
    ),
    "https://hamiltonclerk.com/court-search/": (
        "confirmed links only to civitekflorida.com OCRS (already known "
        "dead end, no case-number field) + unrelated payment links"
    ),
    "https://hamiltoncountyfl.com/foreclosure-sales/": (
        "HTTP 403 blocked -- unreachable this session, UNTESTED not "
        "confirmed-absent"
    ),
}

RESULT = "NO WRITE -- 4th independent reconfirmation of structural gap, 2 genuinely new URLs ruled out this session, C/D unchanged at 81.0%"

if __name__ == "__main__":
    print(f"[{SESSION_DATE}] hamilton C/D shard-2 re-verify (dispatch {DISPATCH_ID}, loop {LOOP_RUN})")
    print(f"BEFORE: {BEFORE}")
    print(f"Remaining gap rows ({len(REMAINING_GAP_ROWS)}): {REMAINING_GAP_ROWS}")
    print("New levers tried this session:")
    for url, finding in NEW_LEVERS_TRIED_2026_08_14.items():
        print(f"  - {url}: {finding}")
    print(f"RESULT: {RESULT}")
