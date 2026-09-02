# Everest Capital — Information Security Policy

**Entities covered:** Everest Capital of Brevard LLC, Everest Capital USA, BidDeed.AI, ZoneWise.AI, Winner Data (winnerdataai.com)
**Owner / Security contact:** Ariel Shapira, Founder & CEO — everestcapital8@gmail.com (monitored)
**Version:** 1.0 — Effective 2026-09-02 — Review cadence: quarterly, or after any security incident

---

## 1. Purpose and scope
This policy defines how Everest Capital identifies, mitigates, and monitors information-security risk across its software platforms and financial data integrations (Stripe, Plaid, bank data). It applies to all systems, code repositories, cloud accounts, and personnel (currently a single founder-operator plus AI-assisted engineering agents operating under the controls below).

## 2. Governance
- **Accountable owner:** Founder & CEO holds all administrative credentials and approves every change in the "always-ask" categories (§7).
- **Risk register:** Security findings are tracked as GitHub issues and in the Supabase `insights` / `finance_ops_log` tables with status, remediation, and verification evidence.
- **Incident history and remediation** are recorded in the internal security log (last major review: July–August 2026 RLS lockdown and key-rotation campaign).

## 3. Data classification
| Class | Examples | Handling |
|---|---|---|
| **Restricted** | API keys, access tokens, Plaid `access_token`, Stripe keys, bank/transaction data, customer PII | Vault-only storage, service-role-only access, never in source or logs |
| **Confidential** | Proprietary parcel/auction intelligence, pricing models, internal ledgers | RLS-protected tables; no anonymous read |
| **Public** | Marketing pages, public government records | No restriction |

## 4. Access control and authentication
- **Principle of least privilege.** Every automated component uses a dedicated, minimally-scoped credential (e.g., Postgres role `cfo_agent_ro` is SELECT-only; Cloudflare API tokens are scoped per purpose; Stripe uses a *restricted* key, not the account secret).
- **Database:** Row-Level Security is enabled on all application tables; no anonymous (`anon`) read policies on restricted or confidential tables; views run with `security_invoker`. Verified July 2026 (security-advisor errors reduced from 587 to 1 accepted PostGIS system-table exception).
- **Human access:** Single administrator; MFA enforced on GitHub, Cloudflare, Supabase, Stripe, and Plaid dashboards. Internal dashboards are gated by Cloudflare Zero Trust Access (identity-based login) and/or per-app secret keys.
- **Service credentials** are held in Supabase Vault or GitHub encrypted secrets; they are write-only from the API layer and are never printed to logs, issues, or chat transcripts.

## 5. Network and data encryption
- **In transit:** TLS 1.2+ everywhere — Cloudflare edge (Workers), Supabase (PostgREST/HTTPS), Stripe and Plaid APIs. No plaintext endpoints.
- **At rest:** Supabase-managed Postgres encrypted at rest (AES-256); Cloudflare Workers secrets encrypted; Supabase Vault (pgsodium) for application secrets.
- **Bank data:** Plaid `access_token`s are stored only in Supabase Vault, never in application tables; transaction data lands in RLS-protected `finance.*` tables readable only by service role and the read-only agent role.

## 6. Secure development and vulnerability management
- **Source control:** All code in GitHub; branch protection on `main`; changes land via commits/PRs with descriptive messages and linked issues.
- **Automated security gates in CI:** Semgrep security scan on pull requests; a deterministic RLS gate that fails any change introducing new tables without RLS or new anonymous access; secret-scanning; type-checks before deploy.
- **Dependency hygiene:** Pinned versions; official SDKs only (e.g., `plaid` npm, `@stripe/sync-engine`); license review before adopting third-party code.
- **Deployment:** Reproducible GitHub Actions workflows deploy to Cloudflare Workers/Supabase; no manual production edits.
- **Key rotation:** Credentials rotated on suspicion or exposure and on a scheduled basis (documented rotations: Cloudflare deploy token, Anthropic API key, Supabase service key — July/August 2026).
- **Patching:** Managed platforms (Supabase, Cloudflare) patch infrastructure; application dependencies reviewed monthly.

## 7. Change control ("always-ask" categories)
The following require explicit founder approval before execution: production schema changes, deletion of production data, security/authentication changes, API-key rotations, new third-party integrations, billing/payment-system changes, and any new recurring spend.

## 8. Logging, monitoring, and incident response
- **Logs:** Cloudflare Workers logs, Supabase logs, GitHub Actions run logs, and application audit tables (`finance_ops_log`, `agent_ops_log`) with actor, action, and timestamp.
- **Monitoring:** Supabase security advisor reviewed after every migration; CI gates block regressions.
- **Incident response:** (1) contain — revoke/rotate affected credentials, lock affected tables; (2) assess scope from logs; (3) remediate via migration/code; (4) verify (negative tests, e.g., anonymous read returns zero rows); (5) record in the security log; (6) notify affected parties/providers as required by law and contract. Target: containment within 24 hours of detection.

## 9. Privacy and consumer data rights
- Everest Capital connects **its own business bank accounts** via Plaid; no consumer end-users' bank data is collected or stored.
- Financial-data use is limited to internal bookkeeping, reconciliation, and reporting. Data is not sold or shared with third parties.
- Deletion: on request or when a connection is removed, the Plaid Item is removed via `/item/remove` and associated rows are purged; Stripe data is mirrored read-only and purged on account closure.
- Retention: financial records retained per statutory requirement (7 years); operational logs 90 days.

## 10. Third-party / vendor management
Core vendors: Supabase (database, vault), Cloudflare (edge, Zero Trust), GitHub (source, CI), Stripe (payments), Plaid (bank data), Anthropic (AI). Each is accessed with scoped credentials; vendor security posture (SOC 2 / ISO 27001) reviewed before onboarding.

## 11. Business continuity
Supabase daily backups with point-in-time recovery; infrastructure defined in code (migrations, workflows, `wrangler.toml`) so environments can be rebuilt from the repository.

## 12. Policy acknowledgment
Approved by: Ariel Shapira, Founder & CEO — 2026-09-02
