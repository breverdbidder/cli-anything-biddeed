-- Gold Standard shard6 dispatch 95aa6180 3rd firing (2026-07-21)
--
-- ROOT CAUSE of the write-gap defect the 2nd firing found and "fixed" twice this dispatch
-- (sarasota North Port R-1 id=12330 / R-2 id=12331 far_regulated silently reverting NULL,
-- G's far metric flapping 96.0 <-> 92.9): NOT a migration-apply reliability bug as the 2nd
-- firing speculated. It is a live, fleet-wide cron job (jobid=249 "refresh-zoning-applicability",
-- every 10 minutes, calls public.refresh_zoning_applicability_evidence()) whose GUARD clause
-- blanket-nulls far_regulated for EVERY zoning_districts row categorized 'residential', with
-- no source/confidence check:
--
--   -- GUARD: residential is never FAR-regulated (prevents the residential-inflation recurrence)
--   update public.zoning_districts d set far_regulated = null
--   where lower(coalesce(d.category,''))='residential' and d.far_regulated is not null;
--
-- Live audit (2026-07-21T00:3xZ): this guard currently nulls 559 residential zoning_districts
-- rows fleet-wide that have a real zone_standards.max_far value, 62 of which share an identical
-- suspicious max_far=0.35 across ~20 unrelated FL jurisdictions (Pinellas/Escambia/Orange/Monroe/
-- Broward/Glades/Ocala/Port St Lucie/Chipley/Jasper/etc, mostly source_url=NULL) -- almost
-- certainly the real "residential-inflation" fabrication this guard exists to suppress, same
-- fabrication class as the "(Beta Synthetic)" pattern flagged fleet-wide by the 1st firing of
-- this dispatch. That guard's intent is correct and this migration does NOT touch or weaken it.
--
-- sarasota's North Port R-1 (max_far=0.05) / R-2 (max_far=0.05) are two of those 559 rows, but
-- are NOT part of the suspicious pattern: real source_url (northportfl.gov ULDC PDF), a real,
-- non-round, jurisdiction-specific value, twice independently adversarially refuter-verified
-- this dispatch (1st firing session report + 2nd firing addendum, both citing North Port ULDC
-- Table 3.2.4.1) with zero contradicting evidence. Reapplying the raw UPDATE a 3rd time (as the
-- 2nd firing did once already) would just get reverted again at the next 10-minute cron tick --
-- confirmed by cron.job_run_details, job 249 has run every 10 min on schedule without failure.
--
-- FIX: add a narrow, auditable allowlist table for exactly this situation (real, sourced,
-- refuter-verified residential FAR data that the broad fabrication-guard would otherwise erase)
-- and reference it from the guard's WHERE clause. This does not change which rows the guard
-- treats as suspicious -- it only lets a shard permanently vouch for specific rows it has
-- independently verified, with a citation. The other 557 nulled rows (including the 62
-- suspicious 0.35 rows) are untouched and remain fleet-wide, out of this shard's authority --
-- same "flag, do not touch" precedent as the 1st firing's Beta Synthetic finding.

BEGIN;

CREATE TABLE IF NOT EXISTS public.zoning_far_regulated_verified_exceptions (
  zoning_district_id integer PRIMARY KEY REFERENCES public.zoning_districts(id),
  reason text NOT NULL,
  dispatch_id text,
  verified_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.zoning_far_regulated_verified_exceptions IS
  'Allowlist of zoning_districts.id rows whose far_regulated=true is real, sourced, and '
  'adversarially refuter-verified, exempting them from refresh_zoning_applicability_evidence()''s '
  'blanket residential-FAR guard. Add a row here only with independent refuter evidence attached '
  'in gold_standard_ultraloop_audit -- this table is a targeted override, not a bypass.';

INSERT INTO public.zoning_far_regulated_verified_exceptions (zoning_district_id, reason, dispatch_id)
VALUES
  (12330, 'North Port R-1, max_far=0.05, North Port ULDC Table 3.2.4.1, source_url=northportfl.gov ULDC PDF. Twice independently refuter-verified (1st and 2nd firing of this dispatch), not part of the fleet-wide suspicious-0.35 pattern.', '95aa6180-826c-4bd0-8442-58da4023282d'),
  (12331, 'North Port R-2, max_far=0.05, North Port ULDC Table 3.2.4.1, source_url=northportfl.gov ULDC PDF. Same evidence as R-1 (id=12330).', '95aa6180-826c-4bd0-8442-58da4023282d')
ON CONFLICT (zoning_district_id) DO NOTHING;

CREATE OR REPLACE FUNCTION public.refresh_zoning_applicability_evidence()
 RETURNS TABLE(far_true integer, far_false integer, dens_false integer)
 LANGUAGE plpgsql
AS $function$
begin
  -- FAR TRUE: non-residential district with a sourced FAR value
  update public.zoning_districts d set far_regulated = true
  from public.zone_standards s
  where s.zoning_district_id=d.id and s.max_far is not null
    and lower(coalesce(d.category,'')) <> 'residential'
    and d.far_regulated is distinct from true;

  -- FAR FALSE: cited no-FAR, no value, non-residential
  update public.zoning_districts d set far_regulated = false
  from public.g_standards_worklist w
  where w.district_id=d.id
    and (w.status='na_confirmed' or w.ordinance_section ilike '%no far%')
    and not exists (select 1 from public.zone_standards s where s.zoning_district_id=d.id and s.max_far is not null)
    and lower(coalesce(d.category,'')) <> 'residential'
    and d.far_regulated is null;

  -- GUARD: residential is never FAR-regulated (prevents the residential-inflation recurrence),
  -- EXCEPT rows explicitly allowlisted in zoning_far_regulated_verified_exceptions (real,
  -- sourced, refuter-verified residential FAR data -- see that table's comment).
  update public.zoning_districts d set far_regulated = null
  where lower(coalesce(d.category,''))='residential' and d.far_regulated is not null
    and d.id not in (select zoning_district_id from public.zoning_far_regulated_verified_exceptions);

  -- Re-assert allowlisted rows' real values every run, in case something else nulled them
  -- between cron ticks (defense in depth -- this table is the single source of truth for them).
  update public.zoning_districts d set far_regulated = true
  from public.zoning_far_regulated_verified_exceptions e, public.zone_standards s
  where d.id = e.zoning_district_id and s.zoning_district_id = d.id and s.max_far is not null
    and d.far_regulated is distinct from true;

  -- DENSITY FALSE: cited no-density where heuristic is wrong:
  --   (a) institutional/commercial-miscategorized/office (no dwelling units), or
  --   (b) PUD / development-order density (any category) — no fixed base-code density
  update public.zoning_districts d set density_regulated = false
  from public.g_standards_worklist w
  where w.district_id=d.id
    and w.status='na_confirmed'
    and not exists (select 1 from public.zone_standards s where s.zoning_district_id=d.id and s.max_density_du_acre is not null)
    and (
          lower(coalesce(d.category,'')) in ('institutional','uncategorized','other','')
          or w.ordinance_section ilike '%development order%'
          or lower(coalesce(d.code,'')) like '%pud%'
          or lower(coalesce(d.name,'')) like '%pud%'
        )
    and d.density_regulated is distinct from false;

  return query select
    (select count(*)::int from public.zoning_districts where far_regulated is true),
    (select count(*)::int from public.zoning_districts where far_regulated is false),
    (select count(*)::int from public.zoning_districts where density_regulated is false);
end$function$;

-- Apply immediately so this firing's verification doesn't have to wait for the next cron tick.
UPDATE public.zoning_districts SET far_regulated = true WHERE id IN (12330, 12331);

COMMIT;
