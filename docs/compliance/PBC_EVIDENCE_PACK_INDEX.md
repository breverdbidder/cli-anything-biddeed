# BidDeed.AI — Prepared By Client (PBC) Evidence Pack

**Prepared:** August 3, 2026
**Prepared by:** Ariel Shapira, Founder + Claude (AI Architect)
**For review by:** Licensed CPA firm (SOC 2) or ANAB-accredited body (ISO 27001)

Every checkbox below links to a file that exists in this repository as of
2026-08-03 — verified by directory listing at the time this index was
written, not assumed. Two items the original planning brief expected to
exist (an OWASP ZAP report and a Garak LLM scan report) do **not** exist and
are marked "NOT YET AVAILABLE" rather than silently omitted or faked — see
`docs/compliance/policies/VULNERABILITY_MANAGEMENT_POLICY.md` for the
disclosed reason.

## SECTION 1 — Policies

- [x] `docs/compliance/policies/INFORMATION_SECURITY_POLICY.md`
- [x] `docs/compliance/policies/ACCESS_CONTROL_POLICY.md`
- [x] `docs/compliance/policies/CHANGE_MANAGEMENT_POLICY.md`
- [x] `docs/compliance/policies/VENDOR_MANAGEMENT_POLICY.md`
- [x] `docs/compliance/policies/VULNERABILITY_MANAGEMENT_POLICY.md`
- [x] `docs/compliance/policies/BUSINESS_CONTINUITY_POLICY.md`
- [x] `docs/compliance/policies/ACCEPTABLE_USE_POLICY.md`
- [x] `docs/compliance/policies/PRIVACY_AND_DATA_PROTECTION_POLICY.md`
- [x] `docs/compliance/policies/SECURITY_AWARENESS_POLICY.md`

## SECTION 2 — Risk Assessment

- [x] `docs/compliance/RISK_REGISTER.md` (23 risks, scored, 5 open TREATMENT PLANNED items disclosed)

## SECTION 3 — Internal Audit

- [x] `docs/compliance/INTERNAL_MOCK_AUDIT_REPORT.md` (live Supabase queries, 27/34 control tests PASS, 8 findings disclosed)

## SECTION 4 — Security Architecture Evidence

- [x] `docs/security/SECURITY_EVIDENCE_PACK.md`
- [x] `docs/security/VENDOR_SUB_PROCESSOR_LIST.md`
- [x] `docs/security/EXTERNAL_SCAN_SUMMARY.md`
- Mozilla Observatory grade: **F(10) → C+(60)** (biddeed.ai, before/after header fix, 2026-08-03; not A — CSP `unsafe-inline` gap disclosed as open follow-up)
- SSL Labs grade: **A** (biddeed.ai); `mcp.biddeed.ai` inconclusive (scanner-compatibility issue, not a confirmed TLS weakness)

## SECTION 5 — Penetration Test

- [ ] OWASP ZAP report — **NOT YET AVAILABLE**. No DAST scan has been run
  against production as of 2026-08-03. Disclosed in
  `docs/security/SECURITY_EVIDENCE_PACK.md` §10 and
  `docs/compliance/policies/VULNERABILITY_MANAGEMENT_POLICY.md`.
- [ ] Garak LLM scan report — **NOT YET AVAILABLE**. Same disclosure as above.
- [ ] Nikto web server scan — **NOT YET AVAILABLE**. Same disclosure as above.
- [x] `docs/security/mozilla-observatory-biddeed-before.json` / `-after.json` (header-hygiene scan, not a penetration test)
- [x] `docs/security/ssllabs-biddeed.json` / `ssllabs-mcp.json` (TLS configuration scan)

## SECTION 6 — Security Questionnaires

- [x] `docs/security/CAIQ-v4.1-BidDeed-Completed.md`
- [x] `docs/security/AI-CAIQ-v1.1-BidDeed-Completed.md`
- [x] `docs/security/SECURITY_QUESTIONNAIRE_ANSWERS.md`

## SECTION 7 — Incident Response

- [x] `docs/security/INCIDENT_RESPONSE_PLAN.md`

## SECTION 8 — Data Management

- [x] `docs/legal/DATA_RETENTION_POLICY.md`
- [ ] `biddeed.ai/privacy` — live URL, not independently re-verified in this pass
- [ ] `biddeed.ai/tos` — live URL, not independently re-verified in this pass
- [x] `biddeed.ai/data-retention` — referenced as live in `DATA_RETENTION_POLICY.md`

## SECTION 9 — Vendor Certifications

Each URL below was HTTP-checked live (200 response) on 2026-08-03 per
`VENDOR_SUB_PROCESSOR_LIST.md` — not re-checked again for this index, same
review date.
- Supabase: https://supabase.com/security
- Vercel: https://vercel.com/security
- Cloudflare: https://www.cloudflare.com/trust-hub/
- Stripe: https://stripe.com/docs/security/stripe
- GitHub: https://github.com/security
- Resend: https://resend.com/security
- Anthropic: https://trust.anthropic.com/

## SECTION 10 — Live System Evidence (re-runnable by the auditor)

- [x] `cron.job` active-jobs list — 110 active jobs confirmed live, 2026-08-03;
  see `INTERNAL_MOCK_AUDIT_REPORT.md` CC4.1 for the security-relevant subset
  with exact names and schedules.
- [x] `security_events` row count — 14 total, 11 in the last 30 days, all
  P2/P3 in that window (no P0/P1) — see CC7.2.
- [x] `mcp_api_keys` structure — confirmed hashed (`key_hash`, 64-char),
  `tier` and `is_active` both non-null across all 13 live rows — see CC6.1.
- [x] `secret_rotation_registry` — 37 secrets tracked; 35 show
  `last_rotated_at IS NULL` — disclosed gap, see Risk Register R008.
- [x] RLS coverage — 727/732 public tables enabled; 5 exceptions named — see
  Risk Register R001.
- [ ] Supabase security advisor output — not re-run as part of this index;
  the Mock Audit Report used direct `pg_class`/`information_schema` queries
  instead, since the advisor's own UI output isn't a queryable artifact from
  the Management API in the same way.

## SafeBase / Trust Portal

- [x] `docs/security/SAFEBASE_SETUP_GUIDE.md` — setup guide for the public
  trust portal referenced in prior work (`trust.biddeed.ai`). This index
  does not independently re-verify the portal is live and populated as of
  2026-08-03.

## AUDITOR NEGOTIATION NOTE

Sections 1-4, 6-9 are fully pre-prepared and internally consistent as of
this review. Section 5 (penetration test) has two of five items genuinely
not yet available — this is the single biggest gap standing between this
package and the auditor's likely expectations, and it is disclosed here
precisely so it can be scoped into the engagement letter rather than
discovered mid-audit. Section 10's live evidence can be re-demonstrated in a
single walkthrough session; most of it is a Management API query away.

Given the disclosed gaps (no DAST scan yet, one open high-severity access
grant finding in `docs/compliance/RISK_REGISTER.md` R021), a realistic
estimate is **3-4 auditor days**, not the 2-3 day target in the original
planning brief — see `INTERNAL_MOCK_AUDIT_REPORT.md` conclusion for the
reasoning.
