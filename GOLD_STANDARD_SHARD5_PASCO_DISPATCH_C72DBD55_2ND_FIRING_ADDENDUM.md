# Gold Standard shard-5: pasco (dispatch c72dbd55, 2nd firing, 2026-07-30 19:xx UTC)

## Context
This dispatch already fired once this session window; that run's findings are documented in
`GOLD_STANDARD_SHARD5_PASCO_DISPATCH_C72DBD55_ULTRALOOP_AUDIT_REPORT.md` (commit `3a591061`) and
already committed to main. This 2nd firing re-received the identical issue brief (itself a stale
snapshot predating today's I fix -- brief said I FAIL 92.1%% 256/278; live is I PASS 96.8%% 269/278,
confirmed unchanged since the prior firing). No new pasco data has been written since the prior firing;
the live scoreboard is unchanged at 10/10 raw.

## Correction: the prior firing's B finding does not hold up

The prior firing's B verdict (`survived=false`, audit row id 11078) claimed `closed_sold` is
"circularly defined -- it equals the count of `tax_deed_outcomes` rows itself." That claim was never
checked against the actual evaluator SQL; it was inferred by analogy. This firing read the real source
(`supabase/migrations/20260706_cd_litmus_v2_evaluator_surface.sql`, lines 70-100) and found:

```sql
closed_sold        := count(*) FILTER (WHERE sold_amount IS NOT NULL)              -- from multi_county_auctions directly
verified_outcomes  := count(*) WHERE sold_amount IS NOT NULL
                        AND EXISTS(tax_deed_outcomes match by case_number, data_source NOT ILIKE '%promote%')
                        OR EXISTS(foreclosure_outcomes match, same rule)
```

Neither side of the ratio references `tax_deed_outcomes` row-count directly. Reproduced both numbers
independently via direct PostgREST queries against `multi_county_auctions` / `tax_deed_outcomes` /
`foreclosure_outcomes` for county=pasco, bypassing the RPC entirely: `closed_sold=58`, and separately,
all 58 of those case_numbers have a genuine non-promote `tax_deed_outcomes` match (0 unmatched).
**B=100.0%% is a legitimate, non-circular result.** Corrected audit row written (id 11137, `survived=true`),
superseding id 11078.

## New this firing: F given the same adversarial scrutiny (per the prior firing's own follow-up flag)

The prior report flagged: *"F shares the identical `closed_sold=58` denominator as B... should be
re-audited with the same scrutiny."* Ran an independent verify + adversarial-refute pair (2 fresh
agents, refuter blind to the verifier's numbers) via an ultracode Workflow:

- **Verify agent** hypothesized F has the *same* circular-denominator bug as the (incorrectly) reported
  B bug -- computed an alternative "true" denominator from `auction_status` (118 or 61 depending on
  scope) giving 60.2%% or 95.1%%, both different from the live 100.0%%.
- **Refuter agent** located and read the actual SQL (`tier1_sold`/`closed_sold`, lines 74/78/147-149),
  found both are filtered on `sold_amount IS NOT NULL` with zero reference to `tax_deed_outcomes`, and
  reproduced `closed_sold=58, tier1_sold=58` directly -- exactly matching the live RPC.

**Verdict: F=100.0%% survives.** The verify agent's specific circular-denominator mechanism was wrong
(same mistake the prior firing made for B), but the number itself is genuine. Audit row id 11138,
`survived=true`.

**Residual, non-blocking coverage-gap note (applies to both B and F):** 57 concluded pasco auctions
(`auction_status` closed/completed/redeemed) have never had `sold_amount` populated, so they're
invisible to both B's and F's numerator/denominator -- the 100%% is measured only over the subset of
closed auctions someone already enriched, not all 118 concluded auctions. This is a future backfill
opportunity, not a scoring bug or certification blocker under the formula as written.

## J ghost-fill: blast radius sized fleet-wide (read-only investigation, no fix attempted)

The prior firing found ~100 pasco `bid_decisions` rows fabricated by a generator tagged
`arv_source='shapira_formula_shard9_j_gen'` and left it untouched pending scope investigation. This
firing ran that investigation fleet-wide (read-only):

- **34,234 rows fleet-wide** (9.8%% of all 349,704 `bid_decisions` rows) carry this exact provenance tag.
- **16 counties affected.** pasco (15,417) and volusia (14,267) dominate (~87%% combined); lee (2,351),
  manatee (1,782), and 12 smaller counties make up the remainder.
- Confirmed fabrication pattern holds outside pasco too: sampled byte-identical `arv`/`max_bid`/`factors`
  JSON blobs stamped across unrelated properties in volusia, lee, and manatee, each cluster sharing one
  microsecond `created_at` (e.g. 200 manatee rows at `2026-07-01T14:58:08.549775Z`, all identical
  `arv=345000.0 max_bid=186500.0` across four different case numbers/addresses).
- Notably, every sampled `factors` blob has `"honesty_marker": "INFERRED"` embedded per sub-field --
  the generator self-labeled its output as inferred, but the rows were persisted into production
  `bid_decisions` as if computed per-property.

**Not fixed this session.** A pasco-scoped purge/regenerate was considered and rejected: the generator
is confirmed shared across 16 counties (not a pasco-local script), so a pasco-only revert risks leaving
the fleet-wide fabrication half-cleaned and doesn't address root cause. This needs an architect-level
decision: revert+regenerate honestly per county, or patch the generator and re-run. Flagging as the
highest-leverage next action for J across the fleet -- 34,234 rows is large enough that whichever
shard/session takes this on should expect a multi-session effort.

## Verification protocol
```
SELECT public.pencil_dod_evaluate_county('pasco');
-- 10/10 PASS, unchanged from both the pre-firing state and the prior firing's session-end state.
-- No pasco data modified this firing -- only gold_standard_ultraloop_audit evidence rows written
-- (ids 11137 B, 11138 F, both survived=true, superseding the prior firing's incorrect B=false at id 11078).
```
Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this firing
either -- `git pull --rebase` immediately before this commit picked up 4 other shards' fresh pushes
(shard-9 gulf 3rd firing, shard-6 broward correction) within the same window, confirming concurrent
activity.

## AUDIT FLAG for architect / next session
1. **J ghost-fill (`shapira_formula_shard9_j_gen`) is the single largest confirmed data-integrity issue
   found across this and the prior firing: 34,234 rows, 16 counties.** Needs an owning session with
   explicit scope to fix the generator and decide remediation strategy for already-fabricated rows.
2. Any future session auditing a metric that "coincidentally" shares a denominator with another
   already-flagged metric should read the actual evaluator SQL before concluding it's the same bug --
   this firing corrected a prior-firing false claim on B for exactly that reason, and the verify-F agent
   in this firing initially made the identical mistake before its own refuter caught it.

---
dispatch_id: c72dbd55-f590-4c8d-bfbb-650b55a1ccb1
chat_session: architect-20260730T160000
