# Security Questionnaire Answer Bank

**Last updated:** August 3, 2026. **This is not legal advice.**

Lookup table for the 50 most common vendor security questionnaire (VSQ)
questions. When a customer or investor sends a questionnaire, find the
closest matching question below and copy/adapt the answer — don't
re-derive from scratch each time. Every answer here is grounded in the
same verified evidence as `CAIQ-v4.1-BidDeed-Completed.md` and
`AI-CAIQ-v1.1-BidDeed-Completed.md`; if this document and either of those
ever disagree, treat the CAIQ/AI-CAIQ as the more detailed source and
update this file.

**Before sending any answer externally:** if the underlying control has
changed since August 3, 2026 (e.g., MFA gets verified, a pen test gets
run, a rotation policy starts executing), update the answer here first —
do not send a stale claim just because it's already written.

---

## Encryption & Data Protection

### Q: Do you encrypt data at rest?
A: Yes. All data is encrypted at rest via Supabase's platform-managed
AES-256 encryption (Supabase is SOC 2 Type II certified). This is inherited
from our database vendor and enforced at the platform layer, not something
our application code can disable.

### Q: Do you encrypt data in transit?
A: Yes. TLS is enforced on every request at the Cloudflare and Vercel edge.
`biddeed.ai` holds an SSL Labs grade A (verified live). `mcp.biddeed.ai`'s
automated SSL Labs probe could not complete (scanner-blocked by Vercel's
edge, not a finding of weak TLS) — a direct `curl` handshake against it
completes cleanly on TLS 1.3/HTTP2.

### Q: Where is customer data physically stored?
A: United States only. Primary database: Supabase (US region). Application
hosting: Vercel (US). CDN/WAF: Cloudflare (US, global edge for caching, not
data storage). Payments: Stripe (US, PCI DSS Level 1). No sub-processor in
our vendor list stores customer data outside the US.

### Q: Do you support customer-managed encryption keys (BYOK)?
A: Not currently. This is not offered at our current stage.

### Q: How is data classified (public vs. sensitive)?
A: Informally, in three tiers: customer PII (email, billing identifiers),
Florida public court/property records (non-personal, sourced from
government filings), and hashed API usage metering. We do not yet publish
a formal written data classification policy as a standalone document.

---

## Access Control & Identity

### Q: How is access to your systems controlled?
A: MCP API access uses OAuth 2.1 (WorkOS AuthKit, RFC 9728 discovery) or a
scoped `bd_live_*` API key, both validated server-side on every call and
gated by customer tier. Production infrastructure access (GitHub, Supabase,
Cloudflare, Vercel) is limited to the founder — there are no other
employees or contractors with access.

### Q: Do you have MFA enabled on administrative accounts?
A: **We have not independently re-verified current MFA enrollment status
on our GitHub, Supabase, Cloudflare, and Vercel admin accounts as of this
document's date, and we won't claim it's confirmed until we have.** If this
is a blocking requirement for your evaluation, ask us for a current
screenshot/status check — we'll provide one rather than assert an
unverified "yes."

### Q: Do you enforce least-privilege access?
A: Yes. MCP tools are tier-gated (free/investor/pro/proplus/enterprise);
higher-risk tool tiers require a certification gate, and bypass attempts
are logged as security events.

### Q: How quickly can you revoke a compromised credential?
A: Immediately. API keys are disabled via a single `is_active=false` flag
update (`mcp_api_keys` table) — documented as the first step in our P0-A
incident playbook.

### Q: Do you run background checks on employees with system access?
A: Not applicable — BidDeed.AI has zero employees. The founder, Ariel
Shapira, is the only individual with production access. This eliminates
insider-threat surface from a second party by construction, rather than
mitigating it via policy.

### Q: How many people can access customer data?
A: One — the founder. No shared credentials, no offboarding risk, no
second party to grant or revoke access from.

---

## Testing & Vulnerability Management

### Q: Do you conduct penetration testing?
A: **Not yet.** No third-party or self-run DAST (e.g., OWASP ZAP) scan has
been run against production infrastructure as of this document's date.
This is disclosed on our public `/security` page rather than omitted; it's
an open item, scheduled as a follow-up pending scope confirmation for
scanning live customer-facing infrastructure. We do run static analysis
(Semgrep SAST), secret scanning (Gitleaks), and dependency audits on every
pull request.

### Q: What does your CI/CD security gate check?
A: Every pull request runs Semgrep SAST (default + secrets + JS/TS/Python
rulesets), Gitleaks secret detection, and npm/pip dependency audit.
CRITICAL/HIGH findings block the merge — this is a hard gate, not an
advisory report.

### Q: Have you had a third party assess your AI/LLM system specifically?
A: Not yet. No LLM red-team or adversarial-prompt-injection scan has been
run against our production MCP server or chatbot as of this document's
date.

### Q: Do you have a vulnerability disclosure / responsible disclosure program?
A: We accept reports at `security@biddeed.ai` and aim to respond within 48
hours. We do not yet run a formal bug bounty program.

### Q: What HTTP security headers do you set?
A: `biddeed.ai` sets HSTS (2yr, includeSubDomains, preload),
Content-Security-Policy, X-Content-Type-Options, X-Frame-Options,
Referrer-Policy, and Permissions-Policy. A prior Mozilla Observatory scan
found these missing entirely (grade F, 10/100); after deploying the fix,
a live re-scan confirmed grade C+ (60/100, 8/10 tests passing) — not yet A.
Our CSP still permits `unsafe-inline` for scripts/styles, which is what
caps the grade below A, pending an inline-script-to-nonce refactor.

---

## Incident Response & Detection

### Q: Do you have a documented incident response plan?
A: Yes. Written IRP with P0–P3 severity classification and specific
playbooks for data breach, prompt-injection success, bulk data
exfiltration, and brute-force API key attacks. Incident Commander: Ariel
Shapira. P0 response SLA: 1 hour. Available under NDA/on request — not
published in full detail publicly, since it documents exact remediation
steps and internal table names.

### Q: How would you notify us of a breach affecting our data?
A: Within 72 hours of confirming the breach, using the customer
notification template in our IRP, describing what happened, what data was
involved, containment steps taken, and what (if anything) you should do.
If more than 500 Florida residents are affected, we also notify the FL
Department of Legal Affairs per FS 501.171, within 30 days of determining
the breach occurred.

### Q: What logging/monitoring do you have in place?
A: `security_events` (structured security event log) and
`security_scan_results` (per-PR SAST/secret/dependency findings) tables in
our production database; `taxi_meter_streams`/`taxi_meter_tools` for
per-call API usage metering; Telegram-based real-time alerting for
security-relevant events via internal monitoring scripts.

### Q: Do you log access to secrets/credentials?
A: Not currently for direct vault-level decryption events — this is a
disclosed platform limitation (our secrets manager, Supabase Vault, does
not log decryption events by default, and no separate audit extension is
installed). Application-level access to secrets goes only through gated
accessor functions with name allow-lists, never direct table reads from an
interactive context.

### Q: Has your incident response plan been tested?
A: The plan is documented and dated; our first scheduled quarterly
tabletop review has not yet occurred as of this document's date (next due
November 2026).

---

## Data Retention & Privacy

### Q: What is your data retention policy?
A: Published at `biddeed.ai/data-retention`. Summary: API usage metering —
retained per active billing cycle (a fixed 90-day auto-purge for this data
is a stated goal, not yet independently confirmed as implemented); payment
records — 7 years (IRS requirement); customer account data — active
account life + 7 years post-closure; security event logs — 1 year; chat
history — 30 days.

### Q: How do we request deletion of our data?
A: Email `privacy@biddeed.ai`. We process deletion requests within 30
days. Florida public-record auction/property data cannot be deleted from
our copy, since it is sourced from county government systems we don't
control and was never personal data about you to begin with.

### Q: Are you GDPR compliant?
A: We do not currently target GDPR compliance as a formal certification —
our customer base and data processing are US/Florida-focused. If you are
an EU-based customer with GDPR requirements, contact `privacy@biddeed.ai`
to discuss your specific needs before relying on this document alone.

### Q: Are you CCPA compliant?
A: We have not pursued formal CCPA certification. Our deletion-request
process (`privacy@biddeed.ai`, 30-day turnaround) covers the practical
substance of a consumer deletion right, but this has not been reviewed
against CCPA's specific requirements by counsel as of this document's date.

### Q: What Florida-specific privacy law applies to you?
A: Florida's Information Protection Act (FS 501.171) governs our breach
notification obligations. As a platform handling Florida foreclosure/tax
deed public records, we also operate within the disclosure norms of FS
197.552 and FS 713.07 for the underlying public-record data itself.

---

## Sub-Processors & Vendor Management

### Q: Who are your sub-processors?
A: Supabase (database), Vercel (MCP server hosting), Cloudflare (CDN/WAF),
Stripe (payments), Resend (transactional email), Anthropic (LLM
inference), GitHub (source/CI). Full list with data-handled and
security-page links: `VENDOR_SUB_PROCESSOR_LIST.md`, reviewed 2026-08-03,
next review due February 2027.

### Q: Do your sub-processors hold SOC 2 certifications?
A: Supabase, Vercel, Cloudflare, and GitHub are each SOC 2 Type II
certified per their own published trust pages (not independently
re-verified by us beyond reading those pages). Stripe holds PCI DSS Level
1 and SOC 2. We do not independently re-audit our vendors' certifications
— we cite their own published attestations.

### Q: How do you vet new vendors before onboarding?
A: Currently by reviewing the vendor's own published security/trust page
before integration. We do not yet run a formal, standardized
pre-onboarding vendor security questionnaire process — this is a known gap
for future vendor additions, not something we claim to have today.

### Q: Do any of your vendors process data outside the United States?
A: Not per our current vendor list — Cloudflare's edge network is global
by design for caching/CDN purposes, but our actual data stores and
processing sub-processors (Supabase, Vercel, Stripe) are US-region.

---

## Business Continuity

### Q: What is your uptime SLA?
A: We do not publish our own SLA yet. Our infrastructure vendors (Supabase,
Vercel, Cloudflare) each publish >99.9% uptime SLAs at the platform level.
We own no physical infrastructure that would introduce a separate
single-point-of-failure beyond those vendors.

### Q: Do you have a disaster recovery plan?
A: Database backup/restore is managed at the Supabase platform level; we
have not independently tested a full restore-from-backup drill this
session. A standalone, BidDeed-authored business continuity plan document
does not yet exist separately from our incident response plan.

### Q: What happens to our data if BidDeed.AI shuts down?
A: Not currently formalized in a written wind-down/data-portability
commitment. If this is material to your evaluation, raise it directly with
`security@biddeed.ai` — we're a solo-founder company and this is a fair
question to ask explicitly rather than assume.

---

## AI / LLM-Specific

### Q: How do you protect against prompt injection?
A: We run native pattern-based prompt-injection and secret-leak scanning
(`guardrails.js`) at the single canonical tool-call chokepoint of our MCP
server, on all 25 tools — both caller arguments and tool results are
scanned before results are cached for reuse. All scraped county court
documents and case data are explicitly labeled to the model as untrusted
external data, never instructions. This is a native JavaScript
implementation (not a third-party framework like LlamaFirewall or LLM
Guard) because our server runtime has no Python execution path — a
documented, deliberate deviation, not a gap.

### Q: Is customer data used to train your AI models?
A: No. Chat content is sent to Anthropic for inference only, not retained
by us for fine-tuning. Our proprietary foreclosure/tax-deed scoring model
trains exclusively on Florida public court and property records, not on
individual customer accounts or usage behavior.

### Q: Do you monitor your AI model for bias or fairness issues?
A: Not currently as a dedicated process. We do have a data-quality
reconciliation mechanism that checks whether our auction records match the
official county source, but that is a data-freshness control, not a
model-fairness control — we're not going to represent it as the latter.

### Q: Can you explain individual AI-driven recommendations (explainability)?
A: Not yet at the per-prediction feature-importance level (e.g., SHAP) for
customer-facing users. Every report is explicitly framed as
decision-support with human accountability (the founder's own methodology
attribution), not an unexplained black-box output — but granular
per-prediction explainability is a roadmap item, not a current capability.

### Q: What is your AI model's accuracy/performance?
A: Our production foreclosure/tax-deed outcome classifier (XGBoost,
version v14.0) has a consistently observed AUC of approximately 0.78
across independent internal evaluations. We do not disclose training
dataset size, feature set, or model weights — these are protected trade
secrets under our IP policy, available for review under NDA in a
qualified diligence process.

### Q: Is there human oversight before AI output reaches a customer?
A: Yes for the methodology and scoring logic itself (founder-owned, no
autonomous retrain/redeploy without review). There is no fully autonomous
action path — e.g., the system never places a bid on a customer's behalf;
all output is decision-support for a human bidder.

---

## Compliance & Certifications

### Q: Do you have a SOC 2 report?
A: SOC 2 Type I is currently in preparation via TrustCloud (an
audit-readiness platform), not yet complete or certified. In the interim,
we provide a completed CAIQ v4-style self-assessment, an AI-specific
security self-assessment, our external scan summary (Mozilla HTTP
Observatory + SSL Labs), and this questionnaire bank — available at
`trust.biddeed.ai` once our SafeBase trust portal setup is complete, or
directly via `security@biddeed.ai` in the meantime.

### Q: Are you ISO 27001 certified?
A: No. Not currently pursued or claimed.

### Q: Do you carry cyber liability insurance?
A: Not currently. Planned post-Series A. Our security architecture (native
prompt-injection scanning, RLS on 723/728 public database tables, per-PR
SAST/secret-scan gate, tier-gated access control) is designed to reduce
both breach probability and blast radius in the meantime.

### Q: What is Row-Level Security coverage on your database?
A: 723 of 728 public tables (99%) have RLS enabled, verified by a direct
`pg_class.relrowsecurity` query. The remaining tables are reference/lookup
data with no customer or credential content.

### Q: Is your network access to the database restricted by IP?
A: No. Our Supabase project currently allows connections from any IP
(`0.0.0.0/0`) — confirmed live. We investigated restricting this to our
actual infrastructure's egress ranges and found it currently infeasible
without either a $100/mo Vercel add-on (for a static egress IP) or
allowlisting GitHub Actions' full published range (7,297 CIDR blocks, too
broad to be a meaningful restriction). Our actual compensating control for
credential protection is a gated, name-allow-listed accessor-function
pattern for all secrets, not network-level restriction. This is disclosed
as an open item, not a claimed control.

### Q: Do you rotate secrets/API keys on a regular schedule?
A: We have a live secret rotation *tracking* system (`secret_rotation_registry`,
37 tracked secrets) with automated weekly due-date alerting. As of this
document's date, the rotation itself has not yet executed for most tracked
secrets (35 of 37 have never been rotated) — the tracking and alerting
infrastructure is real and operating; the actual rotation cadence is a
work in progress, not yet a steady-state control. We're stating this
directly rather than claiming a rotation cadence that isn't happening yet.

---

*Questions not covered here: security@biddeed.ai. This document is
reviewed alongside `CAIQ-v4.1-BidDeed-Completed.md` and
`AI-CAIQ-v1.1-BidDeed-Completed.md` — treat those as the more detailed
source if this summary and either of them ever diverge.*
