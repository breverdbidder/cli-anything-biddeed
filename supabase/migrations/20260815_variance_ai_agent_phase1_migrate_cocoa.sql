-- Variance AI Agent — Phase 1 migration
-- Issue: breverdbidder/cli-anything-biddeed#19094
-- Spec: VARIANCE_AI_AGENT_METAPROMPT.md section 6
-- cocoa_variance_projects (4 rows) -> variance_applications
-- cocoa_variance_documents (9 rows) -> variance_documents
-- Old tables are NOT dropped — kept in place per non-goals until acceptance test verified.
-- jurisdiction_id 7 = Cocoa Beach (public.jurisdictions), verified live 2026-08-15.
-- board_type='city_commission' for all 4: every migrated case shows City Commission
-- as the recorded final approver/voter (per attorney/vote_result fields already stored).

INSERT INTO public.variance_applications (
  jurisdiction_id, parcel_id, address, variance_category, variance_type,
  requested_relief, applicant_entity, owner_representative, board_type,
  case_status, approval_date, vote_result, attorney, planner, engineer,
  architect, surveyor, construction_status, timeline, notes, created_at, updated_at
)
SELECT
  7, parcel_id, address, 'area_dimensional', 'height',
  variance_requested, applicant_entity, owner_representative, 'city_commission',
  case_status, approval_date, vote_result, attorney, planner, engineer,
  architect, surveyor, construction_status, timeline, notes, created_at, updated_at
FROM public.cocoa_variance_projects
WHERE NOT EXISTS (
  SELECT 1 FROM public.variance_applications va
  WHERE va.jurisdiction_id = 7 AND va.address = cocoa_variance_projects.address
);

INSERT INTO public.variance_documents (
  application_id, doc_type, doc_title, source_url, full_text, pulled_at
)
SELECT
  va.id, d.doc_type, d.doc_title, d.source_url, d.full_text, d.pulled_at
FROM public.cocoa_variance_documents d
JOIN public.cocoa_variance_projects p ON p.project_name = d.project_name
JOIN public.variance_applications va ON va.jurisdiction_id = 7 AND va.address = p.address
WHERE NOT EXISTS (
  SELECT 1 FROM public.variance_documents vd
  WHERE vd.application_id = va.id AND vd.doc_title = d.doc_title
);
