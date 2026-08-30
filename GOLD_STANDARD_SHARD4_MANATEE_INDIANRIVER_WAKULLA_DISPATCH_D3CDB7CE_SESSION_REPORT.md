# Gold Standard shard-4: manatee / indian_river / wakulla (dispatch `d3cdb7ce-0688-4840-8151-51fdc744931a`)

Headless session, 2026-08-30 16:00Z. ULTRALOOP fallback mode (Task/Agent-orchestrated fan-out
research + independent adversarial verify, claims logged to `gold_standard_ultraloop_audit`).

## SCOREBOARD DELTA (live `pencil_dod_evaluate_county`, brief baseline vs live-at-session-start vs after)

| County | Brief baseline | Live at session start | After this session | Notes |
|---|---|---|---|---|
| manatee | 9/10 (C fail) | 9/10 (C fail, 89.5%) | 9/10 (C fail, 89.5%) | Hard structural ceiling, reconfirmed not re-worked (see below) |
| indian_river | 8/10 (C,D fail) | **10/10 (all pass)** | 10/10 | Already fixed by an earlier same-day session (commit `f4f53127`, issue #19605) — brief data was stale; cached `gold_standard_scoreboard` still shows C/D FAIL from `loop_run_id 15558` (13:30Z), pre-dating that fix |
| wakulla | 6/10 (C,E,I,J fail) | 6/10 (C,E,I,J fail) | 6/10 (C,E,I,J fail) | **J moved 86.5%→92.3% (44/52 true→48/52), a real gain — no letter flip (still <95% threshold)** |

## KEY FINDING: this exact shard scope was already worked this morning under a different dispatch

Before doing any new work, this session read `GOLD_STANDARD_SHARD4_MANATEE_SUWANNEE_WAKULLA_DISPATCH_0BF31675_SESSION_REPORT.md`
(dispatch `0bf31675`, 08:00Z wave, same day) — an exhaustive session on manatee+wakulla (this
dispatch's exact two non-certified counties, minus indian_river plus suwannee). That session:
- Reconfirmed manatee C and wakulla C are **hard structural ceilings** (canon deliberately
  excludes `CLERK_SSOT_CANCELLED` rows from C; manatee's ceiling is 159/172=92.4%, wakulla's is
  41/52=78.8% — both below the 95% threshold by construction, independently documented across 9+
  counties fleet-wide in `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`).
- Attempted wakulla E (TXD-124/125/126/127 parcel recovery) and got an honest 0/4 — wakullaclerk.com
  was unreachable that session.
- Backfilled wakulla I from 78.8%→90.4% via FL GIO value backfill + a newly-discovered
  "Zoning_Master_Pro" ArcGIS layer, landing at a session-ceiling of 47/52 (max reachable this
  session was 49/52=94.2%, still <95%).
- Found and documented a **fleet-wide evaluator bug**: letter J's `EXISTS` join matches
  `bid_decisions` to `multi_county_auctions` on `case_number` alone with no county filter, so
  wakulla's `25-CA-145` was being counted `deal_complete` via an unrelated **jefferson** county
  row. True wakulla J baseline was 44/52=84.6%, not the displayed 45/52=86.5%. Explicitly did not
  patch the shared evaluator function (correct call — single-shard unilateral edit to a fleet-wide
  function is out of scope).
- Attempted a real J generator run and got 0/8: its own live-state check reported the 4 CA cases
  (25-CA-9, 26-CA-19, 26-CA-31, 25-CA-145) as still missing assessed_value/market_value, even
  though the I-letter backfill (same session, same day) had supposedly already patched exactly
  those 4 rows.

This session **did not re-run the already-exhausted manatee-C / wakulla-C / wakulla-E
investigations** (re-verified their conclusions still hold via one fresh fresh probe, not a full
re-investigation, to avoid burning session budget re-deriving the same evidence). Instead it found
one genuinely new, previously-missed lever.

## WHAT SHIPPED THIS SESSION

**wakulla J: 44/52=84.6% (true) → 48/52=92.3% (true), FAIL→FAIL but a real +3.7pt gain**

Root cause of the morning session's 0/8 result: by the time its J-generator script ran, the I-letter
backfill for `25-CA-9`/`26-CA-19`/`26-CA-31`/`25-CA-145` had, in fact, already landed in the same
session (see `supabase/migrations/20260830_gold_standard_shard4_0bf31675_wakulla_i_card_completeness_backfill.sql`,
which patches exactly these 4 rows' assessed_value/market_value). This session's live query
confirmed all 4 rows genuinely carry real, non-null `assessed_value`/`market_value` today
(277716 / 152344 / 250045 / 151262) — the morning J-script's docstring narrative describing them
as still-NULL was stale/inaccurate relative to the actual DB state at the time it ran (or ran
before the I-backfill committed within the same session's pipeline — order not fully
reconstructable from the commit log alone).

Given the precondition was actually satisfied, this session:
1. Staged the production Shapira v14.0 model (`shapira_models` row, bucket `shapira-models`,
   `v14/2026-05-27-180308/{model.json,features.json}`) to `/tmp/shapira`.
2. Re-ran the existing, unmodified, previously audit-survived
   `scripts/shard7_wakulla_j_generator_real.py` (no code changes — same real-ARV formula
   `GREATEST(assessed_value, market_value)`, same real XGBoost v14 inference, same CMA-arm and
   factor-key construction already used for wakulla's other 44 rows).
3. Result: `inserted=4, updated=44, skipped_no_real_value=4` (the 4 TXD cases, still genuinely
   blocked). The 4 new rows are genuinely `county_slug='wakulla'` (not a collision), have distinct
   real ARVs and distinct real ml_scores (0.1067 / 0.954 / 0.9572 / 0.4667 — not a flat constant),
   and all 5 required factor keys (`distress_location`, `distress_property`, `distress_owner`,
   `cma_distressed`, `cma_resale`) populated per-property.
4. Live `pencil_dod_evaluate_county('wakulla')` before: J `{"pass": false, "detail":
   "deal_complete=45", "metric": 86.5}` (already known collision-inflated, true baseline 44/52).
   After: J `{"pass": false, "detail": "deal_complete=48", "metric": 92.3}`. Still FAIL (needs
   ≥50/52), but the 25-CA-145 collision is now moot (a real wakulla row now independently
   satisfies the same EXISTS check the jefferson row was previously the sole source of), and 3
   genuinely new rows closed.
5. Remaining gap: 2026-TXD-124/125/126/127 (4 rows). A fresh agent dispatched this session
   independently re-attempted parcel/owner discovery for these via `wakullaclerk.org`'s live tax
   deed sales page (confirmed reachable, unlike the morning session's report of an outage) and
   the current Wakulla Property Appraiser domain (`search.mywakullapa.com`, replacing the dead
   `wakullapa.com`) — reconfirmed **NOT FOUND** for all 4: the clerk page shows "Redeemed" status
   with zero linked documents/owner/parcel data (unlike sibling active-for-sale certs, which do
   have linked PDFs), and the appraiser portal is unreachable (`ECONNRESET`). This session's own
   J-generator run independently reconfirms the same 4-row gap (`skipped_no_real_value=4`). No
   `parcel_id`, `assessed_value`, or `bid_decisions` row was fabricated for these 4 cases.
   **48/52=92.3% is a genuine session ceiling** — J cannot reach 95% until these 4 rows get a
   parcel_id via a channel not yet found (clerk records-request or Tax Collector contact, per the
   morning session's own recommendation).

Adversarially verified by an independent refuter agent this session (not the agent/process that
made the fix): **SURVIVED**. Re-ran the live RPC, re-queried `bid_decisions` scoped to
`county_slug='wakulla'`, confirmed the 4 new rows' ARVs/ml_scores/factors are real and distinct,
confirmed the 4 TXD cases still have zero `bid_decisions` rows, confirmed the pre-existing 44 rows
were not corrupted, and confirmed the evaluator function itself was not modified. Logged to
`gold_standard_ultraloop_audit` id `19754` (dispatch `d3cdb7ce`, county=wakulla, letter=J,
survived=true).

## CEILINGS RECONFIRMED (no writes attempted — already exhaustively documented same-day)

- **manatee C**: 154/172=89.5%, max reachable 159/172=92.4% — below 95% by canon design
  (`CLERK_SSOT_CANCELLED` exclusion). See `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`.
- **wakulla C**: 41/52=78.8% — same canon-level exclusion; every non-cancelled row is already
  `matched_clean`.
- **wakulla E**: 48/52=92.3% — independently reconfirmed blocked this session (see above), same
  conclusion as the 08:00Z session with a different (now-live) domain.
- **wakulla I**: 47/52=90.4% — unchanged this session; the 08:00Z session already reached this
  session's own reachable ceiling (49/52=94.2% max, still <95%) and this session found no new
  lever (I's gap is downstream of the same E blocker plus one genuinely-ambiguous zoning seam at
  `25-CA-9`, already correctly left unresolved).

## indian_river: reconfirm-only, no action needed

Live `pencil_dod_evaluate_county('indian_river')` shows 10/10 (all letters PASS), fixed earlier
today by an unrelated session (`f4f53127 fix(gold-standard): indian_river C/D via live
RealAuction AJAX harvest, issue #19605`). The brief's baseline (8/10, C/D fail) and the cached
`gold_standard_scoreboard` table (still showing C/D FAIL as of `loop_run_id 15558`, evaluated
13:30Z) are both stale relative to the live evaluator — **the scoreboard cache has not been
refreshed since the fix landed**. No further action was taken (no write needed); flagging the
stale-cache gap for whichever session next runs `gold_standard_loop()`.

## Guardrail compliance

- No fabricated `parcel_id`, `assessed_value`, `bid_decisions`, or `parity_status` row.
- `pencil_dod_evaluate_county` was not modified (fleet-wide function, out of single-shard scope).
- `gold_standard_loop()` / `gold_standard_certify()` were **not** invoked — other shard sessions
  were plausibly still in flight; per-county `pencil_dod_evaluate_county` calls used instead, per
  this dispatch's own instructions.
- Mandatory close-out write applied to `gold_standard_campaign` (dispatch `d3cdb7ce...`,
  `exit_reason='genuine_leverage_exhausted_this_session'`, `criteria_passed` populated with the
  live A–J booleans for all 3 counties, `session_end_at` set).

## NEXT-SESSION PRIORITIES

1. **wakulla J/E/I**: the only remaining honest lever is a non-web channel for
   2026-TXD-124/125/126/127 — a Wakulla Clerk records request (Form DR-512 tax deed applications)
   or a direct call to the Wakulla Tax Collector, per the 08:00Z session's own recommendation.
   Further web-scraping attempts on the same 2 domains are unlikely to yield new results (2
   independent sessions, different times, same conclusion).
2. **wakulla J evaluator collision bug**: `GOLD_STANDARD_J_EVALUATOR_CROSS_COUNTY_COLLISION_FINDING_20260830.md`
   still needs AI-Architect triage for a fleet-wide `bd.county_slug = mca.county` join-predicate
   fix — this session's work made the wakulla-side symptom moot but the structural bug is
   unpatched and likely affects other counties in both directions.
3. **manatee C / wakulla C canon decision**: `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`'s
   Option A/B/C recommendation is still open across 9+ counties fleet-wide — this is now a
   repeated, multi-week, multi-session cost sink until an owner decision lands.
4. **gold_standard_scoreboard cache staleness**: indian_river (and possibly others) shows stale
   FAIL letters in the cached scoreboard table hours after the live evaluator already passed them
   — worth a `gold_standard_loop()` refresh next time no other shard is confirmed in-flight, so
   certification logic (which may read the cache) doesn't miss an already-earned PASS.
