# Gold Standard shard-3: lake / madison / union — dispatch 3c272d5a

Session: `architect-20260901T080000`, loop run 15894, 2026-09-01 08:00Z. `decision_log` id=2971.

## Live baseline (session start, matched issue brief exactly — zero drift)

| County | Score | Failing letters |
|---|---|---|
| lake | 9/10 | C 87.9% (matched_clean=124/141) |
| madison | 8/10 | B null (verified=0/closed_sold=0), F null (tier1_sold=0/closed_sold=0) |
| union | 6/10 | C 75.0% (3/4), E 75.0% (3/4), I 75.0% (3/4), J 75.0% (3/4) |

## Live result (session end, re-verified via `pencil_dod_evaluate_county`)

Identical to baseline for all three counties — zero writes applied, zero drift, zero regression.

```
lake:    A PASS B PASS C FAIL(87.9) D PASS E PASS F PASS G PASS H PASS I PASS J PASS  -- 9/10
madison: A PASS B FAIL(null) C PASS D PASS E PASS F FAIL(null) G PASS H PASS I PASS J PASS -- 8/10
union:   A PASS B PASS C FAIL(75.0) D PASS E FAIL(75.0) F PASS G PASS H PASS I FAIL(75.0) J FAIL(75.0) -- 6/10
```

## FINDING #1 — lake C, madison B/F: NOT re-attempted (same-day precedent already exhausted these)

A prior same-day session (dispatch `923b7ff3`, run 15558, ~16:00Z the day before this
UTC-crossing session) already reconfirmed both:
- **lake C**: capped by the fleet-wide `CLERK_SSOT_CANCELLED`-vs-`matched_clean` canon
  question, declined for unilateral fix by 8+ prior architect sessions since 2026-08-16
  (id=1373 through id=2733) because it retroactively changes certification math for
  ~20 counties. Outside single-shard authority.
- **madison B/F**: 12th+ consecutive session reaching the same conclusion — every
  reachable channel (myfloridacounty ORI, Civitek OCRS, Grizzly/floridapa.com WMS/WFS
  sales layers, qpublic) is Turnstile-gated or access-locked. Only remaining lever is
  a direct Clerk's-office records request, outside automated-session scope.

Re-running either within hours of that reconfirmation would be duplicate, low-value
work. This session's fresh-research budget was spent entirely on union, the one
target with genuinely unexplored state.

## FINDING #2 — union C: newly diagnosed as the SAME structural ceiling pattern (not a bug)

`matched_clean` = 3/4 because case `63-2025-CA-0053` carries `parity_status=
CLERK_SSOT_CANCELLED`, evidenced by a real, cited clerk record (Order Granting Motion
to Cancel Foreclosure Sale and Vacate Final Judgment, filed 2026-08-03, Book 489 Page
561, cross-referenced against the Final Judgment of Foreclosure, Book 480 Page 6 —
already in `parity_source`). Per the evaluator's own documented design (see
`supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql`),
`CLERK_SSOT_CANCELLED` is intentionally excluded from `matched_clean` (it represents a
real divergence the clerk source resolved, not a no-divergence clean match) while
counting toward `matched_any` (which is 100.0%, confirming this). With only 4 total
union auctions, one genuinely-cancelled case structurally caps C at 75% — the exact
same "evaluator by design" ceiling already established for lake/st_lucie/charlotte C.
Not re-litigated for the same fleet-wide-authority reason as Finding #1. No write made.

## FINDING #3 — union E/I/J: genuinely researched fresh, genuinely blocked

All three gate on the single row `af29ad63-3b4e-4ec8-8ec5-b6bbfb0a63b2`, case
`63-2026-CA-0022` (scheduled foreclosure, auction_date 2026-10-15, `created_at`
2026-08-26 — new since the last union-focused session, dispatch `342f5d3e`, 2026-08-09,
which only had 3 union auctions total). `property_address`/`parcel_id` are both NULL;
J is blocked transitively (`bid_decisions` has zero rows for this case, and the
evaluator's card-completeness/deal-completeness checks require address+geo+value+
parcel-zoned first).

Ran a 3-agent parallel ULTRALOOP research workflow (dispatch scoped, one angle per
agent — unionclerk.com subpages/direct docket, statewide court-record aggregators +
legal-notice publishers, property-appraiser/GIS) — **all three found=false**, zero
trace of the case anywhere on the public web (only unrelated Union County cases
surfaced in search results, explicitly checked and ruled out).

Went further than the agents with a direct real-browser (Playwright + system
Chromium) session against Civitek OCRS county 63 (`civitekflorida.com/ocrs/county/63/`,
the backing system for `unionclerk.com`'s official-records search):
- `unionclerk.com`'s own calendar page (re-scraped live via the existing verified
  `scripts/shard9_union_clerk_realdata_ingest.py`) currently lists only 1 foreclosure
  case (`63-2024-CA-0047`) — confirms case `63-2026-CA-0022` is not yet on the
  public calendar, consistent with its ~6-week-out sale date.
- Drove the full Public → Disclaimer → Case Search flow on Civitek OCRS, correctly
  filled Year=2026, Court Type=Circuit Civil (CA), Sequence#=22 (decoded from the
  case number format `63-2026-CA-0022`), and confirmed all three fields accept and
  retain the values.
- The form carries a `cf-turnstile-response` hidden field (Cloudflare Turnstile).
  Confirmed via direct DOM read that this token **never populates** (empty string)
  even after an 8s pre-submit wait + a further 20s post-submit wait — the Search
  button click silently resets the form to blank with **no validation error message**
  rendered anywhere in the page body. This is a bot-detection silent block, not a
  form-validation failure (all required fields were correctly filled).
- Matches the exact same root cause documented extensively elsewhere in this campaign
  for other counties' Civitek OCRS instances (e.g. madison's Third Circuit OCRS,
  bradford's ORI search). Per campaign guardrails, CAPTCHA-solving/detection-evasion
  tooling was not attempted.

No write made for E/I/J. BLANK > WRONG.

## Session close-out

- `gold_standard_campaign` id=5494 updated: `criteria_passed` per-county A-J (matches
  the live-reconfirmed table above), `exit_reason='ceilings_reconfirmed_no_new_lever_found'`,
  `session_end_at` recorded.
- `decision_log` id=2971 records full findings, alternatives considered/rejected,
  reasoning, and the zero-drift outcome.
- No `gold_standard_ultraloop_audit` rows inserted — no letter's status changed and no
  "letter passes" claim was made this session to adversarially verify. All ULTRALOOP
  workflow agent verdicts (3x found=false on union docket research) are negative/
  no-fabrication findings, captured in this report and `decision_log` id=2971 instead.
- `gold_standard_certify()` not run — none of the 3 counties are at 10/10.

## SQL VERIFICATION

```sql
-- lake
SELECT public.pencil_dod_evaluate_county('lake');
-> {"A":{"pass":true,"metric":11},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":87.9},
    "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":97.9},"F":{"pass":true,"metric":100.0},
    "G":{"pass":true,"metric":96.0},"H":{"pass":true,"metric":0.9},"I":{"pass":true,"metric":95.0},
    "J":{"pass":true,"metric":97.2},"auctions_total":141}

-- madison
SELECT public.pencil_dod_evaluate_county('madison');
-> {"A":{"pass":true,"metric":2},"B":{"pass":false,"metric":null},"C":{"pass":true,"metric":100.0},
    "D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null},
    "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.0},"I":{"pass":true,"metric":100.0},
    "J":{"pass":true,"metric":100.0},"auctions_total":8}

-- union
SELECT public.pencil_dod_evaluate_county('union');
-> {"A":{"pass":true,"metric":1},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":75.0},
    "D":{"pass":true,"metric":100.0},"E":{"pass":false,"metric":75.0},"F":{"pass":true,"metric":100.0},
    "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.2},"I":{"pass":false,"metric":75.0},
    "J":{"pass":false,"metric":75.0},"auctions_total":4}
```
Timestamp: 2026-09-01T08:18Z (session start and session end evaluations byte-identical).

## Next-session priorities

1. **union E/I/J**: only remaining lever is waiting for `63-2026-CA-0022` to appear on
   `unionclerk.com`'s live calendar as the 2026-10-15 sale date approaches (the site's
   calendar appears to be a rolling near-term window, not a full-docket listing) —
   check back in the following session and re-run `scripts/shard9_union_clerk_realdata_ingest.py`
   first before any manual research, since it may resolve this for free.
2. **union C / lake C / madison B/F**: all three are now-documented structural
   ceilings needing either (a) explicit cross-shard/architect authority to resolve the
   `CLERK_SSOT_CANCELLED` canon question fleet-wide, or (b) a human/owner-initiated
   Clerk's-office records request for madison. Not single-shard-session-fixable.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
