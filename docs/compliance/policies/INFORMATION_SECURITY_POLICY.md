# BidDeed.AI — Information Security Policy (Master)

**Effective:** August 3, 2026
**Owner:** Ariel Shapira, Founder, BidDeed.AI / Everest Capital USA
**Status:** Prepared-by-client (PBC) draft for SOC 2 Type I / ISO 27001 pre-audit review.
This is an AI-generated draft (Claude, acting as AI Architect) intended for review
and sign-off by a licensed CPA firm (SOC 2) or ANAB-accredited certification body
(ISO 27001) — it is not itself an attestation or certification.

This is not legal advice.

---

## 1. Purpose & Scope

This policy governs all BidDeed.AI and ZoneWise.AI systems, data, and operations.
It applies to:

- Ariel Shapira, sole operator and Information Security Officer.
- All automated systems acting on the company's behalf: Claude Code (CC) agents,
  pg_cron scheduled jobs (110 active jobs in `cron.job` as of 2026-08-03, verified
  live), and Supabase Edge Functions.
- Everest Capital USA has zero W-2 employees. There is no internal workforce
  attack surface beyond the founder.

**Data in scope:**
- Florida public property, foreclosure, and tax-deed auction records
  (`multi_county_auctions`, `fl_parcels`, `zoning_assignments`) — public
  government records, not personal data.
- Customer PII: email address, Stripe customer ID (`mcp_api_keys`, `lead_profiles`).
- API keys — stored as SHA-256 hashes (`mcp_api_keys.key_hash`, confirmed
  64-character hash values, never plaintext) plus a non-secret `key_prefix`
  (e.g. `bd_live_rcMeTf`) used for display/lookup only.
- Vault secrets (`secret_rotation_registry`, 37 tracked secrets as of 2026-08-03).

## 2. Information Security Objectives

- **Confidentiality:** customer data is accessible only through scoped, hashed
  API keys gated by tier (`mcp_api_keys.tier` ∈ free/investor/pro/proplus/enterprise).
- **Integrity:** `gold_standard_*`, `insights`, `taxi_meter_*`, and
  `multi_county_auctions` are protected source-of-truth objects — writes require
  an explicit approval line naming the object (see Change Management Policy).
- **Availability:** Vercel (MCP server) and Supabase (database) both publish a
  99.9% SLA. `llm-health-5min` (cron jobid 10935, `*/5 * * * *`, active) checks
  platform health every 5 minutes.

## 3. Roles & Responsibilities

- **Information Security Officer:** Ariel Shapira — sole role, sole owner. No
  segregation-of-duties control exists because there is no second person; this
  is disclosed as a known control limitation of a solo-founder company, not
  hidden.
- **Automated security systems:** MCP guardrail scanning
  (`packages/biddeed-mcp/src/security/guardrails.js`, pattern-based
  prompt-injection and secret-leak detection at the single `handleToolCall`
  chokepoint), `security-alert-sweep` (cron jobid 10937, `*/15 * * * *`,
  active), `mcp-anomaly-detect-30min` (cron jobid 10973, `*/30 * * * *`, active).
- **External security partners:** Vercel, Supabase, Cloudflare — controls
  inherited per their own published SOC 2 Type II / ISO 27001 attestations
  (see `VENDOR_SUB_PROCESSOR_LIST.md`; this document does not independently
  re-verify vendor certification status beyond what each vendor's own trust
  page states).

## 4. Asset Management

- Crown-jewel assets: Shapira Formula parameters, `mcp_customers`,
  `fl_parcels`, `stripe_*` tables, vault secrets.
- Asset classification:
  - **Public** — FL property/auction records (no restriction).
  - **Confidential** — customer PII, usage logs.
  - **Restricted** — API key hashes, vault secrets, service-role credentials.
- 727 of 732 public-schema tables have Postgres Row-Level Security enabled
  (verified live via `pg_class.relrowsecurity`, 2026-08-03 — see Risk Register
  R001 for the 5 exceptions and why each is accepted).

## 5. Access Control

Full detail in `ACCESS_CONTROL_POLICY.md`. Summary:
- Least privilege: MCP tools gated by `tier`; S3/S5 tools additionally require
  `cert_required=true` verification before any billable call.
- No shared credentials. No plaintext secrets committed to the repository
  (enforced by `scripts/hooks/pre-bash-commit-quality.js` secret-pattern scan).
- API keys are hashed at rest (`mcp_api_keys.key_hash`, SHA-256, 64 chars) —
  confirmed by direct query, not assumed.

## 6. Cryptography

- Encryption at rest: AES-256, Supabase-managed (per Supabase's own security
  page — not independently re-verified by BidDeed this cycle).
- Encryption in transit: TLS 1.3, Cloudflare + Vercel edge termination.
  SSL Labs grade **A** on `biddeed.ai` (verified 2026-08-03,
  `docs/security/ssllabs-biddeed.json`). `mcp.biddeed.ai` SSL Labs probe
  returned inconclusive (scanner-compatibility issue, not a confirmed TLS
  weakness — flagged `UNKNOWN` per Honesty Protocol, not `FAIL`).
- Key management: Supabase Vault. `secret_rotation_registry` tracks 37
  secrets with a defined rotation interval (60–90 days depending on secret).
  **Known gap, disclosed:** as of 2026-08-03, 35 of 37 registered secrets show
  `last_rotated_at IS NULL` — the registry tracks rotation *schedule*, but the
  rotation-execution step has only run twice since the registry was created.
  Tracked as R008 in the Risk Register.

## 7. Physical Security

No owned physical infrastructure. All compute and storage run on Vercel,
Supabase, and Cloudflare. Physical controls are inherited per each vendor's
own SOC 2 Type II report.

## 8. Operations Security

- All deployments run through GitHub Actions (`cc-runner-ghonly.yml`).
- No direct production DB writes from interactive chat sessions — writes go
  through SECURITY DEFINER functions or GHA-run migrations, per the
  Credential Handling rule (GTM-22D).
- RLS is expected on all new tables; current live coverage is 727/732 (99.3%),
  not "all" — see §4.
- CI security gate: `.github/workflows/security-scan.yml` runs Semgrep SAST +
  Gitleaks + npm/pip audit on every PR. **Disclosed gap:** the
  `security_scan_results` table this workflow is designed to write to
  currently holds 0 rows (verified live, 2026-08-03) — the workflow file
  exists and is wired into PR gating, but no run has yet persisted a result
  row to this table. See Mock Audit Report CC7.1.

## 9. Incident Management

Full plan: `docs/security/INCIDENT_RESPONSE_PLAN.md`.
- P0 response SLA: 1 hour.
- Customer notification target: within 72 hours (internal operating target,
  faster than the statutory outer bound).
- Florida FIPA (FS 501.171) statutory requirement: notify the FL Department
  of Legal Affairs and affected individuals within 30 days of determining a
  breach affecting >500 FL residents occurred. The 72-hour internal target
  and the 30-day statutory ceiling are not in conflict — the former is an
  operating goal, the latter is the legal floor.

## 10. Compliance

- Florida Information Protection Act (FS 501.171).
- Florida foreclosure/tax-deed statutes (FS 197.552, FS 713.07).
- SOC 2 Type I: **In Preparation** — this package is the pre-audit evidence
  set, not an attestation.
- ISO 27001: **In Preparation** — no certificate has been issued.
- No external penetration test (OWASP ZAP or otherwise) has been run against
  production as of 2026-08-03. This is disclosed on the public `/security`
  page and in `SECURITY_EVIDENCE_PACK.md` §10, not hidden. External scans run
  to date are limited to Mozilla HTTP Observatory (header hygiene) and SSL
  Labs (TLS configuration) — see `EXTERNAL_SCAN_SUMMARY.md`.

## 11. Policy Review

- Reviewed: August 3, 2026.
- Next review: quarterly, or immediately upon any material architecture
  change (new vendor, new data flow, new production surface).
- Owner: Ariel Shapira.
