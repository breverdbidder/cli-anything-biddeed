# Security Awareness Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

## 1. Solo-Founder Context

Everest Capital USA has zero employees. A formal, multi-person security
training program is not applicable. In its place, this policy establishes a
quarterly self-review discipline for the sole operator.

## 2. Quarterly Self-Review Checklist

- OWASP LLM Top 10 (AI-specific threats relevant to the MCP/chatbot surface).
- CISA Known Exploited Vulnerabilities catalog, filtered to the stack in use
  (Node.js, PostgreSQL, Cloudflare Workers, Vercel).
- Supabase security advisor findings (run after any DDL operation, reviewed
  quarterly at minimum even absent a schema change).
- This 9-document policy suite, reviewed for continued accuracy against live
  system state.

## 3. Social Engineering Defenses

- Hardware security key (YubiKey) on all critical accounts — **planned, not
  yet purchased** as of 2026-08-03 (Risk Register R014).
- Carrier-level SIM port freeze on the founder's phone number.
- Phishing defense: bookmark canonical login URLs for GitHub, Supabase,
  Vercel, Cloudflare; never follow an email login link.

## 4. Annual Review

Next annual review: August 2027 (12 months from this policy's effective
date).
