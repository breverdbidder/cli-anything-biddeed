-- social_content_queue.value_source (issue #19129, AMEND #19128)
--
-- Paper-equity banners compute value_estimate as the first non-null of
-- market_value, po_market_value, po_avm_value, assessed_value. This column
-- persists which one was actually used per row so copy/audits can tell
-- "market value" apart from "county assessed value" -- the two must never
-- be conflated per #19129 item 2. Nullable and additive: only
-- source_type='property_spotlight' rows populate it; county_snapshot rows
-- (no per-property equity claim) leave it null, zero behavior change.
ALTER TABLE public.social_content_queue
  ADD COLUMN IF NOT EXISTS value_source text;

COMMENT ON COLUMN public.social_content_queue.value_source IS
  'Which multi_county_auctions column fed value_estimate for this banner''s equity claim: market_value | po_market_value | po_avm_value | assessed_value. Null for rows with no per-property equity claim (e.g. county_snapshot).';
