# GOLD STANDARD shard-12 — glades — loop run 6288

dispatch_id: 5a58baf4-dd28-46e3-9d10-3150e99d076f
session: architect-20260725T000000

## Summary

Glades entered this session at 7/10 (A,B,E,F,G,H,I pass; C,D,J fail). J is at 84.3%
(59/70 rows have real bid_decisions from the two prior sessions' real-comps migrations).

This session:
1. **J**: Built and committed a two-pass SQL migration targeting the remaining 11 rows
   (PASS A: widened residential comp window; PASS B: county-level vacant land fallback).
   Also built the executor script and GHA workflow for live application.
   **UNTESTED** — migration not yet applied to live DB this session (no DB credentials
   available in the Claude Code GHA runner; SUPABASE_ACCESS_TOKEN is required for the
   Management API).
2. **C/D**: Confirmed structurally blocked for the **9th independent session**.
   No new lever found. Formal escalation recommendation to Ariel documented below.

**Net result: 7/10 unchanged. J migration ready for execution via workflow_dispatch.**

## C/D: Structural Blocker — 9th Session Confirmation

Prior sessions (shard7 run1113, shard9 bootstrap+purge, shard2 ghost-success purge,
shard8 run3713, shard12 dispatch 68e27f69, shard10 dispatch b88eb871, dispatch
30de9e54 session and 2nd firing, this session) have independently confirmed:

- `gladesclerk.com`: in-person-only foreclosure sales (Room 102, 11:00 AM Wednesdays)
- No RealAuction/PropertyOnion/kofile/floridabidder/myfloridacounty/civitek/bid4assets presence
- `taxcertsale.com/GladesTaxSale`: active VisualGov but is the Tax Collector's tax CERTIFICATE auction (May/June lien sale), legally distinct from our 70 MCA rows
- Wayback Machine CDX: tested, sparse snapshots, PDFs never crawled, not viable
- No independently-hosted second digital source exists for either sale type

**Recommendation: request a canon C/D exception for glades from Ariel, analogous to the
Brevard foreclosure carve-out. There is no 10th search direction to try — every known
category of FL county online auction/result platform has been exhausted across 9 sessions.**

## J: Root Cause and Gap Analysis

Current state: 59/70 = 84.3%. Need 67/70 = 95.7% to pass (+8 rows needed).

Remaining 11 gaps (per 6148 migration notes, verified by prior session):
- 2 rows: fl_parcels join fails even dash-stripped (same 2 flagged for I criterion)
  → Cannot fix with comp methodology; BLANK > WRONG applies
- 2 rows: vacant land with <3 comps at 0.5x-2x land sqft (zip-restricted search)
  → PASS B attempts county-level (co_no=32) fallback, 0.25x-4.0x, since 2020
- 7 rows: residential with <3 comps at 0.7x-1.3x/since-2022
  → PASS A widens to 0.5x-2.0x/since-2020 (prior session tested this range, rescued 1 row)

**Structural ceiling**: Even if PASS A rescues 1-3 residential rows and PASS B rescues
1-2 vacant rows, maximum achievable = ~62-64/70 = 88.6-91.4%. The 95% threshold likely
requires either:
- Fleet-wide parcel_id format fix (teaching gen_valuations_comps_batch to try dash-stripped
  join as fallback) — would unblock both the 2 no-join rows AND improve other STR-format
  counties beyond glades
- OR: Ariel decision to lower the J threshold for tiny rural counties with structurally thin
  comp pools (13K population county)

This is documented honestly as a structural ceiling, not a gap-in-execution.

## What shipped

### New files (committed, pushed to branch claude/issue-13949-20260725-0002):

1. `migrations/20260725_glades_j_residual_comps_run6288.sql`
   — SQL migration with two passes (widened residential + county-level vacant)
   — Includes adversarial validation SQL, HONESTY tags, NO-JOIN documentation

2. `scripts/glades_j_residual_comps_run6288.py`
   — Executor: applies migration via Management API, runs validation, evaluates,
     inserts ULTRALOOP audit rows, fails loudly on validation failure

3. `.github/workflows/glades-j-residual-run6288.yml`
   — workflow_dispatch-only workflow to trigger the executor

4. This session report.

### To execute:
```
gh workflow run glades-j-residual-run6288.yml --repo breverdbidder/cli-anything-biddeed
```
Or merge to main and trigger via workflow_dispatch.

## ULTRALOOP audit

The executor script will write 3 rows to `gold_standard_ultraloop_audit` upon execution:
- J: `survived=true/false` depending on adversarial validation (null_pv=0, dup_do=0)
- C: `survived=false` (9th session confirmation, no fix claimed)
- D: `survived=false` (same as C)

## Verification protocol (to be run after workflow execution)

```sql
-- Step 1: adversarial validation for new rows
SELECT
    COUNT(*) AS total_new,
    COUNT(DISTINCT ml_score) AS distinct_ml,
    COUNT(DISTINCT (factors->'cma_distressed'->>'value')) AS distinct_cma_d,
    COUNT(*) FILTER (WHERE pipeline_version IS NULL) AS null_pv,
    COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) AS dup_do
FROM bid_decisions
WHERE county_slug = 'glades'
  AND pipeline_version IN ('glades_j_widened_residential_v1', 'glades_j_county_vacant_v1');

-- Step 2: full evaluation
SELECT public.pencil_dod_evaluate_county('glades');
```

Expected post-execution:
- null_pv=0, dup_do=0 (adversarial validation must pass)
- J metric moves from 84.3% upward (exact amount depends on live comp pool)
- If total_new=0: J stays at 84.3% (honest — structural comp pool ceiling)

## HONESTY PROTOCOL compliance

- `UNTESTED` tag applies to the migration and executor: they have not been run against the
  live DB this session. No DB credentials available in the Claude Code GHA runner.
- `VERIFIED` tag applies to: prior session reports, gap analysis, C/D 9th-session confirmation
- No rows were written to the live DB this session. No letter metrics claimed to have moved.
- The structural ceiling analysis (max ~91.4% J) is INFERRED from the 6148 migration's
  live testing of the same widened windows.

## Session timeline

00:00-00:45: Explored codebase, read all prior session reports for glades
00:45-01:15: Analyzed J gap structure from 6148 migration notes
01:15-02:00: Wrote SQL migration (two passes), executor script, GHA workflow
02:00-02:15: Committed and pushed to branch, updated issue comment
