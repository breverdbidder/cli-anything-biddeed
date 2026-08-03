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

## POST-DEPLOY RESULT (verified)

Commit `95d8c2ff` deployed via `.github/workflows/deploy-worker.yml` (run
`30803730257`, success, 2026-08-03 ~10:00 UTC). Re-scanned immediately after:

| Target | Grade | Score | Tests passed | Raw file |
|---|---|---|---|---|
| biddeed.ai | **C+** | 60/100 | 8/10 | `mozilla-observatory-biddeed-after.json` |

**This does not meet the "A or above" target stated in the brief.** Reporting
that honestly rather than rounding up. History from the scanner itself:
F(10) → C+(60) in the same host record, confirming the header fix is what
moved the grade, not scan noise. `curl -I` against the live site (checked
5x post-deploy) confirms all 6 new headers present: `strict-transport-security`,
`content-security-policy`, `permissions-policy`, `referrer-policy`,
`x-frame-options`, `x-content-type-options`.

**Why C+ and not A:** this API version doesn't return a per-test breakdown,
but per the "Known limitation" above, Mozilla's algorithm caps CSP credit
when `script-src`/`style-src` include `'unsafe-inline'` — which this fix
still does, on purpose, because removing it requires converting every inline
`<script>` block in `src/worker.js` (PostHog init, per-page interaction
handlers) to a nonce-based or externalized pattern. That is a real code
change, not a header addition, and was out of scope for this
"pure-documentation, zero-cost" session per the goal statement. Full detail
at https://developer.mozilla.org/en-US/observatory/analyze?host=biddeed.ai

**Named follow-up to actually reach A:** externalize or nonce the inline
scripts in `src/worker.js`, then re-scan. Tracked here, not silently
dropped.

**Transient note during verification:** in the ~90 seconds after deploy,
`/data-retention` alternated between 200 (new code) and 404 (old code) across
different Cloudflare edge colos — normal rolling propagation, not a bug.
Stabilized to 200 across 5 consecutive checks afterward; confirmed again at
scan time (`status_code: 200` in the Observatory result above).

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
| biddeed.ai missing security headers | FIXED and DEPLOYED — verified live (F→C+, 10→60) | `mozilla-observatory-biddeed-after.json`, deploy run `30803730257` |
| biddeed.ai TLS | Already A — no action needed | `ssllabs-biddeed.json` |
| mcp.biddeed.ai security headers | Not modified this session — Vercel-hosted, outside `src/worker.js`'s scope | `response-headers-mcp.txt` |
| mcp.biddeed.ai TLS | UNKNOWN — scanner could not complete; not a confirmed fail | `ssllabs-mcp.json` |
| CSP `unsafe-inline` (blocks reaching A) | OPEN, named follow-up — not done this session | See "Why C+ and not A" above |
