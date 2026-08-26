-- SummitLeads: hard guard against plaintiff/lender names reaching routing.
--
-- Incident (2026-08-26 00:15:36 UTC): the summitleads-daily.yml scheduled run
-- (cron '0 0 * * *', run 32914286666) executed SPRINT2 of
-- scripts/summitleads_pipeline.py -- a single set-based INSERT...SELECT that
-- promotes any non-placeholder-identity auction winner straight to
-- summitleads.leads with no check for whether the "winner" is actually the
-- foreclosing plaintiff/servicer taking the property back via credit bid.
-- 17 of the 21 leads created in that statement carry entity_name values like
-- FREEDOM MORTGAGE CORPORATION, U.S. BANK NATIONAL ASSOCIATION, WILMINGTON
-- SAVINGS FUND SOCIETY, FANNIE MAE, and the HUD Secretary -- lenders, not
-- buyer prospects. This was the real scheduled pipeline, not an ad hoc SQL
-- insert (verified: run timing 00:15:02-00:18:32 UTC brackets the 00:15:36
-- row timestamp exactly; both 2026-08-26 scheduled runs, 32914286666 and
-- 32929608761, are confirmed live in `gh run list`). Live-verified via the
-- Management API (summitleads schema isn't exposed through PostgREST) that
-- none of the 21 rows were ever routed or delivered -- both runs crashed
-- inside sprint3b_appraiser_verify() before reaching SPRINT4 (routing) or
-- sprint5_deliver() -- so no plaintiff/lender name actually reached Mariam
-- Shapira for this batch. That does not make the underlying gap safe: the
-- next pipeline run that completes past sprint3b would route and deliver
-- these 17 rows exactly as-is, since nothing upstream of SPRINT4 filters on
-- entity type. This migration closes that gap at the schema level so it does
-- not depend on any particular script's logic staying correct, and covers
-- any future ad hoc insert into summitleads.leads too.

alter table summitleads.leads
  add column if not exists is_lender_or_plaintiff boolean not null default false,
  add column if not exists manual_buyer_override boolean not null default false;

comment on column summitleads.leads.is_lender_or_plaintiff is
  'Auto-set by leads_tag_lender_or_plaintiff when entity_name matches a lender/plaintiff/servicer pattern. The lender/servicer took the property back at auction (credit bid) -- not a third-party buyer prospect. Routing is blocked for these unless manual_buyer_override is set after human review.';
comment on column summitleads.leads.manual_buyer_override is
  'Set true by a human after verifying a lead flagged is_lender_or_plaintiff is actually a legitimate buyer (e.g. an individual whose name happens to contain "trust" via a custodial IRA). Never set by automation.';

create or replace function summitleads.tag_lender_or_plaintiff()
returns trigger
language plpgsql
as $$
begin
  if new.entity_name ~* '(mortgage|bank|n\.a\.|national association|savings fund|loan servicing|trust\y|fannie mae|freddie mac|\yhud\y|department of housing|association)' then
    new.is_lender_or_plaintiff := true;
    new.consent_certificate := coalesce(new.consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD');
  end if;
  return new;
end;
$$;

drop trigger if exists leads_tag_lender_or_plaintiff on summitleads.leads;
create trigger leads_tag_lender_or_plaintiff
  before insert or update of entity_name on summitleads.leads
  for each row execute function summitleads.tag_lender_or_plaintiff();

-- Hard backstop: block routing a flagged lead, independent of which script
-- (or ad hoc session) tries to insert into routing_decisions. Fires per-row;
-- the pipeline's SPRINT4 query must exclude flagged leads itself so a single
-- flagged row in a batch doesn't abort routing for the rest of that batch.
create or replace function summitleads.block_lender_plaintiff_routing()
returns trigger
language plpgsql
as $$
declare
  v_flagged boolean;
  v_override boolean;
  v_entity text;
begin
  select is_lender_or_plaintiff, manual_buyer_override, entity_name
    into v_flagged, v_override, v_entity
  from summitleads.leads where lead_id = new.lead_id;

  if v_flagged and not v_override then
    raise exception 'summitleads.routing_decisions blocked: lead % (entity_name=%) is flagged is_lender_or_plaintiff -- the lender/servicer took the property back, not a buyer prospect. Set manual_buyer_override=true after human review to route anyway.',
      new.lead_id, v_entity;
  end if;
  return new;
end;
$$;

drop trigger if exists routing_decisions_block_lender_plaintiff on summitleads.routing_decisions;
create trigger routing_decisions_block_lender_plaintiff
  before insert on summitleads.routing_decisions
  for each row execute function summitleads.block_lender_plaintiff_routing();

-- Retroactive fix for item 5 of #19428's incident follow-up: tag (not
-- delete) the existing lender/plaintiff rows so they carry the compliance
-- flag and can never be auto-routed. Non-destructive -- these rows remain in
-- summitleads.leads as an honest signal-events audit trail; they are simply
-- excluded from ever reaching a producer.
update summitleads.leads
set is_lender_or_plaintiff = true,
    consent_certificate = coalesce(consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD')
where entity_name ~* '(mortgage|bank|n\.a\.|national association|savings fund|loan servicing|trust\y|fannie mae|freddie mac|\yhud\y|department of housing|association)'
  and is_lender_or_plaintiff = false;
