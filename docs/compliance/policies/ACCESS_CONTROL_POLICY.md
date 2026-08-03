# Access Control Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

## 1. Multi-Factor Authentication

MFA is required on every account with write access to production: GitHub,
Supabase (dashboard + Management API token), Vercel, Cloudflare. Hardware
security key (YubiKey) enrollment is planned but **not yet purchased** as of
2026-08-03 (see Risk Register R014) — TOTP-based MFA is the current control.

## 2. API Key Model

- Customer-facing access uses OAuth 2.1 scoped API keys (`bd_live_*` prefix),
  one per customer, gated by `mcp_api_keys.tier`.
- Keys are hashed at rest (`key_hash`, SHA-256, 64 hex chars — confirmed by
  direct query against 3 sample rows, 2026-08-03). The raw key is shown to the
  customer exactly once at issuance and is not recoverable from the database.
- `mcp_api_keys` had 13 total rows at last review, 0 with a NULL `tier` or
  NULL `is_active` (verified live, 2026-08-03).

## 3. Access Review

- Quarterly: Ariel reviews all rows in `mcp_api_keys` where `is_active = true`
  against actual customer billing status in Stripe.
- Ad hoc: any P0/P1 security event triggers an out-of-cycle review of the
  affected key and any keys sharing the same `stripe_customer_id`.

## 4. Termination / Revocation

Immediate, single-statement revocation:
```sql
UPDATE mcp_api_keys SET is_active = false WHERE key_hash = '<hash>';
```
This is the same mechanism documented in the Incident Response Plan P0-A and
P1-A playbooks — access control and incident response use one shared kill
switch, not two divergent code paths.

## 5. No Shared Accounts

- No shared logins across GitHub, Supabase, Vercel, or Cloudflare.
- No root/admin API keys embedded in application code. Privileged database
  operations run exclusively through `SECURITY DEFINER` Postgres functions
  owned by `postgres`, callable only by `postgres` or `service_role` — never
  raw table grants to `anon` or `authenticated` for write paths.

## 6. Privileged Access — Known Open Finding

`get_vault_secret_mcp()` has no internal gate and `EXECUTE` is granted to
`PUBLIC`/`anon`/`authenticated`/`service_role`/`postgres` — functionally an
unrestricted vault read for anyone holding an anon key. This is a carried-over
open finding from GTM-22D (2026-07-19), not newly discovered here, and it is
listed as a residual risk (R002-adjacent) rather than silently omitted from
this policy. Tightening this grant requires Supabase-support-level access
because `REVOKE ... FROM service_role` on `vault.decrypted_secrets` cannot be
executed by the `postgres` role itself (grantor is `supabase_admin`).
