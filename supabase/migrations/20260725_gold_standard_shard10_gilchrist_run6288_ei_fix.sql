-- GOLD STANDARD shard-10 gilchrist (dispatch 28bd9542, loop run 6288)
-- E/I gap-fix: gilchrist grew from 6 to 14 auctions since the 2026-07-18 10/10 session;
-- the 8 new rows were never enriched, dragging E (parcel linkage) to 57.1% and
-- I (card completeness) to 42.9%.
--
-- Applied live via Supabase Management API during the session (pooler/psql auth
-- fails in this sandbox, matching every prior gilchrist session's finding).
-- This file tracks that live application in git; it is safe to re-run (idempotent
-- final values, ON CONFLICT DO NOTHING on inserts).

-- 1) Tax-deed rows 26-0010-TD / 26-0013-TD: real geo + assessed value from the
--    Gilchrist Property Appraiser live ArcGIS layer (gis1.hcpao.org), matched by
--    exact STRAP (dsp_strap format cracked this session: raw strap "150732..." <->
--    dashed dsp_strap "32-07-15-...").
UPDATE multi_county_auctions SET latitude = 29.8317984, longitude = -82.8369373, assessed_value = 4326
  WHERE county = 'gilchrist' AND case_number = '26-0010-TD' AND parcel_id = '320715-00360019-0070';
UPDATE multi_county_auctions SET latitude = 29.8968813, longitude = -82.8224045, assessed_value = 935
  WHERE county = 'gilchrist' AND case_number = '26-0013-TD' AND parcel_id = '090715-00770000-0240';

INSERT INTO parcel_zones (jurisdiction_id, parcel_id, zone_code, source)
  VALUES
    (883, '320715-00360019-0070', 'R-1', 'inferred:pattern_match_sibling_gilchrist_parcels_shard10_dispatch28bd9542'),
    (883, '090715-00770000-0240', 'R-1', 'inferred:pattern_match_sibling_gilchrist_parcels_shard10_dispatch28bd9542')
  ON CONFLICT DO NOTHING;

-- 2) Ghost-success remediation: 212025CA000035CAAXMX and 212024CA000010CAAXMX were
--    passing I's card_complete check on a FABRICATED placeholder coordinate
--    (29.7227, -82.7954) reused identically across multiple different addresses
--    (found by two independent adversarial verifier agents this session). Replaced
--    with real GIS centroids after confirming the GIS record's owner_addr matches
--    this DB row's property_address exactly (327 NE SIXTH AVE / 4299 SW CR 344).
--    Two more sibling rows (26-0005-TD, 212025CA000069CAAXMX) share the same
--    placeholder and were NOT fixed -- see session report for why (parcel_id
--    "171015" does not resolve on the GIS layer; the other candidate GIS match
--    has a use_dscr/assessed_value inconsistency suggesting a possible pre-existing
--    parcel mismatch -- left open rather than compounding the error).
UPDATE multi_county_auctions SET latitude = 29.6178878, longitude = -82.8152085
  WHERE county = 'gilchrist' AND case_number = '212025CA000035CAAXMX' AND parcel_id = '16-10-15-0046-000A-0041';
UPDATE multi_county_auctions SET latitude = 29.6637662, longitude = -82.87854
  WHERE county = 'gilchrist' AND case_number = '212024CA000010CAAXMX' AND parcel_id = '350914000000010000';

-- 3) The 6 remaining unlinked foreclosure cases (212025CA000064CAAXMX,
--    212026CA000004CAAXMX, 212025CA000033CAAXMX, 212025CA000070CAAXMX,
--    212025CA000043CAAXMX, 212025CA000036CAAXMX) were researched via a dedicated
--    research->apply->adversarial-verify Workflow (wf_e6239ab9-906, 18 agents) and
--    ALL returned confidence=UNKNOWN with zero writes -- genuine source-side data
--    gaps (gilchrist.realforeclose.com does not publish parcel/owner data for
--    pre-sale foreclosure listings; qpublic.schneidercorp.com, the only system that
--    could resolve it, is Cloudflare-blocked; Firecrawl had 0 API credits this
--    session). No SQL for these six -- BLANK > WRONG, adversarially confirmed as
--    honest skips, not ghost-successes. E therefore remains FAIL at 57.1% (8/14).

-- ULTRALOOP audit trail: 2 rows written to gold_standard_ultraloop_audit
-- (dispatch_id 28bd9542-c34b-42af-97c6-7ad3e8205808, ids 9791/9792, letters I/E,
-- both survived=true).
