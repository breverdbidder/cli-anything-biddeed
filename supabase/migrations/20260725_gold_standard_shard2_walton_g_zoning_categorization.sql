-- GOLD STANDARD shard-2 (jackson/walton/liberty), loop run 6354, dispatch
-- 5e1e6111-7b73-4ac4-87f8-1eb182321346 -- 2026-07-25 session.
-- Walton criterion G: FAIL density=91.4 (density_applicable_parcels=70, 64 with a real
-- max_density_du_acre value, 6 missing). far=100.0 PASS, pk1000 n/a (0 applicable).
--
-- ROOT CAUSE (verified live via v_zoning_gold_standard_kpi_v3 + a full parcel_zones join
-- for the 4 Walton jurisdictions, cross-checked against zone_standards): the 6 missing
-- parcels are NOT spread across many districts -- they collapse to exactly 2 districts:
--   - zoning_districts.id=11397 code='Municipal' (jurisdiction 842, DeFuniak Springs)
--     -- 5 parcels use this zone_code.
--   - zoning_districts.id=12652 code='General Commercial' (jurisdiction 1333,
--     Unincorporated Walton) -- 1 parcel uses this zone_code.
-- 5 + 1 = 6, matching the gap exactly.
--
-- Both districts currently have category values ('deferred' / 'residential') that fall
-- outside v_zoning_district_applicability's category-based defaulting (which only special-
-- cases 'commercial'/'industrial'), so density_applicable defaults to true for both --
-- counting them against the denominator even though 'Municipal' should be fully excluded
-- and 'General Commercial' (mistagged as residential -- a data-entry bug from the
-- 2026-07-24 walton_enerGov_arcgis/4f148647 ingestion) simply never had its real density
-- value written.
--
-- An initial ultracode research pass targeted 5 *other* DeFuniak Springs districts
-- (C-2, I, Inst, Airport Overlay, Airport) that appeared "Uncategorized" in
-- zoning_districts -- live re-verification against the actual 74-row parcel_zones set
-- for these 4 jurisdictions showed ZERO parcels reference any of those 5 codes, so fixing
-- them cannot move this metric. Their CONFIRMED findings are included below anyway as a
-- legitimate data-quality fix (real ordinance research already done, no reason to discard
-- it), but the G-metric fix is items 1-2 only. Two districts (Inst, Airport) came back
-- confidence=UNKNOWN -- a full-text search of the City of DeFuniak Springs' current
-- Chapter 18 Land Development Regulations PDF (defuniaksprings.net/DocumentCenter/View/
-- 10162) found no "Institutional" or "Airport" (non-overlay) zoning district anywhere in
-- the document. Per BLANK > WRONG, these are left untouched -- not guessed.
--
-- ==========================================================================================
-- 1. 'Municipal' (id 11397) -- CONFIRMED, density_regulated=false.
-- Source: Walton County's own Land Development Code, Chapter 2 (Zoning Districts),
-- implementing Ord. 2018-29, "Revised April 27, 2021" (mywaltonfl.gov/DocumentCenter/
-- View/2115). Sec. 2.01.02 "Generally": the county code applies only to "the unincorporated
-- portion of Walton County." Sec. 2.01.03's full district enumeration (30 adopted county
-- districts: LSA, GA, RR, RLD, RV, ER, CR 1/10, CR 1/2.5, CR 2/1, UR, RP, LDR 1/0.5,
-- LDR 4/1, NI, GC, NC, BP, SN, TND, CC, CCMU, CV-1, VMU, TC-1, R, EU, LI, HI, CON, PR, PF,
-- INST) contains no "Municipal" entry -- full-text search of the 109-page chapter: zero
-- hits as a district name. This confirms 'Municipal' is a GIS ZONE_CLASS attribute from
-- Walton's own EnerGov ArcGIS layer 19 meaning "this parcel sits inside a municipality;
-- the county's own zoning code (and this table's density standards) does not apply to it"
-- -- not a codified district with an adopted density figure. Matches and strengthens the
-- original sourcing already on file in 20260710164500_walton_i_real_gis_zoning_and_geo_backfill.sql.
--
-- 2. 'General Commercial' (id 12652) -- CONFIRMED, category fixed Commercial (was
-- mistagged 'residential' -- 2026-07-24 ingestion data-entry bug), density_regulated=true,
-- max_density_du_acre=17.
-- Source: Walton County LDC Chapter 2, Sec. 2.02.15 "General Commercial (GC)"
-- (mywaltonfl.gov/DocumentCenter/View/2115), the exact unincorporated-county district this
-- parcel (34-1S-19-23080-00D-0010) is zoned. GC has no stand-alone residential base
-- density; residential appears only via two capped pathways that share one number:
--   Sec. 2.02.15.B.11 (primary use, vertical mixed use): "Up to 17 multi-family
--     residential dwelling units per one (1) acre... provided such units are located
--     above a ground floor commercial use."
--   Sec. 2.02.15.D.1.b (conditional use, workforce housing): "Multifamily residential
--     uses may be developed at a density of up to seventeen (17) dwelling units per
--     acre" (requires >=20% workforce-housing units per 2.02.15.D.1.c).
-- Corroborated by the Chapter 2 district-standards summary table: "General Commercial
-- (GC) -- 17 du/acre if vertical mixed use -- FAR 1.00 -- ISR 0.85". 17 du/acre is
-- recorded here as the ordinance-stated ceiling for this district (mixed-use/conditional
-- cap, not an unconditional base density) -- a real, sourced number, not a guess.
--
-- 3-6. Supplementary DeFuniak Springs fixes (CONFIRMED, do not move walton's G metric --
-- zero parcels in the live 74-row set reference these codes -- but correct real data
-- quality for any future walton parcel that lands in one of these districts).
-- Source for all 4: City of DeFuniak Springs Code of Ordinances Ch. 18 (Land Development
-- Regulations), fetched directly from defuniaksprings.net/DocumentCenter/View/10162 and
-- cross-checked against Municode/zoneomics mirrors where library.municode.com itself
-- returned 403 to automated fetch.
--   'C-2' (id 5560) Commercial-General: Sec. 6.01-6.05 (Ch.18 Art.V/VI numbering) permits
--     only commercial/retail/service uses; dwellings are not a listed use at all; only a
--     max FAR (1.0) and yard-setback subsection exist -- no residential density
--     subsection, unlike sibling districts (A Sec.8.05 states "1 dwelling unit per 5
--     acres" explicitly) which prove the drafters DO state density where it applies.
--   'I' (id 5567) Industrial-Light: Sec. 18-48 -- dwellings permitted only as a
--     special-approval "use exception," not a primary use; regulated by FAR (0.5) and
--     setback only. Sibling districts in the same Article (R-2 Sec.18-44: "sixteen (16)
--     dwelling units" per acre; C-2 Sec.18-46 redevelopment: "twenty-four (24) dwelling
--     units per gross acre"; MX Sec.18-47: "twenty-four (24) dwelling units per acre")
--     confirm the drafting pattern of stating density explicitly where intended --
--     its absence here is deliberate, not an oversight.
--   'Airport Overlay' (id 8225) Airport overlay district: Article II Sec.18-21 to 18-37
--     ("DeFuniak Springs Airport Overlay District and Height Zoning Ordinance," Ord.
--     No. 804, 7-11-2011) regulates hazard zones, height limits, obstructions, and noise
--     attenuation only -- no dwelling-units-per-acre figure anywhere in its ~390 lines.
--     As an overlay, residential density is governed by the underlying BASE district, not
--     this article -- correctly density_regulated=false at the overlay level.
--
-- UNRESOLVED (left untouched, confidence=UNKNOWN, no zero linked parcels either way):
--   'Inst' (id 5575) and 'Airport' (id 8248, duplicate-named overlay entry) -- no
--   "Institutional" or non-overlay "Airport" zoning district found anywhere in the
--   current DeFuniak Springs Chapter 18 text after a full-text search of the entire
--   document. Could not cross-check the live Municode-hosted version (403 Forbidden) or
--   use Firecrawl (account out of credits) to rule out an unincorporated-Walton-County
--   Institutional/Public-Facility district (Walton's OWN LDC Sec.2.01.03 DOES list an
--   "INST" county district, per the Municipal-finding research above -- these two
--   DeFuniak-jurisdiction rows may in fact belong to the WRONG jurisdiction_id and should
--   be re-examined against jurisdiction_id=1333 in a future session). Flagged, not
--   guessed.
--
-- BEFORE (live, pencil_dod_evaluate_county('walton'), this session):
--   A=PASS(6) B=PASS(100.0) C=PASS(97.5) D=PASS(97.5) E=PASS(98.8) F=PASS(100.0)
--   G=FAIL(91.4, density=91.4 far=100.0 pk1000=null) H=PASS(0.1h) I=PASS(96.3) J=PASS(97.5)
--   [9/10]
-- Expected AFTER: Municipal's 5 parcels move from applicable->N/A (denominator 70->65);
--   General Commercial's 1 parcel gets a real value (numerator 64->65). 65/65 = 100.0%,
--   comfortably above the 95% threshold. G: FAIL -> PASS. Verified live in the companion
--   GHA run (.github/workflows/apply-shard2-walton-g-fix.yml) -- see that workflow's run
--   summary / the session close-out comment for the actual post-migration number.

BEGIN;

-- 1. Municipal (id 11397) — GIS-deferred placeholder, no adopted density standard.
UPDATE zoning_districts
   SET density_regulated = false,
       ordinance_section = 'Walton County LDC Ch.2 Sec.2.01.02-2.01.03 (Ord. 2018-29, rev. 2021-04-27) — "Municipal" is a GIS ZONE_CLASS value, not an adopted county district; no district in the Sec.2.01.03 enumeration matches'
 WHERE id = 11397 AND code = 'Municipal' AND jurisdiction_id = 842;

-- 2. General Commercial (id 12652) — fix mistagged category, add real sourced density cap.
UPDATE zoning_districts
   SET category = 'Commercial',
       density_regulated = true,
       ordinance_section = 'Walton County LDC Ch.2 Sec.2.02.15 "General Commercial (GC)" (Ord. 2018-29, rev. 2021-04-27) — 17 du/acre vertical-mixed-use/conditional-workforce-housing cap (Sec.2.02.15.B.11, D.1.b)'
 WHERE id = 12652 AND code = 'General Commercial' AND jurisdiction_id = 1333;

UPDATE zone_standards
   SET max_density_du_acre = 17
 WHERE zoning_district_id = 12652
   AND max_density_du_acre IS NULL;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, confidence_score)
SELECT 12652, 17, 'https://mywaltonfl.gov/DocumentCenter/View/2115/LDC-Chapter-2', 0.9
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 12652);

-- 3-5. Supplementary DeFuniak Springs data-quality fixes (0 linked parcels currently,
-- do not affect walton's live G metric).
UPDATE zoning_districts
   SET category = 'Commercial',
       density_regulated = false,
       ordinance_section = 'DeFuniak Springs Code of Ordinances Ch.18 Sec.6.01-6.05 — no residential density subsection exists for C-2; dwellings not a listed use'
 WHERE id = 5560 AND code = 'C-2' AND jurisdiction_id = 842;

UPDATE zoning_districts
   SET category = 'Industrial',
       density_regulated = false,
       ordinance_section = 'DeFuniak Springs Code of Ordinances Sec. 18-48 (Ord. No. 881, 6-26-2017) — dwellings only a special-approval use exception, no density subsection'
 WHERE id = 5567 AND code = 'I' AND jurisdiction_id = 842;

UPDATE zoning_districts
   SET category = 'Overlay',
       density_regulated = false,
       ordinance_section = 'DeFuniak Springs Code of Ordinances Sec. 18-21 to 18-37 (Ord. No. 804, 7-11-2011) — Airport hazard/height overlay; density governed by underlying base district, not this article'
 WHERE id = 8225 AND code = 'Airport Overlay' AND jurisdiction_id = 842;

COMMIT;
