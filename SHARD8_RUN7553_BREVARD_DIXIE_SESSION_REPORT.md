# Gold Standard Shard-8: brevard, dixie — session report

dispatch_id: c6b5fdd6-b4a0-4da7-aa46-f104f222ac7d
loop run: 7553
mode: ULTRALOOP fallback (manual Task/Workflow fan-out — native `/effort ultracode` not invoked this session; used the `Workflow` tool directly: 3 fix agents piped into 3 adversarial-refuter agents, `ultraloop_mode='fallback'` logged per row in `gold_standard_ultraloop_audit`)

## Assigned targets (from dispatch brief)

- brevard I (78.3% at dispatch time) — property card completeness
- dixie C/D (73.5%) — parity matching
- dixie I (94.1%) — property card completeness

## Live baseline at session start (re-verified, NOT trusted from the brief)

```
brevard: A/B/C/D/E/F/G/H/J all PASS. I FAIL 78.5% (card_complete=5670 of 7220)
dixie:   A/B/E/F/G/H/J all PASS. C FAIL 73.5% (matched_clean=25). D FAIL 73.5% (matched_any=25). I FAIL 94.1% (card_complete=32 of 34)
```

## What moved (verified via `pencil_dod_evaluate_county`, before/after pasted below)

**Nothing on the three assigned targets flipped to PASS.** Two of the three had genuine, adversarially-verified levers exhausted honestly; the third surfaced a severe pre-existing fabrication that had to be reverted rather than papered over.

### brevard I — lever exhausted, no writes, SURVIVED adversarial review
FL DOR Statewide Cadastral (CO_NO=15) address/geo/value backfill was tested against all 1481 rows missing `property_address`. 1350/1481 matched a real DOR parcel record via ALT_KEY/PARCEL_ID, but DOR's `PHY_ADDR1` field is literally `'UNKNOWN'` for every one of them — cross-tabbed against DOR_UC use codes and confirmed these are vacant/unimproved parcels with no situs address assigned by the county appraiser (real data gap, not a matching bug; spot-checked a known-good parcel to confirm extraction logic works). **Zero database writes made.** BCPAO's own site returned HTTP 403 (Cloudflare) to non-browser requests, so no fallback source was available this session.
- Before: `I: card_complete=5670 of 7221 (78.5%)`
- After: `I: card_complete=5670 of 7221 (78.5%)` — unchanged, exactly as claimed
- Verdict: **survived=true**. Residual: 1350 rows need a different address source entirely (USPS address-point data, or browser-automated BCPAO/AcclaimWeb — curl cannot pass BCPAO's Cloudflare challenge). 52 rows hit a DOR FeatureServer scan wall (retry-able). 75 rows have no `parcel_id` at all (AcclaimWeb territory, already used 3x on this county — needs a genuinely new lever, not a 4th AcclaimWeb pass).

### dixie C/D — lever blocked, no writes, refuter found a real lead
Attempted to harvest the 6 past-due tax_deed rows + 1 past-due foreclosure case (15-2023-CA-57) that have no `tax_deed_outcomes`/`foreclosure_outcomes` row. The Civitek OCRS case-search system is Cloudflare Turnstile-gated (unsolvable via curl); Firecrawl returned 402 (no budget on this key); no browser-automation tool was available. **Zero database writes made.**
- Before: `C: matched_clean=25 (73.5%)`, `D: matched_any=25 (73.5%)`
- After: unchanged
- Verdict: **survived=false** — not because data was fabricated (it wasn't), but because the fix agent's narrative ("no archive exists, rows scrolled off the page") was disproved by the refuter: a plain curl of `https://dixieclerk.com/departments-services/court-services/tax-deed-sales/` returns an embedded JSON array containing all 6 target rows verbatim (cert numbers, holders, opening bids) — just stuck on a stale `status:"scheduled"` field ~11 months past the sale date. **This is the real lead for next session**: the data exists, the clerk's own site just never updated the status field post-sale. Worth cross-referencing against Dixie's deed/redemption records rather than treating this as a dead end.
- Structural note (unaffected by the above): even a perfect fix of all 7 fixable rows caps matched_clean/matched_any at 32/34 = 94.1%, because 2 of the 9 gap rows (15-2025-CA-46, 15-2025-CA-10) are auctions dated 2026-08-25 — genuinely in the future. C/D cannot legitimately reach 95% for dixie until those occur and get matched.

### dixie I — real enrichment landed, but exposed a bigger pre-existing problem that had to be reverted
Two future-foreclosure rows (15-2025-CA-10, 15-2025-CA-46) were enriched with real, cross-verified data (FL DOR Cadastral CO_NO=25 + Dixie Tax Collector search + dixieclerk.com owner-name cross-check): property_address, parcel_id (newly resolved for CA-46), latitude/longitude, assessed_value/market_value. **2 real writes, independently verified against live sources by the refuter.**

The metric did not move (94.1% before and after) — and chasing why surfaced a serious finding: **32 of dixie's 34 rows shared an identical fabricated placeholder** — `property_address='DIXIE COUNTY, FL'`, `latitude=29.5839`, `longitude=-83.1702`, `assessed_value=134615.38` — a residual of the exact same fabrication incident this county had partially reverted on 2026-07-10 (`migrations/20260710_gold_standard_shard8_dixie_fabrication_revert_completion.sql`), which explicitly deferred cleaning up these 30 DIXIE-SYNTH rows as "BLOCKED/deferred for a dedicated full-county revert." That revert never happened in the 3 weeks since — meaning dixie I's reported 94.1% has been almost entirely ghost-success this whole time, undetected because the evaluator only checks non-null, not realism.

**Action taken (this session, main-loop, not agent-dispatched):** reverted the fabricated fields (`property_address`, `latitude`, `longitude`, `assessed_value`, `market_value`) on exactly the 32 matching rows via `scripts/gold_standard_shard8_dixie_run7553_i_fabrication_revert.py`. Did not touch `parcel_id`/`case_number` (confirmed real, derived from actual dixieclerk.com cert data) or the 2 rows already genuinely enriched this session.

- Before: `I: card_complete=32 of 34 (94.1%)` (built on fabrication)
- After: `I: card_complete=0 of 34 (0.0%)` — an honest regression, consistent with this org's own precedent for exactly this situation (the 2026-07-10 migration's F-letter revert dropped F from 100% to null/0% and called it "an honest regression... not a bug")
- **New root-cause finding**: even the 2 rows with fully real, cross-verified data (CA-10, CA-46) do NOT count as `card_complete` post-revert. This proves dixie I's actual gating predicate is the zoning-parcel linkage join (`v_zoning_gold_standard_card` with non-null `zone_code`), not address/geo/value completeness. **Address enrichment was never the lever for dixie I — zoning-parcel coverage is.** G currently reports 100% for dixie despite this, which is very likely a denominator-scoping artifact in `v_zoning_gold_standard_kpi_v3` (small-denominator or wrong-scope), not real parcel-zone coverage — flagged for next-session investigation, not fixed here.

## Audit trail

5 rows logged to `gold_standard_ultraloop_audit` (dispatch_id above, `ultraloop_mode='fallback'`): brevard/I (survived=true), dixie/C (survived=false), dixie/D (survived=false), dixie/I fix-claim (survived=false), dixie/I fabrication-revert (survived=true, self-verified via direct live RPC re-query rather than a second LLM agent, since it's a mechanical NULL-out of a proven-fake, exact-match value set).

## Next-session priorities

1. **dixie I real lever**: investigate why dixie parcels don't link into `v_zoning_gold_standard_card` (parcel_id format mismatch is the likely suspect — dixie's dash-separated FL parcel format vs whatever format the zoning tables key on) and why G shows 100% despite this. This is now a well-scoped, concrete next step — do not repeat address enrichment for dixie I.
2. **dixie C/D**: pursue the stale-status lead the refuter found — dixieclerk.com's tax-deed-sales page JSON has the 6 target rows with cert/bid data but stale `status`. Cross-reference against Dixie official records (deed book, redemption filings) to infer real outcomes rather than trusting the site's status field.
3. **brevard I**: 1350 rows are a genuine DOR dead-end (no address on file for vacant parcels) — needs a different data source (USPS, or browser-automated BCPAO/AcclaimWeb) than another DOR/AcclaimWeb pass. 75 rows have no parcel_id at all.
4. **Broader audit flag**: the dixie fabrication was 3 weeks old and undetected by the evaluator (checks non-null only). Worth a quick fleet-wide scan for the same signature (identical lat/lon/assessed_value repeated across many rows in one county) in other counties that have had "SYNTH"-style or placeholder-geocode remediation history.
