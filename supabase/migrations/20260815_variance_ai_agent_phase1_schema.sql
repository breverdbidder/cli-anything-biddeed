-- Variance AI Agent — Phase 1 schema
-- Issue: breverdbidder/cli-anything-biddeed#19094
-- Spec: VARIANCE_AI_AGENT_METAPROMPT.md sections 4, 6
-- Generalizes cocoa_variance_projects/cocoa_variance_documents statewide.
-- Does NOT drop the old tables (kept until acceptance test passes).
--
-- Deviation from spec: section 4.1 names variance_applications.parcel_id as
-- "FK -> fl_parcels.parcel_id", but fl_parcels.parcel_id is only unique in
-- combination with co_no (fl_parcels_co_no_parcel_id_key), not on its own —
-- there is no single-column unique/PK target for a FK. parcel_id is stored
-- as plain text with no enforced FK, matching the existing
-- cocoa_variance_projects.parcel_id pattern (also unconstrained text).

CREATE TABLE IF NOT EXISTS public.variance_applications (
  id BIGSERIAL PRIMARY KEY,
  jurisdiction_id BIGINT NOT NULL REFERENCES public.jurisdictions(id),
  parcel_id TEXT,
  address TEXT,
  variance_category TEXT CHECK (variance_category IN ('area_dimensional','use')),
  variance_type TEXT NOT NULL CHECK (variance_type IN ('setback','height','lot_coverage','parking','density','sign','use','other')),
  current_requirement TEXT,
  requested_relief TEXT,
  applicant_entity TEXT,
  owner_representative TEXT,
  case_number TEXT,
  board_type TEXT CHECK (board_type IN ('board_of_adjustment','planning_zoning_board','city_commission')),
  case_status TEXT CHECK (case_status IN ('pre_application','filed','hearing_scheduled','approved','approved_with_conditions','denied','withdrawn','appealed')),
  filed_date DATE,
  hearing_date DATE,
  approval_date DATE,
  vote_result TEXT,
  attorney TEXT,
  planner TEXT,
  engineer TEXT,
  architect TEXT,
  surveyor TEXT,
  construction_status TEXT,
  timeline JSONB,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.variance_applications ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.variance_documents (
  id BIGSERIAL PRIMARY KEY,
  application_id BIGINT NOT NULL REFERENCES public.variance_applications(id) ON DELETE CASCADE,
  doc_type TEXT NOT NULL CHECK (doc_type IN (
    'pre_app_meeting_notes','application_form','site_plan','survey_document',
    'variance_justification_report','attorney_justification_letter','agenda',
    'staff_report','commission_minutes','resolution','permit_construction_status_report',
    'public_notice','adjacent_owner_notification','news_article','other'
  )),
  doc_title TEXT NOT NULL,
  source_url TEXT,
  full_text TEXT,
  pulled_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.variance_documents ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.variance_criteria_findings (
  id BIGSERIAL PRIMARY KEY,
  application_id BIGINT NOT NULL REFERENCES public.variance_applications(id) ON DELETE CASCADE,
  criterion_key TEXT NOT NULL CHECK (criterion_key IN (
    'special_conditions_peculiar','not_self_created','unnecessary_hardship',
    'no_special_privilege','minimum_variance_necessary','not_detrimental_to_public_welfare'
  )),
  finding_text TEXT,
  board_determination TEXT CHECK (board_determination IN ('met','not_met','not_addressed','contested')),
  source_doc_id BIGINT REFERENCES public.variance_documents(id)
);

ALTER TABLE public.variance_criteria_findings ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.variance_jurisdiction_rules (
  id BIGSERIAL PRIMARY KEY,
  jurisdiction_id BIGINT NOT NULL REFERENCES public.jurisdictions(id),
  variance_type TEXT NOT NULL CHECK (variance_type IN ('setback','height','lot_coverage','parking','density','sign','use','other')),
  is_permitted BOOLEAN,
  prohibition_note TEXT,
  board_type TEXT CHECK (board_type IN ('board_of_adjustment','planning_zoning_board','city_commission')),
  statutory_criteria_section TEXT,
  application_fee TEXT,
  typical_timeline_weeks INTEGER,
  public_notice_requirements TEXT,
  source_url TEXT,
  verified_at TIMESTAMPTZ,
  UNIQUE (jurisdiction_id, variance_type)
);

ALTER TABLE public.variance_jurisdiction_rules ENABLE ROW LEVEL SECURITY;

-- 4.5 variance_precedents — view, not a table. v1 similarity = jurisdiction+type match only.
CREATE OR REPLACE VIEW public.variance_precedents AS
SELECT
  a.id AS application_id,
  a.jurisdiction_id,
  a.variance_type,
  a.address,
  a.case_status,
  a.vote_result,
  a.approval_date,
  p.id AS precedent_application_id,
  p.address AS precedent_address,
  p.case_status AS precedent_case_status,
  p.vote_result AS precedent_vote_result,
  p.approval_date AS precedent_approval_date,
  p.current_requirement AS precedent_current_requirement,
  p.requested_relief AS precedent_requested_relief
FROM public.variance_applications a
JOIN public.variance_applications p
  ON p.jurisdiction_id = a.jurisdiction_id
 AND p.variance_type = a.variance_type
 AND p.id <> a.id;
