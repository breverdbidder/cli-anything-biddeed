# Duval — Criterion B: Foreclosure Outcomes Capture (BUILD DIRECTIVE)

status: ARMED — fires on first Claude Code run after OAuth refresh
owner: AI Architect -> Claude Code session
blocked_by: claude-code-action.yml returns 401 until CLAUDE_CODE_OAUTH_TOKEN is refreshed
created: 2026-06-15 (session: Duval B/G status)

## Problem (VERIFIED this session)
- foreclosure_outcomes WHERE county ILIKE 'duval' AND data_source='duval_realforeclose' = 40 rows, frozen since 21:01Z.
- Supervisor target for B = >= 800. No outcomes-capture workflow exists.
- Only live GHA workflow = scrape-realauction-county.yml (CALENDAR discovery) — cannot move B.
- Gold B is measured vs the FULL frozen calendar (auctions_total = 20,025). 40 / 20,025 = 0.2%.
- summit_chat_dispatch B/G rows were kindless -> R5 quarantined -> never reached GitHub.

## Build (end to end)
1. New workflow scrape-duval-foreclose-results.yml (RealAuction/realforeclose RESULTS endpoint, Duval).
   Per auction capture: case_number, parcel_id, sale_date, third_party_winner (winning_bidder),
   winning_amount (sold_amount), sale_status.
2. Write to public.foreclosure_outcomes, data_source='duval_realforeclose', collision-guarded,
   with source + captured_at. Honesty markers on every field (VERIFIED/INFERRED).
3. Write-back into multi_county_auctions: sold_amount, winning_bidder, tier1_sale_status,
   tier1_sold_amount, *_captured_at. Then promote_tier1_from_outcomes() picks it up.
4. Daily post-auction loop: after each Duval auction day, capture same-day results immediately;
   feed third_party_winner + winning_amount as Shapira Formula training features.
5. Backfill the dead window: 2026-04-24 -> present (last real sold_amount_captured_at was Apr 24).
6. MOAT-ONLY: zero po_* / propertyonion_* reads. Linkage via zw_parcels / fl_parcels / BCPAO bridge.
7. Denominator guard: B measured vs auctions_total (20,025), NEVER closed_sold subset.
   Add gold_standard_precert_guards row guard_type='denominator_integrity' for B (mirror G's).

## Dispatch fix (so it does not re-quarantine)
- The launching summit_chat_dispatch row MUST carry dispatch_inputs.kind (NOT kindless).
- Do NOT blind-edit everest_dispatch_tick (45 live gh_push successes depend on it).
- Confirm a workflow_run_url is captured after dispatch.

## Done when
- foreclosure_outcomes (duval_realforeclose) >= 800 AND climbing daily (not a one-shot backfill).
- v_pencil_duval_dod.pct_verified_outcomes computed vs auctions_total (subset bug fixed).
- gold_standard_scoreboard duval b_verified_outcomes = PASS under the denominator guard.
- A real run_url exists in gha_dispatch_log for the results workflow.

## Trigger (after OAuth refresh)
Open issue in breverdbidder/cli-anything-biddeed labeled 'claude-code', body references this file:
docs/plans/DUVAL-B-OUTCOMES-BUILD.md
