-- SHARD-3 continuation: bradford — real foreclosure lane ingestion, tax-deed lane confirmed genuinely empty
-- dispatch_id: 09e317ef-d722-4e29-a310-77593b6e8658
-- Session: architect-20260703T080000 (loop run 2550)
--
-- PRIOR STATE (verified live before this migration): bradford A=FAIL (fc=0 td=0), pipeline.counties
-- row auto-seeded 2026-05-20 from realauction_subdomains with all platform/url columns NULL,
-- pipeline_status='pending'. Two prior sessions this same dispatch_id (see
-- 20260703_shard3_hamilton_ghost_success_revert_pasco_i_fix_bradford_discovery.sql and
-- 20260703_shard3_hamilton_real_taxdeed_ingestion_pasco_palmbeach_ceiling_confirmed.sql)
-- independently confirmed bradford.realforeclose.com and bradford.realtaxdeed.com both return
-- HTTP 403 to WebFetch and concluded "needs authenticated/headless-browser scraping, not
-- available in this sandbox (no firecrawl CLI/API key configured)".
--
-- NEW FINDING this session: a working `firecrawl` CLI (npx firecrawl-cli, no API key required --
-- free tier) is available in this sandbox and was NOT available/attempted in the prior two
-- passes. This unlocks real scraping bradford's actual sale-tracking mechanism. Root cause of
-- the 403s: bradford.realforeclose.com / bradford.realtaxdeed.com are NOT bradford's real
-- platform at all -- both subdomains merely redirect to RealAuction's generic parent marketing
-- site (confirmed: identical marketing-page content returned for both URLs, no bradford-specific
-- tenant). Bradford County is NOT a RealAuction client. Web search found the real source:
-- bradfordclerk.com/tax-deeds-and-foreclosure-sales/ -- Bradford runs IN-PERSON courthouse sales
-- only (945 N. Temple Ave., Starke, FL, 11:00am), the same operating pattern already documented
-- for Brevard foreclosures in the COUNTY EXCEPTIONS section of this campaign's brief.
--
-- That page links a Box.com folder "Tax Deed & Foreclosure Sale Lists" containing two live,
-- dated files, both fetched and verified this session:
--   1. "FORECLOSURE SALE LIST 6-25-2026.doc" (updated Jun 25 2026, current) -- an RTF export
--      from the Clerk's own "Mortgage Foreclosure Report" system listing 4 real, currently
--      scheduled foreclosure sales with case number / judgment amount / parties / sale date.
--   2. "NO SALES001.pdf" (Dec 18 2025) -- a one-line clerk notice: "WE HAVE NO TAX DEED SALES
--      SCHEDULED AT THIS TIME." This is a real, verified NEGATIVE finding, not a scrape gap:
--      Bradford genuinely has zero tax deed sales on the calendar right now. Per canon, A
--      requires fc>0 AND td>0, so A remains FAIL today even after this fix -- that is the
--      honest, correct outcome, not a shortfall in this migration.
--
-- ACTION TAKEN (live, this session, via Supabase Management API -- curl, not python urllib;
-- urllib hits Cloudflare error 1010 browser-integrity block on this endpoint, curl does not,
-- confirmed by the prior session's same finding):
--   1. UPDATE pipeline.counties: set foreclosure_platform/url and taxdeed_platform/url to the
--      real clerk-html source (bradfordclerk.com), pipeline_status='partial' (foreclosure lane
--      real+ingested, tax-deed lane real+verified-empty), notes documenting the verified-zero
--      tax-deed finding with today's date so no future session re-burns time rediscovering the
--      same 403s on the wrong (non-existent) RealAuction tenant.
--   2. INSERT 4 rows into multi_county_auctions: county='bradford', sale_type='foreclosure',
--      case_number/judgment_amount/plaintiff/auction_date taken verbatim from the RTF list,
--      auction_status='upcoming' (all 4 sale dates are Jul-Aug 2026, future relative to today
--      2026-07-03), auction_venue='in_person' (chk_auction_venue only allows 'online'/'in_person';
--      the courthouse street address is documented here in this comment, not a table column),
--      data_source='clerk_fc:bradfordclerk.com/tax-deeds-and-foreclosure-sales/',
--      provenance='live_firecrawl_20260703_verified_real'. ON CONFLICT (county,case_number,
--      sale_type) DO NOTHING (idempotent rerun safety). Venue: Bradford County Courthouse,
--      945 N. Temple Ave., Starke, FL 32091, sales begin 11:00am.
--
-- VERIFIED via pencil_dod_evaluate_county('bradford') before/after -- see closing session
-- summary for the pasted before/after JSON.
--
-- NOT DONE / left honestly open for the next session:
--   - Hamilton I/J enrichment lead investigated (hamiltonpa.com resolves fine via firecrawl,
--     unlike the prior 403 finding -- it fronts a Schneider Corp "Beacon" GIS portal, parcel
--     report pages ARE fetchable, e.g. beacon.schneidercorp.com/.../PageTypeID=4&PageID=6411&
--     KeyValue=3139-160 returns real land-value data). NOT pursued further this session: the
--     one parcel test-fetched (3139-160, a 2.2-acre rural cert parcel) has a genuinely BLANK
--     "Location Address" field -- real vacant land with no situs address, not a scrape gap.
--     Since I's card_complete requires property_address IS NOT NULL among other fields, several
--     of hamilton's 10 remaining cert parcels may be structurally capped the same way. Flagging
--     for a session that fetches all 10 and checks how many actually have a real address before
--     committing to building the enrichment pipeline (avoid low-yield speculative build, Karpathy
--     K2/K3).
--   - Bradford tax-deed lane: genuinely empty right now, not a bug. Re-check on a future session
--     (the clerk's Box folder is the canonical live source going forward) rather than re-diagnosing
--     the RealAuction 403s again.

BEGIN;

UPDATE pipeline.counties
SET foreclosure_platform = 'clerk_html',
    foreclosure_url = 'https://bradfordclerk.com/tax-deeds-and-foreclosure-sales/',
    taxdeed_platform = 'clerk_html',
    taxdeed_url = 'https://bradfordclerk.com/tax-deeds-and-foreclosure-sales/',
    pipeline_status = 'partial',
    pipeline_health = 'partial',
    notes = 'Verified live 2026-07-03 (shard3, dispatch 09e317ef): bradford.realforeclose.com / '
            || 'bradford.realtaxdeed.com are NOT bradford-specific -- both redirect to the '
            || 'RealAuction generic marketing site; bradford is not a RealAuction client. Real '
            || 'source is bradfordclerk.com/tax-deeds-and-foreclosure-sales/, in-person courthouse '
            || 'sales only (same pattern as Brevard foreclosures). Foreclosure list: Box.com folder '
            || 'linked from that page, "FORECLOSURE SALE LIST" doc, refreshed by clerk staff '
            || '(dated 2026-06-25 as of this check). Tax deed lane VERIFIED GENUINELY EMPTY via '
            || 'clerk PDF "WE HAVE NO TAX DEED SALES SCHEDULED AT THIS TIME" (dated 2025-12-18) -- '
            || 'not a scrape failure, A will legitimately stay FAIL until Bradford schedules a '
            || 'tax deed sale. Do not re-attempt the RealAuction subdomains.'
WHERE county_slug = 'bradford';

INSERT INTO multi_county_auctions
  (county, state, sale_type, case_number, judgment_amount, plaintiff, auction_date,
   auction_status, auction_venue, data_source, provenance)
VALUES
  ('bradford','FL','foreclosure','25000457CAAXMX',118078.88,'VYSTAR CREDIT UNION vs EBENAL, AMY R et al','2026-07-16',
   'upcoming','in_person',
   'clerk_fc:bradfordclerk.com/tax-deeds-and-foreclosure-sales/','live_firecrawl_20260703_verified_real'),
  ('bradford','FL','foreclosure','25000439CAAXMX',257526.86,'PLANET HOME LENDING, LLC vs BARRANCO PINTO, JONATTAN H et al','2026-08-13',
   'upcoming','in_person',
   'clerk_fc:bradfordclerk.com/tax-deeds-and-foreclosure-sales/','live_firecrawl_20260703_verified_real'),
  ('bradford','FL','foreclosure','25000487CAAXMX',163079.71,'LEMIRE, MICHAEL et al vs WILLIAMS, BILLY JOE et al','2026-08-13',
   'upcoming','in_person',
   'clerk_fc:bradfordclerk.com/tax-deeds-and-foreclosure-sales/','live_firecrawl_20260703_verified_real'),
  ('bradford','FL','foreclosure','24000431CAAXMX',323472.55,'PROVIDENT FUNDING ASSOCIATES LP vs MCDAVID, PAUL et al','2026-08-20',
   'upcoming','in_person',
   'clerk_fc:bradfordclerk.com/tax-deeds-and-foreclosure-sales/','live_firecrawl_20260703_verified_real')
ON CONFLICT (county, case_number, sale_type) DO NOTHING;

COMMIT;

-- Verification
SELECT public.pencil_dod_evaluate_county('bradford');
