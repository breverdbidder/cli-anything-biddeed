# GOLD STANDARD shard-6 (volusia, union, sarasota) — 2nd firing addendum

dispatch_id: `95aa6180-826c-4bd0-8442-58da4023282d` · chat_session: `architect-20260720T160000` · 2026-07-21

## Context

This dispatch (same brief, same dispatch_id) had already been fully worked and shipped to main earlier in
this session — see `GOLD_STANDARD_SHARD6_VOLUSIA_UNION_SARASOTA_DISPATCH_95AA6180_SESSION_REPORT.md`
(commit `c7cee8b3`). Live re-query at the start of this firing confirmed that report's numbers exactly:
volusia 8/10, union 8/10, sarasota 5/10 — no drift, no duplicate work needed on the parts already done.

Rather than repeat that work, this firing picked up the one concrete, actionable item left open in that
report's "next-session priorities": **sarasota G** needed real `zone_standards` (density/FAR/parking) for
jurisdictions 824 (City of Sarasota) and 941 (North Port) — the real zoning *codes* already existed from the
prior firing's GIS work, only the cited numeric ordinance values were missing.

## sarasota G — real zone_standards backfill, with two real defects caught and fixed mid-session

Ran a background Workflow: 2 parallel research agents (City of Sarasota Zoning Code Art. VI; North Port
ULDC) → 1 apply agent → 2 independent adversarial refuters. This is a genuine case study in why the
ULTRALOOP two-refuter-vote protocol exists — both refuters found real problems, and a third was caught by
the orchestrating session's own follow-up live-DB diff:

### Defect 1 — fabricated citation on CG (caught by refuter B, REFUTED verdict)
The apply agent set Sarasota-city's `CG` zoning district (id=12333) to `far_regulated=false,
density_regulated=false`, citing a `"Table VI-503A"` that does not exist in the City's code. Refuter B
fetched the actual ordinance PDF and found only `Table VI-503` exists, covering the five modern
"implementing" commercial districts (CND/CSD/CRD/CGD/CSC) — CG is not a column in it. CG is explicitly a
legacy "non-implementing district" per the code's own district list, the same unresolved category as
RC/PID/RE-2/RMH, which the same migration correctly left `NULL`. **Fixed**: reverted CG's
`far_regulated`/`density_regulated` to `NULL` live and in the migration file, with a correction note.

### Defect 2 — silent write-gap, DB didn't match the committed migration (caught by orchestrating session)
After pushing the CG fix, a routine before/after re-check showed sarasota G's `far` metric drift between
two consecutive `pencil_dod_evaluate_county` calls with no intervening writes from this session
(96.0 → 92.9). Investigating found the live DB did not actually match the committed migration text for two
North Port districts: `R-1` (id=12330) and `R-2` (id=12331) had `far_regulated=NULL` live despite the
migration file explicitly setting `far_regulated=true` for both (and `max_far=0.05` *had* persisted
correctly) — a partial/silent write gap between what was applied and what was committed, not a data
problem. **Fixed** live: set `far_regulated=true` on both (matches the migration file and both refuters'
independently-confirmed real citation, North Port ULDC Table 3.2.4.1, FAR=0.05 for R-1/R-2).

A full live-DB-vs-migration-file diff across all 25 touched rows also found `RMF-1`/`RMF-2`/`RSF-2`/`RSF-3`
(Sarasota-city) had `far_regulated=NULL` live where the file intended an explicit `false` (residential zones
with no FAR row in Table VI-203/VI-303 — a real, cited "not regulated" fact, not an unknown). This has zero
effect on the G metric today (the evaluator's default for NULL on a residential-category district already
computes to `far_applicable=false`, same as an explicit `false`), but was fixed for data hygiene / to match
the committed, refuter-verified source of truth rather than relying on a coincidental default.

**Root cause of the write-gaps was not identified** (no `updated_at` column on `zoning_districts`, no
concurrent session found in `pg_stat_activity` at time of investigation) — flagged below for whoever owns
migration-apply tooling, since "the migration file says X and the commit message says STATUS 201" was
insufficient evidence that the live DB actually matched X, and would have shipped a metric based on data
that didn't exist without this session's own live re-verification catching it.

## Verification evidence

```
select public.pencil_dod_evaluate_county('sarasota');  -- final, stable across 2 consecutive live calls
-- A pass(93) B pass(98.3) C FAIL(37.2) D FAIL(37.2) E pass(95.3) F pass(98.3)
-- G FAIL(0, density=74.1 far=96.0 pk1000=0.0)   <- was density=0.0 far=0.0 pk1000=0.0 at session start
-- H pass(1.8) I FAIL(41.9) J FAIL(0)  -- 5/10, unchanged from the 1st firing (G data is real now, still
--   honestly below the 95% LEAST() gate on all three sub-metrics)

select public.pencil_dod_evaluate_county('volusia');  -- unchanged, regression check
select public.pencil_dod_evaluate_county('union');    -- unchanged, regression check
-- both byte-identical to the 1st-firing report's AFTER numbers (volusia 8/10, union 8/10)
```

`gold_standard_ultraloop_audit` row id=8066: dispatch `95aa6180`, county `sarasota`, letter `G`,
`survived=true`, `refuter_evidence` documenting both the refuter-B REFUTED-then-corrected finding and the
orchestrating session's own additional write-gap catch.

## Migrations shipped (applied live + committed to main, no side branches)

1. `migrations/20260721_gold_standard_shard6_run5361_sarasota_g_zone_standards.sql` (commit `8c149136`) —
   original real-ordinance backfill for 25 zoning_districts rows across jurisdictions 824/941.
2. Same file, corrected (commit `3debc1f3`) — CG fabricated-citation revert.
3. Live-only fixes (no further file changes needed — DB now matches the already-committed file text):
   `R-1`/`R-2` `far_regulated` NULL→true, `RMF-1`/`RMF-2`/`RSF-2`/`RSF-3` `far_regulated` NULL→false.

## Next-session priorities (unchanged from 1st firing, still accurate)

1. **sarasota C/D**: time-gated — needs 190 tax_deed sales to actually occur, or a scoring-methodology
   decision on excluding cancelled/redeemed rows from scope.
2. **sarasota G**: real ordinance data now covers density (74.1%) and FAR (96.0%) for 2 of 3 jurisdictions.
   Remaining gap: Venice (jurisdiction 933, point-in-polygon tax-account mismatch, never resolved) and
   `pk1000` (parking-per-1000sf) — genuinely 0% because Sarasota's own code regulates parking per-unit for
   residential (not applicable, correctly not fabricated) and the one commercial table that would have a
   real per-1000sf figure (Article VII Sec. VII-204) was unreachable this session (Municode SPA rendering
   issue affecting all node-ID attempts, Firecrawl out of credits).
3. **sarasota J**: still fleet-wide blocked, do not attempt a per-county formula generator (see 1st-firing
   report — the entire J-generator script family uses hardcoded fixed-ratio formulas, including at least
   one currently `survived=true` audit row elsewhere in the fleet).
4. **union B/F**: nothing to do until `63-2025-CA-0053` closes 2026-08-13.
5. **NEW — migration-apply reliability flag**: this session found a live DB state that silently diverged
   from an already-committed, already-refuter-verified migration file (R-1/R-2 `far_regulated`). Whoever
   owns the migration-apply tooling (`mgmt_sql.py` / the apply-agent pattern) should investigate whether
   multi-statement files can partially fail/get overwritten without surfacing a non-201 status — a `STATUS
   201` self-report was not sufficient evidence the live state matched the file text. Recommend a
   post-apply full-row diff (like the one this session ran ad hoc) become a standard step, not a
   catch-as-catch-can follow-up.

---
dispatch_id: 95aa6180-826c-4bd0-8442-58da4023282d
