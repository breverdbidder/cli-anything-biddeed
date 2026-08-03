# Acceptable Use Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

## 1. Permitted Use

BidDeed.AI's MCP tools and chatbot are provided for Florida foreclosure and
tax-deed auction investment intelligence only.

## 2. Prohibited Use

- Using MCP tools to scrape or resell competitor data.
- Bulk data export beyond the customer's tier limits.
- Reverse-engineering the Shapira Formula or any proprietary scoring model
  through repeated probing.
- Attempting prompt injection against the chatbot or MCP tool-call interface.

## 3. Rate Limiting

Enforced at the Cloudflare WAF layer: 30 requests/minute on `/chat/api`, 60
requests/minute on `/api/mcp`. Violations return HTTP 429.

## 4. Prompt Injection Response

A confirmed prompt injection attempt is treated as a P0 security event per
the Incident Response Plan (P0-B playbook) — immediate API key suspension,
guardrail pattern update, and regression test added to
`packages/biddeed-mcp/test/guardrails.test.js`.

## 5. Bulk-Sweep Detection

`mcp-anomaly-detect-30min` (cron jobid 10973, `*/30 * * * *`, confirmed
active) flags anomalous usage patterns (e.g., an API key querying an unusual
number of counties in a short window) for review under the P1-A playbook.

## 6. Consequences

Confirmed violations result in immediate key revocation
(`UPDATE mcp_api_keys SET is_active = false`) and, where warranted, referral
for legal action under Florida law. There is no formal three-strikes
process — a single confirmed prompt-injection or exfiltration attempt is
sufficient grounds for immediate suspension pending investigation.
