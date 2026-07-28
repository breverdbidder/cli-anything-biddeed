-- GOLD STANDARD shard-1 (brevard/sumter/citrus/madison), dispatch 2f4312f9-1601-4103-8c7e-0eeb036ac834
--
-- DIAGNOSIS (VERIFIED live 2026-07-28 via pencil_dod_evaluate_county):
-- - brevard: 10/10 PASS live. Certification blocked only by ULTRALOOP evidence
--   staleness (adversarial_survival_0_of_10 -- last survived rows were 9+ days
--   old, outside the 7-day certify() window). Addressed separately by a fresh
--   ULTRALOOP audit+verify workflow run this session (gold_standard_ultraloop_audit
--   rows inserted, not part of this migration).
-- - sumter: 10/10 PASS live. Certification blocked by partial staleness
--   (adversarial_survival_5_of_10 -- letters A/C/D/H/J stale >7d). Same
--   ULTRALOOP refresh addressed this.
-- - citrus: E/I genuinely FAIL (180/191 = 94.2%%, need 182). Re-verified the
--   2026-07-27 architect-triage diagnosis (migration
--   20260727e_architect_triage_15181_citrus_e_ghost_linkage_purge.sql) stands:
--   2 MULTIPLE-PARCELS cases (schema-limited), 5 pending-judgment cases
--   (future auction dates), 4 CAPTCHA/paywall-gated. Firecrawl credits
--   confirmed still exhausted live today (remaining_credits=-4). NEW finding:
--   citrusclerk.org is migrating its foreclosure platform from RealForeclose
--   to Bid4Assets, with all foreclosure sales paused 2026-07-13 through
--   2026-08-17 (first Bid4Assets auction 2026-08-17) -- this is why case
--   2025 CA 000999 A (calendared 07-23, now past) never resolved. INFERRED
--   from news coverage, not yet cross-checked against the clerk docket
--   directly. No auction data changed for citrus in this migration --
--   informational note only, so the next session doesn't repeat today's
--   investigation from scratch.
-- - madison: A/B/F genuinely FAIL. A is FAIL by design (fc=5 td=0, tax-deed
--   page still lists zero properties, consistent with the 2026-07-10
--   finding). B/F FAIL because closed_sold=0 (no sold_amount on any of the
--   5 rows). Investigated the 2 past-due cases: 25-79-CA was NOT sold on its
--   old 07-14 date -- the clerk's live page shows it RESCHEDULED to
--   2026-09-08 (judgment $44,511.47 unchanged, still future so doesn't move
--   B/F yet; auction_date corrected below, this IS a real data fix). Case
--   21-36-CA (was 07-16) has disappeared from the clerk calendar entirely
--   with no results/archive section anywhere on the site -- outcome unknown.
--   Exhausted alternate sources: myfloridacounty.com/orisearch/40 needs a
--   party name we don't have; Civitek OCRS is JS-gated (browser-use CLI not
--   installed in this runner); madisonpa.com/qpublic are bot-blocked (403).
--   Two independent WebSearch summaries hallucinated conflicting dollar
--   amounts for 21-36-CA and were correctly discarded, not reported --
--   no fabrication. B/F remain a genuine external blocker pending either a
--   phone call to the clerk (850-973-1500) or JS-capable browser tooling.

-- ULTRALOOP AUDIT FINDING (brevard, VERIFIED live 2026-07-28 via fan-out
-- measure+adversarial-refute workflow, 15 measure/verify pairs across
-- brevard(10 letters)+sumter(5 stale letters)): brevard was NOT an honest
-- 10/10 as the brief assumed. Three real ghost-successes found:
--
-- 1. Letter E: original claim asserted "zero garbage parcel_id values" but
--    the refuter found 94 rows with parcel_id LIKE 'SYN-%%' (synthetic
--    placeholder IDs, not real BCPAO section-township-range numbers)
--    inflating the numerator. Purged below (same ghost-purge pattern as
--    citrus commit c96d7fce same week). E still PASSES honestly after
--    purge: 7047/7215 = 97.7%% (was falsely 99.0%%).
--
-- 2. Letter I: the evaluator's `property_address IS NOT NULL` check was
--    satisfied by 2122 rows containing literal placeholder strings
--    ('0 UNKNOWN', 'UNKNOWN', 'UNKNOWN FL', etc. -- 8 variants) instead of
--    a real address. Purged below. Honest post-purge metric:
--    card_complete=4865/7215=67.4%%, a GENUINE FAIL (evaluator had been
--    reporting a false PASS at 96.1%%). This is the same
--    null-coerced-to-pass anomaly class as the citrus 2026-07-27 E
--    ghost-linkage purge, just on the address field instead of parcel_id.
--
-- 3. Letter J: bid_decisions rows pass the evaluator's `factors ? key`
--    existence check, but the refuter proved the underlying values are a
--    MECHANICAL PLACEHOLDER FILL, not genuine per-property ML/CMA scoring:
--    brevard's 6690 rows collapse to 8 distinct ml_score values (87.3%% are
--    exactly 0.8200) and a near-constant distress_location=0.65 /
--    distress_owner+distress_property=(0.6,0.7) tuple. sumter's all-11
--    rows share one exact tuple (ml_score=0.5500, distress_owner=0.55,
--    distress_location=0.42, distress_property=0.5, cma_resale/cma_distressed
--    as pure arv*1.12/arv*0.87 multiples) written in only 2 batch
--    timestamps -- and the SAME tuple recurs in alachua (4/52 rows) and bay
--    (36/196 rows), proving this is a FLEET-WIDE mechanical fill script, not
--    county-specific data. NOT purged/fixed here: there is no real
--    per-property data underneath to restore, this needs the actual
--    Shapira-formula/two-arm-CMA generator rebuilt (out of this shard's
--    authority -- 4 auction-data counties, not the deal-thesis pipeline).
--    ESCALATED to AI Architect: J's evaluator contract (bd.factors ? key
--    existence, zero value-variance/authenticity check) is fleet-wide
--    exploitable and should not be trusted as evidence of real deal
--    intelligence until the generator is rebuilt or the evaluator adds a
--    variance/distinctness check.
--
-- Letter G: refuter also found parcel_zones has 363,876 rows for brevard
-- but only 340,446 distinct parcel_ids -- ~23,430 stale duplicate rows from
-- an unpurged prior re-ingestion batch (created_at 2026-01-23 vs corrected
-- 2026-03-04 re-ingestion). Does NOT change G's reported density/far/pk1000
-- percentages (those reproduced exactly), so G's PASS is not itself false,
-- but the "63,876 parcels" headline figure is inflated. NOT fixed here
-- (zoning_assignments ingestion dedup is out of this shard's scope) --
-- flagged as a residual for the zoning-ingest owner.
--
-- All 15 measure+verify results and full refuter evidence are persisted in
-- gold_standard_ultraloop_audit (dispatch_id 2f4312f9-1601-4103-8c7e-0eeb036ac834,
-- ultraloop_mode='native'), applied live via mgmt_sql.py before this file
-- was written, replayed here for reviewability.

UPDATE public.multi_county_auctions
SET parcel_id = NULL
WHERE lower(county) = 'brevard' AND parcel_id LIKE 'SYN-%';

UPDATE public.multi_county_auctions
SET property_address = NULL
WHERE lower(county) = 'brevard' AND property_address IS NOT NULL
  AND upper(trim(property_address)) LIKE '%UNKNOWN%';

-- Real data fix: madison case 25-79-CA rescheduled sale date (verified live
-- against madisonclerk.com today; was stale at 2026-07-14).
UPDATE public.multi_county_auctions
SET auction_date = '2026-09-08'
WHERE lower(county) = 'madison' AND case_number = '25-79-CA' AND sale_type = 'foreclosure';

-- Informational notes only -- no auction/outcome data fabricated or altered.
UPDATE pipeline.counties
SET notes = notes || E'\n\nGOLD STANDARD shard-1 dispatch 2f4312f9 (2026-07-28, re-verified live): E/I still FAIL (180/191=94.2%%, need 182). Re-confirmed the 2026-07-27 architect-triage diagnosis stands: 2 MULTIPLE-PARCELS cases (schema-limited), 5 pending-judgment cases (future auction 08/20-09/03), 4 CAPTCHA/paywall-gated. Firecrawl credits still exhausted (remaining_credits=-4, billing period stale since 2026-03/04 -- account needs renewal, flagging repo-wide, not citrus-specific). NEW FINDING today: citrusclerk.org is migrating its foreclosure platform from RealForeclose to Bid4Assets -- all Citrus foreclosure sales are PAUSED 2026-07-13 through 2026-08-17 during the migration (first Bid4Assets auction 2026-08-17), per a GlobeNewswire release corroborated by news syndication (INFERRED from news coverage, not yet cross-checked against the clerk docket directly -- next session should verify via SCORSS or a direct clerk-site fetch and then update foreclosure_platform/foreclosure_url to bid4assets once live). This explains why case 2025 CA 000999 A (calendared 07-23, now past) never resolved to a sale -- it was paused, not scraper failure. No auction data changed by this note.'
WHERE lower(county_slug) = 'citrus';

UPDATE pipeline.counties
SET notes = notes || E'\n\nGOLD STANDARD shard-1 dispatch 2f4312f9 (2026-07-28, re-verified live): A still FAIL by design (fc=5 td=0, tax-deed page still empty, consistent with 2026-07-10 finding). B/F still FAIL (closed_sold=0, no sold_amount on any of the 5 rows). Investigated the 2 past-due cases specifically: case 25-79-CA was NOT sold on its old 07-14 date -- clerk page now shows it RESCHEDULED to 2026-09-08 (judgment $44,511.47, addr 338 SW HORRY AVE, parcel 00-00-00-3765-000-000 -- auction_date corrected in multi_county_auctions from 2026-07-14 to 2026-09-08, still future so wont move B/F yet). Case 21-36-CA (was 07-16) has DISAPPEARED from the clerk calendar entirely with no results/archive section on the site -- outcome unknown (sold, dismissed, or continued off-calendar). Checked for an alternate source: madisonclerk.com foreclosure-sales page is calendar-only (no results archive); myfloridacounty.com/orisearch/40 (Official Records) requires party name, not case number, and we do not have the defendant name; Civitek OCRS (civitekflorida.com/ocrs/county/40/) public tier could not be reached (browser-use CLI not installed in this runner, JS-gated); madisonpa.com and qpublic both 403 bot-blocked. No dollar figure fabricated -- two independent WebSearch summaries hallucinated conflicting amounts for 21-36-CA across separate queries and were discarded, not reported. B/F genuinely unresolvable today without a phone call to the clerk (850-973-1500) for 21-36-CA''s disposition, or JS-capable browser access to Civitek OCRS/qpublic. Flagging for next session: try browser-use or Playwright (installed and working?) against Civitek OCRS public tier, or escalate the phone-call option to Ariel.'
WHERE lower(county_slug) = 'madison';
