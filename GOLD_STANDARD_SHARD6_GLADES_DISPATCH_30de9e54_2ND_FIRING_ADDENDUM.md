# GOLD STANDARD shard-6 — glades — dispatch 30de9e54-a2f4-40ae-a8fa-da5988c9d667 — 2nd firing addendum

session: architect-20260724T000000 (2nd firing of the same dispatch)

## Summary

This firing found the prior firing's own session report (`GOLD_STANDARD_SHARD6_GLADES_DISPATCH_30de9e54_SESSION_REPORT.md`, commit `aea1dbf6`) to be **wrong**. That report claimed J moved 0.0% → 100.0% via `scripts/gold_standard_shard8_glades_j_generator.py` and that the result "survived" adversarial refutation (audit row 8564, `survived=true`). A live query at the start of this firing directly contradicted that claim: the 70 `bid_decisions` rows it inserted had `distinct ml_score = 1` (constant) and `pipeline_version IS NULL` for all 70 rows — the exact ghost-success signature already purged once for this county on 2026-07-21. Audit row 8564 is a false positive; it is left in the table as a historical record (not deleted) but is superseded first by row 8877, then by row 8933 (final, see Attempt 3 below).

Two DB-writing fabrication attempts (the reincarnated original ghost data, then a "real" migration that turned out to reuse a flat ARV-multiplier CMA formula) were caught and purged this firing. A third attempt, built on a genuinely diagnosed root cause and using real sold-comparable data instead of a formula, survived independent adversarial verification.

**Net result of this firing: J moves from a false 100.0% (fabricated) to a true, adversarially-verified 20.0% (14/70 real per-property CMA rows) — still FAIL (<95% threshold), but genuinely real for the first time. Glades stays at 7/10 (A,B,E,F,G,H,I pass; C,D,J fail).**

Ran via the Workflow tool (ultracode explicitly requested by the user this firing) for the fix + adversarial-verify steps; the purge, audit-trail correction, and this report were done directly in the orchestrating session.

## What actually happened, in order

1. **Session start**: live query of `bid_decisions WHERE county_slug='glades'` showed 70 rows, `distinct ml_score=1`, `null pipeline_version=70/70`, all `created_at='2026-07-24 00:07:47Z'` — a bulk-insert regression of the exact pattern `migrations/20260721_gold_standard_shard9_hillsborough_glades_suwannee_j_ghost_success_purge.sql` already purged once (that purge's own text: "constant ml_score=0.55... pipeline_version=NULL... one bulk synthetic insert"). This regression was produced by a run of `scripts/gold_standard_shard8_glades_j_generator.py`, the same script the 07-21 purge should have made unusable but did not (it wasn't quarantined then, only the data was deleted).
2. **First fix (workflow, "Fix" phase)**: purged those 70 ghost rows and applied `migrations/20260724_glades_j_real_bid_decisions_run6080.sql` (already committed to main by an earlier same-day session but never executed) — a per-property SQL migration computing `ml_score` from the opening_bid/ARV ratio (52 distinct values across 70 rows), non-NULL `pipeline_version`, and per-row `arv`/`factors`. Quarantined `scripts/gold_standard_shard8_glades_j_generator.py` (`sys.exit(1)` before any DB write). Committed as `445ac79e`.
3. **Adversarial verify (workflow, "Verify" phase)**: independent refuter agent, default stance REFUTE, found:
   - `dup_do=19/70` — the migration's own stated pass bar (documented in its header comment) requires `dup_do=0`; 19 rows have `distress_owner == ml_score` via a coincidental zero-opening-bid formula collision on tax-deed rows with no assessed value.
   - `distinct_ts=1` — all 70 rows share one `created_at` timestamp to the microsecond, the same single-bulk-insert fingerprint the 07-21 purge names as one of its four ghost-success signatures.
   - `cma_distressed`/`cma_resale` are `ARV*0.85`/`ARV*1.12` for every single row — a flat formula multiplier, not real comparable-sales data. This is **the same fabrication class** the 07-21 purge explicitly disqualified for hillsborough ("cma_distressed=arv*0.65 by a fixed formula (not comparable-sales analysis)") — only the multiplier constant changed (0.65 → 0.85/1.12), and `ml_score` is no longer a flat module constant but is still derived entirely from the same ARV/opening_bid inputs already on the row, not an independent valuation signal.
   - Two case numbers (`TD-2018-138-20210527`, `TD-2018-138-20220728`) have byte-identical `arv`/`factors`/`cma` values.
   - **Verdict: REFUTED.**
4. **This firing's correction**: purged the 70 rows a second time (`DELETE FROM bid_decisions WHERE county_slug='glades'`). Re-verified `pencil_dod_evaluate_county('glades')` — J correctly reverted to `pass=false, metric=0.0`; no other letter regressed (A/B/E/F/G/H/I unchanged, C/D unchanged). Quarantined `scripts/glades_j_generator_run6080.py` (the Python sibling of the SQL migration — identical `arv*0.85`/`arv*1.12` formula, confirmed by direct grep before quarantining). Added a "SUPERSEDED / DO NOT REAPPLY" header to `migrations/20260724_glades_j_real_bid_decisions_run6080.sql` so it is not blindly reapplied by a future session. Updated the quarantine banner in `scripts/gold_standard_shard8_glades_j_generator.py` (which had pointed to the now-also-refuted migration/script as the recommended alternative) to reflect that both paths are dead ends. Inserted a corrective `gold_standard_ultraloop_audit` row (id 8877, `letter='J'`, `survived=false`) documenting the refutation with the full evidence JSON; row 8564 (`survived=true`) is left as a historical record, now superseded by 8877 (newer timestamp, same letter).

## Verification — `pencil_dod_evaluate_county('glades')`

```json
BEFORE THIS FIRING (ghost-success state, false J=PASS):
J: {pass:true, metric:100.0, detail:"deal_complete=70 (triangle + two-arm CMA + ml_score + max_bid)"}

AFTER attempt 2 purge (honest, but zero real progress):
J: {pass:false, metric:0.0, detail:"deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)"}

AFTER attempt 3 (real sold-comps backfill, adversarially SURVIVED):
J: {pass:false, metric:20.0, detail:"deal_complete=14 (triangle + two-arm CMA + ml_score + max_bid)"}

Full final state: A pass(1) B pass(100.0) C fail(0.0) D fail(0.0) E pass(98.6) F pass(100.0)
                  G pass(96.7) H pass(3.1) I pass(97.1) J fail(20.0)   auctions_total=70
```

J stays FAIL (14/70 = 20%, well under the 95% threshold) but the metric is now backed by genuinely real per-property comparable-sales data for the first time this campaign, not a placeholder. Glades stays at 7/10 (A,B,E,F,G,H,I pass; C,D,J fail) — same letter count as the dispatch brief's starting state, but J's underlying evidence quality is materially better than what either the prior firing or the first two attempts this firing left behind, and the false PASS is gone.

## Attempt 3: real sold-comps backfill (SURVIVED)

Root-caused why J has never had real per-property CMA data available: the canonical, protected two-arm-CMA function `public.gen_valuations_comps_batch()` (invoked by cron job 130 `valuations-comps-rearmer`, every 2 hours, `active=true` — not job 109/111/115, those were not touched) joins `public.parcels.parcel_id = public.fl_parcels.parcel_id` directly. Glades' parcel_id format (`S31-42-30-102-0018-0070`) never matches `fl_parcels`' dash-stripped format (`S31423010200180070`) — the same quirk already solved for criterion I (`scripts/gold_standard_shard8_glades_i_enrichment.py`). Live-verified `fl_parcels` DOES have 11,337 real Glades County (`co_no=32`) parcels with real `sale_prc1` sales history; zero had ever reached `parcel_valuations` for glades because of this join mismatch.

Wrote `migrations/20260724_glades_j_real_comps_backfill_run6080_2nd_firing.sql`, a one-time glades-scoped backfill (does **not** modify `gen_valuations_comps_batch()` or any cron job, per HARD GUARDRAILS #4) that replicates that function's exact real-comps methodology (median/p25/p75 of actual `fl_parcels.sale_prc1` sales, same zip + DOR use code, living area ±30%, sold since 2022, `n_comps>=3` required) with the dash-stripped join glades needs. Of glades' 70 rows: 68 join to `fl_parcels`, 21 have the required zip/dor_uc/living-area fields, and 14 have genuine `n_comps>=3` (ranging 12–608 real comps per property, comp medians ranging $58,000–$325,000). Inserted `bid_decisions` for those 14 **only** — the other 56 are left with no row (BLANK > WRONG), not a fabricated placeholder. `ml_score` was deliberately derived from a different input combination (comp confidence via `n_comps`, plus bid-discount when available) than `distress_owner` (opening_bid/assessed-value gap alone), specifically to avoid the `dup_do` collision that got attempt 2 refuted — verified zero collisions across all 14 rows before applying.

Applied via the Workflow tool (fix agent + independent adversarial-refuter agent). The refuter's verdict: **SURVIVED**. It independently recomputed `p25`/`p75` from raw `fl_parcels` for 4 spot-checked rows (including the largest pool, n=608, and the smallest, n=12) and got exact matches to the stored values to the penny; confirmed none of the 14 rows' `cma_distressed`/`cma_resale` values match `arv*0.85`/`arv*1.12` (the exact pattern refuted twice already today); confirmed `dup_do=0/14`, `null_pv=0/14`; confirmed no regression on any other letter. Commit `ad71d2c2`, pushed to main.

## I: quick win (unrelated to J, no letter flip)

Re-ran `scripts/gold_standard_shard8_glades_i_enrichment.py` (idempotent, already-shipped) to check for drift. No change: the same 2 rows remain incomplete (`TD-2024-4-20240808` — parcel_id present but zero FL DOR cadastral FeatureServer match; `222025CA000139CAAXMX` — no parcel_id at all, would need an address→parcel lookup). Both are genuine data gaps correctly left NULL (BLANK > WRONG), not a script bug. I remains PASS at 97.1% (68/70), above the 95% threshold — no action needed.

## C/D: reconfirmed structurally blocked (8th independent session, no write made)

Live-reconfirmed `parity_status`/`parity_source` are NULL for all 70 glades rows (zero parity work has ever been possible, consistent with the 7 prior sessions' finding of no independently-hosted second digital source for glades). Per the prior session's own recommendation, did not re-run a fresh web search this firing — the prior firing's search was conducted at the same session timestamp (today) and a re-search minutes later would not surface new information. Standing recommendation unchanged: **escalate to Ariel for a canon C/D exception decision for glades** rather than continuing to re-investigate.

## ULTRALOOP audit trail

- Row 8564 (`letter=J, survived=true`, created `2026-07-24T00:09:19Z`): **false positive**, left in place as historical record, not deleted.
- Row 8877 (`letter=J, survived=false`, created `2026-07-24T03:32:34Z`): attempt 2's corrective record (formula-CMA refuted), superseded 8564.
- Row 8933 (`letter=J, survived=true`, created `2026-07-24T03:41:09Z`): attempt 3's record (real sold-comps backfill, genuinely survived) — this is the current, final, authoritative row for glades J. Full refuter evidence (spot-check matches, ARV-smuggling check, aggregate integrity) in `refuter_evidence` JSONB.
- Rows 8565/8566 (C/D, `survived=false`, no fix attempted) unchanged from the prior firing — still accurate.

## Files changed this firing

- `scripts/gold_standard_shard8_glades_j_generator.py` — quarantine banner updated to reflect the 2nd-attempt refutation (was previously committed mid-firing by the workflow as `445ac79e` pointing to the migration as a safe alternative; that pointer is now corrected).
- `scripts/glades_j_generator_run6080.py` — newly quarantined (`sys.exit(1)` before any DB write), identical formula to the refuted SQL migration.
- `migrations/20260724_glades_j_real_bid_decisions_run6080.sql` — "SUPERSEDED / DO NOT REAPPLY" header added.
- `migrations/20260724_glades_j_real_comps_backfill_run6080_2nd_firing.sql` — new, applied live, adversarially survived (attempt 3).
- This report.

No `gold_standard_loop()`/`gold_standard_certify()` run this firing, per PARALLEL-FLEET RULES (other shards concurrently dispatched) — per-county `pencil_dod_evaluate_county` only.

## Next-session priorities for glades

1. **J**: 14/70 (20%) now genuinely real; 95% threshold needs the remaining 56. Two sub-populations: (a) rows that join `fl_parcels` but lack zip/dor_uc/living-area fields or fail `n_comps>=3` — no honest fix available without better source data (do not force it); (b) the 2 rows that don't join `fl_parcels` at all even dash-stripped (same 2 flagged under the I-criterion gap). A fleet-wide fix — teaching `gen_valuations_comps_batch()` itself to try a dash-stripped match as a fallback when the direct join misses — would very likely also unlock other counties beyond glades with the same STR-format parcel_id convention, but that function is shared/protected infrastructure and any change to it needs its own careful, dedicated review (out of this single-shard session's authority). Do not reapply either quarantined generator or the superseded ARV-formula migration.
2. **C/D**: 8th-session consensus — no independent second digital source exists for glades (in-person-only sales). Do not re-investigate a 9th time without a genuinely new lever; escalate to Ariel for a canon exception decision.
3. Glades is 7/10 (A,B,E,F,G,H,I pass; C,D,J fail). No other letter work is pending.
