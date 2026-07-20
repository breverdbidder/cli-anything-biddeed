-- GOLD STANDARD shard-4 (putnam/franklin/suwannee), dispatch 6eb17f60-d04c-404c-96f6-b8181e4c302c.
-- ULTRALOOP: 1 workflow fanned 2 research agents (franklin B/F, suwannee A/B/F re-check) via the
-- Workflow tool, each claim followed by an independent adversarial refuter agent (10 claims, 4
-- survived first pass). The orchestrator then did its own tie-breaking research on 2 refuted
-- franklin claims and a follow-up parcel-matching pass for suwannee. All findings logged to
-- gold_standard_ultraloop_audit (ids 7935-7938). Applied live via the Supabase Management API SQL
-- endpoint (psql/pooler auth unreachable from this sandbox, same as several prior sessions this
-- month) and PostgREST; this file documents the change for replay/audit.
--
-- BASELINE (pencil_dod_evaluate_county, verified live before any work):
--   putnam:   10/10, already gold. No action needed, re-verified unchanged.
--   franklin: 8/10 -- B FAIL (null, 0/0), F FAIL (null, 0/0). Everything else already PASS.
--   suwannee: 7/10 -- A FAIL (fc=0/td=9), B FAIL (null, 0/0), F FAIL (null, 0/0).
--
-- === FRANKLIN B/F -- REAL FIX, 8/10 -> 10/10 ===
-- Franklin's 5 tax-deed rows are all real (data_source=franklinclerk_wp_rest, live WordPress REST
-- feed re-confirmed today), 4 with auction_date 2026-07-08 (12 days past). That feed's own 'status'
-- field still read 'scheduled' for all 4 -- but independently inspecting
-- franklinclerk.com/public-sales/tax-deeds/ showed this is literally the SAME feed re-embedded
-- client-side to power an "Upcoming Tax Deed Sales" widget, not a separate results tracker (an
-- adversarial refuter initially treated it as an independent contradicting source and refuted 2 of
-- the 4 sale claims on that basis; the orchestrator's follow-up check overturned that once the
-- same-source relationship was established).
-- Real post-sale outcomes were instead captured from the Franklin County Property Appraiser's
-- recorded-instrument sales-history table (franklin-search.gsacorp.io/parcel/<id>, GSA Cadastral
-- platform), independently re-fetched and reproduced verbatim by both a refuter agent and the
-- orchestrator: 4 real "TAX DEED" instruments recorded 2026-07-14 (6 days post-auction, normal
-- recording lag), OR Book 1449 sequential pages 325/328/331/335, distinct real grantor/grantee
-- names, prices $11,000-$20,700 (all above opening bid, consistent with a competitive auction):
--   TDA 93-2023  (05-07S-03W-1001-000T-0270) -> $14,000 to HARTNESS CALVIN
--   TDA 616-2023 (30-08S-06W-1000-000B-0030) -> $20,700 to BRANCH MICHAEL F
--   TDA 624-2023 (30-08S-06W-1003-000B-0100) -> $16,000 to HARTNESS CALVIN
--   TDA 632-2023 (30-08S-06W-1011-0000-0440) -> $11,000 to CREAMER JONATHAN R
-- Direct confirmation via myfloridacounty.com/orisearch (deep-linked from the appraiser page) was
-- attempted by both the refuter and the orchestrator but is Cloudflare-Turnstile gated -- a real
-- access limitation, documented, not treated as contradicting evidence.
-- TDA 411-2023 (29-07S-04W-1002-0000-0070) correctly left untouched: status=redeemed (certificate
-- redemption, not a sale -- no sold_amount exists and none should be written).
-- Written: multi_county_auctions.sold_amount/winning_bidder/auction_status for the 4 cases, plus a
-- tax_deed_outcomes row per case (data_source='franklin_pa_gsacorp_recorded_td:2026-07-20', not
-- '%promote%', satisfying the independent-outcome requirement), then public.promote_tier1_from_
-- outcomes() was called once live (existing function, not modified) to populate tier1_sold_amount.
-- pencil_dod_evaluate_county('franklin'): B null(0/0)->100.0(4/4); F null(0/0)->100.0(4/4).
-- No regression on C/D/E/G/H/I/J (all pre-existing rows, only sold-outcome fields touched).
-- franklin: 8/10 -> 10/10.
-- Also corrected stale pipeline.counties metadata (pipeline_status 'blocked'->'active',
-- pipeline_health 'inactive'->'healthy') -- the prior note described only the dead RealTDM/
-- RealForeclose lanes (2026-07-02 investigation) and never recorded that the WP REST feed superseded
-- them as the real, live, working source.
--
-- === SUWANNEE A -- major new lead found, correctly NOT applied this session (no-regression rule) ===
-- Suwannee's realforeclose.com foreclosure lane re-confirmed genuinely empty (0 dayid cells Jul-Nov
-- 2026; control-checked same day against Brevard/Duval/Orange/Marion on the same platform, which
-- show 1/18/19/17 -- the scrape methodology itself is sound, this is a real county-specific zero).
-- BUT: realforeclose.com was the wrong venue entirely. suwgov.org/court-services/foreclosures/
-- (live, same-day-updated) states Suwannee foreclosure sales are held IN PERSON on the courthouse
-- steps -- same pattern as the existing Brevard exception -- and links a continuously-revised sale
-- list (suwgov.org/wp-content/uploads/Foreclosure-List-2-1-12.docx, 'Revised July 20, 2026', fetched
-- and parsed live from the real docx XML) with 6 real scheduled cases: 25-CA-197 (7/23), 25-CA-170
-- (7/28), 26-CA-19 (8/13), 25-CA-200 (8/18), 26-CA-2 (8/27), 26-CA-7 (8/27), all 2026.
-- 5 of 6 defendants were independently parcel-matched via a reverse-engineered, unauthenticated
-- Suwannee Property Appraiser API (GET suwannee-search.gsacorp.io/api/livesearch/<name> ->
-- /parcel/<id>), re-verified by the orchestrator against 2 of the 5 matches:
--   Dowdy (25-CA-197)   -> 17-06S-14E-04200-620080, 608 Savannah St NW, Branford FL, $117,081
--   Saavedra (25-CA-170)-> 32-03S-13E-08767-000011, 14127 CR 252, Live Oak FL, $107,513 mkt
--   Ramirez (26-CA-19)  -> 07-05S-13E-09108-050440, vacant/no situs address, $19,495
--   Sage (26-CA-2)      -> 17-02S-12E-09953-001000, 7490 193rd Rd, Live Oak FL, $128,528
--   Gleiss (26-CA-7)    -> 06-04S-15E-00750-000210, 15645 53rd Pl, Wellborn FL, $125,153
-- David Thomas (25-CA-200) unresolved: 3 same-name candidates, no public docket to disambiguate
-- (Suwannee civil court records are not online).
-- NOT WRITTEN to multi_county_auctions: v_zoning_gold_standard_card was checked live for all 5
-- resolved parcel_ids -- zero have a zone_code. Inserting now would grow suwannee auctions_total
-- 9->14 with zero I-card-complete numerator growth, dropping I from 100.0 (9/9, PASS, a critical-
-- three letter) to <95 (9/14, FAIL) -- a real regression, not a scoring artifact. Held back per the
-- campaign's no-regression rule. Full findings (case numbers, dates, parcel IDs, addresses, values,
-- the reusable /api/livesearch/ discovery) logged to pipeline.counties.notes and
-- gold_standard_ultraloop_audit (id 7937, survived=true) so a future session with zoning/parcel_zones
-- coverage for these 5 parcels can insert immediately without re-deriving any of this.
--
-- === SUWANNEE B/F -- re-checked, still genuinely unresolved (no write) ===
-- Cases 4666/4667 (auction_date 2026-07-09): the realtaxdeed.com CALACT/CALSCH day-counter was shown
-- to be non-authoritative (a known-past 2026-06-04 auction, 47 days old, also still reads CALACT=0),
-- and neither case number appears in the Clerk's own current published TD schedule PDF at all
-- (Schedule-07.20.2026.pdf lists only 4706-4712/4784 for the 8/6/2026 sale) -- a genuine case-number/
-- format discrepancy versus the county's real TD#/YYYY-#### convention, flagged as an open question
-- for a future session, not resolved as sold or not-sold. No write made; state unchanged.
--
-- AFTER (pencil_dod_evaluate_county, re-verified live immediately after the writes above):
--   putnam:   unchanged, 10/10.
--   franklin: 8/10 -> 10/10 (B, F both PASS; C/D/E/G/H/I/J unchanged PASS).
--   suwannee: unchanged, 7/10 (A/B/F FAIL -- A has a ready-to-ship fix blocked only on zoning
--             linkage for 5 specific parcels; B/F remain a genuine open case-number discrepancy).
--
-- No SQL statements below write anything beyond what is documented above -- the actual writes for
-- multi_county_auctions, tax_deed_outcomes, and pipeline.counties were applied live via the Supabase
-- Management API SQL endpoint during this session; this file replays them verbatim for audit/replay
-- continuity.

BEGIN;

UPDATE multi_county_auctions
SET sold_amount = 14000,
    winning_bidder = 'HARTNESS CALVIN',
    auction_status = 'sold',
    sold_amount_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20',
    sold_amount_captured_at = now(),
    winning_bidder_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20'
WHERE lower(county) = 'franklin' AND case_number = 'TDA 93-2023' AND sold_amount IS NULL;

INSERT INTO tax_deed_outcomes (case_number, county, auction_date, parcel_id, winning_bid, outcome, winner_name, data_source, source_url, enriched_at)
SELECT 'TDA 93-2023', 'franklin', '2026-07-08', '05-07S-03W-1001-000T-0270', 14000, 'sold', 'HARTNESS CALVIN', 'franklin_pa_gsacorp_recorded_td:2026-07-20', 'https://franklin-search.gsacorp.io/parcel/03W07S051001000T0270', now()
WHERE NOT EXISTS (SELECT 1 FROM tax_deed_outcomes WHERE case_number = 'TDA 93-2023' AND county = 'franklin');

UPDATE multi_county_auctions
SET sold_amount = 20700,
    winning_bidder = 'BRANCH MICHAEL F',
    auction_status = 'sold',
    sold_amount_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20',
    sold_amount_captured_at = now(),
    winning_bidder_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20'
WHERE lower(county) = 'franklin' AND case_number = 'TDA 616-2023' AND sold_amount IS NULL;

INSERT INTO tax_deed_outcomes (case_number, county, auction_date, parcel_id, winning_bid, outcome, winner_name, data_source, source_url, enriched_at)
SELECT 'TDA 616-2023', 'franklin', '2026-07-08', '30-08S-06W-1000-000B-0030', 20700, 'sold', 'BRANCH MICHAEL F', 'franklin_pa_gsacorp_recorded_td:2026-07-20', 'https://franklin-search.gsacorp.io/parcel/06W08S301000000B0030', now()
WHERE NOT EXISTS (SELECT 1 FROM tax_deed_outcomes WHERE case_number = 'TDA 616-2023' AND county = 'franklin');

UPDATE multi_county_auctions
SET sold_amount = 16000,
    winning_bidder = 'HARTNESS CALVIN',
    auction_status = 'sold',
    sold_amount_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20',
    sold_amount_captured_at = now(),
    winning_bidder_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20'
WHERE lower(county) = 'franklin' AND case_number = 'TDA 624-2023' AND sold_amount IS NULL;

INSERT INTO tax_deed_outcomes (case_number, county, auction_date, parcel_id, winning_bid, outcome, winner_name, data_source, source_url, enriched_at)
SELECT 'TDA 624-2023', 'franklin', '2026-07-08', '30-08S-06W-1003-000B-0100', 16000, 'sold', 'HARTNESS CALVIN', 'franklin_pa_gsacorp_recorded_td:2026-07-20', 'https://franklin-search.gsacorp.io/parcel/06W08S301003000B0100', now()
WHERE NOT EXISTS (SELECT 1 FROM tax_deed_outcomes WHERE case_number = 'TDA 624-2023' AND county = 'franklin');

UPDATE multi_county_auctions
SET sold_amount = 11000,
    winning_bidder = 'CREAMER JONATHAN R',
    auction_status = 'sold',
    sold_amount_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20',
    sold_amount_captured_at = now(),
    winning_bidder_source = 'franklin_pa_gsacorp_recorded_td:2026-07-20'
WHERE lower(county) = 'franklin' AND case_number = 'TDA 632-2023' AND sold_amount IS NULL;

INSERT INTO tax_deed_outcomes (case_number, county, auction_date, parcel_id, winning_bid, outcome, winner_name, data_source, source_url, enriched_at)
SELECT 'TDA 632-2023', 'franklin', '2026-07-08', '30-08S-06W-1011-0000-0440', 11000, 'sold', 'CREAMER JONATHAN R', 'franklin_pa_gsacorp_recorded_td:2026-07-20', 'https://franklin-search.gsacorp.io/parcel/06W08S30101100000440', now()
WHERE NOT EXISTS (SELECT 1 FROM tax_deed_outcomes WHERE case_number = 'TDA 632-2023' AND county = 'franklin');

UPDATE pipeline.counties
SET pipeline_status = 'active',
    pipeline_health = 'healthy'
WHERE county_slug = 'franklin';

COMMIT;

SELECT public.promote_tier1_from_outcomes();
