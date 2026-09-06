-- Issue #20043 item 6 — nightly batch ML scoring table (schema only).
--
-- SCOPE NOTE: the issue asks for both this table AND a new
-- .github/workflows/ml-score-nightly.yml cron workflow. The workflow file
-- is deliberately NOT created in this dispatch — creating/editing GHA
-- workflow files is blocked by this repo's standing mandate M5 ("no
-- workflow-file edits"), which this dispatch may not override even when
-- the issue body asks for it (per M5's own text: "if a task cannot be
-- completed without breaking one of these, STOP that part... finish the
-- rest"). This table ships so a human (or a future dispatch scoped to
-- explicitly permit a workflow-file change) can wire the nightly job
-- against a schema that already exists and is already read by the report
-- engine.
--
-- Also note (verified against live code, not assumed from the issue body):
-- the "3-way split" bug this item describes (xgb_prob = catb_prob =
-- lgbm_prob) does NOT exist in the current ensemble-model.js — it was fixed
-- under issue #19079 (Aug 14 2026). The retired v14.0 path that had the bug
-- is explicitly marked DEAD and is never called. See docs/spec/20043.md for
-- the full evidence trail.

CREATE TABLE IF NOT EXISTS public.ml_scores (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  mca_id         uuid NOT NULL REFERENCES public.multi_county_auctions(id),
  model_version  text NOT NULL,
  p_third_party  numeric,
  xgb_prob       numeric,
  lgbm_prob      numeric,
  catb_prob      numeric,
  feature_vector jsonb,
  scored_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (mca_id, model_version)
);

CREATE INDEX IF NOT EXISTS idx_ml_scores_mca_id ON public.ml_scores (mca_id);

ALTER TABLE public.ml_scores ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ml_scores_service_role_only ON public.ml_scores;
CREATE POLICY ml_scores_service_role_only
  ON public.ml_scores
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
