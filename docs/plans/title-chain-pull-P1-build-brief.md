# title_chain.pull - P1 Build Brief

> Status: READY_TO_BUILD | Scope: Duval County / Acclaim | Mode: two_owner O&E
> Spec SSOT: Supabase public.pencil_mcp_tool_spec WHERE tool_name='title_chain.pull'
> Result model: public.title_chain_pull + title_chain_owner + title_chain_encumbrance + title_chain_gap (already created + indexed)

## 1. Why
title_chain.pull is the backbone of the PENCIL/ZoneWise report. It feeds four report-parity sections (chain_of_title, open mortgages, recorded liens, title-affecting events) and is the input to lien_survival.classify and fc_outcome.label. Until it exists, report depth cannot reach insured-grade parity. Parity comes from PRIMARY SOURCES (county Official Records + DOR), never from a competitor pipe.

## 2. P1 Scope (DO ONLY THIS)
- County: Duval only.
- Platform: Acclaim (clerk Official Records API - already decoded in repo for fc_outcome labeling; REUSE that client, do not rebuild).
- Depth: two_owner ONLY (current owner + immediately prior owner).
- Deliverable: given a Duval parcel, produce the deed INTO the current owner and the deed INTO the prior owner, each reconciled to the parcel legal description, written to the result tables.
- OUT OF SCOPE for P1: full-chain recursion (P3), encumbrance/grantor sweep (P2), non-Acclaim counties (P4). Do NOT build these.

## 3. Inputs
- selector_kind: parcel_id | situs_address | owner_name | instrument_number (P1 must support parcel_id; others optional)
- selector_value: text
- county: 'Duval' (fixed for P1)
- depth: 'two_owner' (fixed for P1)
- as_of_date: optional, default today

## 4. Data Sources
- Acclaim Official Records client (existing in repo - reuse).
- Parcel resolver: zw_parcels (77 cols) + FL DOR cadastral -> current owner name + most-recent deed reference + legal_description.

## 5. Algorithm (P1)
1. Resolve entry: parcel_id -> zw_parcels/DOR -> current owner name, most-recent deed (book/page or instrument#), legal_description. If selector is address/owner/instrument, resolve to parcel_id first.
2. Pull deed-in (current owner): query Acclaim grantee index for the deed where grantee = current owner. Capture deed_type, deed_date, book_page, instrument_no, grantor, consideration. Owner seq=1, period_start=deed_date, period_end=null.
3. Pull prior deed: grantor of seq=1 deed = prior owner. Query Acclaim grantee index for the deed INTO that prior owner. Owner seq=2, period_end = seq=1 deed_date.
4. Reconcile each deed to the parcel legal_description (see gate, section 6). Stop after seq=2 (two_owner).
5. Write title_chain_pull header + up to two title_chain_owner rows. Any unreconciled hop -> title_chain_gap row, NOT a guessed owner.

## 6. The Reconciliation Gate (decides correctness)
FL Official Records are GRANTOR/GRANTEE NAME-indexed, not parcel-indexed. A name match is NOT a parcel match. Every deed pulled MUST be reconciled to the parcel legal_description before it is trusted:
- matched_legal -> deed legal description matches parcel legal description -> honesty_marker=VERIFIED
- name_only -> name matches but legal description NOT confirmed -> honesty_marker=INFERRED, reconciliation_confidence='name_only'
- unmatched -> cannot tie to parcel -> DO NOT write an owner row; write a title_chain_gap (reason='name_break' or 'missing_deed'), honesty_marker=UNKNOWN
RULE: BLANK > WRONG. A disclosed gap is correct output; an uncertain hop asserted as fact is a failure.

## 7. Output (write to scaffolded tables)
- title_chain_pull: header (parcel_id, county, selector_kind, selector_value, depth, source_platform='acclaim', status, reconciliation jsonb, honesty_summary jsonb, legal_description).
- title_chain_owner: one row per reconciled owner-period (seq, owner_name, owner_name_normalized, deed_type, deed_date, book_page, instrument_no, grantor, consideration, period_start, period_end, reconciliation_confidence, honesty_marker).
- title_chain_gap: any break.
- title_chain_encumbrance: leave EMPTY in P1.

## 8. Honesty / Liability
- Every output field carries a marker (VERIFIED from record / INFERRED name-only / UNKNOWN).
- Output is record-sourced intelligence: cite book/page on every instrument; state "per recorded instruments"; no opinion of marketability; gaps disclosed not filled. Inherits the ZoneWise disclaimer/shield (intelligence, not a title opinion; no indemnity).

## 9. Acceptance Criteria (testable)
- AC1: For 10 sample Duval parcels with a known recent sale, returns seq=1 and seq=2 owners with book/page populated.
- AC2: For every returned owner, reconciliation_confidence is set; the seq=1 deed is matched_legal (VERIFIED) or the case is logged as a gap with reason.
- AC3: No owner row is written with honesty_marker=VERIFIED unless legal description matched.
- AC4: A parcel whose prior deed cannot be tied to the legal description produces a title_chain_gap row, NOT a guessed owner.
- AC5: Re-running on the same parcel is idempotent (no duplicate owner rows per pull).
- AC6: Runs in GHA ubuntu-latest in < 6h for the 10-parcel batch; no secrets in logs/commits.

## 10. Build Constraints
- DEFAULT INFRA: Supabase + GHA only. Acclaim client + Playwright (if needed) install natively in ubuntu-latest. No Hetzner unless a single run cannot finish in 6h.
- EG14 + K1-K4 gates on prod. K1 think-first with V/U/I tags. K2 simplicity. K3 surgical (<=20% line growth). K4 goal-driven.
- CRED hygiene: secrets by name only; pre-flight grep on POST/PUT/LOG; never embed credentials in commits/logs/YAML.
- Honesty Protocol V3: every claim marker+basis; BLANK>WRONG; self_audit at end of run.

## 11. Pointers
- Spec SSOT: SELECT * FROM public.pencil_mcp_tool_spec WHERE tool_name='title_chain.pull' ORDER BY component_kind, ord;
- Result model: title_chain_pull, title_chain_owner, title_chain_encumbrance, title_chain_gap (created + indexed).
- Report parity context: public.pencil_report_parity_spec (sections 3,4,5,10 depend on this tool).
- Pairing reminder: never ship BidDeed without ZoneWise; foreclosures + tax deeds always together.
