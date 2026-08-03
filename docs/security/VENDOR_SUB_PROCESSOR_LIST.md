# BidDeed.AI Sub-Processor / Vendor List

**Last reviewed:** August 3, 2026
**Method:** every security-page URL below was HTTP-checked live on 2026-08-03
(200 response). No certification is listed unless it appears on the vendor's
own published security/trust page — this document does not assert a
certification exists beyond what that page states, and does not claim
BidDeed.AI itself holds any of these certifications.

This is not legal advice.

| Vendor | Purpose | Data they handle | Location | Security / trust page | Last reviewed |
|---|---|---|---|---|---|
| **Supabase** | Primary database (`mocerqjnksmhcjzxrewo`) | Customer email, Stripe customer IDs, hashed API keys, auction/property records | US | https://supabase.com/security | 2026-08-03 |
| **Vercel** | Hosts the MCP server (`mcp.biddeed.ai`) | API requests/responses in transit, tool-call payloads | US | https://vercel.com/security | 2026-08-03 |
| **Cloudflare** | CDN, Worker runtime, and WAF for `biddeed.ai` | Edge traffic, chat requests, lead-capture form submissions | US (global edge) | https://www.cloudflare.com/trust-hub/ | 2026-08-03 |
| **Stripe** | Payment processing and billing (`biddeed-checkout`, `stripe-webhook` functions) | Payment card data (never touches BidDeed servers directly — Stripe Checkout/Elements), billing email | US | https://stripe.com/docs/security/stripe | 2026-08-03 |
| **Resend** | Transactional email delivery | Customer email address, email content (notifications, receipts) | US | https://resend.com/security | 2026-08-03 |
| **Anthropic** | LLM inference for the chatbot (`/chat/api`, routed via `claude-router` / Smart Router — chat tier does not call `api.anthropic.com` directly) | Chat message content sent by the customer during a session | US | https://trust.anthropic.com/ | 2026-08-03 |
| **GitHub** | Source code repository, CI/CD (Actions) | Source code, CI logs, no customer PII by design | US | https://github.com/security | 2026-08-03 |
| **Telegram** | Internal ops/security alerting only (Sentinel/Patrol scripts) | **No customer data** — operational alert text only | N/A | https://core.telegram.org/#telegram-faq | 2026-08-03 |
| **Florida county platforms** (RealForeclose / RealAuction / RealTaxDeed, county clerk sites, county property appraiser sites) | Source of public foreclosure/tax-deed auction records | Public government records only — no BidDeed customer data flows to these platforms | US (FL) | N/A — public government systems, not a data sub-processor of customer PII | 2026-08-03 |

## Not a sub-processor of customer data

- **MindStudio** — appears in `src/worker.js` only as an allow-listed outbound
  link domain (`app.mindstudio.ai`) for sanitizing chatbot output links. It is
  not currently in the customer-data processing pipeline. If that changes,
  this document must be updated before customer data is sent to it.

## Certifications — explicitly not claimed

This document intentionally does **not** assert SOC 2, ISO 27001, or PCI DSS
status for any vendor beyond what is stated on the vendor's own linked page
at the time of review. Readers should click through to the vendor's page for
the current, authoritative certification status — vendor compliance posture
changes over time and this table is a point-in-time snapshot.

## Review cadence

This list should be reviewed whenever a new vendor is added to the data path,
and at minimum every 6 months. Next review due: **February 2027** (6 months
from 2026-08-03).
