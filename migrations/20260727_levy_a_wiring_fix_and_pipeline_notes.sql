-- GOLD STANDARD shard-6 (run6871), county=levy, criterion A wiring fix.
-- dispatch_id: 82fd00da-86e2-4a25-bd65-c778762256bd
-- date: 2026-07-27
--
-- CONTEXT:
--   levy is 9/10 — only A (dual-product coverage) failing: fc=0, td=29.
--   levyclerk.com genuinely has "no foreclosure sales available at this time".
--   This has been independently verified 5+ times across sessions (2026-07-10,
--   -11, -23, -27). A is an honest FAIL, not a scraper gap.
--
-- WIRING BUG FOUND AND FIXED (code change, not schema):
--   shard13-levy-daily-scraper.yml levy-taxsmart job was missing
--   SUPABASE_ACCESS_TOKEN from its env block. The scraper's _fc_upsert_sql()
--   uses the Management API SQL endpoint which requires SUPABASE_ACCESS_TOKEN.
--   Without it, any real FC cases found on levyclerk.com would log
--   "ERROR: FC cases found but SUPABASE_ACCESS_TOKEN not set" and silently
--   fail to persist — meaning criterion A could never be won even when real
--   foreclosure sales appear. Fixed in same commit as this migration.
--
-- SUPPLEMENTARY SOURCE ADDED:
--   floridapublicnotices.com probed for upcoming Levy FC notices.
--   Prior sessions found 1 Levy notice (Case 2025000075CAAXMX, sale 04/20/2026
--   — already past as of 07/27/2026). The new probe_floridapublicnotices_levy()
--   function filters to future-only sales and de-dupes against levyclerk.com.
--
-- KNOWN DEAD ENDS (do not re-investigate without new leads):
--   - levy.agverso.com: confirmed Levy County PUBLIC LIBRARY catalog (Auto-Graphics
--     OPAC), not court records. JSF/Angular SPA, no REST endpoint accessible
--     without headless browser.
--   - civitekflorida.com/ocrs/county/38: Levy County OCRS, JSF/PrimeFaces
--     session-token wall. Cannot scrape without browser automation. county ID=38.
--   - floridapublicnotices.com: monitored by scraper now (supplementary source).
--   - circuit8.org: procedural pages only, no case data.
--
-- SCHEMA CHANGE: update pipeline.counties notes for levy to document status.

UPDATE pipeline.counties
SET
  notes = 'Verified 2026-07-27 (dispatch 82fd00da/run6871, 5th independent check): levyclerk.com explicitly states "no foreclosure sales available at this time". Sources exhausted: (1) levyclerk.com/foreclosure-sales — primary, polled daily, returns 0 (honest); (2) floridapublicnotices.com — supplementary, monitored by scraper, last known Levy notice (2025000075CAAXMX) was future-dated 04/20/2026, now past; (3) civitekflorida.com/ocrs/county/38 — JSF/PrimeFaces session wall, requires headless browser unavailable in GHA; (4) levy.agverso.com — CONFIRMED library OPAC (Auto-Graphics SPA), not court records; (5) circuit8.org — procedural pages only. Wiring bug fixed 2026-07-27: SUPABASE_ACCESS_TOKEN added to levy-taxsmart GHA job so FC cases persist when they appear. A will resolve naturally when a real sale is scheduled. Do not re-investigate dead ends 3-5 without a new lead or browser automation.',
  pipeline_health = 'healthy',
  updated_at = NOW()
WHERE lower(county_slug) = 'levy';

-- Verify the update applied (informational — run manually to confirm)
-- SELECT county_slug, pipeline_health, notes FROM pipeline.counties WHERE lower(county_slug)='levy';
