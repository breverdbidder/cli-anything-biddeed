# BidDeed.AI Security Evidence Pack

**Last updated:** August 3, 2026
**Prepared by:** Ariel Shapira, Founder, BidDeed.AI / Everest Capital USA

This is the single document to hand an investor or enterprise prospect who
asks "what's your security posture." Every linked document is committed to
`breverdbidder/cli-anything-biddeed` under `docs/security/` and `docs/legal/`.
This is not legal advice.

## 1. Security Architecture Summary

BidDeed.AI is a solo-founder Florida foreclosure/tax-deed auction
intelligence platform. Customer-facing traffic terminates at Cloudflare
(TLS, WAF, edge caching) in front of a Cloudflare Worker serving the
marketing site and chatbot at `biddeed.ai`, and at Vercel in front of the
MCP tool server at `mcp.biddeed.ai`. Both surfaces read and write a single
Supabase Postgres database (`mocerqjnksmhcjzxrewo`) that holds customer
account records, billing/usage metering, and Florida public auction data.

The system's most distinctive security surface is that it is an AI product:
the MCP server accepts natural-language tool calls and the chatbot accepts
free-text customer input, both of which are treated as untrusted input to an
LLM. Guardrail scanning (§5) exists specifically because the attack surface
here is prompt injection and data exfiltration through a chat interface, not
just classic web app vulnerabilities.

## 2. Data Flow Diagram

```
                    ┌─────────────┐
   Customer  ─────▶ │  Cloudflare │  TLS termination, WAF, edge cache
  (browser/MCP)     │ (biddeed.ai)│
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌──────────────────┐     ┌──────────────────────┐
     │ Cloudflare Worker │     │   Vercel (MCP server)│
     │  (marketing/chat) │     │   mcp.biddeed.ai      │
     └─────────┬──────────┘     └──────────┬────────────┘
               │  guardrails.js scan        │  guardrails.js scan
               │  (chat input)               │  (tool args + results)
               ▼                             ▼
        ┌─────────────────────────────────────────┐
        │        Supabase Postgres                  │
        │  mocerqjnksmhcjzxrewo.supabase.co          │
        │  RLS enabled on 723/728 public tables      │
        └─────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Stripe (payments)      │
              │  Resend (email)         │
              │  Anthropic (LLM infer.) │
              └────────────────────────┘
```

Note: `BIDDEED_SSOT.md` (dated 2026-07-20) records `mcp.biddeed.ai` as
served by a local machine via Cloudflare Tunnel rather than Vercel. Live
`curl -I` evidence gathered 2026-08-03 (this session) shows Vercel response
headers on `mcp.biddeed.ai`. This diagram reflects the live-observed
topology; see `EXTERNAL_SCAN_SUMMARY.md` for the full note. This discrepancy
is flagged for owner follow-up, not silently resolved.

## 3. Controls Summary Table

| Control | Implementation | Status |
|---|---|---|
| Encryption in transit | TLS on every request (Cloudflare + Vercel edge termination) | VERIFIED — SSL Labs grade A on biddeed.ai (`ssllabs-biddeed.json`) |
| Encryption at rest | Supabase-managed encryption at rest | VERIFIED per Supabase's own security page (see vendor list) — not independently re-verified this session |
| Access control | OAuth 2.1 (WorkOS AuthKit) or scoped `bd_live_*` API keys on every MCP call; `mcp_api_keys.is_active` kill switch | VERIFIED — table exists live, referenced in Incident Response Plan |
| Row-Level Security | 723/728 public tables (99%) | VERIFIED by direct `pg_class.relrowsecurity` query, per `/security` page, August 2026 |
| AI/prompt-injection guardrails | Pattern-based scanning at the single `handleToolCall` chokepoint (`packages/biddeed-mcp/src/security/guardrails.js`) | VERIFIED — code present, 60/60 tests passing as of commit `31a71992` |
| Rate limiting / abuse control | Billing-gated, idempotency-keyed MCP tool calls (no double-charge/double-execute on retry) | VERIFIED — per `/security` page |
| Logging / monitoring | `security_events`, `security_scan_results`, `taxi_meter_streams`/`taxi_meter_tools` | VERIFIED — tables exist live (REST HEAD checks, 2026-08-03) |
| CI security gate | Semgrep SAST + Gitleaks + npm/pip audit on every PR (`.github/workflows/security-scan.yml`) | VERIFIED — workflow file present |
| HTTP security headers (biddeed.ai) | HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy | FIXED this session (`src/worker.js`), pending deploy — see `EXTERNAL_SCAN_SUMMARY.md` |
| External DAST (OWASP ZAP) | Not yet run against production | OPEN — flagged on `/security` page as not yet performed, pending scope confirmation |

## 4. Compliance Posture

- **SOC 2 Type I:** In preparation.
- **CASA Tier 2:** Planned.
- **Florida FIPA (FS 501.171):** Breach notification procedure documented in
  the Incident Response Plan and Data Retention Policy.
- No certification is claimed on the public `/security` page beyond what is
  directly verifiable — see the "No fake badges" statement on that page.

## 5. AI-Specific Security

- **Prompt injection protection:** native pattern-based scanning
  (`guardrails.js`) at the MCP server's single canonical tool-call
  chokepoint — scans both caller arguments and tool results before results
  are cached for idempotent replay.
- **Untrusted-data labeling:** every MCP tool response carries an explicit
  notice that scraped county records and case data are untrusted external
  data, never instructions to the model.
- **Known deviation from an earlier spec:** an earlier brief called for
  Python-based `llm-guard`/`LlamaFirewall`. The MCP server is Node ESM with
  no Python runtime in its deploy path, so native JS pattern-based scanning
  was implemented instead — documented in commit `31a71992`, not hidden.

## 6. Incident Response

See [`INCIDENT_RESPONSE_PLAN.md`](./INCIDENT_RESPONSE_PLAN.md) (internal,
GitHub-only — not published to the public website). Security contact:
security@biddeed.ai.

## 7. Vendor List

See [`VENDOR_SUB_PROCESSOR_LIST.md`](./VENDOR_SUB_PROCESSOR_LIST.md).

## 8. Data Retention

See [`../legal/DATA_RETENTION_POLICY.md`](../legal/DATA_RETENTION_POLICY.md),
live at https://biddeed.ai/data-retention.

## 9. External Scan Results

See [`EXTERNAL_SCAN_SUMMARY.md`](./EXTERNAL_SCAN_SUMMARY.md) — Mozilla HTTP
Observatory and SSL Labs results, raw JSON attached.

## 10. Penetration Test

**Not yet performed.** No OWASP ZAP (or other DAST) scan has been run
against production as of this document's creation. This is disclosed
explicitly rather than omitted — the public `/security` page states the
same. Running one against live customer-facing infrastructure is a
decision that needs an explicit go-ahead, not something to do silently in
a documentation session.

## 11. Founder Security Statement

> I've spent 20+ years in Florida tax-deed and foreclosure investing and
> hold a 14-claim provisional patent on the analysis this platform
> automates. As a solo founder, I don't have a security team — which means
> I don't get to hide behind one. Every control on this page is something I
> can point to directly: a live query, a passing CI gate, a header on the
> wire. Where something isn't done yet, this page says so instead of
> claiming it. That's the standard I'd want from a vendor handling my own
> deal data, and it's the one I'm holding this platform to.
>
> — Ariel Shapira

---

*This document is not legal advice. Contact security@biddeed.ai to request
this evidence pack or ask a question not covered here.*
