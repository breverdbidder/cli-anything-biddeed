-- Gold Standard shard-6, run6148, collier G fix: RSF-3/4/5 + MH (unincorp) density,
-- Marco Island RSF-3 density, Naples R1-7.5 implied density.
--
-- Resolves the residual flagged in GOLD_STANDARD_SHARD12_COLLIER_DISPATCH_9D04299E_2ND_FIRING_ADDENDUM.md
-- as "still genuinely unknown (no fixed value found in two sessions of searching)".
--
-- Collier County UNINCORPORATED LDC Sec 2.05.01 "Density Standards and Housing Types"
-- (https://library.municode.com/fl/collier_county/codes/land_development_code,
-- nodeId=CH2ZODIUS_2.05.00DEST_2.05.01DESTHOTY, jobId=490700, productId=13992,
-- codified through Ord. No. 26-10, Supplement 33) -- fetched live and parsed with a
-- real HTML table parser (not OCR/summary) directly against the "Maximum Density
-- (units per gross acre)" column. CONFIRMED tier: RSF-3=3, RSF-4=4, RSF-5=5
-- (confirms the RSF-N naming convention IS the density figure), MH=7.26 (row "MH 9",
-- footnote 9 is a use-clarification note about modular homes, not a density caveat;
-- cross-corroborated within the same table against VR's footnoted 7.26 for
-- "single-family and mobile home, with or without clustering").
--
-- Marco Island (separate incorporated municipality, own LDC Ch. 30 Sec 30-85
-- "Dimensional standards and regulations") RSF-3=3 du/acre -- HYPOTHESIS tier:
-- library.municode.com returned 403 directly; sourced via a third-party mirror
-- (zoneomics.com/code/marco-island-FL/chapter_2) that reproduces genuine
-- section-numbered ordinance text with real Municode nodeId/ordinance-id cross
-- links (Ord. No. 17-02, 18-09, 24-17) and an internally-consistent RSF-2=2/
-- RSF-3=3/RSF-4=4 progression alongside matching min-lot-area figures
-- (20,000/10,000/7,500 sqft) -- not independently re-verified against the
-- primary library.municode.com host in this session.
--
-- Naples (separate incorporated municipality) R1-7.5 "Residence District" --
-- ATTEMPTED then REVERTED. Original research computed an implied max density
-- (43,560 sqft/acre / 7,500 sqft min lot = 5.8 du/acre, one unit per lot) since
-- the ordinance states no density figure directly. An independent adversarial
-- refuter re-fetched the SAME corroborating mirror (zoneomics.com) and found it
-- explicitly states NO density figure is stated OR implied for R1-7.5 --
-- directly contradicting the implied-density methodology -- and separately
-- flagged a conceptual conflation: subdivision-yield theoretical density is not
-- the same as per-parcel entitlement (a single already-platted auction lot
-- yields exactly 1 unit regardless of acreage, so 5.8 as max_density_du_acre
-- risked misleading downstream deal-analysis). REVERTED to NULL live
-- (confidence_score restored to 0.15, the pre-session partial-data state).
-- See gold_standard_ultraloop_audit id=9229 (survived=false) for the full
-- refuter evidence. Left as a genuine, honestly-documented residual gap.

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
VALUES
  (10668, 3,    'https://library.municode.com/fl/collier_county/codes/land_development_code?nodeId=CH2ZODIUS_2.05.00DEST_2.05.01DESTHOTY', '2.05.01', 1.0),  -- Collier unincorp RSF-3
  (11695, 4,    'https://library.municode.com/fl/collier_county/codes/land_development_code?nodeId=CH2ZODIUS_2.05.00DEST_2.05.01DESTHOTY', '2.05.01', 1.0),  -- Collier unincorp RSF-4
  (11696, 5,    'https://library.municode.com/fl/collier_county/codes/land_development_code?nodeId=CH2ZODIUS_2.05.00DEST_2.05.01DESTHOTY', '2.05.01', 1.0),  -- Collier unincorp RSF-5
  (11690, 7.26, 'https://library.municode.com/fl/collier_county/codes/land_development_code?nodeId=CH2ZODIUS_2.05.00DEST_2.05.01DESTHOTY', '2.05.01', 1.0),  -- Collier unincorp MH
  (12157, 3,    'https://www.zoneomics.com/code/marco-island-FL/chapter_2 (mirrors library.municode.com/fl/marco_island/codes/code_of_ordinances Sec 30-85; not independently re-verified against primary host)', '30-85', 0.6)  -- Marco Island RSF-3
ON CONFLICT DO NOTHING;

-- Naples R1-7.5 implied-density write was applied then REVERTED live in the same
-- session after adversarial refutation (see comment block above) -- restored to
-- its pre-session state (max_density_du_acre NULL, confidence_score 0.15).
UPDATE zone_standards
SET max_density_du_acre = NULL,
    source_url = NULL,
    ordinance_section = NULL,
    confidence_score = 0.15
WHERE zoning_district_id = 6470;  -- Naples R1-7.5
