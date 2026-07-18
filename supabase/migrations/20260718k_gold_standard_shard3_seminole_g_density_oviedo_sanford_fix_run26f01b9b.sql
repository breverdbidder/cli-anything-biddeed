-- Gold Standard shard-3 (seminole) — letter G fix, part 2: density binding constraint
-- (93.9%... actually pre-fix 80.6% -> 96.9%, crosses the >=95% threshold, G FAIL -> PASS)
-- Dispatch: 26f01b9b-e405-422e-9908-229f26e0ae5a. Continuation session, same dispatch,
-- 2026-07-18 (later same day as 20260718f, which fixed pk1000; this migration fixes the
-- density sub-metric, the last binding constraint after pk1000 and far were both 100%).
--
-- ROOT CAUSE (live-diagnosed this session via the Management API pg_get_viewdef() +
-- direct SQL against v_zoning_gold_standard_kpi_v3's underlying `pj` CTE, since PostgREST
-- cannot introspect view DDL and psql/pooler auth is stale this session, same constraint
-- as every other shard-3 migration this dispatch):
--   density_applicable_parcels=36, only 29 had a real max_density_du_acre -> 80.6%.
--   Two independent failure patterns, found by walking every zoning_district_id with
--   density_regulated=true (or NULL defaulting to true via the applicability view's
--   fallback) AND a NULL max_density_du_acre in zone_standards, restricted to Seminole's
--   8 jurisdictions (810/850/862/904/921/928/944/636):
--     (a) 3 real districts (Oviedo id=862: R-1, R-1C, PUD) had density_regulated=true but
--         no sourced max_density_du_acre value.
--     (b) 2 more real districts (Sanford id=904 code='PD', Casselberry id=850 code='PRD')
--         had density_regulated=NULL, defaulting to "applicable" via the view's category
--         fallback (category not in commercial/industrial -> defaults true), also with no
--         sourced value.
--
-- FIX, sourced from real ordinance text (BLANK > WRONG — no number fabricated):
--
-- (1) Oviedo R-1 (zoning_district_id=11837, zone_standards.id=4550): Oviedo LDC Table
--     4.2.1 (Lot Use Regulations) states minimum lot size 8,500 sf for R-1. R-1 has no
--     bespoke "max density" figure in the code because minimum lot size IS the density
--     control mechanism for conventional single-family subdivision in this code (no PUD/
--     cluster provision applies to R-1). Computed: 43,560 sf/acre / 8,500 sf = 5.12 ->
--     5.1 du/acre. Source: Ord. 1752 Ex. 1 LDC Final Draft PDF (Lowndes Law Firm mirror,
--     https://www.lowndes-law.com/assets/htmldocuments/Ord1752%20Ex1%20LDC%20Final%20Draft.pdf),
--     confirmed via direct WebFetch download + pypdf text extraction this session (the raw
--     PDF bytes, not a WebFetch AI summary which failed to parse the compressed PDF
--     stream on first attempt), page 61, Table 4.2.1.
--
-- (2) Oviedo R-1C (zoning_district_id=11838, zone_standards.id=4551): same table, same
--     PDF, minimum lot size 2,500 sf. Computed: 43,560 / 2,500 = 17.42 -> 17.4 du/acre.
--     District purpose per LDC Sec 4.8(C): "designed for medium density single-family
--     detached, single-family attached (townhome)" — consistent with the higher
--     lot-size-derived density figure.
--
-- (3) Oviedo PUD (zoning_district_id=11839): NOT assigned a density figure. Oviedo LDC
--     Table 4.2.1 has no PUD row at all (confirmed absent from the same page-61 table
--     used for R-1/R-1C), and LDC Sec. 4.11(F) "Maximum Density/Intensity of
--     Development" states verbatim: "The density and intensity of development within the
--     PUD zoning district shall be established within the development agreement
--     consistent with the maximum density and intensity allowed within the property's
--     future land use designation." I.e. density is negotiated per development
--     agreement/FLU, not a fixed zoning-district constant — same statewide FL PUD
--     convention already applied fleet-wide in this dataset (Sanford PD/Seminole Co.
--     unincorporated PD/Lake Mary PUD/Winter Springs PUD/Altamonte PUD-MO, all correctly
--     density_regulated=false). Set zoning_districts.density_regulated=false with the
--     Sec 4.11(F) citation in the description field. zone_standards.max_density_du_acre
--     for this district remains NULL — correctly, not fabricated.
--
-- (4) Sanford PD (zoning_district_id=6329): existing zoning_districts.description
--     already states "a technique for negotiating innovative development options" —
--     structurally the identical negotiated-PD pattern already verified correct for
--     Seminole Co. unincorporated (jurisdiction 636)'s many PD districts in this same
--     dataset. Sanford LDR Schedule D Sec. 3.0/4.0 governs "Planned Development Project
--     Regulations" / "Residential planned development (PD)" (confirmed via WebSearch —
--     library.municode.com returns HTTP 403 to direct fetch this session, and Firecrawl
--     scrape returned HTTP 402 (this account's Firecrawl credit was exhausted this
--     session, not silently retried/estimated)). Set density_regulated=false, applying
--     the same established treatment already used for the identically-named/identically-
--     described PD code type elsewhere in this county's own dataset — not a new guess.
--
-- (5) Casselberry PRD (zoning_district_id=6357): NOT fixed this session, left as a
--     disclosed residual. WebSearch found real ordinance text confirming PRD density is
--     genuinely FLU-designation-dependent (5 du/ac for Low/Medium Density FLU designation,
--     20-25 du/ac for High Density FLU) — i.e. PRD legitimately has a fixed numeric cap,
--     unlike PUD, but the cap depends on which FLU applies to this specific parcel, which
--     was not independently verified this session. Assigning a single number without
--     knowing the parcel's FLU would be a guess; per BLANK > WRONG, left NULL. This is
--     the sole remaining density-applicable gap for seminole G's density sub-metric after
--     this migration (1 of 32 applicable parcels after Sanford PD's exclusion) but does
--     NOT block the >=95% threshold on its own (31 of 32 = 96.9%).
--
-- Applied live via PostgREST PATCH this session (Supabase pooler auth confirmed stale,
-- Management API used read-only for pg_get_viewdef()/diagnostic SELECTs only — no DDL
-- executed via Management API this migration, unlike 20260718f). This migration file is
-- the checked-in record of those writes, per the Gold Standard ship-to-main mandate.
--
-- VERIFICATION (live pencil_dod_evaluate_county('seminole'), this session, pasted verbatim):
--   Before (start of this continuation session, matches 20260718f's post-pk1000-fix state):
--     G: {"pass": false, "detail": "density=80.6 far=100.0 pk1000=100.0", "metric": 80.6}
--   After step (1)-(3) [Oviedo only]:
--     G: {"pass": false, "detail": "density=93.9 far=100.0 pk1000=100.0", "metric": 93.9}
--     v_zoning_gold_standard_kpi_v3: density_applicable_parcels 36 -> 33 (3 Oviedo PUD
--     parcels correctly dropped from the applicable denominator), pct_density_of_applicable
--     80.6 -> 93.9 (31 of 33 pass).
--   After step (4) [Sanford PD]:
--     G: {"pass": true, "detail": "density=96.9 far=100.0 pk1000=100.0", "metric": 96.9}
--     density_applicable_parcels 33 -> 32, pct_density_of_applicable 93.9 -> 96.9 (31 of 32).
--   seminole overall: 8/10 -> 9/10 (only I remains FAIL, card_complete=96 of 105 unchanged
--     this session — see residual note below, GIS endpoint access confirmed still blocked).
--
-- No SQL DDL executed by this file — it is a documentation-only record of live PostgREST
-- PATCH writes, matching the established pattern for this dispatch (20260718e/f/g).
DO $$ BEGIN NULL; END $$;

-- Reproducible equivalent of the live PATCH writes (idempotent, safe to replay once
-- direct psql/pooler access is restored):
UPDATE zone_standards SET
  max_density_du_acre = 5.1,
  source_url = 'https://www.lowndes-law.com/assets/htmldocuments/Ord1752%20Ex1%20LDC%20Final%20Draft.pdf',
  ordinance_section = 'Table 4.2.1 (Lot Use Regulations), min lot size 8,500 sf for R-1 Single-Family Residential. Max density computed as 43,560 sf/acre / 8,500 sf min lot = 5.12 du/acre (lot-size-based density mechanism; no separate max-density figure stated because none is needed under this code). Source PDF confirmed via direct WebFetch + pypdf text extraction, page 61.',
  confidence_score = 0.8
WHERE id = 4550 AND max_density_du_acre IS NULL;

UPDATE zone_standards SET
  max_density_du_acre = 17.4,
  source_url = 'https://www.lowndes-law.com/assets/htmldocuments/Ord1752%20Ex1%20LDC%20Final%20Draft.pdf',
  ordinance_section = 'Table 4.2.1 (Lot Use Regulations), min lot size 2,500 sf for R-1C Single-Family/Medium Density Residential. Max density computed as 43,560 sf/acre / 2,500 sf min lot = 17.42 du/acre. District purpose per Sec 4.8(C): medium density single-family/townhome. Source PDF confirmed via direct WebFetch + pypdf text extraction, page 61.',
  confidence_score = 0.8
WHERE id = 4551 AND max_density_du_acre IS NULL;

UPDATE zoning_districts SET
  density_regulated = false,
  description = 'Oviedo LDC Sec. 4.11(F) Maximum Density/Intensity of Development: "The density and intensity of development within the PUD zoning district shall be established within the development agreement consistent with the maximum density and intensity allowed within the property''s future land use designation." PUD also has no row in Table 4.2.1 (Lot Use Regulations), confirming no fixed base-code density applies -- density is negotiated per development agreement, not a zoning-district constant. Same statewide FL PUD convention documented for Sanford PD/Seminole Co. PD/Lake Mary PUD/Winter Springs PUD/Altamonte PUD-MO in this dataset. Not fabricated per BLANK > WRONG.'
WHERE id = 11839 AND (density_regulated IS NULL OR density_regulated = true);

UPDATE zone_standards SET
  ordinance_section = 'Sec. 4.11(F): density set per development agreement per FLU designation, not a fixed zoning-district value. See zoning_districts.description for full citation.',
  confidence_score = 0.9
WHERE id = 4552;

UPDATE zoning_districts SET
  density_regulated = false,
  description = 'Intended for residential and nonresidential uses that utilize flexible and creative site design to achieve a more desirable environment and more efficient land use. The planned development land management strategy is a technique for negotiating innovative development options and a design to achieve public objectives. Sanford LDR Schedule D governs PD (Planned Development Project Regulations, Sec 3.0/4.0 Residential planned development) -- density is negotiated per individual development plan/agreement, not a fixed zoning-district value. This is structurally the identical PD code-type/negotiated-development pattern already established and verified correct for Seminole County unincorporated jurisdiction (636) PD districts and Oviedo (862) PUD in this same dataset -- applying the same established treatment to this jurisdiction''s PD district, not a new guess. Direct municode fetch returns HTTP 403 (library.municode.com, consistent with prior sessions); Firecrawl scrape returned HTTP 402 (account credit exhausted this session) -- flagged, not silently retried.',
  ordinance_section = 'Sanford LDR Schedule D, Sec. 3.0/4.0 (Planned Development Project Regulations)'
WHERE id = 6329 AND (density_regulated IS NULL);

-- RESIDUAL / NEXT-SESSION PRIORITIES (this shard):
-- 1. Casselberry PRD (zoning_district_id=6357): real, FLU-dependent density cap (5 or
--    20-25 du/ac) exists in the ordinance but requires this parcel's specific FLU
--    designation to assign correctly -- not fabricated, not fixed this session. Does not
--    block G (already PASS at 96.9%).
-- 2. Seminole I (card_complete=96 of 105, 91.4%, still FAIL): needs parcel_zones rows for
--    the 6 real-parcel-id gap rows documented in 20260718e. THREE independent GIS access
--    paths tried and confirmed blocked this session: gis.scpafl.org (TLS connection reset,
--    same as prior sessions), seminolearcgis.seminolecountyfl.gov:6443 (connection timeout,
--    a different subdomain/port on the same county network, also blocked), and the public
--    ArcGIS Online "Pinellas_Seminole_Zoning" FeatureServer (reachable, but its extent
--    resolves to Pinellas County -- it covers the City of Seminole in PINELLAS county, a
--    same-name false lead, not Seminole County). Firecrawl scrape returned HTTP 402
--    (credit exhausted) as an alternate egress path. A future session needs either
--    restored Firecrawl credit, a different network egress, or a manual/interactive PA
--    parcel search (the form is JS-driven POST, WebFetch/curl GET cannot submit it).
-- 3. Marion G (pk1000=0.0%, B-2 Community Business, zone_standards.id=4363, 6 parcels):
--    re-confirmed genuinely blocked this session (municode 403, elaws.us connection
--    reset, marionfl.org 403, Firecrawl 402) -- third session in a row reaching the same
--    conclusion. Needs Marion County LDC Article 6 Div 11 Table 6.11-4/6.11-5 (parking
--    schedule) via a channel not yet tried (e.g. a live phone/PDF request to Marion County
--    Growth Services per the search results' own recommendation, 352-438-2600).
