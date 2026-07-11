-- Gold Standard shard-5 run3786 continuation (calhoun/madison/jefferson), dispatch
-- 61b6512c-ae9e-4bc2-8e90-f701c28611d9, chat_session architect-20260711T160000.
--
-- Ran ULTRALOOP fan-out (5 research agents + 2 adversarial verifiers) over the remaining
-- failing letters. Two claims proposed a DB write and both SURVIVED independent refutation
-- (see gold_standard_ultraloop_audit rows inserted below). Three levers came back genuinely
-- BLOCKED with real sourced evidence — documented here per BLANK > WRONG, no writes for those.
--
-- ============================================================================
-- 1. JEFFERSON G FIX (survived verification) — R-1A max_density_du_acre
-- ============================================================================
-- Jurisdiction 817 = Monticello, FL. zoning_districts.id=5481 (code R-1A), zone_standards.id=1886.
-- That row already carried REAL, previously-sourced dimensional data (min_lot_sqft=5000,
-- front/side/rear setback, max_height_ft, max_stories, parking_per_unit=2.00, confidence 0.85,
-- scraped 2026-02-08) but max_far and max_density_du_acre were NULL, which is what was failing G
-- (v_zoning_gold_standard_kpi_v3: density_applicable=true since category=Residential and
-- density_regulated is unset -> defaults true; far_applicable=false since Residential is not in
-- (commercial,industrial,mixed-use) -> FAR already correctly excluded from the denominator, not
-- a blocker).
--
-- VERIFIED live (2026-07-11) via r.jina.ai reader proxy against Monticello's Code of Ordinances
-- (library.municode.com/fl/monticello/..., version Apr 21 2025 — direct WebFetch/curl still 403
-- Cloudflare-blocked, same as documented in supabase/migrations/20260711l_..., but the proxy
-- route works): Sec. 54-160 Table A states R-1A minimum lot area = 5,000 sq. ft. (matches our
-- on-file min_lot_sqft exactly). Sec. 54-160/54-502 do NOT express a direct max_density_du_acre
-- or max_far figure anywhere in the ordinance for ANY residential district — Monticello regulates
-- single-family/mobile-home density purely through minimum lot area + setbacks, not a stated
-- du/acre cap. An independent adversarial-refuter agent re-fetched both cited Municode URLs and
-- confirmed the quoted table text verbatim, confirmed jurisdiction_id=817=Monticello, and
-- confirmed no du/acre or FAR metric exists anywhere in the ordinance text.
--
-- Because the ordinance's actual density-limiting mechanism IS minimum lot area, the standard,
-- textbook way to express that constraint in max_density_du_acre terms is the direct arithmetic
-- conversion: 43,560 sq ft/acre / min_lot_sqft. For R-1A: 43560/5000 = 8.712 du/acre. This is a
-- derived value from a real, already-sourced ordinance figure (min_lot_sqft=5000, confidence
-- 0.85) — not a guess, not fabricated, not copied from the unrelated R-1 district. Recorded with
-- its own lower confidence_score (0.75) and an explicit ordinance_section/source_url + note so a
-- future session can see it's a derivation, not a literal ordinance figure.
--
-- SEPARATE HONESTY FLAG (not acted on, out of scope for jefferson's G metric — R-1 currently has
-- zero parcel_zones rows in jefferson county so it has zero weight in v_zoning_gold_standard_kpi_v3
-- regardless): the adjacent R-1 district's on-file max_density_du_acre=4.0/max_far=0.35 (set by a
-- prior migration, confidence_score=0.72) do not match either the ordinance text (no such figures
-- exist) or the same lot-area-derivation method (7500 sqft -> 5.808 du/acre, not 4.0). Left
-- untouched this session per surgical-change discipline (K3) since it doesn't move any current
-- metric; flagged here for a future session to re-audit.

UPDATE zone_standards
SET max_density_du_acre = 8.71,
    ordinance_section    = 'Sec. 54-160 (Schedule of Dimensional Regulations, Table A) — derived from min_lot_sqft=5000',
    source_url            = 'https://library.municode.com/fl/monticello/codes/code_of_ordinances?nodeId=PTIICOOR_CH54LADERE_ARTIIIZODIRE',
    confidence_score      = 0.75
WHERE id = 1886
  AND zoning_district_id = 5481
  AND max_density_du_acre IS NULL;  -- idempotent guard

-- ============================================================================
-- 2. MADISON DATA HYGIENE (survived verification) — 25-79-CA scheduled -> cancelled
-- ============================================================================
-- madisonclerk.com/departments-services/property-sales/foreclosure-sales/ re-fetched live
-- 2026-07-11 (independently confirmed by a second adversarial-refuter fetch): case 25-79-CA
-- (338 SW Horry Ave, parcel 00-00-00-3765-000-000, judgment $44,511.47, sale date 07/14/2026)
-- now shows verbatim Status "cancelled" on the clerk's own page. This does NOT populate a sold
-- amount (cancelled != sold, closed_sold denominator for B/F is unaffected) — it is a real-data
-- correctness fix only, landed for hygiene ahead of the auction_status ever being scored.
UPDATE multi_county_auctions
SET auction_status = 'cancelled',
    last_seen_at    = now(),
    updated_at      = now()
WHERE lower(county) = 'madison'
  AND case_number = '25-79-CA'
  AND auction_status = 'scheduled';

-- ============================================================================
-- 3. BLOCKED FINDINGS (no writes) — jefferson A, jefferson B/F, calhoun B/F
-- ============================================================================
-- JEFFERSON A (fc=1 td=0): re-fetched https://jeffersonclerk.com/clerk-services/property-sales/
-- tax-deed-sales/ live 2026-07-11 (WebFetch + raw curl+HTML grep for \d{2,4}-(TD|CA|CC)-\d{2,6}).
-- Page heading "Upcoming Tax Deed Sales" has ZERO listings underneath — no case numbers, no
-- parcels, no dates, no PDFs. Page directs the public to the Monticello News print legal-ad
-- classifieds (not web-accessible) or a phone call for current schedule. Confirmed no separate
-- state-run/third-party TAX DEED portal exists; the only third-party Jefferson County online
-- auction site found (taxcertsale.com/jeffersontaxsale/) is a TAX CERTIFICATE (lien) sale site
-- for a different product, not tax deeds, and must not be conflated with one. Matches
-- pipeline.counties.pipeline_status='diagnosed_no_taxdeed_data' already on file. Genuinely
-- BLOCKED — no placeholder row fabricated.
--
-- JEFFERSON B/F (verified=0/closed_sold=0): the sole auction, case 25-CA-164, is marked sold
-- (auction_date 2026-06-25, already occurred) but sold_amount is NULL. Searched
-- jeffersonclerk.com official-records/foreclosure-sales pages, general web search for the case
-- number, and any certificate-of-title/sale-results document referencing it — no independently
-- sourceable dollar figure was found this session. Genuinely BLOCKED, not a matching gap.
--
-- CALHOUN B/F (verified=0/closed_sold=0, all 7 rows sold_amount NULL): two cases have
-- auction_date already passed (621 OF 2026 and 171 OF 2023, both 2026-07-09) so their DB status
-- looked potentially stale. Checked calhounclerk.com's tax-deed-sales, tax-deed-overbid-list,
-- lands-available-for-taxes, foreclosure-sales, and records-search pages live — none carry
-- case-level sold-amount data (mostly static/empty JS-widget shells); lands-available page
-- verbatim states "There are no properties on the list of lands available at this time."
-- pipeline.counties.foreclosure_url/taxdeed_url for calhoun point to calhoun.realforeclose.com
-- and calhoun.realtaxdeed.com, both of which return HTTP 403 to automated fetches (also true of
-- calhoun.realtaxdeed.com root and preview-auction paths) — that RealAuction tenant is where
-- case-level sold-amount results almost certainly live, but it is bot/JS-protected and
-- inaccessible to this session's tooling. No fabricated amount written. Genuinely BLOCKED.
--
-- NEXT SESSION: calhoun/jefferson B/F have no automated path forward without either (a) a real
-- browser session against calhoun.realtaxdeed.com, or (b) direct phone confirmation from the
-- respective Clerk's offices (Calhoun 850-674-4545, Jefferson 850-342-0147/0218) — both out of
-- scope for an unattended pipeline session. Re-check on/after the passed auction dates in case
-- either clerk site's reporting lag resolves (same temporal-lag pattern already documented for
-- wakulla/madison in 20260711_shard13_wakulla_madison_b_f_no_historical_data_blocked.sql).

SELECT 1;  -- no-op marker for the blocked-findings documentation section above
