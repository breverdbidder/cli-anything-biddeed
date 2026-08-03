# CSA CAIQ — BidDeed.AI Self-Assessment

**Prepared by:** Ariel Shapira, Founder, BidDeed.AI / Everest Capital USA
**Date:** August 3, 2026
**Scope:** `mcp.biddeed.ai` (MCP tool server), `biddeed.ai` (marketing/chat site), Supabase project `mocerqjnksmhcjzxrewo`
**This is not legal advice, and this is not a certified audit.** It is a vendor
self-assessment, structured against the Cloud Security Alliance Consensus
Assessments Initiative Questionnaire (CAIQ) domain model.

## Version note (read before distributing)

**INFERRED, not confirmed this session:** the brief that requested this
document specified "CAIQ v4.1" and "207 controls." The CSA's most recent
publicly documented CAIQ release at the time of this session's knowledge is
**v4.0.2** (mapped 1:1 to CSA Cloud Controls Matrix v4.0.12, ~197 controls).
No live check against `cloudsecurityalliance.org` was performed this session
to confirm a "v4.1" revision exists or to pull its exact control-ID list
verbatim. Rather than fabricate control IDs from memory and risk citing
codes that don't match the official spreadsheet, this document is organized
by the same **17 CCM/CAIQ domains** and answers the *substance* of each
domain's control intent, with representative control references. **Before
handing this to a counterparty who will cross-reference it line-by-line
against the official CSA workbook, download the current official CAIQ
spreadsheet from `cloudsecurityalliance.org/star` and re-map these answers
into it — do not represent this document as a verbatim reproduction of the
numbered CSA workbook.**

## How to read the answers

- **YES** — control is implemented; evidence cited is a live query, a file
  in this repo, or a table confirmed to exist by direct check.
- **NO** — control is not implemented. Stated plainly, not hedged.
- **PARTIAL** — some but not all of the control's substance is met; the gap
  is named.
- **N/A** — control does not apply to BidDeed's architecture (e.g., no
  physical datacenter is owned).
- **INHERITED** — control is the responsibility of an upstream SOC 2 Type
  II-certified vendor (Supabase, Vercel, Cloudflare, Stripe, GitHub); we did
  not re-verify their control independently, we reference their published
  security page.

Every YES below traces to a control that exists in this codebase or database
today, checked live during the August 3, 2026 security documentation
session or the companion sessions on the same date (`docs/security/
EXTERNAL_SCAN_SUMMARY.md`, `SECURITY_EVIDENCE_PACK.md`, `vault-audit-
2026-08-03.md`, `ip-allowlist-research.md`). Where this document's answer
differs from what an earlier internal brief assumed, the correction is
called out explicitly — see "Corrections from the originating brief" below.

---

## Corrections from the originating brief

The internal brief that requested this CAIQ assumed several controls that do
**not** match live evidence gathered in the same session. Per the operating
contract (`CC_META_PROMPT.md` §2.3 — "the DoD query itself may be wrong"),
these are corrected here rather than answered as if the brief's assumptions
were true:

| Brief assumed | Live evidence | This document answers |
|---|---|---|
| LlamaFirewall (Meta) + LLM Guard (Protect AI) on 36 MCP tools | MCP server is Node ESM with no Python runtime in its deploy path. Actual control: native JS pattern-based prompt-injection/secret-leak scanning in `packages/biddeed-mcp/src/security/guardrails.js` at the single `handleToolCall` chokepoint — documented deviation, commit `31a71992`. 25 tools, not 36, per the live `/security` page copy. | AIS/TVM answers describe the real guardrails.js control, not LlamaFirewall/LLM Guard. |
| OWASP ZAP DAST scan conducted August 2026, report at `docs/security/zap-report-2026-08-03.html` | No such file exists. `SECURITY_EVIDENCE_PACK.md` §10 and the live `/security` page both state explicitly: "Not yet performed... pending scope confirmation." | TVM-02 answered NO, not YES. |
| Garak LLM vulnerability scanner run monthly | No reference to Garak found anywhere in this repository. | Not claimed anywhere in this document. |
| `mcp_usage_log` table | Does not exist (confirmed 404 on REST HEAD, per `INCIDENT_RESPONSE_PLAN.md` §3 correction note). The real per-call metering tables are `taxi_meter_streams` / `taxi_meter_tools`. | LOG answers cite the real table names. |
| MFA "enforced" on GitHub/Supabase/Cloudflare/Vercel | No live check of MFA status on any of these four accounts was performed this session or found documented elsewhere in the repo. | IAM-02 answered PARTIAL/UNVERIFIED, not YES — see that row. |
| Secrets on a 90-day rotation schedule | `vault-audit-2026-08-03.md`: 35 of 37 tracked secrets have never been rotated (`last_rotated_at IS NULL`); the registry and a Monday-cadence alert exist, but the rotation itself is not yet happening on a 90-day cycle. | CEK-03 answered PARTIAL, with the real registry cited as evidence of the *tracking* control, not the rotation cadence. |
| Supabase network access restricted | `ip-allowlist-research.md`: confirmed live `dbAllowedCidrs: ["0.0.0.0/0"]` — fully open, blocked on investigation (Vercel has no fetchable static egress range without a $100/mo add-on forbidden by cost non-goals). | IVS/DCS answers do not claim network-level DB restriction. |

---

## A&A — Audit & Assurance

| Control | Answer | Evidence |
|---|---|---|
| A&A-01 Independent audit program exists | PARTIAL | No third-party financial/security audit firm engaged. Continuous internal evidence: `security_events`, `security_scan_results` tables (confirmed live, REST HEAD 200), and this document's own August 2026 self-assessment cycle. |
| A&A-02 Audit scope covers infrastructure and application layers | YES | `.github/workflows/security-scan.yml` runs Semgrep SAST + Gitleaks + npm/pip audit on every PR; upstream infra (Supabase/Vercel/Cloudflare) covered by their own SOC 2 Type II audits (inherited, not independently re-verified). |
| A&A-03 Independent penetration testing performed | NO | Not yet performed against production. Explicitly disclosed, not omitted — see `SECURITY_EVIDENCE_PACK.md` §10 and the live `/security` page. |
| A&A-04 Audit findings tracked to remediation | YES | `security_scan_results` table stores per-PR SAST/secret/dependency findings; CRITICAL/HIGH block merge (hard gate, not advisory). |
| A&A-05 Right-to-audit clause offered to enterprise customers | PARTIAL | No formal contractual audit-rights clause published yet; available on request via `security@biddeed.ai` for enterprise deals. |

## AIS — Application & Interface Security

| Control | Answer | Evidence |
|---|---|---|
| AIS-01 Secure SDLC with static analysis | YES | Semgrep SAST (`p/default`, `p/secrets`, `p/javascript`, `p/typescript`, `p/python`) on every PR to main. |
| AIS-02 Customer access requirements documented and enforced | YES | OAuth 2.1 (WorkOS AuthKit, RFC 9728 protected-resource discovery) or scoped `bd_live_*` API keys, validated server-side on every MCP call. |
| AIS-03 Application security testing before release | PARTIAL | SAST on every PR (YES). Independent DAST (OWASP ZAP): NOT yet run — see corrections table above. |
| AIS-04 Data input validation | YES | All MCP tool arguments pass through the guardrails.js pattern-scanning chokepoint before reaching a tool handler; billing/idempotency gate also validates request shape. |
| AIS-05 Baseline security requirements for outsourced/bespoke development | N/A | Solo founder, no outsourced development. |

## BCR — Business Continuity Management & Operational Resilience

| Control | Answer | Evidence |
|---|---|---|
| BCR-01 Business continuity plan documented | PARTIAL | No standalone BCP document exists yet. Infra resilience is inherited: Supabase, Vercel, and Cloudflare each publish >99.9% uptime SLAs; BidDeed owns no single-point physical infrastructure. |
| BCR-02 Disaster recovery / backup strategy | INHERITED | Supabase manages automated Postgres backups at the platform level; BidDeed has not independently verified backup restore procedures this session. |
| BCR-03 Business continuity testing performed | NO | No documented DR test/tabletop for infrastructure failure. (Note: the *incident response* tabletop — a related but distinct process — is scheduled quarterly per `INCIDENT_RESPONSE_PLAN.md` §7, next due November 2026.) |
| BCR-04 Equipment / physical redundancy | N/A | No BidDeed-owned datacenter or physical hosting equipment. |

## CCC — Change Control & Configuration Management

| Control | Answer | Evidence |
|---|---|---|
| CCC-01 Documented change management process | YES | All changes flow through GitHub PRs to `main`; Cloudflare Worker and Vercel both auto-deploy on merge; `.claude/rules/scripts.md` and `CC_META_PROMPT.md` codify agent-driven change discipline. |
| CCC-02 Change approval and testing before production | PARTIAL | CI security gate blocks CRITICAL/HIGH findings pre-merge. No mandatory human code review step is enforced for solo-founder commits (there is no second engineer) — this is a named structural gap, not hidden. |
| CCC-03 Configuration baseline / infrastructure-as-code | PARTIAL | Supabase migrations are file-based and version-controlled (`supabase/migrations/`). Cloudflare/Vercel project settings are managed via their dashboards, not fully codified as IaC. |
| CCC-04 Unauthorized software change detection | YES | Gitleaks + Semgrep run on every PR; any change lands as a diff reviewable in GitHub, not a hidden config edit. |

## CEK — Cryptography, Encryption & Key Management

| Control | Answer | Evidence |
|---|---|---|
| CEK-01 Encryption at rest | INHERITED (YES) | Supabase-managed AES-256 encryption at rest on the primary Postgres database — per Supabase's own published security documentation, not independently re-verified this session. |
| CEK-02 Encryption in transit | YES | TLS enforced at Cloudflare + Vercel edge termination on every request. SSL Labs grade **A** on `biddeed.ai` (`ssllabs-biddeed.json`, live 2026-08-03). `mcp.biddeed.ai`'s SSL Labs probe was inconclusive (scanner-blocked, not a finding of weak TLS) but `curl -I` confirms a normal TLS 1.3/HTTP2 handshake. |
| CEK-03 Key/secret rotation policy and tracking | PARTIAL | `public.secret_rotation_registry` (37 rows) and a weekly Monday 09:00 UTC `pg_cron` due-date check with Telegram alerting are live and verified (`vault-audit-2026-08-03.md`). **However**, 35 of 37 tracked secrets have never actually been rotated (`last_rotated_at IS NULL`) — the tracking/alerting control exists; the rotation cadence itself is not yet operating. Answered PARTIAL, not YES, per the corrections table above. |
| CEK-04 Secrets never committed to source / no plaintext storage | YES | Secrets live in Supabase Vault (encrypted) or GitHub Actions secrets, accessed only through gated SECURITY DEFINER functions (`cli_anything_get_secret`, `get_vault_secret_gated`) with name allow-lists — never via direct table read from an interactive/chat context (`CREDENTIAL HANDLING`, GTM-22D). One open finding: `get_vault_secret_mcp()` has no internal gate and overly broad EXECUTE grants — tracked as an unresolved follow-up, not hidden. |
| CEK-05 Key management for customer-controlled encryption | N/A | BidDeed does not offer customer-managed encryption keys (BYOK) at this stage. |

## DCS — Datacenter Security

| Control | Answer | Evidence |
|---|---|---|
| DCS-01 through DCS-09 (physical security, environmental controls, equipment maintenance, etc.) | INHERITED / N/A | BidDeed owns no physical datacenter. All physical/environmental controls are the responsibility of Supabase, Vercel, and Cloudflare, each SOC 2 Type II certified. Refer to their published trust pages (`supabase.com/security`, `vercel.com/security`, `cloudflare.com/trust-hub`) for their datacenter attestations — not independently re-verified by BidDeed this session. |

## DSP — Data Security & Privacy Lifecycle Management

| Control | Answer | Evidence |
|---|---|---|
| DSP-01 Data classified by sensitivity | PARTIAL | Informal classification exists in practice (customer PII vs. public FL court/property records vs. hashed usage metering) but is not written as a formal data classification policy document. |
| DSP-02 PII inventory maintained | PARTIAL | Customer PII is limited and known (email, Stripe customer ID, billing identifiers in `lead_profiles`/`mcp_api_keys`) but no standalone PII inventory document exists separate from `DATA_RETENTION_POLICY.md`. |
| DSP-03 Data retention and deletion policy published | YES | `docs/legal/DATA_RETENTION_POLICY.md`, live at `biddeed.ai/data-retention`. Per-table retention windows stated; deletion requests processed within 30 days via `privacy@biddeed.ai`. |
| DSP-04 Automated data purge for logs/usage data | PARTIAL | `security_events` purges at 1 year, `claude_chat_history` at 30 days (per policy). **Not verified this session:** an automated 90-day purge for `taxi_meter_streams`/`taxi_meter_tools` usage metering — explicitly flagged as unconfirmed in `DATA_RETENTION_POLICY.md`'s own correction note, not claimed as done. |
| DSP-05 No training of third-party foundation models on customer data without disclosure | YES | Chat content is routed to Anthropic for inference per the vendor list; BidDeed does not separately fine-tune or share customer data with any other model provider. Foreclosure/tax-deed ML scoring (`shapira_models` XGBoost) trains only on public Florida court/property records, not on individual customer account data. |
| DSP-06 Data residency documented | YES | All primary data stores (Supabase, Vercel, Cloudflare, Stripe) are US-region; no offshore processing identified in the vendor list. |

## GRC — Governance, Risk & Compliance

| Control | Answer | Evidence |
|---|---|---|
| GRC-01 Information security governance program | PARTIAL | No formal ISMS (e.g., ISO 27001-style policy set) exists. Operational governance is codified in `CLAUDE.md`, `CC_META_PROMPT.md`, and the Honesty Protocol — these function as de facto engineering/security governance for a solo-founder operation but are not a certified governance framework. |
| GRC-02 Risk assessment performed and documented | PARTIAL | Ad hoc risk findings are logged as they're discovered (e.g., this session's IP-allowlist blocker, the `get_vault_secret_mcp()` grant finding) but there is no standing, scheduled enterprise risk register. |
| GRC-03 Security policies reviewed and approved | PARTIAL | Individual policy documents (IRP, Data Retention, Vendor List) each carry a "last reviewed" date and a stated review cadence, but there is no single umbrella policy-review calendar. |
| GRC-04 Security awareness training | N/A | Solo founder, no employees to train. |

## HRS — Human Resources Security

| Control | Answer | Evidence |
|---|---|---|
| HRS-01 through HRS-11 (background checks, employment agreements, termination access revocation, etc.) | N/A — structural advantage, not a gap | BidDeed.AI has zero employees. Ariel Shapira is the sole individual with any production access. There is no insider-threat surface from a second party, no offboarding risk, no shared credential ever issued to a departing employee. This should be read by reviewers as a smaller attack surface, not an unanswered control. |

## IAM — Identity & Access Management

| Control | Answer | Evidence |
|---|---|---|
| IAM-01 Identity management for customer access | YES | OAuth 2.1 (WorkOS AuthKit) or scoped `bd_live_*` API keys per customer, tier-gated. `mcp_api_keys.is_active` provides an immediate kill switch. |
| IAM-02 Multi-factor authentication enforced on administrative access | **PARTIAL / UNVERIFIED** | No live check of MFA enrollment status on the GitHub, Supabase, Cloudflare, or Vercel admin accounts was performed this session, and no prior document in this repo records having verified it either. This is corrected from the originating brief, which assumed MFA was confirmed enforced on all four. Recommend Ariel confirm and screenshot MFA status on each platform as the actual evidence artifact — do not answer YES here until that's done. |
| IAM-03 Least privilege / role-based access | YES | MCP tools are tier-gated (free/investor/pro/proplus/enterprise); `CERT_REQUIRED` gates apply to higher-risk tool tiers, with bypass attempts logged as P2 security events per the Incident Response Plan. |
| IAM-04 Credential/API key lifecycle management | YES | Keys are created, deactivated (`is_active=false`), and never stored in plaintext; the Incident Response Plan's P0-A/P1-A playbooks name the exact `UPDATE mcp_api_keys` disable path. |
| IAM-05 Segregation of duties | N/A | Solo founder — no second party to segregate duties from. Named as a structural constraint, not a bypassed control. |

## IPY — Interoperability & Portability

| Control | Answer | Evidence |
|---|---|---|
| IPY-01 Open, documented API/protocol | YES | MCP (Model Context Protocol) is an open, publicly specified protocol; tool schemas are documented, not a proprietary black box. |
| IPY-02 Customer data export capability | PARTIAL | Data can be retrieved via authenticated MCP tool calls / direct Supabase export by BidDeed on request; no fully self-service bulk-export UI exists yet for customers. |
| IPY-03 No proprietary lock-in on customer's own data | YES | Customer account and usage data is standard Postgres rows; nothing about the storage format itself locks a customer's own data into a proprietary container. |

## IVS — Infrastructure & Virtualization Security

| Control | Answer | Evidence |
|---|---|---|
| IVS-01 through IVS-13 (hypervisor security, network segmentation, VM hardening, etc.) | INHERITED | Compute/virtualization layer is entirely Vercel- and Cloudflare-managed (serverless/edge); Supabase manages the database VM/container layer. BidDeed owns no VM or hypervisor infrastructure directly. Refer to each vendor's SOC 2 Type II report for this domain. |
| IVS-14 Network-level access restriction to the database | **NO** | Corrected from the originating brief's assumption. Live check 2026-08-03: `dbAllowedCidrs: ["0.0.0.0/0"]`, `dbAllowedCidrsV6: ["::/0"]` — fully open. Investigated and blocked: Vercel has no fetchable static egress IP range without a $100/mo add-on (forbidden by cost constraints), and GitHub Actions' published range (7,297 CIDR blocks) is too broad to be a meaningful control. The actual compensating control is the SECURITY DEFINER accessor-function pattern for credentials, not network restriction — see `ip-allowlist-research.md`. |

## LOG — Logging & Monitoring

| Control | Answer | Evidence |
|---|---|---|
| LOG-01 Security event logging | YES | `security_events` table (confirmed live, REST HEAD 200) captures structured security events; `security_scan_results` captures per-PR SAST/secret/dependency findings. |
| LOG-02 Usage / access logging | YES | `taxi_meter_streams` / `taxi_meter_tools` — confirmed live — record per-call MCP tool usage and billing metering. **Correction:** the previously referenced table name `mcp_usage_log` does not exist; these are the real tables. |
| LOG-03 Automated alerting on security events | YES | Telegram bot alerting via `scripts/sentinel.sh` / `sentinel-patrol.sh`; P0 severity target SLA is 1 hour per the Incident Response Plan. Monthly synthetic-alert test planned (insert a test P0 row, confirm Telegram fires within 15 minutes, delete the row) — see IRP §7. |
| LOG-04 Log retention policy | YES | `security_events`: 1 year then purged, per `DATA_RETENTION_POLICY.md`. |
| LOG-05 Vault/secret access logging | **NO** | `vault-audit-2026-08-03.md`: no `vault_access_log` exists in `public` or `vault` schema; no `pgaudit` extension installed. Supabase Vault does not log decryption events by default — a platform limitation, disclosed rather than hidden. |

## SEF — Security Incident Management, E-Discovery & Cloud Forensics

| Control | Answer | Evidence |
|---|---|---|
| SEF-01 Documented incident response plan | YES | `docs/security/INCIDENT_RESPONSE_PLAN.md` — severity classification (P0–P3), detection sources, per-scenario playbooks (data breach, prompt injection, bulk exfiltration, brute force), customer notification template. |
| SEF-02 Incident reporting channel published | YES | `security@biddeed.ai`, 48-hour response target stated on the public `/security` page. |
| SEF-03 Regulatory breach notification procedure | YES | Florida FIPA (FS 501.171): notify affected individuals and the FL Department of Legal Affairs within 30 days of determining a breach affecting >500 FL residents, per both the IRP and `DATA_RETENTION_POLICY.md`. |
| SEF-04 Incident response plan tested | PARTIAL | Plan is documented and dated; the first quarterly tabletop review is scheduled for November 2026, not yet performed as of this document's date. |

## STA — Supply Chain Management, Transparency & Accountability

| Control | Answer | Evidence |
|---|---|---|
| STA-01 Sub-processor list published and maintained | YES | `docs/security/VENDOR_SUB_PROCESSOR_LIST.md` — every vendor touching customer data, with sourced security-page links, reviewed 2026-08-03, next review due February 2027 (6-month cadence). |
| STA-02 Vendor security posture reviewed before onboarding | PARTIAL | Current vendor list was reviewed retrospectively this session, citing each vendor's own published trust page. No formal pre-onboarding vendor security questionnaire process exists yet for *future* vendor additions. |
| STA-03 Fourth-party (sub-processor's sub-processor) disclosure | N/A | Not independently tracked; customers relying on this should reference each named vendor's own sub-processor list (e.g., Supabase's, Stripe's) directly. |

## TVM — Threat & Vulnerability Management

| Control | Answer | Evidence |
|---|---|---|
| TVM-01 Static/dependency vulnerability scanning | YES | Semgrep SAST + Gitleaks secret scanning + npm/pip dependency audit on every PR via `.github/workflows/security-scan.yml`; CRITICAL/HIGH findings block merge. |
| TVM-02 Independent penetration testing / DAST performed | **NO** | Corrected from the originating brief. Not yet performed against production. `SECURITY_EVIDENCE_PACK.md` §10 and the live `/security` page both disclose this explicitly. No `docs/security/zap-report-2026-08-03.html` exists. |
| TVM-03 HTTP security header hygiene | PARTIAL | Mozilla HTTP Observatory scan (2026-08-03) found `biddeed.ai` at grade **F** (10/100, missing all security headers) prior to this session's fix. `src/worker.js` now sets HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy — deployed and re-scanned live, confirmed grade **C+ (60/100, 8/10 tests passing)**, not yet A (see `EXTERNAL_SCAN_SUMMARY.md`, `mozilla-observatory-biddeed-after.json`). CSP still permits `unsafe-inline` for script/style, which is what caps the score below A — a named, open follow-up (externalize/nonce the inline PostHog and interaction scripts), not resolved this session. |
| TVM-04 AI/LLM-specific adversarial testing | **NO** | No LLM red-team or adversarial prompt-injection scanning tool (Garak or otherwise) has been run. The live `/security` page states this plainly: "not yet run against production... scheduled as a follow-up." |

## UEM — Universal Endpoint Management

| Control | Answer | Evidence |
|---|---|---|
| UEM-01 through UEM-15 (device management, disk encryption, patch management, etc.) | PARTIAL / N/A | Solo founder, single managed device, no fleet of employee endpoints to manage centrally (no MDM needed by definition). No independent verification this session of disk encryption or patch status on that single device — answered PARTIAL rather than assuming YES. |

---

## Summary for procurement reviewers

BidDeed.AI is a solo-founder company with a small, mostly-inherited attack
surface (three SOC 2 Type II-certified infrastructure vendors carry the
bulk of physical/network/datacenter controls). Its genuine, independently
built controls are: OAuth 2.1 / scoped API key access control, tier-gated
MCP tool access, a native prompt-injection/secret-leak scanning chokepoint,
a per-PR SAST/secret/dependency CI gate, a written incident response plan,
and a published data retention policy. Its genuine, disclosed **gaps** as of
this document's date are: no completed third-party penetration test, no
completed LLM red-team scan, an open Supabase network-restriction gap
(root-caused, not silently accepted), unverified MFA enforcement on admin
accounts, and a secret-rotation *tracking* system that is live while the
rotation itself has not yet executed for 35 of 37 secrets. Every gap above
is named because SOC 2 Type I is genuinely in preparation, not complete —
this document is meant to substitute for follow-up questions, not to hide
the ones that would otherwise be asked.

*Questions not answered here: security@biddeed.ai.*
