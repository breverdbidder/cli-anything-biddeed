-- Gold Standard shard-3 (run3645, dispatch fae25c74-55dd-4ef0-840c-569cbf825b29): desoto
-- real baseline data, replacing the wholesale-fabricated dataset purged earlier the same
-- day (migrations/20260710_gold_standard_shard2_desoto_fabrication_purge.sql). That
-- migration's own comment said: "pipeline.counties already has real desoto.realforeclose.com
-- / desoto.realtaxdeed.com config (untouched); a future session must scrape it for real,
-- not re-bootstrap." This migration is that follow-up.
--
-- FINDING 1 (VERIFIED live 2026-07-10): desoto.realforeclose.com and desoto.realtaxdeed.com
-- both HTTP 302-redirect to the generic www.realauction.com marketing splash for every
-- date tested (90-day forward AJAX scan, zero live items) -- no RealAuction tenant is
-- actually provisioned for DeSoto despite pipeline.counties listing those platforms.
-- desoto.floridabidder.com does not resolve (DNS NXDOMAIN). The real live source is the
-- DeSoto Clerk of Court's own website, which publishes periodically-updated PDF sale
-- lists: https://www.desotoclerk.com/public-sales/foreclosures/ (case#, plaintiff/
-- defendant, judgment amount, property address -- no parcel ID column) and
-- https://www.desotoclerk.com/public-sales/tax-deeds/ (tax-deed#, parcel_id, address,
-- starting bid).
--
-- FINDING 2: both live PDFs were fetched and read directly this session (HTTP headers and
-- full content, not trusted from a prior claim). 6 real foreclosure cases (Jul-Sep 2026)
-- and 2 real tax-deed cases (Jul 2026) were captured, each cross-checked line-by-line
-- against the source PDF, with zero collisions against the (empty, post-purge) desoto
-- rows. An independent adversarial-refuter subagent reproduced the same PDF fetch/content
-- itself before this was applied.
--
-- Per the same-day STANDING AUTHORIZATION precedent already live for wakulla/union in this
-- shard (a county's own sole authoritative clerk source IS the tier1 litmus when no
-- second independent online tenant exists), the parity UPDATE below stamps these 8 rows
-- matched_clean/tier1:desoto_clerk_live_20260710.
--
-- E (parcel linkage) is NOT resolved for the 6 foreclosure rows -- the clerk's foreclosure
-- PDF has no parcel-ID column at all (a source-document gap, not a scraper failure); only
-- the 2 tax-deed rows carry a real parcel_id (from the tax-deed PDF, which does list one).
-- A future session should query the DeSoto County Property Appraiser by the 6 street
-- addresses to backfill parcel_id honestly, one address at a time.
--
-- pipeline.counties.notes updated to document the real mechanism (clerk PDF, not
-- RealAuction) so a future session doesn't re-attempt the dead RealAuction path.
--
-- Verified live result (pencil_dod_evaluate_county('desoto'), before -> after):
--   0/10 (auctions_total=0) -> 4/10 (A, C, D, H pass; B, E, F, G, I, J correctly still
--   fail on genuine gaps -- no outcomes yet since these are mostly future sale dates, no
--   foreclosure parcel_id, no zoning coverage, no deal thesis).
-- ============================================================================

INSERT INTO public.multi_county_auctions (county, state, sale_type, auction_date, case_number, judgment_amount, plaintiff, property_address, data_source, source_url, clerk_url, provenance, scraped_at) VALUES
('desoto','FL','foreclosure','2026-07-02','25CA638',186726.81,'SCOTT KUHN','6098 NE THOMAS DR, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/06/6.26Foreclosure.pdf','https://www.desotoclerk.com/public-sales/foreclosures/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','foreclosure','2026-07-02','25CA632',300719.93,'ALTO CAPITAL HOLDINGS','204 N MONROE AVE, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/06/6.26Foreclosure.pdf','https://www.desotoclerk.com/public-sales/foreclosures/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','foreclosure','2026-08-04','25CA317',177277.52,'EQUITY TRUST COMPANY','1549 SW HARLEM CIR, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/06/6.26Foreclosure.pdf','https://www.desotoclerk.com/public-sales/foreclosures/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','foreclosure','2026-08-04','23CA362',335609.88,'EQUITY PRIME MORT','1549 SW WISTERIA ST, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/06/6.26Foreclosure.pdf','https://www.desotoclerk.com/public-sales/foreclosures/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','foreclosure','2026-08-18','24CA502',340911.22,'TH MSR HOLDINGS LLC','7860 SW LIVERPOOL RD, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/06/6.26Foreclosure.pdf','https://www.desotoclerk.com/public-sales/foreclosures/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','foreclosure','2026-09-01','25CA433',250703.39,'US BANK','6098 NE THOMAS DR, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/06/6.26Foreclosure.pdf','https://www.desotoclerk.com/public-sales/foreclosures/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','tax_deed','2026-07-22','26-04-TD',NULL,NULL,'SW SEABOARD AVE, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/07/7.1_TAX-DEED-WEBSITE.pdf','https://www.desotoclerk.com/public-sales/tax-deeds/','clerk_pdf:desoto_20260710',now()),
('desoto','FL','tax_deed','2026-07-29','26-06-TD',NULL,NULL,'3785 NE BONANZA PARK AVE, ARCADIA FL','desoto_clerk_live','https://www.desotoclerk.com/wp-content/uploads/2026/07/7.1_TAX-DEED-WEBSITE.pdf','https://www.desotoclerk.com/public-sales/tax-deeds/','clerk_pdf:desoto_20260710',now());

UPDATE public.multi_county_auctions SET parcel_id='02-38-24-0000-0050-0000', opening_bid=1940.32 WHERE county='desoto' AND case_number='26-04-TD' AND data_source='desoto_clerk_live';
UPDATE public.multi_county_auctions SET parcel_id='20-37-25-00529-0000-015A', opening_bid=2698.98 WHERE county='desoto' AND case_number='26-06-TD' AND data_source='desoto_clerk_live';

UPDATE public.multi_county_auctions SET parity_status='matched_clean', parity_source='tier1:desoto_clerk_live_20260710', parity_checked_at=now(), updated_at=now()
WHERE lower(county)='desoto' AND data_source='desoto_clerk_live';

UPDATE pipeline.counties SET notes = notes || ' | 2026-07-10 gold-standard-shard3-desoto (run3645): RE-VERIFIED desoto.realforeclose.com and desoto.realtaxdeed.com both HTTP 302-redirect to www.realauction.com generic marketing splash for every date tested -- no RealAuction tenant provisioned for DeSoto. desoto.floridabidder.com does not resolve (DNS NXDOMAIN). Real live source is the Clerk of Court''s own website: www.desotoclerk.com/public-sales/foreclosures/ and /public-sales/tax-deeds/ link to periodically-updated clerk-authored PDFs (case#, plaintiff/defendant, judgment amount, address for foreclosure; tax-deed#, parcel_id, address, starting bid for tax deed). Verified live 2026-07-10: 6 real foreclosure cases (Jul-Sep 2026) + 2 real tax-deed cases (Jul 2026) captured, zero collisions with existing DB rows, A/C/D/H now PASS. NEXT: no API/calendar endpoint found -- future scrapes must re-fetch and diff these two PDF URLs (or their successor filenames once the clerk rotates them) periodically; no automated discovery of the next PDF filename is safe without re-checking the public-sales pages first. Foreclosure rows still lack parcel_id (E gap, source PDF has no parcel column) -- needs DeSoto Property Appraiser address lookup next session.', last_scrape_at = now()
WHERE county_slug = 'desoto';
