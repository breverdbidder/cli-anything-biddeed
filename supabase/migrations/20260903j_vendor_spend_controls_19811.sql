-- Issue #19811: Vercel cost-control incident (invoice D2LOTNWY-0007, $102.37 --
-- $20 Pro seat + $82.20 for 29,160 Build CPU Minutes ~=16h/day continuous building
-- + $0.17 other). Layer 3 (vendor audit) + layer 4 (standing overage guard).
--
-- Pre-flight finding: the issue's own text asserts "From finance.v_recurring_costs
-- the real recurring vendors include Anthropic, Supabase, Cloudflare, Vercel,
-- Hostaway, AgentQL, ElevenLabs, Railway, MindStudio, Manus, Tracerfy/Link.com,
-- Bright Data." A live grep of every committed migration in this repo for these
-- vendor names returned ZERO category_rules INSERTs -- but a live query against
-- finance.category_rules (via Management API) shows all of VERCEL, ANTHROPIC,
-- SUPABASE, CLOUDFLARE, HOSTAWAY, AGENTQL, ELEVENLABS, RAILWAY, MINDSTUDIO,
-- Manus, TRACERFY, and Link.com already exist as live patterns. Conclusion:
-- these rows were inserted directly against the live DB in a prior session
-- (Management-API pattern, per this repo's own documented workaround for
-- SUPABASE_DB_PASSWORD auth failing) without a matching migration file ever
-- being committed -- a real migration/live-DB drift, logged here rather than
-- silently re-created. Bright Data has NO category_rules pattern at all (zero
-- rows, any entity) -- either its charges never hit a linked bank account, or
-- they're falling into a generic/uncategorized bucket invisible to this table.
-- Flagged below as action_required, not silently assumed absent-from-ledger =
-- absent-from-spend.
--
-- Second finding, load-bearing for how the alert below is scoped: VERCEL's own
-- ledger rows are three $20.00-$20.88 charges (2026-03-18..2026-08-12) -- the
-- flat Pro seat, not the $82.20 metered overage line. The Aug 18 overage line
-- either posted to a different card/account not yet linked to SimpleFIN, or
-- had not synced as of this session's pull. This means a ledger-derived
-- "150% of trailing median" alert is a REAL but LAGGING control -- it can only
-- fire the day a charge posts to a bank account this system already ingests,
-- never before the charge is incurred. It is not a substitute for Vercel's own
-- Spend Management pre-emptive pause, which is dashboard-only (verified live
-- against vercel.com/docs/spend-management and vercel.com/docs/project-
-- configuration/vercel-json -- no API sets the spend-cap dollar amount itself,
-- only project pause/unpause and webhook wiring are exposed via REST).

begin;

-- ---------------------------------------------------------------------------------------------
-- 1. finance.vendor_spend_controls -- editorial (research-backed) facts about each metered
--    vendor's cap capability, refreshed by hand when a vendor's dashboard changes. Not something
--    SQL can derive on its own (cap_configured/cap_amount live in each vendor's own console).
-- ---------------------------------------------------------------------------------------------
create table finance.vendor_spend_controls (
  vendor text primary key,
  billing_model text not null check (billing_model in ('flat','metered','hybrid','prepaid_credits')),
  cap_configured boolean not null default false,
  cap_amount numeric,
  cap_mechanism text not null,             -- how a cap would actually be set for this vendor
  alert_configured boolean not null default false,
  ledger_charges_90d integer not null default 0,
  ledger_median_90d_dollars numeric,
  ledger_last_charge_dollars numeric,
  ledger_last_charge_date date,
  notes text not null,
  action_required text not null,
  last_reviewed_at timestamptz not null default now()
);

comment on table finance.vendor_spend_controls is
  'Issue #19811: per-vendor metered-overage risk register. ledger_* columns are read from '
  'finance.v_recurring_costs-style bank data (lagging signal); cap_configured/cap_amount/'
  'cap_mechanism are researched facts about each vendor''s own console, refreshed by hand.';

alter table finance.vendor_spend_controls enable row level security;
create policy cfo_agent_ro_select on finance.vendor_spend_controls for select to cfo_agent_ro using (true);
grant select on finance.vendor_spend_controls to cfo_agent_ro;
grant select on finance.vendor_spend_controls to service_role;

-- Read-only convenience view matching the finance.v_* naming convention used elsewhere in this
-- schema (finance.v_recurring_costs, finance.v_commingled_business_costs).
create or replace view finance.v_vendor_spend_controls
with (security_invoker = true) as
select * from finance.vendor_spend_controls order by
  case billing_model when 'metered' then 0 when 'hybrid' then 1 else 2 end,
  coalesce(ledger_median_90d_dollars, 0) desc;

grant select on finance.v_vendor_spend_controls to cfo_agent_ro;

-- ---------------------------------------------------------------------------------------------
-- 2. Seed data. ledger_* columns from a live query against finance.v_recurring_costs-equivalent
--    matched_expenses (Management API, 2026-09-03, filtered to the vendors this issue names).
--    cap_configured/cap_amount/cap_mechanism/notes are researched live against each vendor's
--    current (Sept 2026) docs -- cited inline, not carried over from training-data assumptions.
-- ---------------------------------------------------------------------------------------------
insert into finance.vendor_spend_controls
  (vendor, billing_model, cap_configured, cap_amount, cap_mechanism, alert_configured,
   ledger_charges_90d, ledger_median_90d_dollars, ledger_last_charge_dollars, ledger_last_charge_date,
   notes, action_required)
values
  ('Vercel', 'hybrid', false, null,
   'dashboard_only: Account/Team -> Settings -> Billing -> Spend Management -> set hard $ amount + "Pause Projects". No API sets the $ threshold (vercel.com/docs/spend-management, vercel.com/docs/project-configuration/vercel-json confirm ignoreCommand/pause-project are the only spend-adjacent API surfaces).',
   false, 3, 20.00, 20.88, '2026-08-12',
   'THE incident vendor. $20 Pro seat is flat; Build CPU Minutes, Function invocations/GB-hrs, '
   'bandwidth, ISR reads/writes are all metered with Spend Management OFF by default. Ledger only '
   'shows the flat $20 seat charge -- the $82.20 Aug overage line has not appeared in the bank '
   'feed this session, so the ledger alert below cannot substitute for the dashboard cap on this '
   'vendor specifically.',
   'HIGHEST PRIORITY: Ariel must set Spend Management manually on both the brevardbidderai@gmail.com '
   'personal account (the invoiced one) and the everestcapital8 team (Hobby). Additionally: workflow '
   'files reference at least 2 MORE Vercel team IDs never mentioned in the issue -- '
   'team_UEds2qBzyD9e7rOrX8aakj9K (zonewise-web prod, deploy-prod.yml) and '
   'team_hnNsngSBFPRmWAzVPkxTCMgu (pascal-625-ocean, pascal-track-a.yml). Each Vercel Team has its '
   'own independent billing -- confirm whether either of these IS the brevardbidderai billing '
   'account under a different display name, or is a third/fourth uncapped account.'),

  ('Anthropic', 'hybrid', false, null,
   'dashboard: console.claude.com -> Settings -> Limits -> organization + per-workspace monthly spend limits (USD). Per-user overrides also settable via the Spend Limits API (platform.claude.com/docs/en/manage-claude/spend-limits-api) -- org/workspace-level ceiling itself is dashboard-set, per-user overrides are API-settable on top of it.',
   false,
   53, 11.35, 40.19, '2026-09-01',
   'Explicitly named in the issue as one of the two biggest risks after Vercel. Ledger shows a '
   'burst of ~40 charges between $10-45 on 2026-07-28/29 (2 days) totalling several hundred dollars '
   '-- a metered-API consumption pattern, not a single monthly subscription line, despite CLAUDE.md '
   'stating "primary: Claude (Max plan, never API)". This burst is the closest ledger analogue to '
   'the Vercel build-storm pattern and deserves its own look independent of this session''s scope.',
   'Set an organization-level monthly spend limit in console.claude.com now (dashboard-only, no '
   'API call available for the org ceiling itself). Reconcile the 2026-07-28/29 burst against '
   'CLAUDE.md''s "never API" policy -- if that was Claude Code/API usage rather than Max-plan '
   'seats, the policy is not holding.'),

  ('Supabase', 'hybrid', true, null,
   'dashboard: Organization -> Settings -> Billing -> Spend Cap toggle. Pro plan defaults Spend Cap ON (blocks overage service-side instead of charging) -- but Spend Cap is binary block/allow with NO configurable dollar threshold and NO alert-before-block (github.com/orgs/supabase/discussions/14356; supabase.com/docs/guides/platform/billing-faq).',
   false, 3, 108.43, 153.63, '2026-08-31',
   'Named as the other top-2 risk. cap_configured=true is an ASSUMPTION that this org still has the '
   'Pro-plan default Spend Cap ON (never manually disabled) -- NOT independently verified this '
   'session (no Supabase Management API endpoint exposes this billing toggle; would need a live '
   'dashboard check). If Spend Cap has ever been toggled OFF to pay for overage, this vendor is '
   'actually uncapped today.',
   'CONFIRM (dashboard, 2 minutes): Organization Settings -> Billing -> Spend Cap is ON for the '
   'mocerqjnksmhcjzxrewo project''s org. If already ON, this vendor needs no further action -- '
   'Supabase''s cap has no configurable amount to tune. If OFF, turn it ON immediately.'),

  ('Cloudflare', 'hybrid', false, null,
   'dashboard: Manage Account -> Billing -> Billable Usage -> Create budget alert (launched 2026-04-13, developers.cloudflare.com/billing/manage/budget-alerts/). Alert-only -- fires an email when projected spend crosses a threshold; does NOT pause anything automatically. Separate AI Gateway spend-limit feature exists for AI Gateway specifically, not general Workers/R2/Pages usage.',
   false, 1, 10.46, 10.46, '2026-08-24',
   'Low ledger spend today (2 charges since March), but PAYG Workers/R2/Images billing has no hard '
   'stop, only the new alert-after-the-fact.',
   'Add a Budget Alert at a conservative threshold (e.g. $25) via Billable Usage dashboard -- 5 min, '
   'no cost. No hard cap exists on this vendor at any price; alert is the only lever.'),

  ('Railway', 'metered', false, null,
   'CLI/dashboard: railway usage limit set --target workspace --soft <n> --hard <m> (added 2026-07-10, docs.railway.com/pricing/cost-control). Hard limit takes every workload offline at the ceiling; soft limit only alerts at 75%/90%.',
   false, 1, 5.00, 5.00, '2026-08-20',
   'Currently trivial spend ($5 once), but this is the one vendor in this table with a TRUE '
   'automatic hard-stop available and not yet configured.',
   'Run `railway usage limit set --target workspace --soft 20 --hard 40` (or similar) -- cheapest, '
   'highest-confidence fix in this entire table since Railway''s hard limit is a real kill switch, '
   'not just an alert.'),

  ('ElevenLabs', 'hybrid', false, null,
   'No spend-cap toggle found (flexprice.io/blog/elevenlabs-pricing-breakdown, oakgen.ai): credit '
   'plans (Free/Starter $6/Creator $22/Pro $99/Scale $299/Business $990) auto-bill per-model overage '
   'once the monthly credit allocation is exhausted, with unused credits rolling forward up to 2x '
   'quota. No documented way to hard-stop overage billing from continuing.',
   false, 1, 6.00, 6.00, '2026-08-07',
   'Single $6 charge in the ledger -- looks like Starter-tier or a one-off top-up, low current risk, '
   'but this vendor has no cap mechanism at all if TTS volume grows (reel/voice pipelines per '
   'CLAUDE.md''s biddeed_reels_v2 TTS work).',
   'No dashboard cap exists to configure. Only lever is this session''s new alert (150% of trailing '
   'median / new-vendor detection) plus manually downgrading/pausing the plan if usage grows.'),

  ('Hostaway', 'flat', true, null, 'flat monthly SaaS subscription -- no metered dimension found in vendor pricing pages.',
   false, 2, 168.00, 168.00, '2026-08-03',
   'Property-management SaaS, flat recurring fee ($168/mo observed) -- not a metered-overage risk '
   'in the sense this issue is about.',
   'None. Flat billing; a value change here would show up as a plan-tier change, not a surprise '
   'overage, and the new trailing-median alert still covers that case for free.'),

  ('AgentQL', 'metered', false, null,
   'No published self-serve spend-cap/budget-alert feature found in vendor docs as of this session''s research.',
   false, 0, null, 311.00, '2026-03-09',
   'Single $311 charge 6 months ago, zero charges in the trailing 90 days -- likely a one-time '
   'credit purchase (prepaid-style) rather than an active monthly meter. Lowest-confidence entry in '
   'this table (billing_model INFERRED from the single data point, not confirmed against a live '
   'vendor account).',
   'Low priority given zero recent activity. If usage resumes, re-run this table''s ledger refresh '
   'and check AgentQL''s current console for a budget feature before assuming none exists.'),

  ('MindStudio', 'metered', false, null,
   'No published self-serve spend-cap feature found in vendor docs as of this session''s research.',
   false, 4, 20.00, 20.00, '2026-08-28',
   'Small, fairly steady $20 charges (4 in 90 days) -- modest run-rate, no evidence of a runaway '
   'pattern yet.',
   'Low priority at current spend. Covered by the new trailing-median alert; no vendor-side cap '
   'found to configure.'),

  ('Manus', 'metered', false, null,
   'No published self-serve spend-cap feature found in vendor docs as of this session''s research.',
   false, 1, 10.00, 10.00, '2026-08-31',
   'Single $10 charge, most recent vendor to appear in the ledger (first_seen = last_seen = '
   '2026-08-31) -- exactly the "new vendor appearing" case the standing guard below is built to '
   'catch going forward.',
   'Low priority at current spend. This vendor is the live proof case for the new-vendor alert '
   'reason added to finance.daily_close in this migration.'),

  ('Tracerfy', 'prepaid_credits', true, null,
   'Prepaid credit balance, billed per successful hit ("misses cost nothing" per the Tracerfy MCP '
   'server''s own tool description) -- structurally cannot produce a surprise postpaid overage '
   'invoice the way Vercel/metered-API vendors can.',
   false, 0, null, null, null,
   'category_rules has a live TRACERFY pattern but zero matched ledger rows this session -- either '
   'credit top-ups are paid via a card/account not yet linked to SimpleFIN, or none have occurred '
   'in the ingested window. Structurally low risk regardless (prepaid).',
   'None for overage risk. If a top-up payment method should be tracked for cash-flow purposes, '
   'that is a separate ask from this issue''s "uncapped meter" concern.'),

  ('Bright Data', 'metered', false, null,
   'dashboard: control panel supports per-zone traffic- or dollar-based limits, evaluated every 15 '
   'minutes (not real-time) with 85%-of-balance email alerts (stationx.net/proxidize/thunderbit '
   'reviews, Sept 2026). A busy job can overshoot by up to ~15 minutes of usage before the limit '
   'takes effect -- treat as a soft/delayed cap, not instantaneous.',
   false, 0, null, null, null,
   'NO category_rules pattern exists for this vendor at all (checked live) -- distinct from '
   '"zero charges in the window" like Tracerfy/AgentQL. This vendor is currently INVISIBLE to '
   'finance.v_recurring_costs and to the new alert below, regardless of actual spend, until a '
   'category_rules row is added for it.',
   'TWO actions: (1) add a Bright Data category_rules pattern so its ledger visibility matches '
   'every other vendor in this table; (2) separately, set a per-zone dollar limit in the Bright '
   'Data control panel (evaluated every 15 min, not instant -- pair with alerting, not as a sole '
   'control for a fast-moving scrape job).')
on conflict (vendor) do update set
  billing_model = excluded.billing_model,
  cap_configured = excluded.cap_configured,
  cap_amount = excluded.cap_amount,
  cap_mechanism = excluded.cap_mechanism,
  ledger_charges_90d = excluded.ledger_charges_90d,
  ledger_median_90d_dollars = excluded.ledger_median_90d_dollars,
  ledger_last_charge_dollars = excluded.ledger_last_charge_dollars,
  ledger_last_charge_date = excluded.ledger_last_charge_date,
  notes = excluded.notes,
  action_required = excluded.action_required,
  last_reviewed_at = now();

-- ---------------------------------------------------------------------------------------------
-- 3. Standing guard (item 4 of the issue): extend finance.daily_close (#19765) so any single
--    vendor charge exceeding 150% of that vendor's trailing-3-month median, or any brand-new
--    vendor pattern, fires the existing _send_close_alert path same-day. This is a LAGGING,
--    ledger-based signal (see header note) -- it complements but does not replace the vendor-side
--    caps in finance.vendor_spend_controls above.
-- ---------------------------------------------------------------------------------------------
create or replace function finance.check_vendor_spend_anomalies(p_since date default (current_date - 1))
returns table(vendor text, reason text, charge_dollars numeric, median_90d_dollars numeric, occurrences_before integer)
language sql
security definer
stable
as $function$
  with matched_expenses as (
    select
      cr.pattern as vendor,
      bt.posted_on,
      p.debit_cents as amount_cents
    from finance.bank_transactions bt
    join finance.bank_accounts ba on ba.id = bt.bank_account_id
    join finance.bank_connections bc on bc.id = ba.connection_id
    join finance.journal_entries je on je.ref_table = 'finance.bank_transactions' and je.ref_id = bt.id
    join finance.postings p on p.entry_id = je.id and p.debit_cents > 0
    join finance.accounts a on a.id = p.account_id and a.type = 'EXPENSE' and a.entity_code = bc.entity_code
    join finance.category_rules cr on cr.id = (
      select r.id from finance.category_rules r
      where (r.entity_scope is null or r.entity_scope = bc.entity_code)
        and r.is_transfer = false
        and (r.direction = 'any' or r.direction = 'out')
        and r.match_field = 'name' and (bt.name ilike '%' || r.pattern || '%' or coalesce(finance.normalize_descriptor(bt.name),'') ilike '%' || r.pattern || '%')
      order by r.priority asc, r.id asc limit 1
    )
    where bc.status = 'simplefin'
  ),
  recent as (
    select vendor, posted_on, amount_cents
    from matched_expenses
    where posted_on >= p_since
  ),
  history as (
    select
      r.vendor,
      r.posted_on,
      r.amount_cents,
      (select count(*) from matched_expenses h
        where h.vendor = r.vendor and h.posted_on < r.posted_on and h.posted_on >= r.posted_on - interval '90 days') as occurrences_before,
      (select (percentile_cont(0.5) within group (order by h.amount_cents))::numeric from matched_expenses h
        where h.vendor = r.vendor and h.posted_on < r.posted_on and h.posted_on >= r.posted_on - interval '90 days') as median_before_cents
    from recent r
  )
  select
    h.vendor,
    case when h.occurrences_before = 0 then 'new_vendor_charge' else 'vendor_spend_over_150pct_median' end as reason,
    round(h.amount_cents / 100.0, 2) as charge_dollars,
    round(coalesce(h.median_before_cents, 0) / 100.0, 2) as median_90d_dollars,
    h.occurrences_before::integer
  from history h
  where h.occurrences_before = 0
     or (h.median_before_cents is not null and h.amount_cents > h.median_before_cents * 1.5)
  order by h.vendor;
$function$;

comment on function finance.check_vendor_spend_anomalies(date) is
  'Issue #19811 standing guard: charges posted on/after p_since that are either from a brand-new '
  'vendor (no matching charge in the trailing 90 days) or exceed 150% of that vendor''s trailing '
  '90-day median charge. Called by finance.daily_close(); lagging (fires the day the charge posts '
  'to a linked bank account), not a pre-charge block.';

-- Security-advisor finding (this session, live run against api.supabase.com/v1/projects/.../
-- advisors/security immediately after first applying this migration): a bare CREATE FUNCTION
-- defaults to PUBLIC EXECUTE, which PostgREST turns into anon/authenticated callability over
-- /rest/v1/rpc/check_vendor_spend_anomalies since finance is already in pgrst.db_schemas. Revoked
-- explicitly -- this function should only ever run from finance.daily_close() or service_role.
revoke all on function finance.check_vendor_spend_anomalies(date) from public;
grant execute on function finance.check_vendor_spend_anomalies(date) to service_role;

-- Wire into finance.daily_close: new step (g), same alert path as the existing FAILED/unbalanced/
-- uncategorized>25/simplefin-error reasons. Only the new step is added; every other line of
-- #19765's daily_close is unchanged (surgical, per Karpathy K3 in CLAUDE.md).
create or replace function finance.daily_close(p_from date default null)
returns jsonb
language plpgsql
security definer
as $function$
declare
  v_run_start timestamptz := clock_timestamp();
  v_run_at timestamptz := now();
  v_from date := coalesce(p_from, '2026-01-01'::date);
  v_synced_count bigint := 0;
  v_categorized_count integer := 0;
  v_posted_count integer := 0;
  v_drafts_count integer := 0;
  v_matched_count integer := 0;
  v_exceptions_open integer := 0;
  v_uncategorized_open integer := 0;
  v_unbalanced_count integer := 0;
  v_status text := 'VERIFIED';
  v_error text := null;
  v_alert_reasons text[] := '{}';
  v_pipeline_start timestamptz;
  v_proc record;
  v_recon record;
  v_recurring_count integer;
  v_commingled_count integer;
  v_vendor_anomaly record;
  v_vendor_anomaly_count integer := 0;
  v_summary jsonb;
  v_alert_result jsonb;
begin
  -- (a) SimpleFIN sync -- failure here does not abort the run (categorization/posting should
  -- still process whatever was already synced by an earlier tick), but IS reported/alerted.
  begin
    select coalesce(sum(inserted), 0) into v_synced_count from finance.simplefin_sync(7);
  exception when others then
    v_error := coalesce(v_error, '') || format('simplefin_sync: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons,
      case when sqlerrm ilike '%credential%' or sqlerrm ilike '%auth%'
        then 'simplefin_credential_error' else 'simplefin_sync_error' end);
  end;

  -- (b)+(c)+(f) categorize, post, balance-check -- rolled back together on imbalance.
  v_pipeline_start := clock_timestamp();
  begin
    for v_proc in select * from finance.process_bank_transactions(null) loop
      v_categorized_count := coalesce(v_proc.categorized, 0);
    end loop;

    select
      count(*) filter (where posted_at is not null),
      count(*) filter (where posted_at is null)
      into v_posted_count, v_drafts_count
      from finance.journal_entries
      where created_at >= v_pipeline_start;

    select count(*) into v_unbalanced_count from finance.assert_balanced();
    if v_unbalanced_count > 0 then
      raise exception 'daily_close: % unbalanced journal entries after posting -- aborting this run''s posting step', v_unbalanced_count;
    end if;
  exception when others then
    v_error := coalesce(v_error, '') || format('posting: %s; ', sqlerrm);
    v_status := 'FAILED';
    v_posted_count := 0;
    v_drafts_count := 0;
    v_categorized_count := 0;
    v_alert_reasons := array_append(v_alert_reasons, 'unbalanced_or_posting_error');
  end;

  -- (d) recon
  begin
    for v_recon in select * from finance.recon_run(null, v_from) loop
      v_matched_count := v_matched_count + coalesce(v_recon.matched, 0);
    end loop;
  exception when others then
    v_error := coalesce(v_error, '') || format('recon_run: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons, 'recon_run_error');
  end;

  select count(*) into v_exceptions_open from finance.recon_exceptions where status = 'open';
  select count(*) into v_uncategorized_open from finance.recon_exceptions where status = 'open' and reason = 'uncategorized';

  -- (e) verify the two cost views still compute without error (plain views -- "refresh" is a
  -- no-op by construction, so this step is a liveness check, not a materialized-view refresh).
  begin
    select count(*) into v_recurring_count from finance.v_recurring_costs;
    select count(*) into v_commingled_count from finance.v_commingled_business_costs;
  exception when others then
    v_error := coalesce(v_error, '') || format('cost_views: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons, 'cost_view_error');
  end;

  -- (g) NEW -- issue #19811 standing guard: any vendor charge posted since yesterday that is a
  -- brand-new vendor or exceeds 150% of its own trailing 90-day median.
  begin
    for v_vendor_anomaly in select * from finance.check_vendor_spend_anomalies(current_date - 1) loop
      v_vendor_anomaly_count := v_vendor_anomaly_count + 1;
      v_alert_reasons := array_append(v_alert_reasons, format(
        'vendor_spend_anomaly: %s %s $%s (trailing median $%s, %s prior occurrences)',
        v_vendor_anomaly.vendor, v_vendor_anomaly.reason, v_vendor_anomaly.charge_dollars,
        v_vendor_anomaly.median_90d_dollars, v_vendor_anomaly.occurrences_before));
    end loop;
  exception when others then
    v_error := coalesce(v_error, '') || format('vendor_spend_check: %s; ', sqlerrm);
    v_alert_reasons := array_append(v_alert_reasons, 'vendor_spend_check_error');
  end;

  -- Final re-check: assert_balanced() again post-recon (recon_run only inserts recon_matches,
  -- never postings, so this should be identical to the mid-pipeline check -- re-verified anyway
  -- rather than assumed).
  select count(*) into v_unbalanced_count from finance.assert_balanced();
  if v_unbalanced_count > 0 then
    v_status := 'FAILED';
    if not ('unbalanced_or_posting_error' = any(v_alert_reasons)) then
      v_alert_reasons := array_append(v_alert_reasons, 'unbalanced_after_recon');
    end if;
  end if;

  if v_status <> 'FAILED' and v_uncategorized_open > 25 then
    v_alert_reasons := array_append(v_alert_reasons, format('uncategorized_open=%s > 25', v_uncategorized_open));
  end if;

  v_summary := jsonb_build_object(
    'run_at', v_run_at,
    'status', v_status,
    'synced_count', v_synced_count,
    'categorized_count', v_categorized_count,
    'posted_count', v_posted_count,
    'drafts_count', v_drafts_count,
    'matched_count', v_matched_count,
    'exceptions_open', v_exceptions_open,
    'uncategorized_open', v_uncategorized_open,
    'unbalanced_count', v_unbalanced_count,
    'duration_ms', round(extract(epoch from (clock_timestamp() - v_run_start)) * 1000),
    'error', v_error,
    'alert_reasons', v_alert_reasons,
    'recurring_costs_rows', v_recurring_count,
    'commingled_costs_rows', v_commingled_count,
    'vendor_spend_anomalies', v_vendor_anomaly_count
  );

  insert into finance.cfo_daily_close (
    run_at, status, synced_count, categorized_count, posted_count, drafts_count,
    matched_count, exceptions_open, uncategorized_open, unbalanced_count, duration_ms, error
  ) values (
    v_run_at, v_status, v_synced_count, v_categorized_count, v_posted_count, v_drafts_count,
    v_matched_count, v_exceptions_open, v_uncategorized_open, v_unbalanced_count,
    round(extract(epoch from (clock_timestamp() - v_run_start)) * 1000)::integer, v_error
  );

  if v_status = 'FAILED' or array_length(v_alert_reasons, 1) > 0 then
    v_alert_result := finance._send_close_alert(v_status, v_summary, v_alert_reasons);
    v_summary := v_summary || jsonb_build_object('alert', v_alert_result);
  end if;

  return v_summary;
end;
$function$;

grant execute on function finance.daily_close(date) to service_role;

commit;
