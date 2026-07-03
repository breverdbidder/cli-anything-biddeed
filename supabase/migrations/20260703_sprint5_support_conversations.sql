-- Migration: support_conversations — SPRINT5 #1 member support agent
-- Created: 2026-07-03 | Idempotent: safe to re-run
-- Dispatch: 0db3e80e-7563-4c1e-93b6-4411e8829023

CREATE TABLE IF NOT EXISTS public.support_conversations (
  id                BIGSERIAL PRIMARY KEY,
  session_id        TEXT NOT NULL,
  member_key_prefix TEXT,
  role              TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content           TEXT NOT NULL,
  locale            TEXT NOT NULL DEFAULT 'en',
  model_tier        TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_conversations_session
  ON public.support_conversations (session_id, created_at);

ALTER TABLE public.support_conversations ENABLE ROW LEVEL SECURITY;

-- Widget uses the anon/publishable key and may only insert its own user-role
-- turns. Assistant rows are written exclusively by the support-agent edge
-- function via the service role, which bypasses RLS entirely.
DROP POLICY IF EXISTS support_conversations_anon_insert_user ON public.support_conversations;
CREATE POLICY support_conversations_anon_insert_user
  ON public.support_conversations
  FOR INSERT
  TO anon
  WITH CHECK (role = 'user');
