-- Gold Standard shard-2 (sarasota/columbia, dispatch dd959980), 2026-08-03.
-- APPLIED LIVE via the Supabase Management API SQL endpoint during this
-- session (direct psql connection was blocked -- password auth failure on
-- both the pooler and db.<ref>.supabase.co hosts, consistent with prior
-- sessions' findings). This file documents what was already executed live;
-- it is NOT a pending migration to run.
--
-- CONTEXT: the sarasota_I lane of this session's ultracode workflow inserted
-- 10 new parcel_zones rows (via ags3.scgov.net / scgov_arcgis_scpaservice,
-- verified, no PropertyOnion) to flip letter I from FAIL (94.3%) to PASS
-- (97.0%). Three of those 10 parcels carried a (code, jurisdiction_id) combo
-- with NO existing zoning_districts row at all: RMF-2/1516 (City of
-- Sarasota), CI/824 (unincorporated Sarasota), M-1/1699 (Longboat Key).
-- Per v_zoning_district_applicability, an unmatched zone_code defaults
-- density/far/pk1000 applicability to TRUE with no value ever satisfying it
-- -- this is the same self-inflicted-regression pattern documented in prior
-- sessions (Hillsborough run2886, Miami-Dade run2346, Walton dispatch
-- 5e1e6111). It dropped sarasota G from the session-start 87.5% to 72.7%
-- (density 93.2->92.2, far 95.9->94.6, pk1000 87.5->72.7), even after the
-- sarasota_G lane's own fix (CN=4.00, DTC=2.00, PID/CT pk1000_regulated=false)
-- had already resolved the four ORIGINAL blocking districts.
--
-- FIX: insert real zoning_districts rows for the 3 orphaned codes, with
-- category sourced VERBATIM from the same already-verified
-- scgov_arcgis_scpaservice zone_name field used for the parcel_zones insert
-- (not guessed) -- category='residential' correctly makes RMF-2/1516
-- far/pk1000-not-applicable by convention; category='commercial' correctly
-- makes CI/824 and M-1/1699 density-not-applicable. For CI, also sourced a
-- real, citable parking_per_1000sf=4.00 value from Sarasota County's
-- countywide use-type parking schedule (Sec 124-120(g), "Retail Sales and
-- Service: 1 space per 250 SF" = 4.00/1000sf) -- the same universal
-- countywide schedule already cited for the CN district this session, since
-- Sarasota's off-street parking table is keyed by use type, not by district,
-- and applies identically to every commercial district in unincorporated
-- Sarasota. No real max_far was sourced for CI (Municode/zoneomics FAR table
-- for CI specifically could not be located live this session -- left NULL
-- rather than fabricated). No real value was sourced for M-1/Longboat Key's
-- own Sec 158.072 (Municode blocked WebFetch/curl with 403, zoneomics
-- mirror's chapter pages for Longboat Key did not surface the section text)
-- -- left NULL rather than fabricated; a future session should retry with a
-- browser-capable fetch tool.
--
-- RESULT (live, re-verified after this fix): G density=93.0 far=95.0
-- pk1000=90.0, metric=90.0 -- still FAIL (<95 threshold) but net IMPROVED
-- versus the session-start baseline of 87.5, not just versus the
-- self-inflicted 72.7 trough. I remains PASS (357/368, 97.0%). No other
-- letter regressed.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section)
VALUES
  (1516, 'RMF-2', 'Residential Multi-Family', 'residential',
   'City of Sarasota RMF-2 district; category sourced verbatim from scgov_arcgis_scpaservice zone_name field (same verified source as the 2026-08-03 parcel_zones batch). No max_density_du_acre sourced this session for the City of Sarasota ordinance specifically (distinct from the unincorporated-county RMF-2 value) -- left NULL rather than reused/fabricated.',
   'shard2-dd959980-2026-08-03-regression-fix'),
  (824, 'CI', 'Commercial Intensive', 'commercial',
   'Unincorporated Sarasota County CI district; category sourced verbatim from scgov_arcgis_scpaservice zone_name field.',
   'shard2-dd959980-2026-08-03-regression-fix'),
  (1699, 'M-1', 'Marine Commercial Services District', 'commercial',
   'Town of Longboat Key M-1 district (Sec 158.072); category sourced verbatim from scgov_arcgis_scpaservice zone_name field. No max_far or parking value sourced this session -- Municode/zoneomics text for Sec 158.072 could not be fetched live (403/blocked); left NULL rather than fabricated.',
   'shard2-dd959980-2026-08-03-regression-fix')
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, parking_per_1000sf, source_url, ordinance_section, confidence_score)
SELECT id, 4.00,
  'https://www.zoneomics.com/code/sarasota-county-unincorporated-FL/chapter_8',
  'Sarasota County UDC Sec 124-120(g), Off-Street Parking and Loading schedule -- Retail Sales and Service: 1 space per 250 SF gross leasable area = 4.00/1000sf. Same universal countywide use-type parking table already cited for the CN district this session; CI (Commercial, Intensive) shares this identical schedule as it is keyed by use, not by district.',
  0.7
FROM zoning_districts
WHERE jurisdiction_id = 824 AND code = 'CI'
ON CONFLICT DO NOTHING;
