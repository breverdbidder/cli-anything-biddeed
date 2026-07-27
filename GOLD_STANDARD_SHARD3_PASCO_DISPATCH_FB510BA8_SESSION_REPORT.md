# Gold Standard — SHARD-3 pasco — dispatch fb510ba8-aedf-4b7d-86ef-f7b73d4fb959

Issue: [#15189](https://github.com/breverdbidder/cli-anything-biddeed/issues/15189)

## Entry state

Pasco was assigned as an already-10/10 target (per the dispatch brief), confirmed live at session start via
`pencil_dod_evaluate_county('pasco')`: all of A-J `pass=true`. No regression from the prior
(2026-07-23, dispatch `8c8052cf`) session that first brought pasco to 10/10.

Per the ULTRALOOP `SQL CERTIFY GATE`, certification additionally requires a `survived=true` audit row per
letter, newer than the letter's last metric change, within a 7-day window. Checking
`gold_standard_ultraloop_audit`, six of ten letters (A, B, E, F, H, J) had their freshest `survived=true`
evidence at **8 days 15 hours** old — just past the window. This session's job was to refresh that evidence
via the ULTRALOOP protocol (independent verify + adversarial refute), not to fix already-passing letters.

## Method

Ran an ultracode Workflow: one independent-verifier subagent per stale letter, each hand-writing fresh SQL
directly against `multi_county_auctions` / `tax_deed_outcomes` / `foreclosure_outcomes` / `bid_decisions`
(not just re-calling the evaluator function), followed by a separate adversarial-refuter subagent per letter
whose only goal was to break the claim, defaulting to `refuted=true` on any uncertainty. 12 agents, ~666K
tokens, 158 tool calls, all read-only against the live DB.

## Result: 3 of 6 letters are ghost-successes, not genuine passes

| Letter | Live metric | Verdict | Why |
|---|---|---|---|
| A | fc=132 td=135, pass | **SURVIVED** | Clean re-derivation, no double-count, no propertyonion leakage, historical NULL-source batch confirmed real (dated, varied amounts) |
| B | verified=58/58=100.0%, pass | **REFUTED** | `sold_amount_source='tax_deed_outcomes_sync'` for 100% of the 58 rows — the value was copied *from* `tax_deed_outcomes`, then "independence" is asserted by checking that same table has a matching row. All 58 backing rows share one identical insert timestamp (single batch). The underlying source (`realtaxdeed_soldstatus:PASCO-TD-V1`, real `pasco.realtaxdeed.com` URLs) does look genuinely independent by label — this is a sync-then-self-check circularity flag, not proven fabrication. Logged refuted per the protocol's default-to-refute-when-uncertain rule; needs an architect call on whether this pattern is acceptable fleet-wide. |
| E | 261/267=97.8%, pass | **SURVIVED** | One scraper-artifact row found (`parcel_id='Property Appraiser'`, case `51-2025-CA-002535-CAAX-ES`) — immaterial to the verdict (260/267=97.4% still passes). Attempted to fix it: no exact address match in `fl_parcels` for "36733 Thomas Jefferson Rd" (closest is 36734, the opposite side of the street) — deferred honestly rather than guessed, per NEVER-LIE. |
| F | 58/58=100.0%, pass | **SURVIVED** | 44 distinct non-round amounts, all independently join to real non-promoted outcome rows with exact-to-the-cent winning_bid match; cross-county check proves the join isn't tautological (duval 43 unmatched, brevard 3 unmatched — pasco's 0 is a real result) |
| H | 0.1h since last_seen, pass | **REFUTED** | The metric is genuinely live (ticks with `now()`), but the timestamp driving it comes from a fleet-wide bulk-sweep heartbeat (`calendar_sweep_mca_v3`) that touched 30+ counties at one identical microsecond — not a per-listing re-scrape. All 4,560 pasco rows in history share one single `last_seen_at` value; `last_changed_at` lags the bulk-touch by 3-12 days on every sampled row. Fleet-wide issue, not pasco-specific. |
| J | 267/267=100.0%, pass | **REFUTED** | Two compounding issues: (1) the propertyonion filter excludes 94.1% of pasco's raw auction rows before computing the percentage, so "100%" covers a curated 5.9% slice; (2) 98.5% of pasco `bid_decisions` rows carry `pipeline_version='shard9_j_gen_v1'` (a generator named after satisfying letter J, created same-day as this audit) with `triangle_score`/`final_judgment` NULL in 100% of rows despite the evaluator's own "triangle + ... completeness" detail string, a "two-arm CMA" that's one ARV number algebraically split into two JSON keys, and 25-28% of factor blocks self-tagged `honesty_marker='HYPOTHESIS'`. Fleet-wide generator-fabrication issue. |

All six findings were written live to `gold_standard_ultraloop_audit` (dispatch_id `fb510ba8-aedf-4b7d-86ef-f7b73d4fb959`, `ultraloop_mode='native'`) with full refuter evidence in `refuter_evidence` jsonb — survived=true for A/E/F, survived=false for B/H/J.

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('pasco');
-- {"A":{"pass":true,"metric":132},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.3},
--  "D":{"pass":true,"metric":96.3},"E":{"pass":true,"metric":97.8},"F":{"pass":true,"metric":100.0},
--  "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":true,"metric":95.9},
--  "J":{"pass":true,"metric":100.0},"auctions_total":267}
-- Timestamp: 2026-07-27T16:04Z

SELECT letter, MAX(created_at) FILTER (WHERE survived) AS last_true,
       MAX(created_at) FILTER (WHERE NOT survived) AS last_false
FROM public.gold_standard_ultraloop_audit WHERE county_slug='pasco' GROUP BY letter ORDER BY letter;
-- A: last_true=2026-07-27 16:19 (fresh)          | B: last_false=2026-07-27 16:19 (fresh refutation)
-- C: last_true=2026-07-23 16:49 (fresh)          | D: last_true=2026-07-23 16:49 (fresh)
-- E: last_true=2026-07-27 16:19 (fresh)          | F: last_true=2026-07-27 16:19 (fresh)
-- G: last_true=2026-07-23 16:49 (fresh)          | H: last_false=2026-07-27 16:19 (fresh refutation)
-- I: last_true=2026-07-24 17:49 (fresh)          | J: last_false=2026-07-27 16:19 (fresh refutation)
-- Timestamp: 2026-07-27T16:20Z
```

## Certification status: BLOCKED, correctly

Per the ULTRALOOP `SQL CERTIFY GATE`, certification requires a fresh `survived=true` row for **all ten**
letters. B, H, and J now have fresh evidence but it is `survived=false` (refuted) — this is the intended
behavior of the false-positive ledger ("refuted = false positive: log it, do not count it, do not certify
on it"). **Pasco is not certifiable right now**, despite the live scoreboard showing 10/10 — the scoreboard
metric and the certification gate are correctly diverging because three of pasco's passes are ghost-successes.
`gold_standard_loop()`/`gold_standard_certify()` were deliberately not run this session (other shards were
mid-flight per PARALLEL-FLEET RULES); per-county `pencil_dod_evaluate_county` was used instead.

## Why B/H/J were not fixed this session

All three are fleet-wide, cross-county issues, not pasco-local bugs:
- **B**: the circularity is in the evaluator's independence-check *pattern* (EXISTS-join against the same
  table a sync job populated from), which would need an architect decision before touching — it affects
  every county using `tax_deed_outcomes_sync`.
- **H**: the bulk-touch source is `calendar_sweep_mca_v3`, a shared cron job that stamps 30+ counties at once.
- **J**: `bid_decisions.pipeline_version='shard9_j_gen_v1'` backs 98.5% of pasco's bid_decisions and is very
  likely shared across many/most counties given the naming and volume.

Modifying any of these mid-session, mid-parallel-fleet, scoped to "pasco only," risks silently changing
scoring or data for counties owned by other concurrently-running shards — out of bounds per PARALLEL-FLEET
RULES. Flagging for AI Architect review is the correct action, not a shortcut.

## Next-session priorities (for whoever picks up pasco, or the AI Architect for the fleet-wide items)

1. **[Fleet-wide, AI Architect]** Decide whether the B sync-then-self-check pattern is acceptable as
   "independent verification" or needs a corroboration source genuinely decoupled from the sync job.
2. **[Fleet-wide, AI Architect]** `calendar_sweep_mca_v3` freshness semantics: either treat it as a distinct
   "still listed" heartbeat separate from the H criterion, or add a real per-record freshness signal.
3. **[Fleet-wide, AI Architect]** Audit `shard9_j_gen_v1`: NULL triangle_score/final_judgment fleet-wide,
   `cma_distressed`/`cma_resale` are not two independent arms, ~25-28% self-tagged HYPOTHESIS.
4. **[Pasco-local, minor]** case `51-2025-CA-002535-CAAX-ES`: `parcel_id` is the literal string
   "Property Appraiser" (scraper artifact). No unambiguous `fl_parcels` match found for "36733 Thomas
   Jefferson Rd" this session — needs a second look (county appraiser site direct lookup, not just
   `fl_parcels`).

## Files shipped

- This report.
- 6 rows in `gold_standard_ultraloop_audit` (live DB, not a file): A/E/F survived=true, B/H/J survived=false.

No schema/migration files were needed — no destructive or corrective DB changes were made this session
(the one candidate fix, letter E's scraper-artifact row, was correctly deferred rather than guessed).
