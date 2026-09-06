-- BidDeed.AI — public customer support tickets
-- Project: mocerqjnksmhcjzxrewo
-- Applied as tracked migrations `support_tickets_public_form_20260906`
-- and `support_admins_20260906`.
--
-- ADDITIVE ONLY. public.support_tickets already existed as an empty, unreferenced
-- stub (id, channel, user_id uuid, message, classification, auto_response,
-- github_issue_url, escalated_to, resolved_at, created_at) — zero rows, zero
-- functions/views/crons/FKs/code referencing it in either repo (verified
-- 2026-09-06). Those columns are KEPT: classification / auto_response /
-- escalated_to are the natural home for Deed's AI first response later.
--
-- Access model (house RLS rule, rls_gate_check baseline): RLS ON, NO anon or
-- authenticated policies. Every read/write goes through the Next.js API routes
-- in breverdbidder/biddeed-web using SUPABASE_SERVICE_ROLE_KEY, which is already
-- bound to the biddeed-web-production Worker. Clerk user ids are strings
-- ("user_…"), not uuids, so they live in clerk_user_id.
--
-- Email: no new secret anywhere. An AFTER INSERT trigger posts two Resend
-- emails through pg_net using the vault's existing resend_api_key (biddeed.ai
-- is a verified Resend sending domain). Fire-and-forget; a Resend failure never
-- fails the insert.

-- ---------------------------------------------------------------------------
-- 1. Columns
-- ---------------------------------------------------------------------------
ALTER TABLE public.support_tickets
  ADD COLUMN IF NOT EXISTS ticket_number  text,
  ADD COLUMN IF NOT EXISTS updated_at     timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS name           text,
  ADD COLUMN IF NOT EXISTS email          text,
  ADD COLUMN IF NOT EXISTS clerk_user_id  text,
  ADD COLUMN IF NOT EXISTS category       text NOT NULL DEFAULT 'other',
  ADD COLUMN IF NOT EXISTS priority       text NOT NULL DEFAULT 'normal',
  ADD COLUMN IF NOT EXISTS subject        text,
  ADD COLUMN IF NOT EXISTS status         text NOT NULL DEFAULT 'open',
  ADD COLUMN IF NOT EXISTS page_url       text,
  ADD COLUMN IF NOT EXISTS user_agent     text,
  ADD COLUMN IF NOT EXISTS plan_tier      text,
  ADD COLUMN IF NOT EXISTS metadata       jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS admin_notes    text;

ALTER TABLE public.support_tickets ALTER COLUMN channel SET DEFAULT 'web_support_form';

-- Constraints (table is empty, so these are safe to add directly)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'support_tickets_ticket_number_key') THEN
    ALTER TABLE public.support_tickets ADD CONSTRAINT support_tickets_ticket_number_key UNIQUE (ticket_number);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'support_tickets_category_check') THEN
    ALTER TABLE public.support_tickets ADD CONSTRAINT support_tickets_category_check
      CHECK (category IN ('billing','account','signal_report','auction_data','zoning','bug','feature','security','other'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'support_tickets_priority_check') THEN
    ALTER TABLE public.support_tickets ADD CONSTRAINT support_tickets_priority_check
      CHECK (priority IN ('low','normal','high','urgent'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'support_tickets_status_check') THEN
    ALTER TABLE public.support_tickets ADD CONSTRAINT support_tickets_status_check
      CHECK (status IN ('open','in_progress','waiting_on_customer','resolved','closed'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'support_tickets_email_check') THEN
    ALTER TABLE public.support_tickets ADD CONSTRAINT support_tickets_email_check
      CHECK (email IS NULL OR (email = lower(email) AND email ~ '^[^\s@]+@[^\s@]+\.[^\s@]+$'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_support_tickets_status     ON public.support_tickets (status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_email      ON public.support_tickets (email);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON public.support_tickets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_category   ON public.support_tickets (category);

COMMENT ON TABLE public.support_tickets IS
  'BidDeed.AI public support tickets (biddeed.ai/support). RLS on, no policies: service-role API only. Ticket numbers BD-YYYYMMDD-XXXX.';

-- ---------------------------------------------------------------------------
-- 2. Ticket number BD-YYYYMMDD-XXXX (BEFORE INSERT)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.support_tickets_assign_number()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
  candidate text;
  attempts  int := 0;
BEGIN
  IF NEW.ticket_number IS NOT NULL AND length(trim(NEW.ticket_number)) > 0 THEN
    RETURN NEW;
  END IF;
  LOOP
    candidate := 'BD-' || to_char(timezone('UTC', now()), 'YYYYMMDD') || '-'
                 || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 4));
    EXIT WHEN NOT EXISTS (SELECT 1 FROM public.support_tickets t WHERE t.ticket_number = candidate);
    attempts := attempts + 1;
    IF attempts > 20 THEN
      RAISE EXCEPTION 'could not allocate a unique support ticket_number';
    END IF;
  END LOOP;
  NEW.ticket_number := candidate;
  IF NEW.email IS NOT NULL THEN NEW.email := lower(trim(NEW.email)); END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_support_tickets_number ON public.support_tickets;
CREATE TRIGGER trg_support_tickets_number
  BEFORE INSERT ON public.support_tickets
  FOR EACH ROW EXECUTE FUNCTION public.support_tickets_assign_number();

-- ---------------------------------------------------------------------------
-- 3. updated_at / resolved_at (BEFORE UPDATE)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.support_tickets_touch()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
  NEW.updated_at := now();
  IF NEW.status IN ('resolved','closed') AND (OLD.status IS NULL OR OLD.status NOT IN ('resolved','closed')) THEN
    NEW.resolved_at := COALESCE(NEW.resolved_at, now());
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_support_tickets_touch ON public.support_tickets;
CREATE TRIGGER trg_support_tickets_touch
  BEFORE UPDATE ON public.support_tickets
  FOR EACH ROW EXECUTE FUNCTION public.support_tickets_touch();

-- ---------------------------------------------------------------------------
-- 4. Email notifications via Resend + pg_net (AFTER INSERT, fire-and-forget)
--    Internal copy -> hello@biddeed.ai (reply-to = customer)
--    Acknowledgement -> customer (reply-to = hello@biddeed.ai)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.support_tickets_notify()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, vault, net
AS $$
DECLARE
  v_key       text;
  v_from      text := 'BidDeed.AI Support <support@biddeed.ai>';
  v_inbox     text := 'hello@biddeed.ai';
  v_headers   jsonb;
  v_internal  bigint;
  v_customer  bigint;
  v_body      text;
BEGIN
  SELECT decrypted_secret INTO v_key
  FROM vault.decrypted_secrets WHERE name IN ('resend_api_key','RESEND_API_KEY') LIMIT 1;

  IF v_key IS NULL OR v_key = '' OR NEW.email IS NULL THEN
    UPDATE public.support_tickets
       SET metadata = metadata || jsonb_build_object('notify', jsonb_build_object('skipped', 'no resend key or email', 'at', now()))
     WHERE id = NEW.id;
    RETURN NEW;
  END IF;

  v_headers := jsonb_build_object('Authorization', 'Bearer ' || v_key, 'Content-Type', 'application/json');

  v_body := 'New BidDeed.AI support ticket ' || NEW.ticket_number || E'\n\n'
         || 'From: '     || COALESCE(NEW.name, '') || ' <' || NEW.email || '>' || E'\n'
         || 'Category: ' || NEW.category || E'\n'
         || 'Priority: ' || NEW.priority || E'\n'
         || 'Plan: '     || COALESCE(NEW.plan_tier, 'n/a') || E'\n'
         || 'Page: '     || COALESCE(NEW.page_url, 'n/a') || E'\n'
         || 'User: '     || COALESCE(NEW.clerk_user_id, 'anonymous') || E'\n'
         || 'Agent: '    || COALESCE(NEW.user_agent, 'n/a') || E'\n\n'
         || COALESCE(NEW.message, '') || E'\n\n'
         || 'Inbox: https://biddeed.ai/admin/support';

  BEGIN
    SELECT net.http_post(
      url := 'https://api.resend.com/emails',
      body := jsonb_build_object(
        'from', v_from,
        'to', jsonb_build_array(v_inbox),
        'reply_to', NEW.email,
        'subject', '[' || NEW.ticket_number || '] ' || NEW.category || ': ' || COALESCE(NEW.subject, '(no subject)'),
        'text', v_body
      ),
      headers := v_headers,
      timeout_milliseconds := 8000
    ) INTO v_internal;

    SELECT net.http_post(
      url := 'https://api.resend.com/emails',
      body := jsonb_build_object(
        'from', v_from,
        'to', jsonb_build_array(NEW.email),
        'reply_to', v_inbox,
        'subject', 'We received your request — ticket ' || NEW.ticket_number,
        'text',
          'Hi ' || COALESCE(NULLIF(trim(NEW.name), ''), 'there') || ',' || E'\n\n'
          || 'Thanks for contacting BidDeed.AI. Your ticket number is ' || NEW.ticket_number || '.' || E'\n\n'
          || 'Subject: ' || COALESCE(NEW.subject, '') || E'\n'
          || 'Category: ' || NEW.category || E'\n\n'
          || 'You can check its status any time at https://biddeed.ai/support using this ticket number and this email address. '
          || 'For instant answers on auctions, reports and billing, Deed is available 24/7 at https://biddeed.ai/chat.' || E'\n\n'
          || 'Reply to this email if you need to add anything.' || E'\n\n'
          || '— BidDeed.AI Support'
      ),
      headers := v_headers,
      timeout_milliseconds := 8000
    ) INTO v_customer;
  EXCEPTION WHEN OTHERS THEN
    UPDATE public.support_tickets
       SET metadata = metadata || jsonb_build_object('notify', jsonb_build_object('error', SQLERRM, 'at', now()))
     WHERE id = NEW.id;
    RETURN NEW;
  END;

  UPDATE public.support_tickets
     SET metadata = metadata || jsonb_build_object('notify', jsonb_build_object(
           'internal_request_id', v_internal, 'customer_request_id', v_customer, 'to', v_inbox, 'at', now()))
   WHERE id = NEW.id;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.support_tickets_notify() FROM public, anon, authenticated;

DROP TRIGGER IF EXISTS trg_support_tickets_notify ON public.support_tickets;
CREATE TRIGGER trg_support_tickets_notify
  AFTER INSERT ON public.support_tickets
  FOR EACH ROW EXECUTE FUNCTION public.support_tickets_notify();

-- ---------------------------------------------------------------------------
-- 5. Reply thread (schema only; UI later)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.support_ticket_replies (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id    uuid NOT NULL REFERENCES public.support_tickets(id) ON DELETE CASCADE,
  author_type  text NOT NULL CHECK (author_type IN ('customer','staff','deed')),
  author_email text,
  body         text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_support_ticket_replies_ticket ON public.support_ticket_replies (ticket_id, created_at);
COMMENT ON TABLE public.support_ticket_replies IS 'Reply thread for support_tickets. RLS on, no policies: service-role only.';

-- ---------------------------------------------------------------------------
-- 6. RLS — on, no policies (service_role bypasses). Explicit revokes.
-- ---------------------------------------------------------------------------
ALTER TABLE public.support_tickets        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_ticket_replies ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.support_tickets        FROM anon, authenticated;
REVOKE ALL ON public.support_ticket_replies FROM anon, authenticated;

-- ---------------------------------------------------------------------------
-- 7. Admin allowlist for /admin/support (migration support_admins_20260906)
--    A Clerk session whose verified email is listed here may read/update
--    tickets through /api/support-tickets-admin. No token to paste anywhere.
--    Edit by SQL only: RLS on, no policies.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.support_admins (
  email     text PRIMARY KEY CHECK (email = lower(email)),
  note      text,
  added_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.support_admins ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.support_admins FROM anon, authenticated;
COMMENT ON TABLE public.support_admins IS 'Emails allowed into biddeed.ai/admin/support (matched against verified Clerk emails). Service-role only.';

INSERT INTO public.support_admins (email, note)
VALUES ('everestcapital8@gmail.com', 'Ariel — founder')
ON CONFLICT (email) DO NOTHING;
