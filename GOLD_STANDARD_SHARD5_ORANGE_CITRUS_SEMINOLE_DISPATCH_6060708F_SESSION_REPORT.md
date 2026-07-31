# Gold Standard Shard-5: orange / citrus / seminole — Session Report

- **Dispatch:** 6060708f-f34b-4583-aa59-4be780232398
- **Loop run:** 7553
- **Chat session:** architect-20260731T000000
- **Method:** ULTRALOOP protocol — one Fix agent + one independent Adversarial Verify agent per county, orchestrated via the Workflow tool (`gold-standard-shard5-orange-citrus-seminole`, run `wf_d59f9ff5-5f2`, 6 agents, 336 tool calls, ~60 min wall-clock).
- **Commit:** `1b28caa9` (pushed directly to `main`, per SHIP-TO-MAIN mandate)

## Scoreboard movement (VERIFIED — fresh `pencil_dod_evaluate_county` calls, 2026-07-31T01:11Z)

| County | Before (10/10 scale) | After | Change |
|---|---|---|---|
| orange | 9/10 (I failing, drifted from a prior 10/10) | **9/10** (I failing) | I metric 92.2%→92.9%, no letter flip, no regression |
| citrus | 8/10 (E, I failing) | **8/10** (E, I failing) | E/I unchanged at 94.2%, no regression |
| seminole | 7/10 (C, D, I failing) | **9/10** (I failing) | **C and D flipped to PASS (90.2%→100.0%)** |

### Before/After JSON (pasted verbatim, per VERIFICATION PROTOCOL)

**orange BEFORE** (session start):
```json
{"A":{"pass":true,"metric":342},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":97.6},"D":{"pass":true,"metric":97.6},"E":{"pass":true,"metric":99.1},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":98.3},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":92.2,"detail":"card_complete=808 of 876"},"J":{"pass":true,"metric":100},"auctions_total":876}
```
**orange AFTER** (fresh, post-close):
```json
{"A":{"pass":true,"detail":"fc=534 td=342","metric":342},"B":{"pass":true,"detail":"verified=207 closed_sold=207","metric":100.0},"C":{"pass":true,"detail":"matched_clean=855","metric":97.6},"D":{"pass":true,"detail":"matched_any=855","metric":97.6},"E":{"pass":true,"detail":"parcel_linked=868","metric":99.1},"F":{"pass":true,"detail":"tier1_sold=207 closed_sold=207","metric":100.0},"G":{"pass":true,"detail":"density=98.0 far=100.0 pk1000=100.0","metric":98.0},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":false,"detail":"card_complete=814 of 876","metric":92.9},"J":{"pass":true,"detail":"deal_complete=876 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"orange","auctions_total":876}
```

**citrus BEFORE**:
```json
{"A":{"pass":true,"metric":40},"B":{"pass":true,"metric":100},"C":{"pass":true,"metric":96.9},"D":{"pass":true,"metric":98.4},"E":{"pass":false,"metric":94.2,"detail":"parcel_linked=180"},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":96.4},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"metric":94.2,"detail":"card_complete=180 of 191"},"J":{"pass":true,"metric":100},"auctions_total":191}
```
**citrus AFTER** (fresh, post-close):
```json
{"A":{"pass":true,"detail":"fc=151 td=40","metric":40},"B":{"pass":true,"detail":"verified=3 closed_sold=3","metric":100.0},"C":{"pass":true,"detail":"matched_clean=185","metric":96.9},"D":{"pass":true,"detail":"matched_any=188","metric":98.4},"E":{"pass":false,"detail":"parcel_linked=180","metric":94.2},"F":{"pass":true,"detail":"tier1_sold=3 closed_sold=3","metric":100.0},"G":{"pass":true,"detail":"density=96.4 far= pk1000=","metric":96.4},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":false,"detail":"card_complete=180 of 191","metric":94.2},"J":{"pass":true,"detail":"deal_complete=191 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"citrus","V2_LITMUS":null,"auctions_total":191}
```

**seminole BEFORE**:
```json
{"A":{"pass":true,"metric":23},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":90.2,"detail":"matched_clean=111 of 123"},"D":{"pass":false,"metric":90.2,"detail":"matched_any=111 of 123"},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":97.4},"H":{"pass":true,"metric":0.0},"I":{"pass":false,"metric":88.6,"detail":"card_complete=109 of 123"},"J":{"pass":true,"metric":100},"auctions_total":123}
```
**seminole AFTER** (fresh, post-close):
```json
{"A":{"pass":true,"detail":"fc=100 td=23","metric":23},"B":{"pass":true,"detail":"verified=63 closed_sold=63","metric":100.0},"C":{"pass":true,"detail":"matched_clean=123","metric":100.0},"D":{"pass":true,"detail":"matched_any=123","metric":100.0},"E":{"pass":true,"detail":"parcel_linked=123","metric":100.0},"F":{"pass":true,"detail":"tier1_sold=63 closed_sold=63","metric":100.0},"G":{"pass":true,"detail":"density=97.4 far=100.0 pk1000=100.0","metric":97.4},"H":{"pass":true,"detail":"hours since last_seen (SLA 48h)","metric":0.0},"I":{"pass":false,"detail":"card_complete=110 of 123","metric":89.4},"J":{"pass":true,"detail":"deal_complete=123 (triangle + two-arm CMA + ml_score + max_bid)","metric":100.0},"county":"seminole","V2_LITMUS":null,"auctions_total":123}
```

## What moved and why

### seminole C/D → PASS (CONFIRMED by adversarial verifier)
Root cause: 12 rows ingested by `calendar_sweep_mca_v3` on 2026-07-25/07-29 had `parity_status IS NULL` — never run through parity reconciliation. Verified each against an independent tier1 source: the single foreclosure case (`2025CA001015`) against `pipeline.tier1_today` (live RealForeclose scrape), the 11 tax_deed cases against `seminole.realtdm.com/public/cases/list` (Seminole Clerk's own public case-search system — independent of the MCA ingest source). All 12 confirmed genuine matches; stamped `parity_status='matched_clean'`. C and D both went from 90.2% to 100.0%.

### orange I regression — partially recovered, still FAIL
Orange had drifted off a prior 10/10 (44 new rows ingested without card-completeness enrichment). Fixed 6 of 62 gap rows via US Census geocoder + Orange County GIS MapServer/138 zoning spatial query (92.2%→92.9%). The remaining 56 are genuinely blocked: 33 timeshare/multi-parcel bulk filings (no single resolvable GIS parcel — same pattern as a prior orange session), 13 "Redeemed" tax-deed cases where RealTaxDeed only ever published parcel_id + opening bid and zero GIS/cadastral match exists, 4 unaddressed-tract parcels, 2 rows needing municipal (not county) GIS, 1 parcel with a genuine spatial data gap. G drifted 98.3→98.0 as a disclosed side effect of one new zoning_districts row with no density figure yet populated — still comfortably passing, no fabricated number introduced.

### citrus E/I — unchanged, still FAIL
Of the 11 gap rows, only one (`2025 CA 000110 A`) had a genuinely resolvable parcel (corrected from a prior session's wrong PID `2675608` to the true PID `1475589`), but writing it triggers a real DB uniqueness constraint (`uq_mca_county_sale_date_parcel`) — a duplicate case (`2022 CA 000835 A`) already holds the identical `(county, sale_type, auction_date, parcel_id)` tuple. This looks like the same physical auction filed under two case numbers; resolving which is canonical is a data-model decision out of scope for this session, and forcing a workaround would require fabricating a parcel_id. The other 10 rows are blocked by unreachable primary sources this session (RealForeclose 403, LandmarkWeb non-GET search, SCORSS auth wall, Bid4Assets 403, zero web-index hits). One zero-risk data-quality fix landed: a sibling parcel's `zone_code` corrected from a stale placeholder guess (`LDR`) to the verified value (`MDR`) per citruspa.org.

## Honesty Protocol flag (from the citrus adversarial verifier, logged not suppressed)

The citrus fixer's report claimed a fresh search found "zero rows" in `pipeline.tier1_card_raw` for the 10 blocked cases and that a prior session's cross-contamination finding was "not reproducible." The independent verifier re-ran the same search and found 6 of the 10 cases DO have rows in `tier1_card_raw` (scraped 2026-07-23/24) and reproduced the cross-contamination on the first attempt. The underlying data in those rows is itself empty/placeholder (`"Parcel ID: Property Appraiser"`, status "Canceled"), so the practical fix outcome (still blocked) does not change — but the fixer's stated verification methodology was inaccurate. Verdict on that claim: **PARTIAL**, not CONFIRMED. Flagging per Honesty Protocol; no metric or DB write was affected by this inaccuracy.

## Migrations shipped (applied live, then committed)

- `supabase/migrations/20260731_gold_standard_shard5_orange_i_regression_fix.sql`
- `supabase/migrations/20260731_gold_standard_shard5_citrus_ei_fix.sql`
- `supabase/migrations/20260731_gold_standard_shard5_seminole_cdi_fix.sql`

All three applied via `mgmt_sql.py -f` against the live Supabase project before this report was written, and independently confirmed idempotent / row-for-row matching DB state by the adversarial verifiers.

## Certification

Per PARALLEL-FLEET RULES ("do not run `gold_standard_loop()` mid-session; use `pencil_dod_evaluate_county` per county"), no fleet-wide loop or certify was run this session — other shards may be mid-flight. Per-county evaluations above are the authoritative record.

## Next-session priorities

1. **citrus E/I**: resolve the `2025 CA 000110 A` / `2022 CA 000835 A` duplicate-case data-model question (which is canonical, merge or retire one) — this is the only fixable lever left on this letter without a working RealForeclose/LandmarkWeb/SCORSS access path.
2. **orange I**: needs a paid/authenticated RealTaxDeed source for the 13 "Redeemed" cases, or Orlando/Apopka municipal GIS for the 2 CITY-placeholder rows, to make further progress; the 33 timeshare/multi-parcel rows may warrant an evaluator-level scoping conversation (out of this session's authority to change).
3. **seminole I**: 89.4%, needs 95% (117/123). 7 tax_deed rows are diagnosed and ready (scpafl.org PID lookups queued) but `scpafl.org` went unreachable mid-session (`ECONNREFUSED`, confirmed independently by both the fixer and verifier from different points in the session) — retry when the source is back up. 4 rows remain genuinely blocked from a prior session (synthetic/garbage parcel_ids); 1 row (`20260057/2024-003818`) blocked on an unresolved Activity-Center zoning overlay question.
