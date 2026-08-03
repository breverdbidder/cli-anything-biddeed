# Change Management Policy

**Effective:** August 3, 2026 · **Owner:** Ariel Shapira
AI-generated PBC draft — for CPA/ISO auditor review, not a finished attestation.

## 1. Change Path

All production changes land through GitHub pull requests to `main` on
`breverdbidder/cli-anything-biddeed`. There is no direct-to-production edit
path outside of git. CC (Claude Code) agents commit with descriptive messages
under the same branch/PR discipline as the founder.

## 2. Deployment

- Vercel auto-deploys on merge to `main` (MCP server, `mcp.biddeed.ai`).
- The marketing/chat surface (`biddeed.ai`) deploys via
  `.github/workflows/deploy-worker.yml` to Cloudflare Workers — confirmed live
  by the `95d8c2ff` deploy (run `30803730257`, success, 2026-08-03).

## 3. Protected Objects

`gold_standard_*`, `insights`, `taxi_meter_*`, and `multi_county_auctions` are
protected source-of-truth objects. Any change touching them requires an
explicit approval line in the originating issue naming the object by name —
"probably fine" is not sufficient authorization, per `CC_META_PROMPT.md` §3.4.

## 4. Schema Changes

- Schema changes (CREATE/ALTER TABLE, new indexes, new functions, RLS
  policies) may be dispatched autonomously via `supabase db push` for
  non-destructive operations.
- `DROP TABLE`/`TRUNCATE` on production tables, schema changes to
  billing/payment tables, and `supabase db reset` require Ariel's explicit
  approval — never autonomous.

## 5. Rollback

- Vercel: instant rollback to the prior deployment via the dashboard.
- Cloudflare Worker: redeploy the prior commit via the same GHA workflow.
- Supabase: point-in-time recovery (PITR), RPO 1 hour.

## 6. Change Record

Every merged PR is itself the change record — commit message, diff, and CI
run are permanently attached to the PR. No separate change-log system is
maintained; git history is the system of record (last 10 commits reviewed
live for this package — see Internal Mock Audit Report CC8.1).
