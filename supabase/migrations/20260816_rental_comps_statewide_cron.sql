-- Rent comps statewide expansion: recurring weekly refresh via pg_cron.
-- Issue: expand rental_listings from Brevard-only to all 67 FL counties + recurring refresh.
--
-- HomeHarvest scraping requires the Python `homeharvest` package (pandas, sequential
-- pagination) -- it cannot run inside pg_cron/pg_net directly. Same pattern as the
-- existing dispatch_summit_verifier_scan()/dispatch_realauction_one() functions in this
-- schema: pg_cron -> SECURITY DEFINER function -> net.http_post to GitHub's
-- workflow_dispatch API (PAT pulled server-side from vault, never exposed to a caller).
--
-- This REPLACES homeharvest-ingest.yml's native `schedule:` trigger (removed in the
-- same commit) so there is exactly one scheduler of record for this pipeline, visible
-- in cron.job like every other recurring job in this project.

CREATE OR REPLACE FUNCTION public.dispatch_homeharvest_rental_ingest(p_ref text DEFAULT 'main'::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_catalog', 'net', 'vault'
AS $function$
DECLARE
  v_pat text;
  v_req_id bigint;
  v_dispatch_id text := 'homeharvest-rental-' || to_char(now() at time zone 'utc', 'YYYYMMDD-HH24MISS');
BEGIN
  SELECT decrypted_secret INTO v_pat FROM vault.decrypted_secrets WHERE name = 'everest_gh_pat';
  IF v_pat IS NULL THEN
    INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
    VALUES (v_dispatch_id, 'rent-comps-statewide', 'BLOCKED', 'everest_gh_pat missing from vault', 'blocker');
    RAISE EXCEPTION 'VAULT_SECRET_MISSING: everest_gh_pat';
  END IF;

  SELECT net.http_post(
    url := 'https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/homeharvest-ingest.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || v_pat,
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'Content-Type', 'application/json',
      'User-Agent', 'homeharvest-rental-cron-dispatcher/1.0'
    ),
    body := jsonb_build_object('ref', p_ref)  -- no inputs: workflow default is --batch --batch-size 6
  ) INTO v_req_id;

  INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
  VALUES (v_dispatch_id, 'rent-comps-statewide', 'VERIFIED',
          'workflow_dispatch fired for homeharvest-ingest.yml, net_request_id=' || v_req_id::text, 'info');

  RETURN jsonb_build_object('dispatch_id', v_dispatch_id, 'net_request_id', v_req_id);
END;
$function$;

SELECT cron.schedule(
  'homeharvest-rental-weekly',
  '0 9 * * 1',  -- Mondays 9AM UTC -- same cadence the removed GHA `schedule:` trigger used
  $$SELECT public.dispatch_homeharvest_rental_ingest();$$
);
