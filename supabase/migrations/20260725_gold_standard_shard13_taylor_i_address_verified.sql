-- Gold Standard shard-13 (taylor), dispatch 4c2cb537-516e-441e-b381-3f9a7d906ef6, loop run 6288.
--
-- Case 23-597 CA / parcel_id 05026-000: the on-file placeholder property_address
-- ("TAYLOR COUNTY, FL") and a latitude/longitude that independently verified to
-- resolve to an unrelated parcel (05706-500, a City of Perry road right-of-way)
-- are replaced with the real address and legal description, sourced from the
-- primary recorded Summary Final Judgment of Foreclosure (Taylor County Official
-- Records Book 928, Page 452-458, Instrument 250006203, recorded 2025-11-14).
-- Independently corroborated by two further sources fetched this session: the
-- Re-Notice of Sale PDF at taylorclerk.com/uploads/2026/07/23-597-CA.pdf (filed
-- 2026-07-21) and the live taylorclerk.com/departments/foreclosure-sales/ listing
-- (Case 23-597 CA, Judgment $92,079.12, Sale Date 10/13/2026 -- matches our DB).
--
-- The prior placeholder lat/long is nulled rather than left in place, per
-- BLANK > WRONG -- it is confirmed wrong, not merely unconfirmed.
--
-- parcel_id 05026-000 itself is NOT touched and remains unresolved: FL GIO
-- Statewide Cadastral ArcGIS FeatureServer filtered /query calls (WHERE CO_NO=62
-- ...) time out from this sandbox's network egress, confirmed independently 3x
-- (2 ULTRALOOP workflow agents + this session's own httpx test, 45s timeout) --
-- unfiltered/metadata calls succeed (HTTP 200), so this is a genuine
-- environmental egress limitation on filtered queries, not a quoting bug. This
-- update therefore does NOT move the I letter this session (evaluator formula
-- requires parcel_id to resolve to a zone_code-linked row in
-- v_zoning_gold_standard_card; 05026-000 still does not). Left as-is because
-- nulling it would regress E (parcel_linked) from 100% to 88.9%, an unrelated
-- and unjustified regression.
--
-- B/F reconfirmed genuinely blocked this session (3rd independent same-day
-- confirmation across sessions): pubrecords.taylorclerk.com/PublicInquiry
-- (CDS/nScribe platform, myfloridacounty.com's own Taylor entry resolves to this
-- exact URL) returns a Cloudflare interactive-challenge 403 on every fetch;
-- taylorclerk.com/departments/tax-deeds-surplus/ is stale (dated 2025-02-19,
-- does not cover any 2026 case); taylorclerk.com/departments/foreclosure-sales/
-- removes closed cases (25-196 CA, 25-218 CA both confirmed absent from the live
-- listing); taylor.realtdm.com remains a RealAuction TEST sandbox tenant;
-- qpublic.net/fl/taylor/ is also Cloudflare-gated; FIRECRAWL_API_KEY returned
-- HTTP 402 insufficient-credits, ruling out a JS-render workaround without a
-- spend decision. No sold_amount/tier1_sold_amount written -- none exists to
-- write. See gold_standard_ultraloop_audit rows (dispatch_id
-- 4c2cb537-516e-441e-b381-3f9a7d906ef6, letters B and I, both survived=true) for
-- the full adversarially-verified evidence trail.
--
-- Applied live via the Supabase Management API (direct psql/pooler access
-- unavailable in this sandbox -- password auth failure against both the pooler
-- and db.*.supabase.co direct host). This file is the durable record; the
-- UPDATE below is idempotent to re-run.
--
-- Verified live before: SELECT public.pencil_dod_evaluate_county('taylor')
--   I: {"pass":false,"detail":"card_complete=8 of 9","metric":88.9}
-- Verified live after (re-run post-application):
--   I: {"pass":false,"detail":"card_complete=8 of 9","metric":88.9}  -- unchanged, as expected (see above)
-- taylor: 7/10 -> 7/10 this session (no letter flipped; B/F reconfirmed blocked
-- with 3 new avenues ruled out, I gained a genuine sourced address/legal-desc
-- correction that does not move the metric).

UPDATE multi_county_auctions
SET property_address = '101 Buffalo Drive, Perry, FL 32348',
    city = 'Perry',
    zip = '32348',
    legal_description = 'Lot 101, Belair Manor Subdivision, an unrecorded subdivision of a portion of the E 1/2 of SW 1/4 of SW 1/4 of Section 26, Township 4 South, Range 7 East, Taylor County, Florida',
    latitude = NULL,
    longitude = NULL
WHERE lower(county) = 'taylor' AND case_number = '23-597 CA';
