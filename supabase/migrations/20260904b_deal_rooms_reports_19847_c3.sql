-- issue #19847 C3 — Projects + Report side panel (Claude.ai Projects/Artifacts
-- parity), sub-task of #19829. Builds directly on the #19829 P1 chat identity
-- and persistence convention (public.biddeed_chat_* prefix, RLS default-deny,
-- service_role-only access, owner_email always derived server-side from a
-- verified X-Chat-Token — never trusted from the client body). See
-- docs/spec/19829-P1.md and supabase/migrations/20260904a_chat_persistence_19829_p1.sql
-- for the schema-exposure and naming-collision reasoning that applies here
-- unchanged (public schema only; chat schema is not in PostgREST's exposed
-- list).
--
-- Renamed from "Deal Rooms" to "Projects" per the 2026-09-04 15:40 UTC scope
-- update on issue #19847 (Ariel): a project is one property/bid the customer
-- is working toward, carrying the 5 Sticky Layers
-- (docs/gtm/CTA_AND_STICKY_SPEC.md). This filename is kept unchanged from the
-- original C3 PR — it has never been applied to production (file-only, per
-- this issue's explicit "NEVER apply DDL to production from the runner"
-- instruction) — only its contents were revised in the JUDGE VERDICT fix pass.
--
-- New tables: public.biddeed_projects, public.biddeed_project_items,
-- public.biddeed_project_files, public.biddeed_reports, public.biddeed_share_links.
-- New storage bucket: artifacts (private; Worker signs short-lived download URLs;
-- also holds project files under `{project_id}/{filename}.v{n}`).

CREATE TABLE IF NOT EXISTS public.biddeed_projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_email text NOT NULL,
  name text NOT NULL DEFAULT 'Untitled Project',
  county text,
  case_number text,
  parcel_id text,
  sale_date date,
  notes text,
  -- S4: the project's own chat thread — created lazily on first message sent
  -- with this project's id, then reused (never re-created).
  conversation_id uuid REFERENCES public.biddeed_chat_conversations(id) ON DELETE SET NULL,
  -- S5 memory: write-once at creation (source page/reel intent), used to
  -- answer "how did this project start" without a separate audit table.
  first_touch jsonb,
  -- S1 persistent context: advanced on every GET of this project; the diff
  -- between the old and new value is what drives the "since you were here"
  -- greeting (new county auctions, sale-date drift) computed in src/worker.js.
  last_viewed_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_projects_owner_idx ON public.biddeed_projects (owner_email, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.biddeed_project_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.biddeed_projects(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('conversation', 'report', 'upload', 'parcel')),
  ref_id text NOT NULL,
  added_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_project_items_project_idx ON public.biddeed_project_items (project_id, added_at DESC);

-- Project FILES (scope update: "attachment and download abilities") — upload/
-- version/rename/delete/download of PDF/CSV/DOCX/XLSX/images inside a
-- project. Versioned by filename (nextFileVersion in src/worker.js): the same
-- filename uploaded twice creates v1, v2, ... rather than overwriting.
-- "Download all as a zip" is explicitly NOT built (Ariel: never zip).
CREATE TABLE IF NOT EXISTS public.biddeed_project_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES public.biddeed_projects(id) ON DELETE CASCADE,
  owner_email text NOT NULL,
  storage_path text NOT NULL,
  filename text NOT NULL,
  mime_type text,
  version int NOT NULL DEFAULT 1,
  extracted_text text,
  extraction_status text NOT NULL DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'ok', 'unsupported', 'failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_project_files_project_idx ON public.biddeed_project_files (project_id, filename, version DESC);
CREATE INDEX IF NOT EXISTS biddeed_project_files_owner_idx ON public.biddeed_project_files (owner_email);

CREATE TABLE IF NOT EXISTS public.biddeed_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_email text NOT NULL,
  project_id uuid REFERENCES public.biddeed_projects(id) ON DELETE SET NULL,
  conversation_id uuid REFERENCES public.biddeed_chat_conversations(id) ON DELETE SET NULL,
  title text,
  version int NOT NULL DEFAULT 1,
  format text NOT NULL CHECK (format IN ('pdf', 'csv', 'json')),
  storage_path text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS biddeed_reports_owner_idx ON public.biddeed_reports (owner_email, created_at DESC);
CREATE INDEX IF NOT EXISTS biddeed_reports_project_idx ON public.biddeed_reports (project_id);
CREATE INDEX IF NOT EXISTS biddeed_reports_conversation_idx ON public.biddeed_reports (conversation_id);

CREATE TABLE IF NOT EXISTS public.biddeed_share_links (
  token text PRIMARY KEY,
  report_id uuid NOT NULL REFERENCES public.biddeed_reports(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS biddeed_share_links_report_idx ON public.biddeed_share_links (report_id);

ALTER TABLE public.biddeed_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_project_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_project_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.biddeed_share_links ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.biddeed_projects FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_project_items FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_project_files FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_reports FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.biddeed_share_links FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.biddeed_projects TO service_role;
GRANT ALL ON public.biddeed_project_items TO service_role;
GRANT ALL ON public.biddeed_project_files TO service_role;
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
