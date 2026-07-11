-- GOLD STANDARD CAMPAIGN shard-7, run 3713, county: bradford
-- Purpose: C/D parity backfill via genuinely independent tier1 corroboration.
--
-- Context: Bradford County is a clerk-only county (pipeline.counties.foreclosure_platform
-- = 'clerk_html', bradfordclerk.com) -- NOT a RealAuction county. Verified live 2026-07-11:
-- bradford.realforeclose.com and bradford.realtaxdeed.com both DNS-resolve to RealAuction's
-- shared production ELB but the PREVIEW request 302-redirects OFF-HOST to the generic
-- www.realauction.com marketing homepage (identical off-host-redirect signature already
-- documented for desoto in scripts/cd_litmus_v2_realauction_harvest.py) -- i.e. Bradford is
-- not actually live-hosted on RealAuction, confirming pipeline.counties is correct and the
-- RealAuction AJAX litmus harvester does not apply here.
--
-- Per the campaign brief's own fallback guidance for clerk-only counties, this migration
-- uses the pre-existing clerk-records supplementary litmus pattern (same tier1:bctelegraph_*
-- parity_source convention already used for case 25000457CAAXMX in a prior session) to
-- independently cross-check two more of Bradford's five auction rows against verbatim
-- court-published legal notices in the Bradford County Telegraph (bctelegraph.com), an
-- independent third-party publisher of court-mandated legal notices -- NOT PropertyOnion,
-- NOT our own scrape.
--
-- Verified live 2026-07-11 (WebSearch + direct curl of bctelegraph.com, both 200 OK,
-- Cloudflare does not block this domain unlike bradfordclerk.com itself which 403s from
-- this sandbox):
--   - https://bctelegraph.com/legal-notices-for-2-12-26/ and .../legal-notices-for-2-5-26/
--     both contain, verbatim: "IN THE CIRCUIT COURT OF THE EIGHTH JUDICIAL CIRCUIT IN AND
--     FOR BRADFORD COUNTY, FLORIDA / CASE NO. 25000439CAAXMX / PLANET HOME LENDING, LLC,
--     Plaintiff, vs. JONATTAN H. BARRANCO PINTO, et. al., Defendant(s)." -- exact case
--     number match against our row, no discrepancy found -> matched_clean.
--   - WebSearch corroboration for case 24000431CAAXMX: "Case No. 2024000431CAAXMX involves
--     PROVIDENT FUNDING ASSOCIATES, L.P. as Plaintiff and PAUL MCDAVID ... in Bradford
--     County, Florida ... Circuit Court of the 8th Judicial Circuit ... published in the
--     Bradford County Telegraph in December 2025" -- exact case number match (Florida's
--     standard leading-zero-drop convention: 2024000431 == 24000431), no discrepancy
--     found -> matched_clean.
--
-- NOT touched (honest residuals, not fabricated):
--   - case 25000487CAAXMX: no independent corroboration found within this session's
--     budget (checked multiple bctelegraph.com weekly issues + targeted WebSearch,
--     no hit). Left as parity_status=NULL/unmeasured -- correctly NOT a match yet,
--     not assumed to fail.
--   - tax deed 04-2026-TD-002: independently corroborated for its PARCEL NUMBER only
--     (bctelegraph.com/legal-notices-for-6-18-26/ verbatim: "Parcel Number: 00077-0-00401
--     ... Case Number: 04-2026-TD-002" -- exact match against our row) but this is a
--     tax-deed notice, not a foreclosure-sale-calendar count-parity case, so it is NOT
--     added to parity_status/parity_source here to avoid conflating two different litmus
--     mechanisms (C/D is a foreclosure-sale-calendar construct per pencil_dod_evaluate_county;
--     this parcel-number corroboration is documented here for the record and to support a
--     future E backfill attempt, not written to parity_status).
--
-- This migration documents an UPDATE that was applied directly via the Supabase
-- Management API (SQL passthrough) per shard-7 session instructions; included here
-- for the historical record and to allow reapplication/audit.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:bctelegraph_clerknotice_live_20260711',
    updated_at = now()
WHERE lower(county) = 'bradford'
  AND case_number IN ('25000439CAAXMX', '24000431CAAXMX');
