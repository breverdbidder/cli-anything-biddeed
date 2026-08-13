"""Lake C letter fix (dispatch 7bcb4434-c068-4a5d-b140-0dcf65c8c87f).

BASELINE (VERIFIED live via pencil_dod_evaluate_county, 2026-08-13):
  C: matched_clean=106/120 (88.3%) FAIL — need >=95% (114/120)

DIAGNOSIS: The C gap is exactly the 14 rows carrying
parity_status='CLERK_SSOT_CANCELLED' (parity_source='lake_clerk_foreclosure'
or '...:manual_recheck_20260812'). These are deliberately excluded from
matched_clean by pencil_dod_evaluate_county's design (they count toward D
"matched_any" instead, since D=120/120=100% already) — see migration
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql docstring.
This exclusion pattern is intentional and repeated fleet-wide (wakulla,
manatee, charlotte, desoto/taylor — grep CLERK_SSOT_CANCELLED across scripts/).

ROOT-CAUSE BUG FOUND (scripts/clerk_ssot/run_parity.py, lines ~230-250):
run_parity.py's reconciliation logic can only ever WRITE a row INTO
CLERK_SSOT_CANCELLED (when the live clerk calendar currently shows it
cancelled). It has NO reverse path — the clean_matches UPDATE explicitly
excludes any row already CLERK_SSOT_CANCELLED
(`AND parity_status IS DISTINCT FROM 'CLERK_SSOT_CANCELLED'`), so once a
case is marked cancelled it can never be automatically un-cancelled even if
the court later reschedules it and the clerk calendar reflects that. This
is a structural staleness bug in run_parity.py, not specific to lake, but
only reproduced/fixed for lake in this session (out of scope to patch the
shared script here — flagging for a follow-up SUMMIT).

LIVE VERIFICATION (this session, 2026-08-13):
  Ran scripts/clerk_ssot/parsers/lake.parse_foreclosure() live:
    https://foreclosurecalendar.lakecountyclerkfl.gov/?view=list
    -> 72 rows, 8 currently cancelled on the live calendar.
  Cross-referenced against the 14 DB CLERK_SSOT_CANCELLED case numbers:
    - 7 of 8 live-cancelled rows matched DB rows exactly (still correctly
      cancelled — no action).
    - 6 DB rows are simply absent from the live forward-looking list (their
      auction_date is in the past with no reschedule found — correctly
      excluded, nothing to reconcile without fabricating data).
    - 1 row, case 2024CA000186, was found ON the live calendar with
      cancelled=False, rescheduled to sale_date=2026-12-08 (was
      auction_date=2026-08-18, auction_status=CANCELLED in our DB). This is
      the one genuine, live-verified stale record.

FIX APPLIED (PostgREST PATCH, not run_parity.py's Management-API path —
this sandbox has no exec_sql RPC):
  PATCH multi_county_auctions WHERE county=lake AND case_number=2024CA000186
    auction_status: CANCELLED -> scheduled
    auction_date:   2026-08-18 -> 2026-12-08
    parity_status:  CLERK_SSOT_CANCELLED -> CLERK_VERIFIED
    parity_source:  lake_clerk_foreclosure -> lake_clerk_foreclosure:manual_recheck_20260813

RESULT (confirmed live via pencil_dod_evaluate_county immediately after):
  C: matched_clean 106/120 (88.3%) -> 107/120 (89.2%) — still FAIL
  D: matched_any 120/120 (100.0%) -> 120/120 (100.0%) — unchanged, PASS
  A,B,E,F,H,I,J: unchanged (spot-checked full JSON, no regression)

CONCLUSION: This is a real, non-fabricated, structural ceiling — NOT a
Firecrawl/SPA-gate problem. The clerk_ssot lake parser
(scripts/clerk_ssot/parsers/lake.py) hits a plain ASP.NET WebForms page via
httpx/bs4, no JS/SPA/Cloudflare gate, and works today with zero issues
(confirmed live, 72/72 rows parsed cleanly). Firecrawl was NOT needed and
was NOT re-tested — the officialrecords.lakecountyclerk.org /
courtrecords.lakecountyclerk.org SPA-gated sites referenced in prior lake
sessions are used for B/F sold-amount discovery only (already PASS at
100%), not for C/D, so they are irrelevant to this letter.

Remaining 13 CLERK_SSOT_CANCELLED rows are genuinely cancelled per
live-clerk cross-check (7 still on the live cancelled list; 6 aged off the
forward-looking list entirely with no reschedule evidence). No further
lever exists to raise C to 95% (114/120 needed, i.e. <=6 non-clean rows
tolerated) without either (a) run_parity.py gaining a reverse
un-cancel-on-reschedule path and organically finding more like
2024CA000186 in future daily runs, or (b) fabricating clean status on
genuinely-cancelled sales, which is a Honesty Protocol violation and out of
bounds.

NEXT-SESSION LEVER (real, not yet executed): fix run_parity.py's
clean_matches UPDATE to also re-reconcile CLERK_SSOT_CANCELLED rows whose
ssot_row now shows cancelled=False (i.e. drop the blanket
`parity_status IS DISTINCT FROM 'CLERK_SSOT_CANCELLED'` guard and instead
gate on the ssot_row's live cancelled flag). That is a change to a shared
27-county pipeline script, not a lake-only patch — needs its own review
across all clerk_ssot counties before landing, and was explicitly out of
scope for this session (CLAUDE.md guardrail: do not modify
gold-standard-loop-* scoring logic; this is adjacent-but-different, the
parity RUNNER not the EVALUATOR, but still warrants a dedicated session).
"""

if __name__ == "__main__":
    print(__doc__)
