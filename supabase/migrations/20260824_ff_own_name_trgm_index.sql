-- Daily FF pipeline Sprint 2b (Tracerfy skip-trace) matches a buyer's
-- entity_name against fl_parcels.own_name via a leading-wildcard ILIKE to
-- find their prior-deed mailing address. fl_parcels has 10.5M rows and, until
-- now, only a Duval-scoped (co_no=26) trigram index existed
-- (idx_fl_parcels_duval_ownname_trgm) -- every other county's lookup was a
-- full sequential scan, which timed out live in this session's first real
-- Sprint 2b run. This is the statewide equivalent, so the daily pipeline
-- doesn't silently mislabel a query timeout as "no mailing address on file"
-- (a real ceiling) when it is actually just an unindexed scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fl_parcels_ownname_trgm
    ON public.fl_parcels USING gin (upper(own_name) gin_trgm_ops)
    WHERE own_name IS NOT NULL;
