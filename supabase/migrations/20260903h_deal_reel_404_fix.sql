-- Issue #19796 (P0) -- /deal/:county/:case and /reels/:code both 404 live.
--
-- Root cause #1: get_reel_landing()/get_reel_by_code() both refuse to
-- render a pending_approval row unless the caller passes ?preview=<row id>.
-- All 23/23 live winnerdata.biddeed_reels rows are pending_approval (there
-- is no approval-flip mechanism in this codebase for this table, unlike
-- winnerdata.ff_batches -- see docs/gtm/META.md M8), so every plain
-- /deal/... or /reels/... visit -- which is exactly what a scanned QR code
-- or CTA-chip click produces -- 404s. M8 ("no publish step touched") is
-- about never writing winnerdata.biddeed_reels.status; it says nothing
-- about the page-render gate, and the gate as originally built makes any
-- already-rendered reel's on-screen promise permanently false. Fix: drop
-- the preview-id requirement so pending_approval renders same as
-- approved/posted (still carries its own "PREVIEW -- pending approval, not
-- yet public" banner client-side, per buildDealLandingHtml/
-- buildSingleReelHtml -- that part is untouched). p_preview_id stays in
-- both signatures (worker.js still passes it) but no longer gates anything.
--
-- Root cause #2: agents/reel_studio/analyst.py::mint_variant_short_link()
-- mints short_code/short_url/qr_url for every winnerdata.reel_variants row
-- and bakes biddeed.ai/r/{code} into the rendered video's QR/CTA plate, but
-- never inserts the matching winnerdata.reel_links row that
-- resolve_reel_link()/get_reel_by_code() both require -- so every /r/{code}
-- and /reels/{code} for a variant-minted code 404s with zero rows found,
-- 21/21 confirmed live. This migration backfills the missing rows for the
-- 21 variants that exist today; the paired code change to
-- mint_variant_short_link() (this same commit) stops it recurring for the
-- next batch.
--
-- get_reel_landing() also gains `property_address` (winnerdata.
-- biddeed_reels.property_address -- a public county-record street address,
-- fine per M3, and populated 23/23 on the live rows) in its field
-- allow-list -- issue #19796 Part 1 lists "address" as one of the page's
-- minimum required fields and it was never in this function's SELECT list,
-- so buildDealLandingHtml()/buildPresaleDealHtml() had nothing to render.
--
-- Also repoints every reel-linked winnerdata.reel_links.target at
-- /reels/{code} (the clickable player page) instead of /deal/... directly,
-- per the issue's explicit instruction ("point the /r/<code> resolver at
-- THIS page") -- the player page itself carries a real <a> "View property"
-- link through to /deal/... (reelCardHtml, unchanged). Non-reel links
-- (reel_id is null, e.g. the /auctions short links) are untouched.

begin;

create or replace function public.get_reel_landing(p_county text, p_slug text, p_preview_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_row winnerdata.biddeed_reels%rowtype;
begin
  select * into v_row
  from winnerdata.biddeed_reels
  where lower(replace(county, '_', '-')) = lower(p_county)
    and public.slugify_case_number(case_number) = lower(p_slug)
    and status in ('pending_approval', 'approved', 'posted')
  limit 1;

  if not found then
    return null;
  end if;

  -- issue #19796: pending_approval no longer requires a matching
  -- p_preview_id to render -- see file header. p_preview_id is kept in the
  -- signature only so the existing worker.js call site (which still passes
  -- it) does not need to change.

  return jsonb_build_object(
    'id', v_row.id,
    'case_number', v_row.case_number,
    'county', v_row.county,
    'sale_type', v_row.sale_type,
    'auction_date', v_row.auction_date,
    'sold_amount', v_row.sold_amount,
    'assessed_value', v_row.assessed_value,
    'delta_pct', v_row.delta_pct,
    'condition_json', v_row.condition_json,
    'condition_score', v_row.condition_score,
    'aerial_tight_url', v_row.aerial_tight_url,
    'aerial_wide_url', v_row.aerial_wide_url,
    'street_url', v_row.street_url,
    'parcel_outline', v_row.parcel_outline,
    'status', v_row.status,
    'archetype', v_row.archetype,
    'short_code', v_row.short_code,
    'property_address', v_row.property_address
  );
end;
$$;

grant execute on function public.get_reel_landing(text, text, uuid) to anon, authenticated, service_role;

-- get_reel_by_code(): same preview-gate removal as get_reel_landing(),
-- PLUS prefers a winnerdata.reel_variants match (a specific bolt32 render
-- with its own baked-in title/QR/CTA) over the generic reel-level video, so
-- a per-variant code (Hvj4tq, wvs4hW, ...) plays the actual bolt32 MP4 that
-- code's QR was minted from, not just the reel's shared video_v2_url.
create or replace function public.get_reel_by_code(p_code text, p_preview_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_row winnerdata.biddeed_reels%rowtype;
  v_variant winnerdata.reel_variants%rowtype;
  v_has_variant boolean := false;
begin
  select * into v_variant
  from winnerdata.reel_variants
  where short_code = p_code
    and status in ('pending_approval', 'approved')
  limit 1;

  if found then
    v_has_variant := true;
    select * into v_row
    from winnerdata.biddeed_reels
    where id = v_variant.reel_id
      and status in ('pending_approval', 'approved', 'posted');
  else
    select r.* into v_row
    from winnerdata.biddeed_reels r
    join winnerdata.reel_links l on l.reel_id = r.id
    where l.code = p_code
      and r.status in ('pending_approval', 'approved', 'posted')
    limit 1;
  end if;

  if not found then
    return null;
  end if;

  return jsonb_build_object(
    'id', v_row.id, 'case_number', v_row.case_number, 'county', v_row.county,
    'sale_type', v_row.sale_type, 'auction_date', v_row.auction_date,
    'sold_amount', v_row.sold_amount, 'assessed_value', v_row.assessed_value,
    'delta_pct', v_row.delta_pct, 'condition_json', v_row.condition_json,
    'condition_score', v_row.condition_score, 'aerial_tight_url', v_row.aerial_tight_url,
    'video_v2_url', case when v_has_variant and v_variant.video_url is not null
                          then v_variant.video_url else v_row.video_v2_url end,
    'short_url', 'https://biddeed.ai/r/' || p_code,
    'landing_url', v_row.landing_url, 'status', v_row.status
  );
end;
$$;

grant execute on function public.get_reel_by_code(text, uuid) to anon, authenticated, service_role;

-- Backfill: one winnerdata.reel_links row per reel_variants short_code that
-- doesn't have one yet (root cause #2). target points at the clickable
-- player page for that exact code.
insert into winnerdata.reel_links (code, reel_id, target, utm_content)
select rv.short_code, rv.reel_id, 'https://biddeed.ai/reels/' || rv.short_code, rv.variant_key
from winnerdata.reel_variants rv
where rv.short_code is not null
  and not exists (select 1 from winnerdata.reel_links l where l.code = rv.short_code);

-- Repoint every existing reel-linked short link at its own player page
-- instead of straight to /deal/... (issue's explicit instruction). Links
-- with reel_id is null (e.g. the /auctions short links) are untouched.
update winnerdata.reel_links
set target = 'https://biddeed.ai/reels/' || code, updated_at = now()
where reel_id is not null
  and target <> 'https://biddeed.ai/reels/' || code;

-- Root cause #3, found only by live-curling (not by reading migration
-- filenames in date order -- they are NOT applied in that order; this
-- discovery correction is logged in docs/spec/19796.md per CC_META_PROMPT
-- 2.3). The function actually live before this migration is
-- 20260903c_reel_variant_studio.sql's resolve_reel_link(), which checks
-- winnerdata.reel_variants FIRST and, on a match, redirects straight to
-- v_variant.video_url -- the raw Supabase Storage MP4 -- exactly the
-- behavior issue #19796 reports and asks to be repointed at the player
-- page. The 20260903f/20260903g redefinitions of this same function
-- committed to this repo were never actually applied live; this
-- CREATE OR REPLACE supersedes whichever version is live now, so it is
-- authoritative going forward regardless of that history. Click-metrics
-- logging (winnerdata.reel_variant_metrics) is preserved unchanged.
create or replace function public.resolve_reel_link(p_code text)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_variant winnerdata.reel_variants%rowtype;
  v_row     winnerdata.reel_links%rowtype;
begin
  select * into v_variant
  from winnerdata.reel_variants
  where short_code = p_code;

  if found then
    insert into winnerdata.reel_variant_metrics (variant_id, day, platform, clicks)
    values (v_variant.id, current_date, 'short_link', 1)
    on conflict (variant_id, day, platform)
    do update set clicks = winnerdata.reel_variant_metrics.clicks + 1,
                  updated_at = now();

    -- issue #19796 PART 2: point at this code's own /reels/ player page
    -- (which resolves and plays v_variant.video_url itself via
    -- get_reel_by_code()), never straight at the raw MP4.
    return jsonb_build_object(
      'target', 'https://biddeed.ai/reels/' || p_code,
      'utm_source', 'reel_variant',
      'utm_medium', 'short_link',
      'utm_campaign', v_variant.variant_key
    );
  end if;

  update winnerdata.reel_links
  set clicks = clicks + 1, updated_at = now()
  where code = p_code
  returning * into v_row;

  if not found then
    return null;
  end if;

  return jsonb_build_object(
    'target', v_row.target,
    'utm_source', v_row.utm_source,
    'utm_medium', v_row.utm_medium,
    'utm_campaign', v_row.utm_campaign,
    'utm_content', v_row.utm_content
  );
end;
$$;

grant execute on function public.resolve_reel_link(text) to anon, authenticated, service_role;

commit;
