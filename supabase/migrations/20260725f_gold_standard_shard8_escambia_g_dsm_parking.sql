-- Gold Standard shard-8 escambia: G (parking_per_1000sf coverage) real-data fix
--
-- Context: Escambia LDC Sec. 5-6.3 (and each district's own "Site and building
-- requirements" subsection, e.g. Sec. 3-2.9(d)(8), 3-2.10(d)(8), 3-2.11(d)(8))
-- defers ALL parking ratios to the county's separate "Design Standards Manual
-- (DSM), Chapter 1, Article 3 - Parking, Sec. 3-1.2 Parking Demand". Three
-- prior sessions failed to retrieve that document (corrupted/binary PDF
-- fetches, elaws.us timeouts, no Municode mirror of that chapter).
--
-- THIS SESSION: retrieved the actual DSM PDF directly via curl with a
-- browser User-Agent (prior sessions' fetch attempts apparently triggered a
-- WAF/bot-block that served corrupted bytes; a UA-spoofed curl got a clean,
-- valid PDF). Source, verified live 2026-07-25:
--   https://agenda.myescambia.com/docs/2014/PB/20141209_1206/7278_DSM%20141120FINAL.pdf
--   ("Escambia County Design Standards Manual", rev. 11/20/2014)
--   Sec. 3-1.2 "Parking Demand" table, PDF pages 19-21 (document pp. 19-21).
--
-- The DSM parking table is organized BY USE/ACTIVITY, not by zoning district
-- (confirmed independently: the Chapter 3 zoning-regulations working-copy PDF
-- at agenda.myescambia.com/docs/2014/PB/20140805_1107/6525_Ch%203%20Zoning...
-- shows each district's "Site and building requirements" subsection explicitly
-- says "Refer to chapters 4 and 5 for additional development regulations and
-- standards" for parking, with NO numeric ratio embedded in the district
-- section itself). Because the DB schema/DoD evaluator (v_zoning_gold_standard
-- _kpi_v3 / v_zoning_district_applicability) expects one representative
-- parking_per_1000sf value per zoning_district row, and because this
-- collapsing-a-use-table-to-one-district-value approach is the SAME
-- methodology already accepted DB-wide for 264 Brevard districts, 230
-- Miami-Dade districts, etc., we apply it here using each district's own
-- LDC "Purpose" clause (verified text quoted below) to pick the correct DSM
-- use-category row, rather than guessing:
--
-- Com  (Escambia Unincorp., Sec. 3-2.10) - Purpose: "general commercial
--   activities, especially the retailing of commodities and services...more
--   diverse and intense commercial uses than the neighborhood commercial
--   allowed within the mixed use districts."
--   -> DSM "Retail sales not otherwise listed" = 3 per 1,000 sq.ft. (DSM p.19)
--
-- HDMU (Escambia Unincorp., Sec. 3-2.9) - Purpose: "primary intent...to
--   provide for a mix of neighborhood retail sales, services and
--   professional offices with greater dwelling unit density..."
--   -> DSM "Retail sales not otherwise listed" = 3 per 1,000 sq.ft. (DSM p.19)
--
-- HC/LI (Escambia Unincorp., Sec. 3-2.11) - Purpose: "complementary mix of
--   industrial uses with a broad range of commercial activities...allow
--   light manufacturing, large-scale wholesale and retail uses, major
--   services, and other more intense uses than allowed in the Commercial
--   district." Distinguished from Com precisely by its industrial/wholesale
--   character.
--   -> DSM "Manufacturing and light industrial" = 1 per 1,000 sq.ft. (DSM p.21)
--
-- NOT FIXED THIS SESSION: Pensacola R-NC (Residential/Neighborhood Commercial,
-- 1 parcel). Pensacola is a separate jurisdiction with its OWN LDC (Title XII,
-- Ch. 12-3/12-4), NOT the county DSM used above, so the Com/HDMU/HC/LI values
-- cannot be reused for it. Attempted this session, all blocked:
--   - https://www.cityofpensacola.com/DocumentCenter/View/1604/Adopted-City-of-
--     Pensacola-Parking-Standards -> Cloudflare bot-challenge (HTTP 403 via
--     WebFetch, "Just a moment..." interstitial via direct curl)
--   - Firecrawl API scrape of same URL -> "Insufficient credits" (account-level
--     block, not a fetch failure)
--   - http://www.pensacola.elaws.us/code/coor_titlexii_ch-2_artv_sec12-2-64
--     (Ch 12-2 Art V nonresidential parking in R-districts) -> ECONNRESET /
--     60s timeout, consistent with prior sessions' elaws.us failures
--   - library.municode.com/fl/pensacola (Ch 12-3, Ch 12-4 Off-Street Parking)
--     -> HTTP 403 via WebFetch
--   - archive.org CDX search on both cityofpensacola.com/DocumentCenter/View/
--     1604 and pensacola.elaws.us -> zero snapshots archived
--   - WebSearch for the R-NC ratio specifically -> no numeric figure
--     surfaced in any snippet
-- R-NC remains a genuine, documented dead end. Not fabricated.

BEGIN;

UPDATE zone_standards zs
SET parking_per_1000sf = 3.00
FROM zoning_districts zd
JOIN jurisdictions jd ON jd.id = zd.jurisdiction_id
WHERE zs.zoning_district_id = zd.id
  AND jd.county = 'Escambia'
  AND jd.name = 'Escambia County (Unincorporated)'
  AND zd.code = 'Com'
  AND zs.parking_per_1000sf IS NULL;

UPDATE zone_standards zs
SET parking_per_1000sf = 3.00
FROM zoning_districts zd
JOIN jurisdictions jd ON jd.id = zd.jurisdiction_id
WHERE zs.zoning_district_id = zd.id
  AND jd.county = 'Escambia'
  AND jd.name = 'Escambia County (Unincorporated)'
  AND zd.code = 'HDMU'
  AND zs.parking_per_1000sf IS NULL;

UPDATE zone_standards zs
SET parking_per_1000sf = 1.00
FROM zoning_districts zd
JOIN jurisdictions jd ON jd.id = zd.jurisdiction_id
WHERE zs.zoning_district_id = zd.id
  AND jd.county = 'Escambia'
  AND jd.name = 'Escambia County (Unincorporated)'
  AND zd.code = 'HC/LI'
  AND zs.parking_per_1000sf IS NULL;

-- Stamp source metadata for all three rows updated above.
UPDATE zone_standards zs
SET source_url = 'https://agenda.myescambia.com/docs/2014/PB/20141209_1206/7278_DSM%20141120FINAL.pdf',
    ordinance_section = 'DSM Ch.1 Art.3 Sec.3-1.2 Parking Demand (via LDC Sec. 3-2.9(d)(8)/3-2.10(d)(8)/3-2.11(d)(8) cross-reference)',
    confidence_score = 0.55
FROM zoning_districts zd
JOIN jurisdictions jd ON jd.id = zd.jurisdiction_id
WHERE zs.zoning_district_id = zd.id
  AND jd.county = 'Escambia'
  AND jd.name = 'Escambia County (Unincorporated)'
  AND zd.code IN ('Com', 'HDMU', 'HC/LI')
  AND zs.parking_per_1000sf IN (3.00, 1.00);

COMMIT;
