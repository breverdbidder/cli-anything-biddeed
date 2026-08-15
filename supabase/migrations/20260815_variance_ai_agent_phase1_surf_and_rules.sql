-- Variance AI Agent — Phase 1 validation data
-- Issue: breverdbidder/cli-anything-biddeed#19094
-- Spec: VARIANCE_AI_AGENT_METAPROMPT.md section 5

-- "The Surf at Cocoa Beach" precedent — sourced, not fabricated.
-- Real primary source: Cocoa Beach City Commission Regular Meeting agenda,
-- July 7 2016, Item J1 (public hearing), Granicus clip_id=2870:
-- https://cocoabeach.granicus.com/GeneratedAgendaViewer.php?view_id=4&clip_id=2870
-- Agenda text (verbatim, fetched live): "Consider a request for a variance to
-- allow a condominium complex, Ocean Dunes, located at 33, 35, 37, 39, and 41
-- North Atlantic Avenue and Tax ID: 2517526 with no address, to be constructed
-- to a maximum height of 60 feet above the crown of the abutting roadway,
-- exceeding the maximum height limitation by 15 feet."
-- This independently corroborates (matching height=60ft and address block) the
-- secondhand mention already in variance_documents id=6 (2022 attorney letter
-- citing "The Surf at Cocoa Beach... 60ft"). ClickOrlando news (2020/2021)
-- confirms the site was later built out as "The Surf," a 25-unit, 5-story
-- condo, developer team publicly tied to Howie Dorough, broke ground 3/2021.
-- NOT independently confirmed: the exact commission vote tally/resolution
-- number, and whether DB parcel "25 3711-DD-A-3.XA" (65 N Atlantic, common
-- area) is the identical legal parcel to 2016 Tax ID 2517526 (33-41 N
-- Atlantic) post-renumbering. case_status='approved' is an inference from the
-- confirmed built structure, not a directly-sourced vote record — flagged
-- explicitly in notes below, same evidentiary standard already used for the
-- pre-existing Wavecrest row (id=3) construction_status field.
INSERT INTO public.variance_applications (
  jurisdiction_id, address, variance_category, variance_type,
  current_requirement, requested_relief, applicant_entity, board_type,
  case_status, hearing_date, notes
)
SELECT 7,
  '33-41 N Atlantic Ave, Cocoa Beach, FL (2016 hearing address block; site later built out and addressed/branded as 65 N Atlantic Ave / "The Surf at Cocoa Beach" — parcel/address identity across the renumbering NOT independently confirmed this session)',
  'area_dimensional', 'height',
  '45 ft base height limit (LDC Section 4-40)',
  '60 ft maximum height (15 ft over base) — 2016 hearing agenda item, Tax ID 2517526',
  'Ocean Dunes (project name at 2016 hearing stage; site publicly reported 2020-2021 as developed/branded "The Surf," development team publicly tied to Howie Dorough)',
  'city_commission', 'approved', '2016-07-07',
  'case_status=approved is INFERRED from confirmed subsequent construction (25-unit, 5-story condo, broke ground 3/2021 per ClickOrlando), not from a directly-sourced vote tally or resolution number — neither was found this session. Corroborates the 60ft figure already cited secondhand in variance_documents id=6. Recommend a BCPAO/Clerk-of-Courts follow-up to confirm parcel identity and exact vote record before treating this as fully closed.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.variance_applications
  WHERE jurisdiction_id = 7 AND requested_relief LIKE '60 ft maximum height%'
);

INSERT INTO public.variance_documents (application_id, doc_type, doc_title, source_url, full_text, pulled_at)
SELECT va.id, 'agenda',
  'Cocoa Beach City Commission Regular Meeting Agenda Item J1 - July 7, 2016 (Ocean Dunes / The Surf height variance public hearing)',
  'https://cocoabeach.granicus.com/GeneratedAgendaViewer.php?view_id=4&clip_id=2870',
  'Consider a request for a variance to allow a condominium complex, Ocean Dunes, located at 33, 35, 37, 39, and 41 North Atlantic Avenue and Tax ID: 2517526 with no address, to be constructed to a maximum height of 60 feet above the crown of the abutting roadway, exceeding the maximum height limitation by 15 feet; this is a Public Hearing. A supermajority Commission vote would be required for action on the request. Staff rep: Zach Montgomery, Director of Development Services.',
  now()
FROM public.variance_applications va
WHERE va.jurisdiction_id = 7 AND va.requested_relief LIKE '60 ft maximum height%'
  AND NOT EXISTS (
    SELECT 1 FROM public.variance_documents vd
    WHERE vd.application_id = va.id AND vd.doc_title LIKE 'Cocoa Beach City Commission Regular Meeting Agenda Item J1%'
  );

-- variance_jurisdiction_rules — Cocoa Beach (id=7) + Satellite Beach (id=6) ONLY.
-- Cocoa Beach: direct municode fetch returned 403 (anti-bot) at session time;
-- both sections below are CONFIRMED via multiple independently converging
-- indexed search-engine snippets quoting the actual code text, not via a
-- direct page load. Flagged inline rather than presented as a raw citation.
INSERT INTO public.variance_jurisdiction_rules
  (jurisdiction_id, variance_type, is_permitted, board_type, statutory_criteria_section, source_url, verified_at)
VALUES
  (7, 'height', true, 'city_commission',
   'LDC Chapter IV, Article IV ("Variance, Waivers and Appeals"), Section 4-40 - "Petitions for a height to exceed forty-five (45) feet." Base height 45ft; side setbacks increase 5ft per 10ft of additional height. Procedural chain per case data: BOA/Planning Board review, City Commission final approval. Confirmed via converging search-indexed snippets quoting code text; direct municode.com fetch returned HTTP 403 this session (see 20260815 variance research notes).',
   'https://library.municode.com/fl/cocoa_beach/codes/land_development_code?nodeId=APXBLADECO_CHIVVAWAAP', now()),
  (7, 'setback', true, 'board_of_adjustment',
   'LDC Chapter IV, Article IV, Section 4-39 - "Application for a variance from the board of adjustment" (general/dimensional variance authority, covers setbacks; contains the six-part hardship standard). Confirmed via converging search-indexed snippets quoting code text; direct municode.com fetch returned HTTP 403 this session.',
   'https://library.municode.com/fl/cocoa_beach/codes/land_development_code?nodeId=APXBLADECO_CHIVVAWAAP', now()),
  (6, 'setback', true, 'board_of_adjustment',
   'Chapter 30 (Land Development Regulations), Article IV (Zoning) contains the general dimensional/setback variance authority; Board of Adjustment''s variance-hearing role is confirmed directly via satellitebeach.org (Sec. 30-203 references BOA composition/duties). The EXACT variance subsection number could NOT be independently verified this session: library.municode.com returned HTTP 403 to automated fetch, and Firecrawl returned HTTP 402 (API credits exhausted) on every attempt. The prior-session citation "Section 30-415" was NOT found or corroborated in any accessible source and should be treated as unverified, not confirmed, pending a direct browser session or records request to Satellite Beach Community Development ((321) 773-4407).',
   'https://www.satellitebeach.org/government/city_boards/board_of_adjustment/index.php', now())
ON CONFLICT (jurisdiction_id, variance_type) DO NOTHING;
