-- SHARD-8 Gold Standard: Gulf County — parcel_id fabrication purge
-- county: gulf | letters touched: E (honest regression from ghost-success)
--
-- Context:
--   Baseline audit found 3 of 5 gulf multi_county_auctions rows with
--   fabricated-looking parcel_id placeholders:
--     - 237fb61f-c945-4e72-9fd5-179978d9b1bc: parcel_id = 'GULF-PA-000060CAAXMX-02'
--     - 760b807c-8b7f-4e92-b6cb-7bdc5f840672: parcel_id = 'Property Appraiser'
--     - ab84aca0-37c8-4c61-86c2-67d697c07560: parcel_id = 'GULF-PA-000072CAAXMX-01'
--
--   Verified live (2026-07-10) by fetching the actual gulf.realforeclose.com
--   auction-detail page for AID=1501873 (row 237fb61f): the page returned is a
--   RealAuction splash/login-gate page, not an authenticated detail page. The
--   HTML contains an external-links list with the literal anchor text
--   '<span class="LN_MT">Property Appraiser</span>' — this is the exact string
--   that was scraped into parcel_id for row 760b807c. It is a UI link label,
--   not a parcel number. The confirmed fabrication:
--     'Property Appraiser'            -> scraped link-anchor text, not data
--     'GULF-PA-000060CAAXMX-02'       -> synthetic, derived from case_number
--     'GULF-PA-000072CAAXMX-01'       -> synthetic, derived from case_number
--
--   Cross-check: gulf's two legitimate rows use Gulf County's real folio
--   format (5digit-dash-3digit-letter: '06051-008R', '06248-410R'), which is
--   structurally distinct from the 'GULF-PA-...' synthetic strings and from
--   neighboring panhandle counties' section-township-range formats
--   (confirmed via live query against calhoun/franklin multi_county_auctions
--   for comparison). This confirms the two are real and the three are not.
--
--   Live parcel lookup was attempted (gulfpa.com, qpublic.net,
--   gulfcountypropertyappraiser.org) to replace the placeholders with real
--   folio numbers instead of nulling. gulfpa.com and qpublic.net are
--   Cloudflare-blocked (403) from this environment. The two affected rows
--   with no case-specific street address ("Address On File...") cannot be
--   looked up by address/owner on gulfcountypropertyappraiser.org (which
--   returned HTTP 200) because no real address or owner name exists in our
--   DB for these rows. Gulf's official case-record search
--   (civitekflorida.com/ocrs/county/23/) is public-tier accessible but is a
--   JS/session-driven multi-step search form, not fetchable via a single
--   HTTP GET within this bounded pass. Verification-by-replacement was not
--   achievable live within budget -> nulling was chosen over inventing a
--   value, per the fail-loud invariant.
--
-- Effect: E (parcel_linked) drops from 5/5 (100%, ghost-success) to 2/5 (40%,
-- honest). This is a correct regression, not a bug — ULTRALOOP's explicit
-- purpose is to catch exactly this ghost-success pattern.
--
-- B/F: untouched. Correctly FAIL/null (zero real closed/sold gulf auctions,
-- per the 2026-07-10 fabrication purge documented in
-- scripts/shard7_gulf_bf_outcomes.py). Not touched by this migration.
--
-- H: untouched (last_seen_at intentionally NOT bumped — see session report:
-- root cause is a stub parser in scripts/cairn_multi_county_scraper.py
-- ('custom_clerk' -> parse_custom_clerk always returns probe_only), not a
-- fixable-by-SQL freshness problem. Bumping last_seen_at without a real
-- re-scrape would repeat the exact ghost-success pattern already reverted
-- for gulf on 2026-07-05 and 2026-06-19 (see shard5-daily-scraper.yml
-- comments).

BEGIN;

UPDATE public.multi_county_auctions
SET parcel_id = NULL
WHERE county = 'gulf'
  AND id IN (
    '237fb61f-c945-4e72-9fd5-179978d9b1bc',
    '760b807c-8b7f-4e92-b6cb-7bdc5f840672',
    'ab84aca0-37c8-4c61-86c2-67d697c07560'
  )
  AND parcel_id IN (
    'GULF-PA-000060CAAXMX-02',
    'Property Appraiser',
    'GULF-PA-000072CAAXMX-01'
  );

COMMIT;

-- Verification:
-- SELECT id, case_number, parcel_id FROM public.multi_county_auctions
-- WHERE county = 'gulf' ORDER BY id;
-- Expect: 3 rows with parcel_id IS NULL, 2 rows retain real folio-format IDs
-- ('06051-008R', '06248-410R').
