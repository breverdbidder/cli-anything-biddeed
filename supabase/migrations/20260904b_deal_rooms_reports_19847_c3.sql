-- issue #19847 C3 — Deal Rooms + Report side panel (Claude.ai Projects/Artifacts
-- parity), sub-task of #19829. Builds directly on the #19829 P1 chat identity
-- and persistence convention (public.biddeed_chat_* prefix, RLS default-deny,
-- service_role-only access, owner_email always derived server-side from a
-- verified X-Chat-Token — never trusted from the client body). See
-- docs/spec/19829-P1.md and supabase/migrations/20260904a_chat_persistence_19829_p1.sql
-- for the schema-exposure and naming-collision reasoning that applies here
-- unchanged (public schema only; chat schema is not in PostgREST's exposed
-- list).
--
-- New tables: public.biddeed_deal_rooms, public.biddeed_deal_room_items,
-- public.biddeed_reports, public.biddeed_share_links.
-- New storage bucket: artifacts (private; Worker signs short-lived download URLs).

CREATE TABLE IF NOT EXISTS public.biddeed_deal_rooms (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_email text NOT NULL,
  name text NOT NULL DEFAULT 'Untitled Room',
  county text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_deal_rooms_owner_idx ON public.biddeed_deal_rooms (owner_email, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.biddeed_deal_room_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id uuid NOT NULL REFERENCES public.biddeed_deal_rooms(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('conversation', 'report', 'upload', 'parcel')),
  ref_id text NOT NULL,
  added_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_deal_room_items_room_idx ON public.biddeed_deal_room_items (room_id, added_at DESC);

CREATE TABLE IF NOT EXISTS public.biddeed_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_email text NOT NULL,
  room_id uuid REFERENCES public.biddeed_deal_rooms(id) ON DELETE SET NULL,
  conversation_id uuid REFERENCES public.biddeed_chat_conversations(id) ON DELETE SET NULL,
  title text,
  version int NOT NULL DEFAULT 1,
  format text NOT NULL CHECK (format IN ('pdf', 'csv', 'json')),
  storage_path text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_reports_owner_idx ON public.biddeed_reports (owner_email, created_at DESC);
CREATE INDEX IF NOT EXISTS biddeed_reports_room_idx ON public.biddeed_reports (room_id);
CREATE INDEX IF NOT EXISTS biddeed_reports_conversation_idx ON public.biddeed_reports (conversation_id);

CREATE TABLE IF NOT EXISTS public.biddeed_share_links (
  token text PRIMARY KEY,
  report_id uuid NOT NULL REFERENCES public.biddeed_reports(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS biddeed_share_links_report_idx ON public.biddeed_share_links (report_id);

ALTER TABLE public.biddeed_deal_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_deal_room_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_share_links ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.biddeed_deal_rooms FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_deal_room_items FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_reports FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_share_links FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.biddeed_deal_rooms TO service_role;
GRANT ALL ON public.biddeed_deal_room_items TO service_role;
GRANT ALL ON public.biddeed_reports TO service_role;
GRANT ALL ON public.biddeed_share_links TO service_role;

-- Note: biddeed_share_links has zero permissive RLS policies like every other
-- table here, so PostgREST (anon/authenticated) cannot read it directly. The
-- public GET /r/:token route in src/worker.js reaches it only via the
-- Worker's service_role key, then serves the underlying report content itself
-- (not a client-side Supabase read) -- this is what makes /r/:token
-- server-rendered and safe to be genuinely public without granting anon
-- table access.

INSERT INTO storage.buckets (id, name, public)
VALUES ('artifacts', 'artifacts', false)
ON CONFLICT (id) DO NOTHING;
