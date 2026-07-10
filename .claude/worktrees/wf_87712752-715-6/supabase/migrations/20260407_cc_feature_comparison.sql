-- cc_feature_comparison: tracks native CC feature evaluations
-- Created by SUMMIT #392 (ultraplan native check)

CREATE TABLE IF NOT EXISTS public.cc_feature_comparison (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  feature text NOT NULL,
  cc_version text NOT NULL,
  native_available boolean NOT NULL,
  custom_files_retired text[],
  decision text NOT NULL,
  evidence text,
  summit_issue int,
  evaluated_at timestamptz DEFAULT now()
);

-- Seed: /ultraplan native eval result
INSERT INTO public.cc_feature_comparison (feature, cc_version, native_available, custom_files_retired, decision, evidence, summit_issue)
VALUES (
  '/ultraplan',
  '2.1.92',
  true,
  ARRAY['summit-ultraplan.yml', 'ultraplan-runner.py'],
  'RETIRE_CUSTOM — native /ultraplan in CC 2.1.92 provides full parity (28 refs in cli.js, lifecycle phases: plan_ready/needs_input/running, CCR session URL tracking, PR output)',
  'grep -c ultraplan cli.js = 28; phases: plan_ready, needs_input, running; listed alongside ultrareview, autofix-pr, remote-agent as built-in remote agent types',
  392
);
