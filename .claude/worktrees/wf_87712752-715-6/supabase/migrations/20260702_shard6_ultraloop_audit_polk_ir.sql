-- SHARD-6: record adversarial verification evidence for indian_river, sarasota, polk
-- dispatch_id: 477f6589-379a-4761-b290-c4ed52e45e9b
-- Session: architect-20260702T080000
-- ultraloop_mode: native (Workflow tool, 6 agents, 136 tool calls, live curl/psql evidence)

INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'B',
  'Post-revert honest state: verified=10 closed_sold=10 (100%). The prior 228/228 claim was FABRICATED (self-referential sold_amount copy from tier1_sold_amount + 218 synthetic outcome rows with no source_url, deleted by migration 20260702_shard6_polk_bf_fabrication_revert.sql) and is superseded by this row.',
  '{"mca_rows_reverted": 218, "outcomes_reverted_tax_deed": 39, "outcomes_reverted_foreclosure": 179, "fabrication_signature": "100pct of 218 rows share one identical updated_at 2026-07-02T00:57:37Z; winning_bid==sold_amount for 218/218; source_url NULL for 216/218; no committed scraper/migration produced data_source tier1-shard9-run2280", "honest_metric_after_revert": {"verified_outcomes": 10, "closed_sold": 10, "pct": 100.0}, "sample_size_caveat": "n=10 is tiny relative to 615 total auctions; PASS is numerically true but not representative"}'::jsonb,
  true
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'F',
  'Post-revert honest state: tier1_sold=239 closed_sold=10 -> 2390% ratio. This is an anomalous metric-design failure (tier1_sold_amount populated far beyond the honestly-closed set) inherited from before the fabrication, NOT resolved by removing the fabricated batch. Evaluator SQL currently marks this pass=true (>=95%) but the ratio itself is not credible and must not be treated as a clean certification signal.',
  '{"tier1_sold": 239, "closed_sold": 10, "ratio_pct": 2390.0, "root_cause": "tier1_sold_amount accrued via undocumented prior process far outstrips genuinely-closed (sold_amount populated) rows; same class of anomaly as brevard B 134.1pct (impossible_coverage pattern)", "recommended_fix": "build a real polk-specific authenticated RealForeclose/RealTaxDeed result-page harvest (scripts/county_outcome_harvester.py scrape_realforeclose_results step) to grow closed_sold honestly, rather than certifying on the current ratio", "do_not_certify": true}'::jsonb,
  false
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'J',
  'deal_complete=603/615 (98.0%) passes the evaluator SQL literally (arv/max_bid/ml_score non-null, all 5 factors keys present) and the denominator (615, post-propertyonion-exclusion) is genuine. However independent content inspection shows 102/603 (16.9%) rows are an identical hardcoded placeholder (arv=200000.0, max_bid=80000.0, cma_distressed.estimated_value=null, owner_name=null), 87/603 (14.4%) have max_bid=0.0, and ml_score takes only 2 distinct values (0.45 x597, 0.65 x6) across all 603 rows -- not plausible per-property ML output. cma_distressed/cma_resale are both a single deterministic formula (shapira_formula_v14_heuristic) applied to assessed_value, not an independent comps CMA. Reclassify as SUSPECT, not a clean PASS.',
  '{"denominator_genuine": true, "auctions_total_nonPO": 615, "numerator_sql_correct": true, "deal_complete_count": 603, "placeholder_rows": 102, "placeholder_pct": 16.9, "zero_max_bid_rows": 87, "distinct_ml_score_values": 2, "ml_score_distribution": {"0.45": 597, "0.65": 6}, "cma_source": "shapira_formula_v14_heuristic (deterministic formula on assessed_value, not independent comps)", "honesty_marker_in_data": "HYPOTHESIS (self-labeled by the generator)"}'::jsonb,
  false
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'C',
  'matched_clean=603/615 (98.0%) GENUINE. Verified real prior provenance: parity_source values (tier1_clerk_supplementary_shard11_20260619 x316, tier1_clerk_supplementary_div_shard11_20260619 x99, tier1_supplementary:shard10:2026-06-24 x81, tier1_matched_clean_bootstrap x77, tier1_clerk_supplementary_nullsrc_shard11_20260619 x28, tier1_realforeclose_aids_patch x2) all trace to committed June 2026 migrations (shard7/10/11/12), not the 2026-07-02 fabrication window. The jump from 13.3%->98.0% is legitimately explained by todays fleet-wide propertyonion-exclusion evaluator fix (commit 3b078a98) unmasking already-correct prior work, corroborated by created_at=2026-05-21 (old) despite updated_at re-stamp.',
  '{"propertyonion_rows_excluded": 3904, "propertyonion_pct_of_total": 86.4, "non_po_pool": 615, "matched_clean": 603, "parity_source_breakdown": {"tier1_clerk_supplementary_shard11_20260619": 316, "tier1_clerk_supplementary_div_shard11_20260619": 99, "tier1_supplementary:shard10:2026-06-24": 81, "tier1_matched_clean_bootstrap": 77, "tier1_clerk_supplementary_nullsrc_shard11_20260619": 28, "tier1_realforeclose_aids_patch": 2}, "corroborating_migrations": ["20260619_shard7_polk_bfgi_fixes.sql", "20260619_shard7_s65_polk_cd_parity.sql", "20260619_shard11_*", "20260628_shard2_polk_cd_gh_i_fix.sql", "20260628_polk_tier1_prefix_cd_parity.sql"]}'::jsonb,
  true
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'D',
  'matched_any=603/615 (98.0%) GENUINE — same evidence as C (matched_clean is a subset of matched_any and both resolve to the same 603 count for polk).',
  '{"see_letter": "C", "matched_any": 603, "auctions_total_nonPO": 615}'::jsonb,
  true
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'E',
  'parcel_linked=615/615 (100.0%) GENUINE — same forensic pass as C/D: parcel_id population traces to pre-existing June 2026 shard7/10/11/12 migrations, not the 2026-07-02 window; only updated_at was re-stamped, not parcel_id values.',
  '{"see_letter": "C", "parcel_linked": 615, "auctions_total_nonPO": 615}'::jsonb,
  true
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'polk', 'I',
  'card_complete=614/615 (99.8%) GENUINE — depends on E (parcel linkage, confirmed genuine) and pre-existing address/geo/value enrichment from the same June 2026 migration set; no 2026-07-02 fabrication signature found in the underlying enrichment fields.',
  '{"see_letter": "C", "card_complete": 614, "auctions_total_nonPO": 615}'::jsonb,
  true
),
(
  '477f6589-379a-4761-b290-c4ed52e45e9b', 'native', 'indian_river', 'F',
  'Live metric 238.9% (tier1_sold=43, closed_sold=18) confirmed GENUINE, not fabricated -- structural metric-design gap, not ghost data. Root cause: sold_amount backfill only ever ran for the 18 Tax Deed cases (tier1_sold_amount == sold_amount to the penny for all 18/18), never for the 25 CA/CC foreclosure cases which have tier1_sold_amount populated but sold_amount NULL. The 25 overhang rows have varied, plausible auction dates/amounts and non-clustered updated_at timestamps -- normal operational data, not a copy-artifact. HOWEVER: a prior audit row (id=2291, 2026-06-28) FALSELY claimed "F PASS: tier1_sold=18 closed_sold=18 (100.0%), same denominator fix as B" -- this is disproven by live query (tier1_sold is still 43, was never 18) and constitutes a WRONG-VERIFIED honesty-protocol violation (3x penalty per CLAUDE.md) that this row corrects.',
  '{"tier1_sold": 43, "closed_sold": 18, "ratio_pct": 238.9, "td_cases_matching_exactly": 18, "ca_cc_overhang_rows": 25, "overhang_data_quality": "varied auction_date 2025-05-27 to 2026-07-07, varied amounts $100-$353,600, non-clustered updated_at (16 unique 2026-06-26 + 9 batch 2026-06-28), 4 rows tagged data_source=realforeclose", "false_prior_claim_id": 2291, "false_prior_claim_text": "F PASS: tier1_sold=18 closed_sold=18 (100.0%). Same denominator fix as B.", "false_prior_claim_date": "2026-06-28T08:21:37Z", "correction": "tier1_sold was never 18; it is and remains 43 -- the prior claim copy-pasted Bs fix narrative without verifying F independently", "recommended_fix": "extend sold_amount backfill to CA/CC foreclosure auctions the same way it already covers TD cases; does not require touching indian_river certified 10/10 status since underlying tier1_sold_amount data is genuine"}'::jsonb,
  false
);
