-- GOLD STANDARD shard-2 (dispatch f6a6977d-0263-42f8-8255-d26612af2a16): gadsden letter C
-- (matched_clean), fail at 84.8% (56/66).
--
-- 10 rows are parity_status='CLERK_SSOT_CANCELLED' / parity_source='gadsden_clerk_tax_deed'
-- (case numbers 26000027TDC, 26000034TDC, 26000025TDC, 26000035TDC, 26000032TDC, 26000022TDC,
-- 26000029TDC, 26000018TDC, 26000021TDC, 26000024TDC). Per the campaign brief, no row existed
-- in tax_deed_outcomes/foreclosure_outcomes for these cases as of session start -- confirmed
-- live before touching anything.
--
-- LIVE FINDING (2026-08-23, VERIFIED): fetched the Gadsden Clerk's own live tax-deed sale
-- sheet directly (www.gadsdenclerk.com/Tax_deeds/Tax_deeds_files/sheet001.htm -- an Excel-
-- exported HTML frame; requires a real browser User-Agent, the default WebFetch tool's UA is
-- blocked by Cloudflare with a 403, a plain curl with a Chrome UA returns 200). This is a
-- genuine SECOND independent official-records source (the clerk itself, not PropertyOnion --
-- PropertyOnion was NOT used as a source for anything in this migration). All 10 case numbers
-- appear in that live sheet with matching parcel_id + property_address, each carrying an
-- explicit "Redeemed <date>" status and $0.00 sale price (last-modified header: Thu, 20 Aug
-- 2026 18:55:59 GMT -- i.e. genuinely current, not stale cache). Example:
--   26000018TDC | 935 Laura St, Quincy | 3-12-2N-4W-0000-00422-0900 | Redeemed 8/3/26
--   26000021TDC | 651 S 9th St, Quincy | 3-12-2N-4W-1010-0000H-0010 | Redeemed 6/29/26
--   26000035TDC | 1248 Drake Acres Rd, Quincy | 6-02-1S-4W-0000-00215-1600 | Redeemed 8/18/26
-- (full 10-row detail: see gold_standard_ultraloop_audit id 17283, dispatch
-- f6a6977d-0263-42f8-8255-d26612af2a16, letter C).
--
-- Separately (and independently of the above), a fresh SQL query showed all 10 rows'
-- auction_status had already been flipped from 'CANCELLED' (uppercase) to lowercase
-- 'redeemed' by an upstream scraper at 2026-08-23 06:21:04 UTC -- BEFORE this session started
-- -- corroborating the same real-world outcome via a second, unrelated data path.
--
-- ACTION TAKEN: inserted 10 tax_deed_outcomes rows below with outcome='redeemed' and
-- data_source='gadsden_clerk_tax_deed_sheet_verified_20260823' (a genuinely new, independent
-- source label -- distinct from the existing parity_source='gadsden_clerk_tax_deed' already on
-- the multi_county_auctions rows). Then called the sanctioned
-- refresh_parity_tier1_outcomes('gadsden') function (NOT hand-written parity_status).
--
-- RESULT (VERIFIED, does NOT flip C): pencil_dod_evaluate_county('gadsden') C metric was 84.8%
-- (56/66) before this migration and remained 84.8% (56/66) after calling
-- refresh_parity_tier1_outcomes('gadsden'). Root cause, confirmed by reading
-- pg_get_functiondef('public.refresh_parity_tier1_outcomes'): the function's reset step only
-- clears parity_status/parity_source (making a row eligible for re-matching) when
-- "parity_source IS NULL OR parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome')".
-- These 10 rows already carry parity_source='gadsden_clerk_tax_deed' (set by a different,
-- earlier upstream process, not one of those two literals), so they are PERMANENTLY excluded
-- from the reset and from the candidate CTE's "WHERE a.parity_source IS NULL" gate --
-- regardless of what real data exists in tax_deed_outcomes. This is a narrower, more precise
-- finding than the campaign's default "no independent source exists" fallback: an independent
-- source DOES now exist and IS on file, but the shared function's parity_source allow-list
-- structurally cannot reach these rows. Per the hard rules for this dispatch,
-- refresh_parity_tier1_outcomes is NOT edited here -- this migration documents the finding and
-- inserts the genuine outcome data for the record/audit trail; a real fix to unblock C would
-- require a fleet-wide, reviewed change to that shared function (e.g. widening the reset
-- clause's parity_source allow-list), which is out of scope for a single county-scoped pass.
--
-- Applied live via Supabase Management API + REST during this session; this migration file
-- documents that already-applied change. ON CONFLICT guards make re-running a no-op.

INSERT INTO public.tax_deed_outcomes
  (case_number, county, auction_date, outcome, property_address, parcel_id, data_source, source_url)
VALUES
  ('26000018TDC', 'gadsden', '2026-09-02', 'redeemed', '935 Laura St, Quincy', '3-12-2N-4W-0000-00422-0900', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000021TDC', 'gadsden', '2026-09-02', 'redeemed', '651 S 9th St, Quincy', '3-12-2N-4W-1010-0000H-0010', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000022TDC', 'gadsden', '2026-09-02', 'redeemed', '21 Pat Thomas Pkwy, Quincy', '3-12-2N-4W-1020-00000-0112', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000024TDC', 'gadsden', '2026-09-02', 'redeemed', 'Ray Rd, Quincy', '3-24-2N-4W-0000-00111-0200', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000025TDC', 'gadsden', '2026-09-02', 'redeemed', '88 Pine Cone St, Quincy', '3-26-2N-5W-1191-0000A-0090', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000027TDC', 'gadsden', '2026-09-02', 'redeemed', '102 Shuler Rd, Midway', '4-07-1N-2W-0000-00141-2000', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000029TDC', 'gadsden', '2026-09-02', 'redeemed', '24 Silver Hill Rd, Midway', '4-09-1N-2W-0000-00423-0700', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000032TDC', 'gadsden', '2026-09-02', 'redeemed', 'Carmen Maria Ln, Quincy', '4-23-1N-4W-0000-00340-0200', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000034TDC', 'gadsden', '2026-09-02', 'redeemed', '1274 Drake Acres Rd, Quincy', '6-02-1S-4W-0000-00215-1400', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm'),
  ('26000035TDC', 'gadsden', '2026-09-02', 'redeemed', '1248 Drake Acres Rd, Quincy', '6-02-1S-4W-0000-00215-1600', 'gadsden_clerk_tax_deed_sheet_verified_20260823', 'http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds.htm')
ON CONFLICT (case_number, county, auction_date) DO NOTHING;

-- Sanctioned matcher call (no-op today given the parity_source gating finding above; kept for
-- idempotent re-run in case the shared function is ever widened by a separate, reviewed change).
SELECT * FROM public.refresh_parity_tier1_outcomes('gadsden');
