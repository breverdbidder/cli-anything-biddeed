-- Gold Standard shard-8 (glades), run3713, 2026-07-11
--
-- DIAGNOSIS (re-verified live, this session, hands-on with a headless browser — not inferred):
-- Criterion A requires multi_county_auctions rows with sale_type IN ('foreclosure','tax_deed') for
-- county='glades'. Live count today: fc=0 td=0 (confirmed via pencil_dod_evaluate_county). Every other
-- letter except G is downstream of A by construction (B/C/D/E/F/H/I/J all key off multi_county_auctions
-- rows for glades, of which there are zero, anywhere — no PropertyOnion rows either).
--
-- All known channels re-checked and confirmed still dead end as of 2026-07-11:
--   1. glades.realforeclose.com / glades.realtaxdeed.com -> redirect to www.realauction.com (no tenant).
--   2. gladesclerk.com/foreclosures -> static "Coming Soon" placeholder (WebFetch + Playwright headless
--      chromium both confirm, byte-identical conclusion to 2026-07-10 session).
--   3. gladesclerk.com/tax-deeds -> links to library.municode.com JS SPA node, HTTP 403 to non-browser
--      fetch (ordinance text only, not a sale calendar/listing).
--   4. kofilequicklinks.com/gladesfl/ (Glades Clerk's own "Search Official Records Online" link) ->
--      NEW FINDING this session: this is a book/volume/page paper-index lookup tool (ASP.NET WebForms).
--      It has NO document-type or date-range search field at all -- confirmed by directly driving it with
--      Playwright/headless chromium (a real browser, not just curl) and enumerating every form control.
--      The only "Index Book Type" option is "General Index" covering years 1921-1988. There is no
--      CERTIFICATE OF TITLE / TAX DEED search surface here, browser or no browser. Registered in
--      clerk_platform_adapters as platform='kofile', adapter_status='needs_build' -- confirmed correctly
--      un-built; building it would not help Glades regardless (the field doesn't exist).
--   5. myfloridacounty.com/orisearch/22 -> NEW FINDING this session: DOES have a real document-type +
--      instrument-type + date-range search form (documentTypeID, instrumentTypeID, startDate/endDate),
--      but any POST to the search endpoint is now gated by a Cloudflare Turnstile CAPTCHA ("Please verify
--      you are human"), confirmed by direct Playwright submission. Not automatable without CAPTCHA-solving,
--      which is out of scope/not attempted.
--   6. civitekflorida.com/ocrs/county/22/ -> NEW FINDING this session: a JSF/PrimeFaces case-docket search
--      (public/attorney/registered-user tiers), not a document-type search; no JSON/REST API surfaced
--      (grepped for /api/, /services/, .json -- zero matches). Would require already knowing a case number.
--   7. bid4assets.com -> searched, zero Glades County listings found (other small FL counties do list here;
--      Glades does not).
--
-- CONCLUSION: Glades County publishes zero foreclosure/tax-deed auction data through any online channel
-- today. Sales are in-person courthouse-only. This is a genuine data-availability blocker, not a scraper
-- gap -- there is nothing to scrape. Per HONESTY PROTOCOL / HARD GUARDRAILS, no synthetic/estimated rows
-- are written. No letter metric is claimed to move this session.
--
-- FORWARD LEVER: the one legitimate unlock is detecting the day gladesclerk.com's "Coming Soon" placeholder
-- is replaced with a real list (per 2026-06-24 session note). That has been manually re-checked by hand
-- across four separate sessions (06-24, 07-05, 07-10, 07-11). This migration converts that manual check
-- into an automated, scheduled, alerting watcher so future sessions stop re-deriving this diagnosis and
-- instead get a Telegram alert the moment it changes.

CREATE TABLE IF NOT EXISTS public.county_page_watch (
  id bigserial PRIMARY KEY,
  county_slug text NOT NULL,
  label text NOT NULL,
  url text NOT NULL,
  placeholder_pattern text NOT NULL,
  content_hash text,
  placeholder_present boolean,
  last_checked_at timestamptz,
  last_changed_at timestamptz,
  last_http_status int,
  notes text,
  UNIQUE (county_slug, url)
);

COMMENT ON TABLE public.county_page_watch IS
  'Generic content-hash watcher for county source pages stuck on a static "no data yet" placeholder. '
  'Built for glades A-blocker (shard-8 run3713, 2026-07-11); reusable by any shard hitting the same '
  'gladesclerk.com-style "Coming Soon" dead end -- add a row instead of re-deriving a new pipeline.';

INSERT INTO public.county_page_watch (county_slug, label, url, placeholder_pattern, notes)
VALUES
  ('glades', 'foreclosure calendar', 'https://gladesclerk.com/foreclosures/', 'Coming Soon',
   'A-blocker: in-person courthouse sales only, no online list published, re-verified 2026-07-11'),
  ('glades', 'tax deed calendar', 'https://gladesclerk.com/tax-deeds/', 'Coming Soon',
   'links to Municode JS SPA node (403 to non-browser fetch); page itself carries no inline sale list')
ON CONFLICT (county_slug, url) DO NOTHING;

CREATE OR REPLACE FUNCTION public.county_page_watch_tick()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'extensions'
AS $$
DECLARE
  r record;
  v_resp extensions.http_response;
  v_hash text;
  v_placeholder_present boolean;
  v_changed_count int := 0;
  v_checked_count int := 0;
BEGIN
  FOR r IN SELECT * FROM public.county_page_watch LOOP
    BEGIN
      SELECT * INTO v_resp FROM extensions.http_get(r.url);
    EXCEPTION WHEN OTHERS THEN
      UPDATE public.county_page_watch
        SET last_checked_at = now(), last_http_status = -1
        WHERE id = r.id;
      CONTINUE;
    END;
    v_checked_count := v_checked_count + 1;
    v_hash := md5(COALESCE(v_resp.content, ''));
    v_placeholder_present := COALESCE(v_resp.content, '') ILIKE ('%' || r.placeholder_pattern || '%');

    IF r.placeholder_present = true AND v_placeholder_present = false THEN
      v_changed_count := v_changed_count + 1;
      PERFORM public.fire_workflow_dispatch(
        'breverdbidder/cli-anything-biddeed', 'telegram-notify.yml', 'main',
        jsonb_build_object('message', format(
          'COUNTY WATCH: %s %s placeholder cleared -- %s now shows content, re-check criterion A immediately',
          r.county_slug, r.label, r.url))
      );
    END IF;

    UPDATE public.county_page_watch
      SET last_checked_at = now(),
          last_http_status = v_resp.status,
          last_changed_at = CASE WHEN r.content_hash IS DISTINCT FROM v_hash THEN now() ELSE r.last_changed_at END,
          content_hash = v_hash,
          placeholder_present = v_placeholder_present
      WHERE id = r.id;
  END LOOP;
  RETURN jsonb_build_object('checked', v_checked_count, 'changed_alerts_fired', v_changed_count);
END;
$$;

SELECT cron.schedule('county-page-watch-daily', '17 13 * * *', $$SELECT public.county_page_watch_tick();$$);
