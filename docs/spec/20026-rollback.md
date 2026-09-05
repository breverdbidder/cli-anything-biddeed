# Rollback — issue #20026 — zonewise.ai DNS

Status as of this session: **no DNS change was made** (see docs/spec/20026.md — cutover intentionally not attempted). The values below are the CURRENT LIVE state of zone `zonewise.ai` (zone_id `b32406b78aaaefd55557d77c843a5940`) as recorded in the intent file, unchanged. This doc exists so the future cutover step has the exact restore values on hand before it makes any write, per guardrail #5 in docs/intent/20026.md ("no DNS change without this file committed first").

## Records to restore if a future cutover fails

| Record | Type | Value | Proxy status | Record ID |
|---|---|---|---|---|
| `zonewise.ai` | A | `216.150.1.1` | DNS-only (grey cloud) | `dd1d4f1d75e2e5db26a9bf3cd2fa52e7` |
| `www.zonewise.ai` | CNAME | `b655eaa023f33e94.vercel-dns-017.com` | DNS-only (grey cloud) | `bb6230a10d845c516bb0a91a2a7f079d` |

`mcp.zonewise.ai` currently has **no DNS record** (NXDOMAIN) — it is attached as a domain on the Vercel project but unresolvable. No rollback value needed for it; if it gets bound to the Worker in a future session and needs rollback, the correct action is simply to remove the binding/route (no record to recreate).

## Untouchable records (never modify, per intent guardrail #5)
Clerk records (`clerk.`, `accounts.`, `clk*`, `clkmail.`) and Google MX/SPF/TXT records in this zone.

## Rollback procedure (for whichever session performs cutover)
1. Remove the Worker's custom-domain routes for `zonewise.ai` / `www.zonewise.ai`.
2. Recreate the two records above via the Cloudflare API, DNS-only (not proxied), using the same values (record IDs will differ on recreation — that's expected, Cloudflare doesn't let you re-specify an old ID).
3. Confirm `https://zonewise.ai/` returns `server: Vercel` again before declaring rollback complete.
4. Comment `ROLLED BACK` on issue #20026 with the curl evidence.
