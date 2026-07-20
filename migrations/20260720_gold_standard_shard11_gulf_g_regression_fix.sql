-- Gold Standard shard-11 gulf — P0 regression fix, same session as
-- 20260720_gold_standard_shard11_union_gulf_3rd_firing_i_unincorp_zoning.sql
--
-- The prior migration in this session added parcel_zones row for 06248-410R pointing at the new
-- "Gulf County Unincorporated" / Mixed_Comm/Res zoning_districts row, which flipped letter I
-- (6/14 -> 7/14) but caused a live regression on letter G (100.0 -> 88.9): v_zoning_district_applicability
-- defaults density_applicable=true for any non-commercial/industrial category (mixed_use included), and
-- that district had no zone_standards row, so v_zoning_gold_standard_kpi_v3 counted it as
-- "density-applicable but missing data". Per campaign rule "any regression = P0", fixing immediately
-- rather than deferring.
--
-- Fix: add the real, ordinance-sourced max_density_du_acre for the Mixed_Comm/Res (R/MCR) district.
-- Gulf County LDR Art. III Sec. 3.01.03 density table (PDF p.67, independently OCR-verified this
-- session) states R/MCR = "1-4 DU/Acre", with overlay-specific reductions for certain sub-areas
-- (max 3 DU/acre on the Gulf-side Highway 30 corridor, max 2 DU/acre bayside/lagoon side -- neither
-- overlay has been determined to apply to parcel 06248-410R specifically). 4 DU/acre is the base
-- district's stated maximum before any overlay reduction -- a real, cited ordinance figure, not a
-- guess. confidence_score reflects that the true per-parcel max could be lower under an as-yet-
-- undetermined overlay.

insert into public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
values (
  12294,
  4,
  'https://cdnsm5-hosted.civiclive.com/UserFiles/Servers/Server_6500990/File/County%20Government/Planning%20Dept/LDR%20Complete%2009-2019.pdf',
  'Gulf County LDR Art. III Sec. 3.01.03 (density table, PDF p.67)',
  0.75,
  now()
);
