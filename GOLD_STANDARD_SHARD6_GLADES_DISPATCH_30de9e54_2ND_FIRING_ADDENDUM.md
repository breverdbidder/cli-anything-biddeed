# GOLD STANDARD shard-6 — glades — dispatch 30de9e54-a2f4-40ae-a8fa-da5988c9d667 — 2nd firing addendum

session: architect-20260724T000000 (2nd firing of the same dispatch)

## Summary

This firing found the prior firing's own session report (`GOLD_STANDARD_SHARD6_GLADES_DISPATCH_30de9e54_SESSION_REPORT.md`, commit `aea1dbf6`) to be **wrong**. That report claimed J moved 0.0% → 100.0% via `scripts/gold_standard_shard8_glades_j_generator.py` and that the result "survived" adversarial refutation (audit row 8564, `survived=true`). A live query at the start of this firing directly contradicted that claim: the 70 `bid_decisions` rows it inserted had `distinct ml_score = 1` (constant) and `pipeline_version IS NULL` for all 70 rows — the exact ghost-success signature already purged once for this county on 2026-07-21. Audit row 8564 is a false positive; it is left in the table as a historical record (not deleted) but is superseded by row 8877 below.

**Net result of this firing: J reverts to FAIL 0.0 (honest). Glades stays at 7/10 (A,B,E,F,G,H,I pass; C,D,J fail) — no metric change from the dispatch brief's starting state, but two live fabrication regressions were caught and purged, and the regressing code paths are now quarantined against a third recurrence.**

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

AFTER (honest state, both fabrication attempts purged):
J: {pass:false, metric:0.0, detail:"deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)"}

Full after-state: A pass(1) B pass(100.0) C fail(0.0) D fail(0.0) E pass(98.6) F pass(100.0)
                  G pass(96.7) H pass(2.9) I pass(97.1) J fail(0.0)   auctions_total=70
```

This matches the dispatch brief's starting state exactly (7/10: A,B,E,F,G,H,I pass; C,D,J fail) — no net letter movement this firing, but a materially more honest DB state than what the prior firing left behind.

## I: quick win (unrelated to J, no letter flip)

Re-ran `scripts/gold_standard_shard8_glades_i_enrichment.py` (idempotent, already-shipped) to check for drift. No change: the same 2 rows remain incomplete (`TD-2024-4-20240808` — parcel_id present but zero FL DOR cadastral FeatureServer match; `222025CA000139CAAXMX` — no parcel_id at all, would need an address→parcel lookup). Both are genuine data gaps correctly left NULL (BLANK > WRONG), not a script bug. I remains PASS at 97.1% (68/70), above the 95% threshold — no action needed.

## C/D: reconfirmed structurally blocked (8th independent session, no write made)

Live-reconfirmed `parity_status`/`parity_source` are NULL for all 70 glades rows (zero parity work has ever been possible, consistent with the 7 prior sessions' finding of no independently-hosted second digital source for glades). Per the prior session's own recommendation, did not re-run a fresh web search this firing — the prior firing's search was conducted at the same session timestamp (today) and a re-search minutes later would not surface new information. Standing recommendation unchanged: **escalate to Ariel for a canon C/D exception decision for glades** rather than continuing to re-investigate.

## ULTRALOOP audit trail

- Row 8564 (`letter=J, survived=true`, created `2026-07-24T00:09:19Z`): **false positive**, left in place as historical record, not deleted.
- Row 8877 (`letter=J, survived=false`, created `2026-07-24T03:32:34Z`): this firing's corrective record, supersedes 8564 per the CERTIFY GATE's "newer row wins" rule. Full refuter evidence in `refuter_evidence` JSONB.
- Rows 8565/8566 (C/D, `survived=false`, no fix attempted) unchanged from the prior firing — still accurate.

## Files changed this firing

- `scripts/gold_standard_shard8_glades_j_generator.py` — quarantine banner updated to reflect the 2nd-attempt refutation (was previously committed mid-firing by the workflow as `445ac79e` pointing to the migration as a safe alternative; that pointer is now corrected).
- `scripts/glades_j_generator_run6080.py` — newly quarantined (`sys.exit(1)` before any DB write), identical formula to the refuted SQL migration.
- `migrations/20260724_glades_j_real_bid_decisions_run6080.sql` — "SUPERSEDED / DO NOT REAPPLY" header added.
- This report.

No `gold_standard_loop()`/`gold_standard_certify()` run this firing, per PARALLEL-FLEET RULES (other shards concurrently dispatched) — per-county `pencil_dod_evaluate_county` only.

## Next-session priorities for glades

1. **J**: do not reapply either quarantined generator or the superseded migration. A genuine fix requires wiring `bid_decisions` generation through the real `gen_valuations_comps_batch` two-arm CMA pipeline (per the campaign brief's own J playbook: "the per-minute valuations_comps batch (cron 109) builds inputs — do not modify it") and an actual trained Shapira V14 model `ml_score`, not a hand-written SQL/Python formula off `ARV`/`opening_bid` alone. This is a structurally bigger build than a single migration — consistent with the fleet-wide "J generator does not exist" finding in the campaign brief's own `J ROOT CAUSE SIZED` note.
2. **C/D**: 8th-session consensus — no independent second digital source exists for glades (in-person-only sales). Do not re-investigate a 9th time without a genuinely new lever; escalate to Ariel for a canon exception decision.
3. Glades is 7/10 (A,B,E,F,G,H,I pass; C,D,J fail). No other letter work is pending.
