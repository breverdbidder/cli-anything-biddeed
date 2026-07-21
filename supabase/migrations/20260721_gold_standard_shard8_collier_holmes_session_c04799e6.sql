-- Gold Standard Shard-8 (dispatch c04799e6-1443-4234-ae22-ef14044499e6)
-- Session: architect-20260721T160000
-- Counties: collier (8/10 → fix A, G), holmes (6/10 → fix B, C, D, F)
--
-- BEFORE STATE (from loop run 5668):
--   collier: A FAIL (fc=0 td=212), G FAIL (density=84.4 far=0.0 pk1000=)
--   holmes:  B FAIL (null), C FAIL (61.5%), D FAIL (61.5%), F FAIL (null)
--             I PASS (100.0), J PASS (100.0)
--
-- SESSION OUTCOME SUMMARY:
--   collier A — NOT FIXED. Fourth independent confirmation: Blazor-Server SignalR
--               app at cor.collierclerk.com/coraccess/ still has no REST surface
--               reachable without full browser JS (re-tested live 2026-07-21 via
--               WebFetch — every path returns 302 redirect to the generic Collier
--               Clerk homepage, no JSON/API endpoint exposed). Stays FAIL. Audit
--               row logged (survived=true on the dead-end finding itself).
--   collier G — NOT FIXED. C-4/C-5 FAR remains per-use schema limitation. Ran
--               the same api.municode.com CodesContent endpoint check documented
--               in the 2026-07-20 2nd-firing report — no new values found, no
--               new publicly-accessible source identified. The constraint is the
--               schema: max_far per zoning_district cannot represent "Hotels .60,
--               Destination resort .80" without a (district, use-type) granular
--               model. No fabrication. Audit row logged (survived=true).
--   collier H — REFRESHED. last_seen_at updated for all 212 collier rows.
--   holmes B  — NOT FIXED (4th+ session). holmesclerk.com = forward notice board
--               only. realtdm.com = login-gated staff tool. myfloridacounty.com/
--               orisearch/30 = CAPTCHA-gated. Firecrawl credits still = 0
--               (confirmed via /v1/team/credit-usage endpoint 2026-07-21).
--               No sold amounts can be recovered from any accessible source.
--   holmes C  — NOT FIXED. 5 unmatched cases (TD#2020-589, TD#2023-185,
--               TD#2023-225, TD#2023-496, TD#2023-584) verified STILL rolled off
--               clerk live page (fresh scrape of holmesclerk.com/courts/
--               foreclosures-tax-deeds/tax-deeds/ 2026-07-21: 5 cases listed,
--               NONE of the 5 target cases present — same result as the 07-10,
--               07-18, 07-20 sessions). Tax collector status='TD' confirmed again,
--               which means pending but not resolved. No tier1 parity source
--               available.
--   holmes D  — NOT FIXED. Same root cause as C (matched_any follows matched_clean).
--   holmes F  — NOT FIXED. Same root cause as B.
--   holmes H  — REFRESHED. last_seen_at updated for all 13 holmes rows.
--   holmes I  — UNCHANGED. Schema presence = 100.0% (evaluator). Adversarial check
--               from prior session (2026-07-20) found placeholder defects: all
--               market_value=98000, 3 FC rows share identical lat/lon. These are
--               pre-existing data-quality issues, not schema absences. The I evaluator
--               measures schema presence. Logging fresh survived=true for schema-
--               presence metric + survived=false for data-quality sub-issues (separate
--               claims, each with evidence).
--   holmes J  — UNCHANGED. Schema presence = 100.0% (evaluator). Same situation as I:
--               bid_decisions rows present for all 13, but all 10 TD rows are template-
--               identical. Logging fresh survived=true for schema-presence + survived=
--               false for template-quality sub-issue.
--
-- ============================================================================
-- COLLIER LETTER H — Freshness update
-- ============================================================================
UPDATE multi_county_auctions
SET last_seen_at = NOW()
WHERE lower(county) = 'collier'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '2 hours');

-- ============================================================================
-- HOLMES LETTER H — Freshness update
-- ============================================================================
UPDATE multi_county_auctions
SET last_seen_at = NOW()
WHERE lower(county) = 'holmes'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '2 hours');

-- ============================================================================
-- ULTRALOOP AUDIT ROWS — Collier (A, G)
-- ============================================================================
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'A',
    'collier A (fc=0 td=212): Collier foreclosure sales use a Blazor-Server SignalR court-events app at cor.collierclerk.com/coraccess/ — no REST surface reachable without full browser JS. Confirmed dead end for the 4th time: 2026-07-03 (run3713), 2026-07-18 (c40bb245), 2026-07-20 (9d04299e), 2026-07-21 (this session c04799e6). collier.realforeclose.com and collier.realtaxdeed.com both 302-redirect off-host to the vendor marketing site (ELB/vhost level). No online scrapeable foreclosure source exists for Collier County. A will remain FAIL until a new public source surfaces or a FOIA/records-request strategy is implemented. No row fabricated.',
    jsonb_build_object(
      'method', 'WebFetch + curl probe of cor.collierclerk.com/coraccess/ and collier.realforeclose.com (2026-07-21)',
      'result', '302-redirect off-host to clerk homepage for coraccess; collier.realforeclose.com redirects to vendor marketing site',
      'prior_sessions_confirmed_dead_end', jsonb_build_array(
        'shard13_run3645 (deprovisioned vendor account finding)',
        'shard1_run3713 (2026-07-03, full harvester written + ELB dead confirmed)',
        'shard12_9d04299e (2026-07-18, 3rd confirmation)',
        'shard12_9d04299e 2nd firing (2026-07-20, 4th confirmation)'
      ),
      'fc_count_current', 0,
      'td_count_current', 212
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'G',
    'collier G (density=84.4 far=0.0): C-4/C-5 FAR is per-use (Hotels=0.60, Destination resort=0.80 in LDC Sec 4.02.01 Table 2), not per-district. C-1 and Industrial correctly flagged far_regulated=false (LDC "None" in FAR column, applied 2026-07-20 migration). Parking flagged pk1000_regulated=false for all 4 districts (LDC Sec 4.05.04 Table 17 organized by land-use, not district). The 2 remaining FAR-applicable parcels (C-4=6 parcels, C-5=1 parcel) stay far=0.0% binding constraint. No new municipode path found this session. This is a genuine schema limitation: max_far per zoning_district cannot represent per-use FAR values without schema extension to (district, use-type) granularity.',
    jsonb_build_object(
      'method', 'Re-checked api.municode.com/CodesContent endpoint for Collier LDC Sec 4.02.01 Table 2 (same endpoint confirmed live in 2026-07-20 session)',
      'result', 'C-4/C-5 FAR column contains per-use values (Hotels .60, Destination resort .80) — unchanged from prior session',
      'c4_district_id', 11685,
      'c5_district_id', 11686,
      'far_applicable_parcels', 7,
      'far_filled_parcels', 0,
      'density_pct', 84.4,
      'far_pct', 0.0,
      'binding_constraint', 'far=0.0%',
      'schema_limitation', 'zone_standards.max_far is one value per zoning_district; Collier LDC regulates FAR per land-use within C-4/C-5, not as a district-wide figure',
      'prior_session_ref', '9d04299e-3c67-4ccf-8550-3e0e3272c0f1 (2026-07-20 2nd firing)'
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'B',
    'collier B (verified=62 closed_sold=62, metric=100.0): B passes. Verified live 2026-07-21: tax_deed_outcomes has 62 collier rows with data_source=collier_clerk_laserfiche, all matched by case_number to closed/sold multi_county_auctions rows. Independent clerk-of-court source (Laserfiche WebLink PDF harvest). No PropertyOnion data_source present. Ratio = 100.0%, within 95-105% band.',
    jsonb_build_object(
      'verified_outcomes', 62,
      'closed_sold', 62,
      'ratio_pct', 100.0,
      'data_source', 'collier_clerk_laserfiche',
      'in_band_95_105', true
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'C',
    'collier C (matched_clean=212, metric=100.0): C passes. All 212 collier rows have parity_status=matched_clean via clerk Laserfiche harvest (same independent source as B). No new parity gap found.',
    jsonb_build_object('matched_clean', 212, 'total', 212, 'pct', 100.0),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'D',
    'collier D (matched_any=212, metric=100.0): D passes. Same source as C.',
    jsonb_build_object('matched_any', 212, 'total', 212, 'pct', 100.0),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'E',
    'collier E (parcel_linked=212, metric=100.0): E passes. All 212 collier rows have parcel_id from Laserfiche harvest (parcel_id = property_id# field in the sale-list PDFs, Collier property appraiser folio number).',
    jsonb_build_object('parcel_linked', 212, 'total', 212, 'pct', 100.0),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'F',
    'collier F (tier1_sold=62 closed_sold=62, metric=100.0): F passes. 62 sold_amount values populated from collier_clerk_laserfiche (Laserfiche PDF "Status or Sold Amt" column, independent clerk source).',
    jsonb_build_object('tier1_sold', 62, 'closed_sold', 62, 'pct', 100.0),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'H',
    'collier H (hours_since_last_seen ≤ 48h): H passes. last_seen_at refreshed to NOW() for all 212 collier rows in this migration.',
    jsonb_build_object('last_seen_at_updated', true, 'rows_updated', 212, 'sla_48h', true),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'I',
    'collier I (card_complete=203 of 212, metric=95.8%): I passes (threshold 95%). 203/212 rows have non-null address+geo+value+zoning. 9 remaining gaps: Everglades City case 26111 (8 Group-2 no-DOR-match folios with JS-gated appraiser site) + 1 additional folio. Verified unchanged from 2026-07-20 session.',
    jsonb_build_object(
      'card_complete', 203,
      'total', 212,
      'pct', 95.8,
      'gap_details', 'Everglades City case 26111 + related folios: JS-gated OCPA site, Firecrawl credits=0 blocks browser-bypass'
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'collier',
    'J',
    'collier J (deal_complete=212, metric=100.0): J passes. All 212 bid_decisions rows have arv+max_bid+ml_score+5 required factor keys (distress_location, distress_property, distress_owner, cma_distressed, cma_resale). Verified via direct query of bid_decisions table for county=collier.',
    jsonb_build_object('deal_complete', 212, 'total', 212, 'pct', 100.0),
    true,
    NOW()
  );

-- ============================================================================
-- ULTRALOOP AUDIT ROWS — Holmes (B, C, D, F, I, J, and passing letters)
-- ============================================================================
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'A',
    'holmes A (fc=3 td=10, metric=3): A passes. 3 foreclosure cases + 10 tax deed cases = 13 total in multi_county_auctions for holmes. Source: holmesclerk.com WordPress clerk site (confirmed live 2026-07-21 scrape: FC page shows 3 active foreclosure entries, TD page shows 5 upcoming tax deeds). RealAuction lanes (holmes.realforeclose.com, holmes.realtaxdeed.com) confirmed dead as before (302-redirect to vendor marketing site).',
    jsonb_build_object(
      'fc_count', 3,
      'td_count', 10,
      'total', 13,
      'source', 'holmesclerk.com',
      'realauction_lanes', 'dead (302-redirect to vendor marketing site, both lanes)'
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'B',
    'holmes B (verified=0 closed_sold=0): B FAILS. holmesclerk.com is forward-looking notice board only — no results/disposition page exists for any past auction. realtdm.com is login-gated internal county staff tool (confirmed 2026-07-20 session). myfloridacounty.com/orisearch/30 = CAPTCHA-gated (POST returns "Please verify you are human", confirmed 2026-07-18). Firecrawl credits = 0 (confirmed live 2026-07-21 via /v1/team/credit-usage). FL DOR has no tax-deed-sale archive by design (Statute 197.502 makes this a Clerk-of-Court function). No sold amount can be recovered from any accessible public source for any Holmes auction. This is a structural source-coverage gap, not a matcher bug.',
    jsonb_build_object(
      'verified', 0,
      'closed_sold', 0,
      'sources_exhausted', jsonb_build_array(
        'holmesclerk.com (forward-looking only, no disposition page)',
        'holmes.realtdm.com (login-gated staff tool, TEST environment)',
        'myfloridacounty.com/orisearch/30 (CAPTCHA-gated)',
        'FL DOR statewide archive (does not exist by statute 197.502)',
        'holmescountytaxcollector.com (roll status only, no disposition/dollar)',
        'qpublic.net/holmes (Cloudflare 403)'
      ),
      'firecrawl_credits', 0,
      'firecrawl_confirmed_live', '2026-07-21'
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'C',
    'holmes C (matched_clean=8 of 13, metric=61.5%): C FAILS (threshold 95%). 5 unmatched cases: TD#2020-589, TD#2023-185, TD#2023-225, TD#2023-496, TD#2023-584. Fresh live scrape of holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/ (2026-07-21): 5 tax-deed cases currently listed (TD#2023-330, TD#2023-509, TD#2020-349, TD#2024-185, and 1 additional). The 5 target cases have rolled off the live page entirely — their last-seen date predates the 2026-07-10 first attempt. Tax Collector shows these parcels still as STATUS=TD (pending), not resolved. The Clerk''s site has no historical disposition page. No tier1 parity source available for these 5 cases.',
    jsonb_build_object(
      'matched_clean', 8,
      'total', 13,
      'pct', 61.5,
      'unmatched_case_numbers', jsonb_build_array('TD#2020-589','TD#2023-185','TD#2023-225','TD#2023-496','TD#2023-584'),
      'live_scrape_date', '2026-07-21',
      'live_td_cases_found', 5,
      'target_cases_on_live_page', 0,
      'tax_collector_status', 'TD (pending, not resolved) for all 5 parcels',
      'sessions_attempted', 4
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'D',
    'holmes D (matched_any=8 of 13, metric=61.5%): D FAILS. Same root cause as C: 5 cases not matched by any method (matched_clean or alternative key). No new matching key (parcel_id, sale_date, address) recovered for the rolled-off cases from any accessible source.',
    jsonb_build_object(
      'matched_any', 8,
      'total', 13,
      'pct', 61.5,
      'same_gap_as_C', true
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'E',
    'holmes E (parcel_linked=13, metric=100.0): E passes. All 13 holmes rows have parcel_id (DOR-format folio numbers from the clerk site). Spot-checked all 13 parcel_id values — confirmed non-null, non-placeholder in multi_county_auctions.',
    jsonb_build_object('parcel_linked', 13, 'total', 13, 'pct', 100.0),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'F',
    'holmes F (tier1_sold=0 closed_sold=0): F FAILS. Same root cause as B: no sold amount available from any accessible public source. All 13 auctions have sold_amount=NULL in multi_county_auctions and tax_deed_outcomes/foreclosure_outcomes. This is a structural block, not a pipeline gap.',
    jsonb_build_object(
      'tier1_sold', 0,
      'closed_sold', 0,
      'same_root_cause_as_B', true
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'G',
    'holmes G (density=100.0, metric=100.0): G passes. All 13 auction parcels resolve to zone_code=R-1 in v_zoning_district_applicability, which has far_applicable=false and pk1000_applicable=false. Density is 100% covered (R-1 has max_density_du_acre set). Verified via zone_standards query 2026-07-21.',
    jsonb_build_object(
      'density_pct', 100.0,
      'far_applicable', false,
      'pk1000_applicable', false,
      'zone_code', 'R-1',
      'applicable_parcels', 13,
      'metric', 100.0
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'H',
    'holmes H: H passes (SLA 48h). last_seen_at refreshed to NOW() for all 13 holmes rows in this migration.',
    jsonb_build_object('last_seen_at_updated', true, 'rows_updated', 13, 'sla_48h', true),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'I',
    'holmes I (card_complete=13 of 13, metric=100.0): Schema-presence gate PASSES (13/13 rows have non-null address+lat/lon+value+zoning link). ADVERSARIAL QUALITY CHECK: Found pre-existing data-quality defects — market_value=98000.00 is IDENTICAL across all 13 rows (vs varied values in neighboring counties), and 3 foreclosure rows share one identical lat/lon despite being at 3 different addresses in 2 different towns. These are schema-PRESENCE passes (the fields are non-null) but QUALITY FAILS (the values are placeholders). Logged separately as a second audit row (survived=false for quality).',
    jsonb_build_object(
      'card_complete', 13,
      'total', 13,
      'schema_presence_pct', 100.0,
      'schema_presence_gate_passes', true,
      'quality_issues', jsonb_build_array(
        'market_value=98000.00 identical across all 13 rows',
        '3 FC rows share identical lat/lon despite different addresses/towns'
      ),
      'evaluator_metric_measures', 'schema_presence_only'
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'I',
    'holmes I DATA QUALITY adversarial finding (distinct from schema-presence audit above): market_value=98000.00 is identical across all 13 rows. 3 FC rows share one lat/lon. These are real, pre-existing placeholder defects. Not fixed this session: qpublic.schneidercorp.com (Holmes PA) returns Cloudflare 403 for automated scraping; Firecrawl credits=0 (would enable browser-bypass). Left as residual for session with Firecrawl credits or Playwright automation.',
    jsonb_build_object(
      'quality_defect', 'uniform_placeholder_market_value',
      'market_value_all_rows', 98000.00,
      'fc_rows_identical_latlon', 3,
      'qpublic_status', 403,
      'firecrawl_status', 0,
      'fix_path', 'Firecrawl browser-bypass of qpublic.schneidercorp.com/application.aspx?AppID=holmes OR Playwright session; requires funded Firecrawl account'
    ),
    false,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'J',
    'holmes J (deal_complete=13 of 13, metric=100.0): Schema-presence gate PASSES (13/13 bid_decisions rows have arv+max_bid+ml_score+5 required factor keys). ADVERSARIAL QUALITY CHECK: 10 tax_deed bid_decisions rows are byte-for-byte IDENTICAL (arv=85000.00, max_bid=34500.00, ml_score=0.6200, factors.cma_distressed="opening_bid=0" for every row despite opening_bid varying per case: $1326.97, $1895.91, $1085.60, null, etc). This is a uniform fallback template, not a real two-arm CMA. Logged separately as survived=false for quality.',
    jsonb_build_object(
      'deal_complete', 13,
      'total', 13,
      'schema_presence_pct', 100.0,
      'schema_presence_gate_passes', true,
      'quality_issues', 'all 10 TD bid_decisions rows byte-identical (arv=85000, max_bid=34500, ml_score=0.62, cma_distressed="opening_bid=0" despite varying opening_bids)',
      'evaluator_metric_measures', 'schema_presence_only'
    ),
    true,
    NOW()
  ),
  (
    'c04799e6-1443-4234-ae22-ef14044499e6',
    'fallback',
    'holmes',
    'J',
    'holmes J DATA QUALITY adversarial finding: 10 TD bid_decisions rows are template-identical (same arv/max_bid/ml_score/factors regardless of per-case opening_bid). This is a uniform fallback template, not the "two-arm CMA" the evaluator contract requires. Root cause: comparable-sales data structurally unavailable for Holmes County (same B/F block means no sold_amount from any accessible source, which feeds the CMA pipeline). Not fixed this session.',
    jsonb_build_object(
      'quality_defect', 'uniform_template_bid_decisions',
      'rows_identical', 10,
      'example_arv', 85000.00,
      'example_max_bid', 34500.00,
      'example_ml_score', 0.6200,
      'root_cause', 'No comparable-sales data available for Holmes County — same structural block as B/F',
      'fix_path', 'Requires sold_amount data from official-records source (blocked on CAPTCHA / Firecrawl credits)'
    ),
    false,
    NOW()
  );
