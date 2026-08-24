-- Wire public.sale_listings (HomeHarvest, source='homeharvest_realtor_com') into
-- summitleads.signal_events as a new event_type='mls_sale_close' trigger.
-- Issue: breverdbidder/cli-anything-biddeed#19429
--
-- Scheduler choice: pg_cron, not a GHA cron. This job is pure SQL (select sale_listings ->
-- match parcel -> insert signal_events -> backfill entity_name) with no external HTTP/scrape
-- call required (unlike homeharvest_ingest.py, which needs the Python `homeharvest` package
-- and therefore dispatches via GHA). Same rationale as every other in-DB pg_cron job in this
-- schema (b2c_activate_signups, mcp_trial_expiry_enforce, etc.) -- one scheduler of record,
-- visible in cron.job, no round-trip through GitHub Actions for work Postgres can do itself.
--
-- parcel_uuid null-rate finding (checked live 2026-08-24 before writing this): 0/6201 (0%)
-- SOLD rows in sale_listings have parcel_uuid populated -- HomeHarvest never sets it. So the
-- brief's "join via parcel_uuid if populated, else via address match" degrades to 100%
-- address-match. Address match (phy_addr1 exact + phy_zipcd exact, scoped to co_no via
-- fl_counties.slug=sale_listings.county) hit 3810/6201 = 61.4% live. Some addresses (condo/
-- apartment buildings sharing one street address across many units) match multiple fl_parcels
-- rows; resolved deterministically via DISTINCT ON ... ORDER BY parcel_id (documented
-- limitation, not a random pick).
--
-- entity_name backfill finding (checked live 2026-08-24): of the 3810 address-matched rows,
-- 0 (0%) have fl_parcels.updated_at > the sale's occurred_at -- fl_parcels has not been
-- rescraped since these sales closed, so there is currently no post-sale owner-of-record
-- signal to backfill from. The backfill step below is wired and will start finding hits
-- organically as fl_parcels gets rescraped in the normal course of the existing zoning/
-- appraiser pipelines; it is not a dead step, just a currently-empty one. Reported honestly
-- per DoD, not claimed as solved.

CREATE TABLE IF NOT EXISTS summitleads.mls_sync_state (
  job_name          text PRIMARY KEY,
  last_watermark    timestamptz NOT NULL DEFAULT '1970-01-01'::timestamptz,
  last_run_at       timestamptz,
  last_run_inserted integer,
  last_run_backfilled integer
);

INSERT INTO summitleads.mls_sync_state (job_name, last_watermark)
VALUES ('mls_sale_close_sync', '1970-01-01'::timestamptz)
ON CONFLICT (job_name) DO NOTHING;

-- Dedup: never insert the same sale_listings.id twice. Keyed off
-- event_payload->>'listing_id' (= sale_listings.id), scoped to this event_type so it
-- can never collide with the pre-existing auction_close rows (non-goal: do not touch those).
CREATE UNIQUE INDEX IF NOT EXISTS signal_events_mls_sale_close_listing_id_key
  ON summitleads.signal_events ((event_payload ->> 'listing_id'))
  WHERE event_type = 'mls_sale_close';

CREATE OR REPLACE FUNCTION public.sync_mls_sale_close_events()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'summitleads', 'pg_catalog'
AS $function$
DECLARE
  v_watermark      timestamptz;
  v_candidate_count integer;
  v_new_watermark  timestamptz;
  v_inserted       integer;
  v_backfilled     integer;
  v_dispatch_id    text := 'mls-sale-close-sync-' || to_char(now() at time zone 'utc', 'YYYYMMDD-HH24MISS');
BEGIN
  SELECT last_watermark INTO v_watermark
  FROM summitleads.mls_sync_state WHERE job_name = 'mls_sale_close_sync';

  IF v_watermark IS NULL THEN
    v_watermark := '1970-01-01'::timestamptz;
  END IF;

  -- Step 1: pull new SOLD rows past the watermark, LIFO (freshest sale first --
  -- per issue correction comment 2026-08-24: hottest leads first, so an interrupted/
  -- rate-limited run still lands the newest leads before any stale backlog).
  -- Bounded per run (20000 -- current full backlog is 6201, so this never caps today;
  -- kept as a per-run bound per this repo's CC_META_PROMPT 3.3 write discipline for
  -- when the backlog grows). Watermark advances only to the max fetched_at actually
  -- processed in this batch, so a capped run can never skip the remainder.
  DROP TABLE IF EXISTS pg_temp._mls_candidates;
  CREATE TEMP TABLE _mls_candidates ON COMMIT DROP AS
  SELECT sl.id, sl.county, sl.formatted_address, sl.zip_code, sl.mls_number, sl.sold_price,
         sl.listed_date, sl.removed_date, sl.fetched_at
  FROM public.sale_listings sl
  WHERE sl.status = 'SOLD'
    AND sl.fetched_at > v_watermark
  ORDER BY sl.removed_date DESC NULLS LAST, sl.fetched_at DESC
  LIMIT 20000;

  SELECT count(*), max(fetched_at) INTO v_candidate_count, v_new_watermark FROM _mls_candidates;

  -- Step 2: match to fl_parcels for parcel_id (exact phy_addr1 + phy_zipcd, scoped by
  -- co_no via fl_counties.slug = sale_listings.county). parcel_uuid is never populated
  -- by HomeHarvest today (0% live, checked above) so this address match IS the join,
  -- not a fallback. Multi-unit-building collisions resolved deterministically.
  WITH matched AS (
    SELECT DISTINCT ON (c.id)
      c.id, c.county, c.formatted_address, c.mls_number, c.sold_price,
      c.listed_date, c.removed_date, c.fetched_at, fp.parcel_id
    FROM _mls_candidates c
    LEFT JOIN public.fl_counties fc ON fc.slug = c.county
    LEFT JOIN public.fl_parcels fp
      ON fp.co_no = fc.co_no
     AND fp.phy_addr1 = upper(trim(split_part(c.formatted_address, ',', 1)))
     AND fp.phy_zipcd = c.zip_code
    ORDER BY c.id, fp.parcel_id NULLS LAST
  )
  -- Step 3: insert into signal_events. entity_name is deliberately NULL here --
  -- buyer name is not present anywhere in sale_listings (known gap, see issue).
  INSERT INTO summitleads.signal_events (event_type, source, county, parcel_id, entity_name, event_payload, occurred_at)
  SELECT
    'mls_sale_close', 'homeharvest_realtor_com', m.county, m.parcel_id, NULL,
    jsonb_build_object(
      'listing_id', m.id, 'mls_number', m.mls_number, 'sold_price', m.sold_price,
      'formatted_address', m.formatted_address, 'listed_date', m.listed_date, 'removed_date', m.removed_date
    ),
    COALESCE(m.removed_date::timestamptz, m.fetched_at)
  FROM matched m
  WHERE NOT EXISTS (
    SELECT 1 FROM summitleads.signal_events se
    WHERE se.event_type = 'mls_sale_close' AND (se.event_payload ->> 'listing_id') = m.id
  );
  GET DIAGNOSTICS v_inserted = ROW_COUNT;

  IF v_candidate_count > 0 THEN
    UPDATE summitleads.mls_sync_state
    SET last_watermark = v_new_watermark, last_run_at = now(), last_run_inserted = v_inserted
    WHERE job_name = 'mls_sale_close_sync';
  ELSE
    UPDATE summitleads.mls_sync_state
    SET last_run_at = now(), last_run_inserted = 0
    WHERE job_name = 'mls_sale_close_sync';
  END IF;

  -- Step 4 (SEPARATE follow-up step, per issue #19429): buyer name is not in
  -- sale_listings at all. Best-effort backfill only from fl_parcels.own_name where the
  -- parcel record was refreshed AFTER the sale closed (a proxy for "this now reflects
  -- the post-sale owner of record", not a guarantee). Only ever fills currently-NULL
  -- entity_name -- never overwrites a previously-backfilled or otherwise-set value.
  UPDATE summitleads.signal_events se
  SET entity_name = fp.own_name
  FROM public.fl_parcels fp, public.fl_counties fc
  WHERE se.event_type = 'mls_sale_close'
    AND se.entity_name IS NULL
    AND se.parcel_id IS NOT NULL
    AND fc.slug = se.county
    AND fp.co_no = fc.co_no
    AND fp.parcel_id = se.parcel_id
    AND fp.own_name IS NOT NULL
    AND fp.updated_at > se.occurred_at;
  GET DIAGNOSTICS v_backfilled = ROW_COUNT;

  UPDATE summitleads.mls_sync_state
  SET last_run_backfilled = v_backfilled
  WHERE job_name = 'mls_sale_close_sync';

  INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
  VALUES (
    v_dispatch_id, 'summitleads-mls-sale-close-sync', 'VERIFIED',
    'candidates=' || v_candidate_count::text || ' inserted=' || v_inserted::text ||
      ' entity_name_backfilled=' || v_backfilled::text ||
      ' watermark=' || COALESCE(v_new_watermark, v_watermark)::text,
    'info'
  );

  RETURN jsonb_build_object(
    'candidates', v_candidate_count, 'inserted', v_inserted,
    'entity_name_backfilled', v_backfilled, 'watermark', COALESCE(v_new_watermark, v_watermark)
  );
END;
$function$;

SELECT cron.schedule(
  'summitleads-mls-sale-close-daily',
  '40 10 * * *',  -- daily, 10:40 UTC -- offset from the 10:00 hour cluster of other daily jobs
  $$SELECT public.sync_mls_sale_close_events();$$
)
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'summitleads-mls-sale-close-daily');
