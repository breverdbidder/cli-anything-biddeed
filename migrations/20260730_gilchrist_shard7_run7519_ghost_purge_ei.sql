-- GOLD STANDARD shard-7 gilchrist (dispatch 61f11933, loop run 7519)
-- Ghost-success purge: 212025CA000069CAAXMX and 26-0005-TD held fabricated/unverified
-- geo+value data that was inflating I's card_complete from the well-documented genuine
-- baseline of 6/14 (42.9%) up to 8/14 (57.1%). Applied live via Supabase Management API
-- during the session (direct psql/pooler auth fails in this sandbox, matching every
-- prior gilchrist session's finding).
--
-- Root cause: parcel_zones rows for both parcel_ids carry source tag
-- 'shard5_g_i_fix/shard5_gilchrist_auto' -- an untracked automated process (not any of
-- the 3 documented careful gilchrist sessions: 28bd9542, 5269ffd2, 61f11933-branch) wrote
-- this data between 2026-07-25 and 2026-07-30, bypassing the ULTRALOOP verification gate
-- that two of those sessions explicitly used to DECLINE writing this exact data.
--
-- Live GIS cross-check this session (gis1.hcpao.org ArcGIS REST, reachable via curl -k;
-- raw strap encoding reverse-engineered as dsp_strap groups [SS,TT,RR,block,lot,parcel]
-- with the first 3 groups reversed to [RR,TT,SS] for the 'strap' field):
--
-- 212025CA000069CAAXMX: linked parcel 11-10-16-0552-0010-0060 resolves on live GIS to a
--   VACANT lot, cap_val=$1,300, owner=VISION CONSTRUCTION INC, owner_addr=380 SW 266TH ST
--   NEWBERRY FL -- directly contradicting the DB's claim of a $183,373 single-family home
--   at "7439 SE 78 PL, TRENTON". An exhaustive owner_addr sweep of GIS for "78TH PL"/"78 PL"
--   patterns (28 results) found no parcel at address 7439 anywhere in the county.
--
-- 26-0005-TD: parcel_id "171015" does not resolve as a valid STRAP in either raw or
--   dsp_strap encoding (confirmed: not a valid 18-digit STRAP, no GIS record). The written
--   address "1202 SW FOURTH AVE" does not exist in GIS -- a full sweep of the section-17
--   SW 4TH AVE block (253 parcels) shows house numbers running ...1128, 1234, 1301... with
--   no 1202. The best candidate parcel found by a prior session (171015005100000180, owner
--   "JS REAL PROPERTIES LLC TRUSTEE") was explicitly NOT applied by that session pending
--   case-to-parcel confirmation (gilchristclerk.com 403-blocked) -- and the value actually
--   written ($16,771) does not even match that candidate's live cap_val ($12,750), meaning
--   this was not a careful application of that lead either.
--
-- This is safe to re-run (idempotent WHERE clause pins the exact stale values).

UPDATE multi_county_auctions
SET parcel_id = NULL, latitude = NULL, longitude = NULL, assessed_value = NULL
WHERE county = 'gilchrist' AND case_number = '212025CA000069CAAXMX'
  AND parcel_id = '11-10-16-0552-0010-0060';

UPDATE multi_county_auctions
SET parcel_id = NULL, latitude = NULL, longitude = NULL, assessed_value = NULL
WHERE county = 'gilchrist' AND case_number = '26-0005-TD'
  AND parcel_id = '171015';

-- Result: E parcel_linked 8->6 (57.1%->42.9%), I card_complete 8->6 (57.1%->42.9%).
-- This is a metric REGRESSION in raw number but a CORRECTION in truth -- the 8/14 figure
-- was never real, just undocumented fabrication. E and I now honestly match the baseline
-- independently reconfirmed by 2 prior sessions (28bd9542, 5269ffd2) before the unlogged
-- shard5_gilchrist_auto write occurred.
--
-- The 6 structurally-unlinkable foreclosure cases (212025CA000033CAAXMX,
-- 212025CA000036CAAXMX, 212025CA000043CAAXMX, 212025CA000064CAAXMX, 212025CA000070CAAXMX,
-- 212026CA000004CAAXMX) remain untouched -- 4th consecutive session confirming
-- gilchrist.realforeclose.com does not publish per-parcel data pre-sale, and every system
-- that could resolve it (qpublic, gilchristclerk, Firecrawl) is blocked or exhausted. No
-- SQL for these six -- BLANK > WRONG.

-- ULTRALOOP audit trail: 2 rows written to gold_standard_ultraloop_audit
-- (dispatch_id 61f11933-122d-4474-acf3-65e71d7a707c, letters I (survived=false, this is a
-- refutation/purge record, not a certification claim) and E (survived=true, documents a
-- verified non-improvement / structural block, not a false claim)).
