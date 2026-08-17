-- Exa TAM expansion (#19179 follow-through): store the mandatory ICP
-- verification rationale for entities sourced outside the auction-winner
-- pool. lead_profiles has no existing free-text notes column (confirmed live
-- 2026-08-17 via information_schema.columns), so this adds one rather than
-- overloading an unrelated field.
--
-- Additive only (CC_META_PROMPT.md 3.4): new column, nothing altered/dropped.

ALTER TABLE public.lead_profiles ADD COLUMN IF NOT EXISTS icp_rationale text;

COMMENT ON COLUMN public.lead_profiles.icp_rationale IS
  'One-line PASS rationale from the mandatory Exa-fetch ICP verification gate (source=exa_tam_expansion candidates). Only PASS entities are ever inserted, so presence of a row with this source implies PASS; the text records why.';
