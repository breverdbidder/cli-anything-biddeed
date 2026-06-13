# RealTDM Public O&E Crawl + Parity Mapping - Build Brief

> Status: READY_TO_BUILD | Surface: miamidade.realtdm.com/public (NO AUTH) | Infra: GHA Playwright (ubuntu-latest)
> Architect decision: report output standard = FL tax-deed statutory O&E (RealTDM); Miami-Dade public O&E = ground truth.
> Target tables: public.realtdm_case + public.realtdm_oe_sample (created + indexed)
> Endpoint: realauction_api_endpoints id=8 (TDM_PUBLIC_CASE_LIST)

## 1. Why
Two payoffs from one public surface:
1. REPORT PARITY - the statutory O&E field-set is the report standard PENCIL/ZoneWise must match to reach Dono-grade depth. Public record, no IP issue.
2. GROUND TRUTH - the county's own O&E per case validates title_chain.pull output (did our chain + liens match the official title search?). Stronger than "fields populated."

## 2. Scope
- County: miamidade (subdomain pattern {county}.realtdm.com).
- Crawl /public/cases/list -> per-case detail -> attached O&E / title-search doc.
- Extract the O&E field-set; write realtdm_case + realtdm_oe_sample.
- Map field_inventory into public.pencil_report_parity_spec (confirm/extend the field standard).
- OUT OF SCOPE: any auth-walled area; the realtaxdeed.com bidding XHR (separate, auth-walled); lifting RealTDM layout/branding/code.

## 3. Infra / auth
- GHA ubuntu-latest, Playwright + chromium native. DEFAULT INFRA (Supabase+GHA); no Hetzner.
- NO login required (public surface). Only secret = Supabase service key BY NAME for write-back. No creds in logs/commits.

## 4. Steps
1. GET /public/cases/list; page through all cases. For each: case_no, folio, property_address, sale_date, status, applicant, detail_url. Upsert realtdm_case (UNIQUE county,case_no).
2. For each case: open detail_url; locate the O&E / title-search document (likely PDF); capture oe_doc_url.
3. Parse the O&E doc. Capture VERBATIM field labels into field_inventory (jsonb) plus structured: legal_description, current_owner, vesting_deed_ref, chain[], mortgages[], liens[], easements[], tax_status, parties_to_notice[]. Upsert realtdm_oe_sample.
4. Reconcile field_inventory against pencil_report_parity_spec: mark each spec section confirmed-present; log any NEW field the county includes that the spec lacks.

## 5. Honesty
- Every extracted field carries a marker (VERIFIED from doc / INFERRED parse / UNKNOWN). BLANK > WRONG: do not fabricate a field the doc lacks.
- field_inventory keeps the county's labels verbatim - parity mapping is downstream, not invented at parse time.
- Statutory public record only; data + field-set extracted, NOT the proprietary layout/code.

## 6. Acceptance Criteria
- AC1: realtdm_case populated for all cases on /public/cases/list (count logged).
- AC2: For >= 20 cases with an O&E doc, realtdm_oe_sample populated with field_inventory non-empty.
- AC3: A parity diff is produced: which pencil_report_parity_spec sections (1-13) are confirmed by the county O&E, and any new fields found.
- AC4: For any case whose O&E doc is missing/unparseable, a row is written with honesty_marker=UNKNOWN and the reason - never a fabricated O&E.
- AC5: Idempotent re-run (UNIQUE county,case_no; upsert).
- AC6: Runs in < 6h; no secrets in logs.

## 7. Validation hook (ground truth for title_chain.pull)
- When title_chain.pull (Duval P1) generalizes, run it on Miami-Dade folios present in realtdm_oe_sample and diff our chain/liens vs the county O&E. Emit an accuracy metric. This is the rigorous proof the report is CORRECT, not just complete.

## 8. Pointers
- Tables: public.realtdm_case, public.realtdm_oe_sample (created).
- Parity spec: public.pencil_report_parity_spec (13 sections - the field standard to confirm/extend).
- Tool spec: public.pencil_mcp_tool_spec WHERE tool_name='title_chain.pull' (reference_standard + architect_decision rows).
- Endpoint: public.realauction_api_endpoints id=8.
- Boundary reminder: parity via PUBLIC statutory standard, never a competitor proprietary template (Dono or RealTDM platform).
