-- SHARD-9 (hardee/duval/putnam/okaloosa/lafayette), dispatch 97977765-5157-4919-b206-11f8e29045e3
-- Adversarial-verified research (ULTRALOOP research agent, live WebFetch this session, no
-- Firecrawl available) found two real alternate sources independent of the dead RealAuction
-- tenants documented in pipeline.counties.notes for hardee/okaloosa:
--
-- HARDEE: hardeeclerk.com/departments/circuit-civil/foreclosure-sales/ and
-- .../tax-deeds/tax-deed-sales/ are live, real, official Clerk of Court pages. Sales are held
-- IN-PERSON (Wednesdays 11am, 2nd floor hallway outside Room 202, 417 W Main St, Wauchula FL)
-- -- same pattern as lafayette, no online RealAuction platform. The foreclosure page currently
-- lists ONE real active case: 25000327CAAXMX, 1841 State Road 66, Zolfo Springs FL, judgment
-- $408,906.52, sale date 2026-07-22. This is genuinely-sourced live data (fetched and confirmed
-- by an independent verifier agent this session), not a fabricated/synthetic seed -- inserting
-- it moves hardee A's foreclosure count from 0 to 1 honestly. A remains FAIL (needs BOTH fc>0
-- AND td>0 -- no real tax-deed case number was found this session, the tax-deed-sales page
-- describes sale mechanics but no visible case list in the fetch). foreclosure_platform/
-- taxdeed_platform corrected to clerk_inperson with the real URLs, matching lafayette's pattern.
--
-- OKALOOSA: okaloosaclerk.com/board-services/tax-deed-sales/ confirms tax deed sales are
-- conducted via Bid4Assets (www.bid4assets.com/OkaloosaFLTax/listings), and a parallel
-- Bid4Assets foreclosure listings page was independently found (www.bid4assets.com/OkaloosaFL/
-- listings) -- both fetched live this session (HTTP 200, real auction-list HTML with live 2026
-- sale dates, e.g. Aug 11 2026 tax deed, Jul 9 2026 foreclosure), NOT the dead RealAuction
-- splash. Per-case data on Bid4Assets loads via a backend AJAX call not present in the static
-- HTML fetched this session -- no case-level rows were extracted, so NO auction data is
-- inserted for okaloosa this migration (would require building a Bid4Assets scraper, next
-- session). Recording the real platform/URLs now so the next session does not re-spend time
-- re-discovering this. County appears mid-transition (still links the old RealAuction tenant
-- alongside Bid4Assets), noted honestly.

UPDATE pipeline.counties SET
  foreclosure_platform = 'clerk_inperson',
  foreclosure_url = 'https://www.hardeeclerk.com/departments/circuit-civil/foreclosure-sales/',
  taxdeed_platform = 'clerk_inperson',
  taxdeed_url = 'https://www.hardeeclerk.com/departments/tax-deeds/tax-deed-sales/',
  pipeline_status = 'active',
  notes = COALESCE(notes,'') || ' | 2026-07-10 shard9 run3497 (dispatch 97977765): ULTRALOOP-verified real alternate source found -- hardeeclerk.com, in-person sales (Wed 11am, 417 W Main St Wauchula, 2nd floor outside Rm 202), same pattern as lafayette. One real active foreclosure case ingested (25000327CAAXMX). No tax-deed case list found in this session''s fetch -- A remains FAIL (fc=1 td=0) until a real tax-deed case is sourced. foreclosure_platform/taxdeed_platform corrected realforeclose/realtaxdeed -> clerk_inperson.'
WHERE county_slug = 'hardee';

UPDATE pipeline.counties SET
  notes = COALESCE(notes,'') || ' | 2026-07-10 shard9 run3497 (dispatch 97977765): ULTRALOOP-verified real alternate source found -- okaloosaclerk.com/board-services/tax-deed-sales/ confirms tax deeds move via Bid4Assets (bid4assets.com/OkaloosaFLTax/listings, live, real 2026 sale dates Aug 11 + Sep 8). A parallel Bid4Assets foreclosure listings page also found (bid4assets.com/OkaloosaFL/listings, live, ~13 upcoming 2026 dates Jul 6-Aug 20). County appears mid-transition -- old RealAuction tenant links still present alongside Bid4Assets. Per-case rows load via a backend AJAX call not visible in a plain fetch (no Firecrawl this session) -- NOT scraped this session, no auction data inserted, foreclosure_platform/taxdeed_platform intentionally left unchanged pending a Bid4Assets-specific scraper next session (do not re-spend time re-discovering these URLs).'
WHERE county_slug = 'okaloosa';

INSERT INTO multi_county_auctions
  (county, sale_type, case_number, property_address, auction_date, auction_status,
   judgment_amount, data_source, source_url, created_at)
VALUES
  ('hardee', 'foreclosure', '25000327CAAXMX', '1841 State Road 66, Zolfo Springs, FL',
   '2026-07-22', 'upcoming', 408906.52, 'hardee_clerk_direct',
   'https://www.hardeeclerk.com/departments/circuit-civil/foreclosure-sales/', now());
