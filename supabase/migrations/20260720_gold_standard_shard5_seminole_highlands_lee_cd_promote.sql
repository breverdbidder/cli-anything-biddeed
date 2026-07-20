-- GOLD STANDARD shard-5 (seminole/highlands/lee), dispatch 8acb0c40-fd3b-48a6-b357-fc15c79f973f.
-- C/D fix for highlands + lee: promote rows already sourced directly from the county's
-- tier1 platform (RealForeclose/RealTaxDeed) via calendar_sweep_mca_v3 -- which paginates
-- the JSON UPDATE endpoint (up to 15 pages) unlike the single-page ajax_harvest scripts --
-- but were left with parity_status NULL/mca_only because calendar_sweep_mca.py's Phase C
-- upsert does not set the parity verdict, only the raw auction fields.
--
-- VERIFIED live 2026-07-20 (mgmt_sql.py against mocerqjnksmhcjzxrewo):
--   highlands: 27 tax_deed rows, calendar_sweep_mca_v3, auction_date 2026-08-05..2026-08-19,
--     real Sebring/Avon Park addresses, real opening_bid, real Highlands parcel_id (C-NN-..).
--   lee: 22 foreclosure rows, calendar_sweep_mca_v3, auction_date 2026-06-25/07-09/07-30,
--     real Lee Co addresses, real judgment_amount, real Lee STRAP-format parcel_id.
-- Both counties' foreclosure_platform/taxdeed_platform in pipeline.counties confirm
-- calendar_sweep_mca_v3's BASE_URL is the same tier1 RealForeclose/RealTaxDeed domain
-- already used by the existing 'tier1_realforeclose_*' / 'tier1_live_realtaxdeed_ajax_*'
-- labeled rows for these counties -- this is not a third-party litmus source.
--
-- NOT touched: highlands' 2 'bootstrap_placeholder' rows (case_number
-- HIGHLANDS-FC-2026-001/002, data_source realforeclose:shard5-highlands-fc-v1) -- these
-- carry synthetic placeholder case numbers, not real court case numbers, and are the
-- entirety of highlands' foreclosure lane (A metric fc=2). Flagged as an open integrity
-- gap in the session report; not promoted here (would be a ghost-success/fabrication).

BEGIN;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:calendar_sweep_mca_v3:tax_deed:' || auction_date::text
WHERE lower(county) = 'highlands'
  AND parity_status IS NULL
  AND data_source = 'calendar_sweep_mca_v3'
  AND sale_type = 'tax_deed'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true);

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:calendar_sweep_mca_v3:foreclosure:' || auction_date::text
WHERE lower(county) = 'lee'
  AND parity_status = 'mca_only'
  AND data_source = 'calendar_sweep_mca_v3'
  AND sale_type = 'foreclosure'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true);

COMMIT;
