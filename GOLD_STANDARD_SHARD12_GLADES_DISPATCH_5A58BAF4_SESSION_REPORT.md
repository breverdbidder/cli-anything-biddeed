# GOLD STANDARD shard-12 — glades — dispatch 5a58baf4-dd28-46e3-9d10-3150e99d076f

session: architect-20260725T000000, loop run 6288

## Summary

Glades entered this session at 7/10 (A,B,E,F,G,H,I pass; C,D,J fail). Extended the
established real-comps J methodology from zip-restricted to county-wide comparable
sales, closing 8 of the remaining 11 gap rows with genuine live data. **glades: 7/10 →
8/10.** C/D re-confirmed as a genuine structural dead end via one fresh live check (8th+
consecutive session with this finding) — not re-attempted beyond that per the prior
session's explicit guidance to stop re-investigating a repeatedly-confirmed dead end
absent a genuinely new idea.

## J fix (CONFIRMED, adversarially verified)

**Root cause of the remaining gap** (verified live): of glades' 70 auctions, 59 already
had real bid_decisions rows from three prior honest sessions (zip-restricted living-area
and land-size comps). The remaining 11 broke down as: 2 rows with no `fl_parcels` join at
all (an E-linkage gap, out of this session's scope), and 9 rows that join `fl_parcels`
but failed the exact-ZIP-match comp-pool eligibility check used by the prior migrations.
Glades is a single rural county concentrated in ~2 zip codes — the zip restriction (which
mirrors `gen_valuations_comps_batch()`'s own convention) was artificially narrowing the
comp pool for some DOR use codes even though real same-use-code sales exist elsewhere in
the county.

**Fix**: `migrations/20260725_gold_standard_shard12_glades_j_countywide_comps_run6288.sql`
— drops the zip restriction to county-wide (`fl_parcels.co_no = 32`), keeps the same
dor_uc + real-sale-price + size-tolerance bar, with a cascading 4-tier fallback
(living-area 0.7x-1.3x since 2020 → 0.5x-2.0x since 2018 → land-size 0.5x-2.0x since 2018
→ land-size 0.2x-5.0x since 2016; first tier with ≥3 real comps wins, recorded in the
row's own note field for auditability). Applied live via `mgmt_sql.py` (Management API,
same sanctioned path used by prior glades sessions).

**Result**: 8 of 9 eligible rows cleared the bar with real comp pools (n_comps 3–148,
not synthetic). The 9th (`TD-2022-6-20240118`, ~39-acre agricultural parcel, dor_uc=069)
genuinely has only 2 real arm's-length sales of that use code in the entire county since
2016 even with size restrictions fully removed — left with NO row (BLANK > WRONG). The 2
no-fl_parcels-join rows (`222025CA000139CAAXMX` — foreclosure with no parcel_id yet;
`TD-2024-4-20240808` — parcel not present in fl_parcels) also left open; both require an
E-linkage fix first, not attempted this session (surgical scope).

### Adversarial verification — refuter error caught and corrected

An independent refuter subagent (ULTRALOOP Verify-J phase) initially returned
**REFUTED**, claiming the stored p25/p75 values for two spot-checked rows could not be
reproduced from live `fl_parcels` data. Per SHIP GATE #3 ("the burden of proof is on
whoever disagrees"), I independently re-ran the exact tier queries myself rather than
accepting either verdict blindly:

- `TD-2021-8-20220616` (tier1: co_no=32, dor_uc=008, tot_lvg_ar 1735×0.7–1.3, since 2020):
  live re-query returns 7 real comps `[30000,150000,225000,229000,240000,260000,318000]`
  (the `sale_prc1 > 1000` filter correctly excludes any nominal sales — none are present
  in this set). `percentile_cont(0.25)=187500`, `percentile_cont(0.75)=250000` — **exact
  match** to the stored row.
- `TD-2024-3-20240808` (tier4: co_no=32, dor_uc=099, lnd_sqfoot 6229×0.2–5.0, since 2016):
  live re-query returns 3 real comps `[1200,1300,3500]`. `percentile_cont(0.25)=1250`,
  `percentile_cont(0.75)=2400` — **exact match**.

Both spot-checks the refuter flagged reproduce exactly under the migration's own stated
methodology. The refuter's REFUTED verdict was itself based on a non-matching
reproduction query (it referenced "$100 nominal sales" that do not exist anywhere in the
correctly-filtered set), not a real defect in the migration. This correction, with both
sides' evidence, is logged transparently in the audit row rather than either silently
accepted or silently dismissed.

## SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('glades');
```

BEFORE (this session's live starting point, matches the dispatch brief exactly):
```json
{"A":{"pass":true,"detail":"fc=1 td=69","metric":1},"B":{"pass":true,"detail":"verified=3 closed_sold=3","metric":100},"C":{"pass":false,"detail":"matched_clean=0","metric":0},"D":{"pass":false,"detail":"matched_any=0","metric":0},"E":{"pass":true,"detail":"parcel_linked=69","metric":98.6},"F":{"pass":true,"detail":"tier1_sold=3 closed_sold=3","metric":100},"G":{"pass":true,"detail":"density=96.7 far= pk1000=","metric":96.7},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":8.7},"I":{"pass":true,"detail":"card_complete=68 of 70","metric":97.1},"J":{"pass":false,"detail":"deal_complete=59 (triangle + two-arm CMA + ml_score + max_bid)","metric":84.3},"county":"glades","V2_LITMUS":null,"auctions_total":70}
```

AFTER (2026-07-25T00:2xZ, post-migration, live re-run, timestamp UTC):
```json
{"A":{"pass":true,"detail":"fc=1 td=69","metric":1},"B":{"pass":true,"detail":"verified=3 closed_sold=3","metric":100},"C":{"pass":false,"detail":"matched_clean=0","metric":0},"D":{"pass":false,"detail":"matched_any=0","metric":0},"E":{"pass":true,"detail":"parcel_linked=69","metric":98.6},"F":{"pass":true,"detail":"tier1_sold=3 closed_sold=3","metric":100},"G":{"pass":true,"detail":"density=96.7 far= pk1000=","metric":96.7},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":8.8},"I":{"pass":true,"detail":"card_complete=68 of 70","metric":97.1},"J":{"pass":true,"detail":"deal_complete=67 (triangle + two-arm CMA + ml_score + max_bid)","metric":95.7},"county":"glades","V2_LITMUS":null,"auctions_total":70}
```

**J: FAIL (84.3) → PASS (95.7).** Score: **7/10 → 8/10.** A/B/E/F/G/H/I unchanged
(no regression).

Adversarial row-level validation (run after applying):
```sql
SELECT COUNT(*) AS total, COUNT(DISTINCT ml_score) AS distinct_ml,
  COUNT(DISTINCT (factors->'cma_distressed'->>'value')) AS distinct_cma_d,
  COUNT(*) FILTER (WHERE pipeline_version IS NULL) AS null_pv,
  COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) AS dup_do
FROM bid_decisions WHERE county_slug='glades' AND pipeline_version='glades_j_countywide_comps_v1';
```
Result: `total=8, distinct_ml=8, distinct_cma_d=7, null_pv=0, dup_do=0` — matches the
migration's stated expectation.

## ULTRALOOP workflow (native mode)

Ran one Workflow (`wf_27f9d8ca-87b`, 2 agents, ~103K subagent tokens, 27 tool calls, ~2.7
min): Verify-J (adversarial refuter, initially REFUTED, overturned by my own independent
re-verification above) and Research-CD (one fresh live litmus check).

## ULTRALOOP audit ledger (3 rows, `dispatch_id=5a58baf4-dd28-46e3-9d10-3150e99d076f`)

| id | letter | survived | claim |
|---|---|---|---|
| 9718 | J | true | County-wide comps backfill, 8 rows, live metric moved 84.3→95.7; refuter's initial REFUTED verdict independently disproved |
| 9719 | C | true | Fresh live re-check (PropertyOnion, parked RealAuction subdomains, clerk site, statewide aggregator) confirms still structurally blocked |
| 9720 | D | true | Same root cause/evidence as C |

## C/D — fresh live re-check (no new lever)

One live check this session (not a rebuild of prior work): PropertyOnion's county list
does not include Glades; `glades.realforeclose.com` and `glades.realtaxdeed.com` both
resolve but redirect to RealAuction's generic marketing homepage (parked/unactivated
subdomain pattern, not live county data); `gladesclerk.com`'s own foreclosure and tax-deed
pages link only to the Municode notices library, not a digital sales platform; no FL
statewide clerk aggregator covers glades. This is the 8th+ consecutive session to
independently reconfirm the same structural dead end. Per the prior session's explicit
recommendation, not re-investigated further this session absent a genuinely new idea.

## Residual — next-session priorities for glades

1. **The 3 remaining J gap rows**: `TD-2022-6-20240118` (genuinely thin comp pool, only 2
   real countywide sales of dor_uc=069 since 2016 — likely a permanent structural cap
   unless a much older sale-year window is deemed acceptable) and the 2 no-parcel-join
   rows (`222025CA000139CAAXMX` has only a legal description — "TRACT 16, CRESCENT ACRES"
   — and no parcel_id at all; `TD-2024-4-20240808` has parcel_id
   `S31-42-30-102-0018-0070` but it does not exist in `fl_parcels`). Both need an
   E-linkage investigation (GIS/plat lookup) before J can reach 100%; J is already
   passing at 95.7% so this is optional polish, not urgent.
2. **C/D remain genuinely unmeasurable** for glades — recommend this stops being
   re-investigated every session (per the prior session's own guidance, now reinforced by
   an 8th consecutive confirmation) unless a genuinely new idea surfaces.
3. **OUA zoning district** (2 parcels, flagged in the prior 2026-07-12 session) was not
   revisited this session — out of scope (J was the higher-leverage target per this
   session's own live diagnosis).

Did not run `gold_standard_loop()`/`gold_standard_certify()` — glades is 8/10, not 10/10
(C/D still fail structurally), so certification does not apply. `git pull --rebase`
picked up shard3/shard5/shard6/shard9/shard2 concurrent work with no conflicts, consistent
with PARALLEL-FLEET RULES.
