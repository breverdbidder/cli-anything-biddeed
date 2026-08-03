# External Security Scan Summary

**Scans run:** August 3, 2026, ~09:55–10:00 UTC
**Method:** live HTTP calls to the Mozilla HTTP Observatory API, SSL Labs API,
and raw `curl -I` header dumps against the production domains. Raw output
saved alongside this file.

This is not a penetration test. It covers transport/header hygiene only.

## Mozilla HTTP Observatory

| Target | Grade | Score | Tests passed | Raw file |
|---|---|---|---|---|
| biddeed.ai | **F** | 10/100 | 5/10 | `mozilla-observatory-biddeed-before.json` |
| mcp.biddeed.ai | N/A — scan failed | — | — | scanner returned `scan-failed`: "Site did respond with an unexpected HTTP status code 404." `mcp.biddeed.ai` has no browsable GET route (it's a JSON-RPC MCP endpoint); the Observatory's browser-page model doesn't apply to it. |

**Root cause of the F grade (biddeed.ai):** the Cloudflare Worker set no
security response headers at all prior to this session — no
`Content-Security-Policy`, no `Strict-Transport-Security`, no
`X-Content-Type-Options`, no `X-Frame-Options`, no `Referrer-Policy`, no
`Permissions-Policy`. Confirmed directly via `curl -I` (see
`response-headers-biddeed-before.txt` — only `cache-control`, `content-type`,
Cloudflare's own `report-to`/`nel`/`server`/`cf-ray`/`alt-svc` were present).

**Fix applied this session:** `src/worker.js` now wraps every response with
`withSecurityHeaders()`, setting HSTS (2yr, includeSubDomains, preload),
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: strict-origin-when-cross-origin`, a `Permissions-Policy`
that denies geolocation/camera/microphone, and a `Content-Security-Policy`
scoped to `'self'` plus the specific PostHog and Supabase hosts this site
actually calls.

**Known limitation, disclosed rather than hidden:** the CSP's `script-src`
and `style-src` still include `'unsafe-inline'`. The site's PostHog init
snippet and several per-page interaction scripts are inline `<script>`
blocks without nonces. Mozilla Observatory penalizes `unsafe-inline` in
`script-src` — so this fix is expected to move the grade meaningfully off F,
but **may land below A** until those inline scripts are converted to
nonce-based or externalized. That conversion is a real code change across a
~3,700-line file, not a header tweak, and is out of scope for a
"pure documentation, zero cost" session. It is logged here as the specific,
named follow-up rather than silently left for someone to discover.

**Status:** fix committed; grade re-scan pending deploy via
`.github/workflows/deploy-worker.yml`. See the `POST-DEPLOY RESULT` section
below once available — do not treat the pre-fix F grade as current after
this commit lands.

## SSL Labs (TLS configuration)

| Target | Grade | Notes |
|---|---|---|
| biddeed.ai | **A** (all 4 tested endpoints) | Cloudflare-terminated TLS, cached result from SSL Labs (`status: READY`). Raw: `ssllabs-biddeed.json`. |
| mcp.biddeed.ai | **Inconclusive** — not a finding of weak TLS | SSL Labs could not complete its handshake probe against 2 of 2 endpoints: one returned `"Unexpected failure"` at the `TESTING_ECDHE_PARAMETER_REUSE` step, the other `"Failed to communicate with the secure server"`. This is consistent with Vercel's edge having anti-scanning/bot protection that blocks SSL Labs' non-browser probe pattern, not evidence of a TLS misconfiguration — `curl -I` against the same host completes a normal TLS 1.3/HTTP2 handshake without error. Raw: `ssllabs-mcp.json`. Flagged as `UNKNOWN`, not `FAIL` — per Honesty Protocol, absence of a completed scan is not evidence of a bad grade. |

## Raw response headers

- `response-headers-biddeed-before.txt` — biddeed.ai, pre-fix
- `response-headers-mcp.txt` — mcp.biddeed.ai (note: HSTS already present by
  Vercel platform default, `max-age=63072000`, even before this session's
  Worker-side changes — Vercel is a separate deploy target from the
  Cloudflare Worker and was not modified this session)

## Architecture note surfaced during this scan (not silently resolved)

`BIDDEED_SSOT.md` §1 (dated 2026-07-20) states "no Vercel project exists for
biddeed (verified 2026-07-20)" and describes `mcp.biddeed.ai` as served by
the local Dell via Cloudflare Tunnel. Live evidence gathered this session
(2026-08-03) contradicts that: `curl -I https://mcp.biddeed.ai/` returns
`server: Vercel` and an `x-vercel-id` header. Per CC_META_PROMPT §2.3 ("the
DoD query itself may be wrong") this discrepancy is reported, not silently
resolved — either the SSOT is stale (something changed serving targets
between 2026-07-20 and now) or there is a routing nuance not captured by a
single root-path curl. This document and the Security Evidence Pack use the
live-observed Vercel evidence since it is what was directly verified this
session; `BIDDEED_SSOT.md` §1 itself was not altered, since correcting
production topology is outside this task's scope and deserves its own
verified session.

## Fix ledger

| Item | Status | Evidence |
|---|---|---|
| biddeed.ai missing security headers | FIXED (code) / PENDING (deploy) | `src/worker.js` `withSecurityHeaders()` |
| biddeed.ai TLS | Already A — no action needed | `ssllabs-biddeed.json` |
| mcp.biddeed.ai security headers | Not modified this session — Vercel-hosted, outside `src/worker.js`'s scope | `response-headers-mcp.txt` |
| mcp.biddeed.ai TLS | UNKNOWN — scanner could not complete; not a confirmed fail | `ssllabs-mcp.json` |
| CSP `unsafe-inline` | Open, named follow-up | See "Known limitation" above |
