# Rollback — issue #20025 EXIT VERCEL A (mcp.biddeed.ai)

Written before any DNS change is attempted, per intent guardrail #3
(docs/intent/20025.md). No DNS change has been made in this session — this
file is prepared so cutover can proceed safely whenever a DNS/Routes-scoped
CF token is available.

## Current live DNS record (VERIFIED — read via issue body's own capture, 2026-09-05)
- Zone: `biddeed.ai`, zone_id `dcb6876f057e0bb88be181d6e8d0dcbc`
- Record id: `44c5c371327762c2eeb4a27eea937217`
- Record: `mcp.biddeed.ai CNAME cname.vercel-dns.com`, proxied=false

## Rollback procedure (if any post-cutover gate fails)
1. Recreate the CNAME above exactly: `mcp.biddeed.ai CNAME cname.vercel-dns.com`, proxied=false (dns-only).
   ```
   PUT/POST /zones/dcb6876f057e0bb88be181d6e8d0dcbc/dns_records/44c5c371327762c2eeb4a27eea937217
   { "type": "CNAME", "name": "mcp.biddeed.ai", "content": "cname.vercel-dns.com", "proxied": false }
   ```
   (If the record id no longer exists because it was deleted during cutover, create a new CNAME record with the same name/content/proxied values instead of reusing the old id.)
2. Remove the Worker custom domain binding for `mcp.biddeed.ai` on `biddeed-mcp-production` (Cloudflare dashboard or `wrangler` — do not delete the Worker itself, only the route/custom-domain binding).
3. Confirm `https://mcp.biddeed.ai/api/mcp` again returns `server: Vercel` (not `server: cloudflare`).
4. Comment `ROLLED BACK` on the issue with the failing gate evidence that triggered the rollback.
5. The Vercel deployment and `biddeed-mcp` Vercel project stay untouched — they are not deleted or paused until #19812-C closes the account.

## Non-actions in this session
- No DNS record was created, modified, or deleted.
- No Worker custom domain was bound.
- `biddeed-mcp-production` was never deployed to Cloudflare's edge (workers.dev or otherwise) — see docs/spec/20025.md for why (CF_ACCOUNT_ID/CF_API_TOKEN unavailable in this runner session).
