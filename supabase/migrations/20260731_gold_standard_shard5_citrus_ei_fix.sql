-- Gold Standard shard-5 citrus E (parcel linkage) + I (card completeness) fix, 2026-07-31.
--
-- Context (VERIFIED live, 2026-07-31):
--   pencil_dod_evaluate_county('citrus').E BEFORE: 94.2% (parcel_linked=180 of 191) -- FAIL.
--   pencil_dod_evaluate_county('citrus').I BEFORE: 94.2% (card_complete=180 of 191) -- FAIL.
--   Same 11 gap rows drive both letters (all sale_type=foreclosure, parcel_id IS NULL,
--   property_address IS NULL): 2025 CA 001016 A, 2025 CA 000393 A, 2025 CA 000655 A,
--   2025 CA 000343 A, 2025 CA 000734 A, 2025 CA 000967 A, 2025 CA 000855 A,
--   2025 CA 000607 A, 2025 CA 000999 A, 2024 CA 000179 A, 2025 CA 000110 A.
--
-- Need >=182/191 (95%) on both E and I. RESULT THIS SESSION: 0 of the 11 rows could be
-- legitimately fixed without either fabricating data or violating a real DB constraint
-- (see below) -- all 11 are GENUINELY BLOCKED. This migration applies ONE safe,
-- zero-risk correction (fixing a stale placeholder zone_code guess to a verified value
-- on an ALREADY-linked sibling parcel) that does not move E or I but removes a
-- previously-unsourced guess from the data. E and I metrics are UNCHANGED by this
-- migration; see closing report for full honesty accounting.
--
-- ── 2025 CA 000110 A: researched, VERIFIED real data found, but BLOCKED by a genuine
--    DB uniqueness conflict with an already-authoritative duplicate row ─────────────
--
-- IMPORTANT CORRECTION vs prior-session research notes: the prior session's dispatch
-- notes claimed parcel_id/pin=2675608 for this case. That pin was VERIFIED THIS SESSION
-- to belong to a DIFFERENT, unrelated case (2025 CA 000690 A, 10360 W Pamondeho Cir,
-- Crystal River) -- the two cases' RealForeclose cards were adjacent in the same raw
-- scrape and the wrong pin was carried over. Root-caused via pipeline.tier1_card_raw
-- (county_slug='citrus', case_number_text='2025 CA 000110 A', scraped_at 2026-05-20):
-- the raw_card_text shows the datalet link with pin=1475589 immediately preceding the
-- "47 S DAVIS ST" address line for case 000110 A itself; pin=2675608 belongs to the
-- following card (case 000690 A, "Auction Status Canceled per Bankruptcy").
--
-- SOURCE (VERIFIED live, fetched 2026-07-31):
--   http://www.citruspa.org/_Web/datalets/datalet.aspx?mode=profileall&UseSearch=no&pin=1475589&jur=19&LMparent=20
--   (Citrus County Property Appraiser, live parcel record card)
--   quoted: "Parcel ID/PIN: 18E18S110040 00580 0230 (Altkey: 1475589) | Property Address:
--   47 S Davis St, Beverly Hills, FL 34465 | Owner: Lorenz Victoria | Land Use/Zoning:
--   Residential Non-Waterfront (MDR zoning) | Assessed Value (2025): $125,034 |
--   Market Value (2025): $147,335"
--   This matches pipeline.tier1_card_raw exactly (assessed_value_text "$125,034.00",
--   Auction Sold 03/12/2026 10:02 AM ET Amount $51,100.00 Sold To Plaintiff, Final
--   Judgment Amount $102,592.51).
--
-- BUT: attempting to write parcel_id='1475589' onto case 2025 CA 000110 A FAILED live
-- (STATUS 400, ERROR 23505 duplicate key on unique constraint
-- uq_mca_county_sale_date_parcel (county, sale_type, auction_date, parcel_id)) because
-- multi_county_auctions ALREADY has a DIFFERENT row -- case 2022 CA 000835 A,
-- id=19804470-7883-40e4-a065-1d8128a91f73, tier1_authoritative=true -- with the exact
-- same parcel_id='1475589', property_address='47 S DAVIS ST', auction_date=2026-03-12,
-- sale_type=foreclosure. Both rows describe what is evidently the SAME physical
-- foreclosure auction (same parcel, same address, same sale date) under two different
-- case numbers, with 2022 CA 000835 A already correctly card-complete and flagged
-- authoritative. This is a genuine data-integrity finding (likely a case
-- refiling/renumbering the scraper captured under both the old and new docket number),
-- not a sourcing gap -- and resolving it (deciding which case number is canonical,
-- whether to merge/delete a row) is a data-model decision outside this session's scope
-- and outside the "backfill sourced fields" mandate. Per HONESTY PROTOCOL, this
-- migration does NOT force a workaround (e.g. writing a slightly different/fabricated
-- parcel_id just to dodge the constraint) -- 2025 CA 000110 A is documented as
-- GENUINELY BLOCKED for this reason, even though real source data for the underlying
-- property was found and verified.
--
-- Zone: citruspa.org states zoning label "MDR" (Medium Density Residential) for parcel
-- 1475589. This maps to the EXISTING zoning_districts row jurisdiction_id=1327
-- (Unincorporated Citrus County -- Beverly Hills is an unincorporated CDP; 1327 is
-- already the jurisdiction used for all 250 existing Citrus parcel_zones rows),
-- code='MDR' (id=11145, "Medium Density Residential District"), which ALREADY has
-- max_density_du_acre=4.00 and max_far=0.40 populated -- reusing this row is zero-risk
-- to G (no new unpopulated-standards district created).
--
-- parcel_zones already had a row for parcel_id='1475589' (id=821394, zone_code='LDR',
-- source='inferred_residential_default', created 2026-06-27) -- a stale placeholder
-- guess, NOT sourced from the property appraiser, attached to the ALREADY-authoritative
-- case 2022 CA 000835 A. Since real source data for this exact parcel was verified this
-- session (see above), this migration corrects that existing zone_code from the old
-- guess to the verified MDR value. This does NOT move the citrus E/I metrics (the
-- authoritative row was already parcel_linked/card_complete before this migration; only
-- its zone_code label changes from a guess to a sourced value) but is a genuine,
-- zero-risk data-quality improvement in scope of what this session verified. LDR
-- (id=11144) and MDR (id=11145) are both fully-populated existing districts in the same
-- jurisdiction, so either reuse is zero-risk to G.
--
-- ── Rows left GENUINELY BLOCKED this session (11 -- all of them) ───────────────────
--
-- 2025 CA 000110 A: BLOCKED by the DB uniqueness conflict documented above (real source
-- data exists but cannot be written without either violating a constraint or
-- fabricating a different parcel_id).
--
-- The remaining 10:
--
-- Fresh checks attempted THIS session for all 10 (per task instructions, one fresh
-- check per case before declaring blocked):
--   1. pipeline.tier1_card_raw / tier1_today: broad ILIKE search on case number digits
--      (e.g. '%000655%', '%000967%', '%000855%', '%000179%', '%000343%', '%000393%',
--      '%000607%', '%000734%', '%000999%', '%001016%') against both case_number_text
--      and raw_card_text columns -- ZERO rows returned for any of the 10. Confirmed the
--      prior session's note that "2025 CA 001016 A" tier1_today row actually carries
--      raw_context for "2025 CA 000393 A" is NOT reproducible this session -- neither
--      case appears in tier1_today at all now (rolling window has moved past both).
--   2. Live WebFetch of citrus.realforeclose.com (auction calendar + case preview pages):
--      HTTP 403 Forbidden on every request this session (bare domain and dated preview
--      URLs alike) -- consistent with prior-session note of clerk-site automated-fetch
--      blocks, now extended to the RealForeclose domain itself.
--   3. Live WebFetch of search.citrusclerk.org/LandmarkWeb case-number search: the
--      search interface requires POST/JS form submission (SearchTypeCaseNumber page
--      returns 404 on direct GET; the CFN document-retrieval endpoint used successfully
--      for other rows returns unreadable scanned-image PDF binary, not text). No GET-
--      queryable case-number search endpoint found.
--   4. SCORSS (Citrus Clerk court records) and Bid4Assets (Citrus's foreclosure sale
--      platform as of this session, per WebSearch): scorss.citrusclerk.org requires
--      account/session; bid4assets.com storefront search returned HTTP 403 Forbidden.
--   5. WebSearch (public index) for each case number individually and in combination:
--      zero indexed results for any of the 10 case numbers on any domain.
--   No browser-use CLI available in this sandbox (not installed) to drive the
--   JS/POST-based search forms interactively as a fallback.
--
-- Conclusion: all 10 remaining rows are GENUINELY BLOCKED this session -- every reachable
-- primary source (RealForeclose calendar/case pages, Citrus Clerk LandmarkWeb docket
-- search, SCORSS, Bid4Assets) is either unreachable (403), returns non-text binary, or
-- requires interactive JS/session auth this sandbox cannot drive. No parcel_id or
-- address data exists for these 10 in any DB table available (multi_county_auctions,
-- pipeline.tier1_today, pipeline.tier1_card_raw, tax_deed_outcomes,
-- foreclosure_outcomes). Per HONESTY PROTOCOL / hard guardrails, no value is fabricated
-- for these rows. Case numbers: 2025 CA 001016 A, 2025 CA 000393 A, 2025 CA 000655 A,
-- 2025 CA 000343 A, 2025 CA 000734 A, 2025 CA 000967 A, 2025 CA 000855 A,
-- 2025 CA 000607 A, 2025 CA 000999 A, 2024 CA 000179 A.

SET statement_timeout = 0;

-- ── 1. Diagnostic before update ─────────────────────────────────────────────────
DO $$
DECLARE
  v_before jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('citrus') INTO v_before;
  RAISE NOTICE 'Citrus E BEFORE: %', v_before->'E';
  RAISE NOTICE 'Citrus I BEFORE: %', v_before->'I';
END $$;

-- ── 2. NOTE: no UPDATE to multi_county_auctions for 2025 CA 000110 A -- writing
--    parcel_id='1475589' onto this case FAILS live with ERROR 23505 (unique constraint
--    uq_mca_county_sale_date_parcel) because case 2022 CA 000835 A already holds that
--    exact (county, sale_type, auction_date, parcel_id) combination as an authoritative
--    row. See comment block above. Left as-is (parcel_id/property_address remain NULL,
--    GENUINELY BLOCKED).

-- ── 3. Correct the existing stale-guess parcel_zones row to verified MDR ────────────
-- (attached to the already-authoritative sibling case 2022 CA 000835 A, same parcel)
UPDATE parcel_zones
SET zone_code = 'MDR',
    zone_name = 'Medium Density Residential District',
    source = 'gold_standard_shard5_citrus_ei_20260731_citruspa_verified'
WHERE parcel_id = '1475589'
  AND jurisdiction_id = 1327
  AND source = 'inferred_residential_default';

-- ── 4. Diagnostic after update ──────────────────────────────────────────────────
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('citrus') INTO v_after;
  RAISE NOTICE 'Citrus E AFTER: %', v_after->'E';
  RAISE NOTICE 'Citrus I AFTER: %', v_after->'I';
  RAISE NOTICE 'Citrus G AFTER (regression check): %', v_after->'G';
END $$;
