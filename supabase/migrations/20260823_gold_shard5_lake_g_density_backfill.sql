-- Gold Standard shard-5 (dispatch 79ee1554): LAKE county criterion G (zoning
-- density/FAR/parking coverage) fix.
--
-- Diagnosis (pre-verified, not re-derived here): G was failing at density=91.6%
-- (76 of 83 density-applicable parcels had max_density_du_acre populated; far=93.8%
-- (15/16); pk1000=100% already passing. Binding constraint = density, needed >=95%
-- i.e. >=79 of 83 resolved -- at least 3 more parcels.
--
-- Full gap list re-derived live (2026-08-23) via the join query in the task brief.
-- Six Lake districts have NULL max_density_du_acre and are density-applicable:
--   Tavares RMF-3 (2 parcels), Eustis RT (1), Tavares RMF-2 (1), Tavares RMH-S (1),
--   Tavares R-6 (1), Tavares RSF-2 (1).
--
-- Sourcing (live, 2026-08-23):
--   Tavares Code of Ordinances, Appendix A Land Development Regulations, Chapter 8
--   Zoning Regulations, Sec. 8-11 "Zoning District Regulations" -- confirmed via
--   http://tavares.elaws.us/code/coor_apladere_apxa_ch8_sec8-11 (municode.library
--   itself returns HTTP 403 to automated fetch; elaws.us is the same ordinance body
--   republished, cross-checked against the city's own published dimensional table
--   below). Sec. 8-11 states Table 8-3 ("Development Standards") governs dimensional
--   requirements and confirms NO separate numeric density (du/acre) cap exists in the
--   Tavares code for the RSF/RMF/RMH single- and multi-family districts -- density is
--   NOT a discrete zoning-code value for these districts, it is the mathematical
--   consequence of minimum lot area (43,560 sq ft / min lot sqft = max theoretical
--   density), the standard structure for FL single-family/duplex/small-multifamily
--   zoning that regulates via lot size + setbacks + height rather than a stated cap.
--   Table 8-3 itself pulled directly from the city's published "Zoning Development
--   Standards" PDF (http://www.tavaresfl.gov/DocumentCenter/View/8081, redirect of
--   https://tavares.org/DocumentCenter/View/8081), parsed with pdfplumber:
--     RSF-2: Minimum Lot Area = 6,500 sq. ft.  -> 43,560/6,500 = 6.70 du/acre
--     RMF-2: Minimum Lot Area = 6,500 sq. ft.  -> 43,560/6,500 = 6.70 du/acre
--     RMH-S: Minimum Lot Area = 6,000 sq. ft.  -> 43,560/6,000 = 7.26 du/acre
--   No max_far column exists in Table 8-3 for any residential district in Tavares
--   (only Front/Rear/Side setback, ISR%, lot width, height) -- max_far intentionally
--   left NULL for these 3 rows; that is a genuine "not FAR-regulated by a stated cap"
--   condition for FAR, tracked separately from this density fix and NOT claimed fixed.
--
-- NOT fixed in this migration (left as residual, no real value found):
--   Tavares RMF-3 (district_id 13730, 2 parcels): Table 8-3 lists min lot area = "No
--     minimum" for RMF-3 -- the lot-area-derivation method used above does not apply
--     (no denominator). Sec. 8-11 full text search (elaws.us) confirms no separate
--     numeric density figure exists anywhere in the ordinance for RMF-3. Cannot
--     source a real value; not flagged density_regulated=false either, since RMF-3 is
--     an ordinary multi-family district (not a PUD/case-by-case development order) and
--     Florida practice is that density-by-lot-area districts without a stated minimum
--     lot size typically defer to max height/ISR/parking as the effective envelope
--     control -- this needs a maximum-floor-area-per-unit or unit-count formula from
--     Sec. 8-11 subsections not surfaced by automated fetch. Left failing.
--   Tavares R-6 (district_id 13975, 1 parcel): confirmed via elaws.us full-text search
--     that "R-6" does not appear anywhere in current Tavares Sec. 8-11 zoning district
--     text (only RSF-A/1/2, RMF-2/3, RMH-S/P, MU, CD, C-1/2, I, PFD, PD are defined).
--     The existing district row's own description (set 2026-08-13) already documents
--     this as a deliberate structural placeholder -- GIS zone_name "Urban Residential"
--     with no ordinance match found. Left failing rather than fabricate a value.
--   Eustis RT (district_id 13461, 1 parcel, code "RT", name "Rural Transition"): the
--     City of Eustis 2035 Comprehensive Plan Future Land Use Element, Table A-3.1
--     (https://eustis.civicweb.net/document/34258/..., pulled and parsed live) lists
--     land use categories SR/UR/MH/GC/GI/CBD/RT/MCR/MCI/PI/CON -- RT in that table
--     means "Residential/Office Transitional" (12 du/acre for the residential
--     component), NOT "Rural Transition". No "Rural Transition" category appears
--     anywhere in the current adopted comp plan. Since our row's own name field
--     ("Rural Transition") does not match the current comp plan's RT definition
--     ("Residential/Office Transitional"), applying 12 du/acre here would risk
--     mislabeling a different category as this parcel's real constraint. Left failing
--     rather than fabricate/guess.
--
-- Verification: pencil_dod_evaluate_county('lake') re-run after this migration; G
-- before/after JSON captured in the task report, not duplicated here.

-- RSF-2 (Tavares) -- Table 8-3 min lot area 6,500 sq ft
INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, max_density_du_acre,
  source_url, ordinance_section, confidence_score, scraped_at
) VALUES (
  13976, 6500, 6.70,
  'http://www.tavaresfl.gov/DocumentCenter/View/8081',
  'Tavares Code of Ordinances App. A Ch. 8 Sec. 8-11, Table 8-3 (Development Standards)',
  0.75, now()
);

-- RMF-2 (Tavares) -- Table 8-3 min lot area 6,500 sq ft
INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, max_density_du_acre,
  source_url, ordinance_section, confidence_score, scraped_at
) VALUES (
  13731, 6500, 6.70,
  'http://www.tavaresfl.gov/DocumentCenter/View/8081',
  'Tavares Code of Ordinances App. A Ch. 8 Sec. 8-11, Table 8-3 (Development Standards)',
  0.75, now()
);

-- RMH-S (Tavares) -- Table 8-3 min lot area 6,000 sq ft
INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, max_density_du_acre,
  source_url, ordinance_section, confidence_score, scraped_at
) VALUES (
  13732, 6000, 7.26,
  'http://www.tavaresfl.gov/DocumentCenter/View/8081',
  'Tavares Code of Ordinances App. A Ch. 8 Sec. 8-11, Table 8-3 (Development Standards)',
  0.75, now()
);
