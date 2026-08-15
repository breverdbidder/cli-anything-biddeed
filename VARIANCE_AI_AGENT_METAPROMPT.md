# Variance AI Agent — Architecture, Schema & SOP Meta-Prompt

**Operating contract:** CC_META_PROMPT.md. Read it first. **Companion to** ZONEWISE_MCP_TESTFIT_PARITY_METAPROMPT.md (Section 8 in particular).
**Honesty Protocol V3 applies throughout.** A variance-approval prediction is a decision-support probability, never a guarantee.

## 1. THE TWO REAL TEST CASES

### 1.1 Maurice / Trizek Gulfstream - height variance, Cocoa Beach (3 parcels, 1 site)
Parcels: 3220 N Atlantic Ave (24 3735-CL-*-2, 47916 sf), 3240 Atlantic Ave (24 3734-CL-*-2.01, 62726 sf), 100 Surf Dr (24 3734-CK-2-1, 9148 sf) - all owned by Trizek Gulfstream Inc, one continuous 2.75-acre through-lot Atlantic Ocean to Surf Drive.
Real precedent set already stored (cocoa_variance_projects 4 rows, cocoa_variance_documents 9 rows with full source text): Westin Cocoa Beach Resort/International Palms (1300 N Atlantic, 45ft to 70ft, approved 4-0, Dec 5 2019), Westgate Cocoa Beach Pier Resort (401 Meade Ave, 45 to 70ft, approved 4-1, Jul 7 2022), Wavecrest Drive Condominium/BDH Investment Corp (45 to 70ft, approved unanimous, Aug 18 2022), Destination Downtown/2 N Atlantic (20ft over 45ft base, withdrawn, Apr 2022). A possible 4th precedent - The Surf at Cocoa Beach, 65 N Atlantic, reportedly 60ft - is chat-mentioned only, NOT yet a structured row. Confirm and source properly before counting it, or exclude it.
Real team data already captured per case: attorney, planner, engineer, architect, surveyor (e.g. Westin: attorney Philip P. Nohrr/GrayRobinson, planner Rochelle Lawandales FAICP, engineer AECOM).
zoning_assignments already has 10840 real parcel rows for cocoa_beach - this test case does not need the statewide zoning-assignment expansion mission.

### 1.2 625 Ocean Street - setback variance, Satellite Beach (Ariel's own property)
Parcel 27-37-01-50-7-4, RM-3 zoning, 0.34 acres, Eau Gallie by the Sea Lots 4-12 Block 7.
"Walden" = the 2007 Walden Project, the original entitlement holder, secured the underlying setback variances still in effect, refined by 2015/2018 approvals.
Real approved relief exists but two past sessions give slightly different numbers (front setback to 15ft east per one pass / south-side to 9ft6in per another / rear to 12ft) - RECONCILE against the actual variance resolution/case file before treating either framing as canonical.
zoning_assignments already has 8709 real parcel rows for satellite_beach.

Why both matter as a pair: one is height (deep Cocoa Beach precedent), the other is setback in a different city - proving the schema/agent works for both is the actual test of "not only rezoning and height."

## 2. WHAT ALREADY EXISTS - dont rebuild, extend
Verified live via Supabase, Aug 15 2026.
cocoa_variance_projects (4 rows): project_name, address, parcel_id, applicant_entity, owner_representative, variance_requested, case_status, approval_date, vote_result, attorney, planner, engineer, architect, surveyor, construction_status, timeline jsonb, notes.
cocoa_variance_documents (9 rows, real full source text): project_name, doc_title, doc_type, source_url, full_text, pulled_at. Real observed doc_type values, use as seed of generalized taxonomy: agenda, variance_justification_report, permit_construction_status_report, commission_minutes, attorney_justification_letter, survey_document, news_article.
cocoa_planning_filings: filing_type, title, url, source, relevant_flag, full_text_snippet, notes jsonb, scrape_status, scraped_at, raw_snippet - scrape-queue table, has rows tagged for Maurice/Trizek parcels.
Both cocoa_variance_* tables are Cocoa-Beach-only today - the new schema generalizes statewide without discarding the real data (see migration section).

## 3. RESEARCHED FOUNDATION - the statutory standard
Six-part test near-universal across FL municipalities, verified against real Seminole County and Jacksonville Beach code text plus general FL case-law commentary:
1. Special conditions/circumstances peculiar to the property - not shared by most similar properties in the zoning district
2. Hardship not self-created - not from the applicant's own prior actions, buying with knowledge of the restriction does not create an exception
3. Unnecessary/undue hardship from literal enforcement - financial hardship or desire for greater profit is explicitly NOT sufficient alone
4. No special privilege - granting does not confer a privilege denied to other similarly situated land
5. Minimum variance necessary - smallest deviation that makes reasonable use possible
6. Not detrimental to public welfare/neighborhood character - consistent with the general intent of the code

Critical jurisdiction-variability finding: not every city allows every variance type. Jacksonville Beach explicitly prohibits height variances AND use variances outright ("a height variance shall not be permitted in any zoning district"), while Cocoa Beach grants height variances routinely. The agent must check eligibility per jurisdiction before drafting anything - not optional.
Use variances are broadly disfavored/prohibited across FL municipalities, distinct from area/dimensional variances (setbacks, height, lot coverage, parking) which are the normal grantable case. Schema must distinguish these explicitly.

## 4. SCHEMA - generalized, statewide, all variance types
Designed to absorb the existing Cocoa Beach data, not replace it.

### 4.1 variance_applications (master record, generalizes cocoa_variance_projects)
id, jurisdiction_id (FK -> jurisdictions, the existing 357-row table, do not create a parallel jurisdiction concept), parcel_id (FK -> fl_parcels.parcel_id), address, variance_category (area_dimensional | use), variance_type (setback | height | lot_coverage | parking | density | sign | use | other), current_requirement text, requested_relief text, applicant_entity, owner_representative, case_number, board_type (board_of_adjustment | planning_zoning_board | city_commission - VARIES by jurisdiction, pull from variance_jurisdiction_rules, never assume), case_status (pre_application | filed | hearing_scheduled | approved | approved_with_conditions | denied | withdrawn | appealed), filed_date, hearing_date, approval_date, vote_result, attorney, planner, engineer, architect, surveyor (simple text fields matching what already works), construction_status, timeline jsonb, notes, created_at, updated_at.

### 4.2 variance_criteria_findings (new - operationalizes the six-part test, this is the differentiator)
id, application_id FK, criterion_key (special_conditions_peculiar | not_self_created | unnecessary_hardship | no_special_privilege | minimum_variance_necessary | not_detrimental_to_public_welfare), finding_text, board_determination (met | not_met | not_addressed | contested), source_doc_id FK nullable.

### 4.3 variance_documents (generalizes cocoa_variance_documents, same real doc_type taxonomy, statewide)
id, application_id FK, doc_type (pre_app_meeting_notes | application_form | site_plan | survey_document | variance_justification_report | attorney_justification_letter | agenda | staff_report | commission_minutes | resolution | permit_construction_status_report | public_notice | adjacent_owner_notification | news_article | other), doc_title, source_url, full_text, pulled_at.

### 4.4 variance_jurisdiction_rules (new - makes the agent honest about eligibility)
id, jurisdiction_id FK, variance_type, is_permitted boolean, prohibition_note text, board_type, statutory_criteria_section, application_fee, typical_timeline_weeks, public_notice_requirements text, source_url, verified_at.
Populate FIRST for Cocoa Beach and Satellite Beach only before anything else.

### 4.5 variance_precedents (view over variance_applications, not a new table)
Join variance_applications to itself on same jurisdiction_id + same variance_type + different id. v1 similarity is jurisdiction+type match only - reproduces the manual precedent-finding already done for Maurice's case. Magnitude-of-relief similarity is v2, not required for acceptance.

## 5. VALIDATION PHASE
1. Reconcile the 625 Ocean Street setback numbers - find the actual city variance resolution/case file, not another AI-generated memo.
2. Confirm or exclude "The Surf at Cocoa Beach" as precedent - source it properly or dont count it.
3. Populate variance_jurisdiction_rules for Cocoa Beach and Satellite Beach specifically from real LDC text (both already have cited code sections from prior sessions - verify they still resolve).
4. Do NOT populate variance_jurisdiction_rules for all 357 jurisdictions in this phase - scope to the two test jurisdictions only.

## 6. MIGRATION
cocoa_variance_projects (4 rows) -> variance_applications: map project_name to case identifier, jurisdiction_id='cocoa_beach', variance_category='area_dimensional', variance_type='height' for all 4 (every existing row is a height case).
cocoa_variance_documents (9 rows) -> variance_documents: application_id resolved via project_name match, doc_type values map 1:1.
Keep old tables in place after migration until verified against acceptance test - do not drop.

## 7. MCP TOOL SET (PHASE 1 SCOPE - see dispatch note below for what ships now vs later)
check_variance_eligibility(jurisdiction, variance_type) - FIRST call always, queries variance_jurisdiction_rules, returns permitted/prohibited + board + statutory section, or honest "not yet researched" if no row - never assumes.
find_variance_precedents(jurisdiction, variance_type, parcel_id?) - queries variance_precedents, real comparable cases with real outcomes.
draft_justification_statement(application_id or ad-hoc site facts) - DEFERRED to follow-on issue, not this phase.
score_variance_application(application_id) - DEFERRED to follow-on issue, not this phase.
get_variance_sop(jurisdiction, variance_type) - DEFERRED to follow-on issue, not this phase.
track_variance_case(case_number or application_id) - DEFERRED to follow-on issue, not this phase.

## 8. ACCEPTANCE TEST (Phase 1 subset - items 1-3 only, item 4-5 belong to the deferred tools follow-on)
1. check_variance_eligibility('cocoa_beach', 'height') returns permitted, correctly citing Cocoa Beach LDC height-variance section. check_variance_eligibility('cocoa_beach', 'setback') also returns permitted.
2. find_variance_precedents('cocoa_beach', 'height') returns the real 3 approved + 1 withdrawn cases with correct vote results.
3. Same two calls for satellite_beach/setback using the reconciled 625 Ocean Street numbers as seeded precedent - confirm surfaced correctly.
Post real query output for all of the above as the issue closing comment.

## 9. NON-GOALS
Do not populate variance_jurisdiction_rules for all 357 jurisdictions in this phase.
Do not claim score_variance_application predicts a real outcome with certainty - not in this phase anyway, it is deferred.
Do not draft justification statements with generic boilerplate - not in this phase anyway, it is deferred.
Do not drop cocoa_variance_projects/cocoa_variance_documents until migrated data is verified against the acceptance test.
Do not treat "The Surf at Cocoa Beach" as confirmed precedent until sourced properly.
