-- issue #19829 P1 — persisted chats + search (Claude.ai UI parity, phase 1)
--
-- New tables: public.biddeed_chat_conversations, public.biddeed_chat_messages,
-- public.biddeed_chat_uploads.
--
-- DEVIATION 1 — schema: the issue body (quoting a missing architecture doc,
-- docs/design/BIDDEED_CLAUDE_UI_PARITY_ARCHITECTURE.md, confirmed not to exist
-- anywhere in this repo) calls for "new schemas chat, deal, artifacts, skills,
-- connectors". A dedicated `chat` schema was created and then dropped in this
-- same migration series after live verification showed this Supabase
-- project's PostgREST "exposed schemas" list is {public, graphql_public,
-- pascal, geo_tracker, finance, winnerdata} and does NOT include `chat`.
-- Confirmed live with BOTH the anon key and the service_role key against
-- Accept-Profile: chat -> PGRST106 "Invalid schema: chat" in both cases (this
-- restriction is enforced ahead of role permissions — service_role does not
-- bypass it). The Worker only ever talks to Postgres over PostgREST (direct
-- psql is a known-broken credential path in this environment), so a table in
-- an unexposed schema would be permanently unreachable from production code.
-- Adding `chat` to the exposed-schema list is a project Settings > API change
-- outside this session's authority. Using `public` matches every other table
-- this Worker already reads (multi_county_auctions, lead_profiles, etc.).
--
-- DEVIATION 2 — naming: the obvious prefix `chat_*` (chat_conversations,
-- chat_messages, chat_uploads) collides with a PRE-EXISTING, unrelated table
-- set already in public: chat_messages, chat_uploads, chat_sessions,
-- chat_reconciliation, chat_ground_truth, chat_rate_limit — an internal CC
-- session-analytics system (columns like task_id, domain,
-- adhd_interventions_triggered; nothing to do with biddeed.ai end-user chat).
-- A first migration attempt using `chat_messages`/`chat_uploads` silently hit
-- `CREATE TABLE IF NOT EXISTS` against those pre-existing, differently-shaped
-- tables and failed loudly on the first dependent CREATE INDEX (column
-- conversation_id does not exist) rather than corrupting them — caught before
-- any write, nothing on the pre-existing tables was touched. Renamed to the
-- collision-free `biddeed_chat_*` prefix and re-verified no existing table
-- uses that name in any schema before applying. See docs/spec/19829-P1.md.
--
-- Identity: this app has no Clerk / Supabase Auth anywhere (confirmed via
-- grep — biddeed.ai is fully anonymous today). owner_email is bound
-- server-side by a signed session token (HMAC, see src/worker.js chat
-- identity helpers) — the DB never trusts a client-supplied email column
-- value directly; the Worker always derives owner_email from a verified
-- token before writing or reading.
--
-- Defense in depth: RLS is enabled with zero permissive policies
-- (default-deny for every role) AND anon/authenticated are not granted
-- privileges on top of that, so PostgREST cannot reach these tables under
-- any role except service_role, which only the Worker holds.

CREATE TABLE IF NOT EXISTS public.biddeed_chat_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_email text NOT NULL,
  title text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_chat_conversations_owner_idx ON public.biddeed_chat_conversations (owner_email, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.biddeed_chat_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES public.biddeed_chat_conversations(id) ON DELETE CASCADE,
  owner_email text NOT NULL,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,
  search_vec tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_chat_messages_conversation_idx ON public.biddeed_chat_messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS biddeed_chat_messages_owner_idx ON public.biddeed_chat_messages (owner_email);
CREATE INDEX IF NOT EXISTS biddeed_chat_messages_search_idx ON public.biddeed_chat_messages USING gin (search_vec);

CREATE TABLE IF NOT EXISTS public.biddeed_chat_uploads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid REFERENCES public.biddeed_chat_conversations(id) ON DELETE SET NULL,
  owner_email text NOT NULL,
  storage_path text NOT NULL,
  filename text,
  mime_type text,
  extracted_text text,
  extraction_status text NOT NULL DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'ok', 'unsupported', 'failed')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_chat_uploads_conversation_idx ON public.biddeed_chat_uploads (conversation_id);
CREATE INDEX IF NOT EXISTS biddeed_chat_uploads_owner_idx ON public.biddeed_chat_uploads (owner_email);

ALTER TABLE public.biddeed_chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_chat_uploads ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.biddeed_chat_conversations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_chat_messages FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_chat_uploads FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.biddeed_chat_conversations TO service_role;
GRANT ALL ON public.biddeed_chat_messages TO service_role;
GRANT ALL ON public.biddeed_chat_uploads TO service_role;

-- Storage bucket for P1 uploads (private; Worker signs short-lived URLs).
INSERT INTO storage.buckets (id, name, public)
VALUES ('chat-uploads', 'chat-uploads', false)
ON CONFLICT (id) DO NOTHING;
