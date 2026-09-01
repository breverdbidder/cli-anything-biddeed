# CANON 04 — Operating Rules

**Canon overrides any log, memory line, or prior chat.** See [`README.md`](README.md).
Authoritative as of Aug 24 2026.

## Honesty Protocol V3 tags

Every claim in any session output carries a tag: `VERIFIED` (proof attached —
DB query, curl output, test result, commit SHA), `UNTESTED` (not tested yet,
zero penalty), or `INFERRED` (guessed from context, must include a
one-sentence evidence trail). See `CC_META_PROMPT.md` §0 (PRIME DIRECTIVE) for
the full session-level enforcement of this — this canon entry states the rule
itself; the meta-prompt states the process around it.

- Never claim a number that was not re-queried this session.
- Never claim an MCP server is live without an observed 200 handshake.

## Dispatch routing

Canonical dispatch workflow: GitHub Actions workflow `297104962`
(`cc-runner-ghonly.yml`). Sharded by issue. See `BIDDEED_SSOT.md` for the full
infrastructure inventory this dispatch path runs against.

## Zero-HITL scope

Standing authorization covers: schema-additive migrations, non-destructive
DDL, RLS policies, doc commits, and dispatch of scoped SUMMIT work. Always-ask
list: anything that drops or truncates a protected table
(`gold_standard_*`, `insights`, `taxi_meter_*`, `multi_county_auctions`),
credential rotation, and force-push/history-rewrite operations. See
`CLAUDE.md` Supabase CLI section for the exhaustive list.

## License doctrine (License V2)

- Hard reject: AGPL, GPL, SSPL, BUSL — any copyleft or source-available
  license with field-of-use or network-copyleft terms incompatible with a
  commercial SaaS.
- CourtListener: **permanently out** — do not reconsider without an explicit
  new owner decision.
- `juriscraper` / `eyecite`: BSD-2, approved for forked/vendored use (see
  `fl_appellate_watch.py`).

## Memory discipline

**Canon at top.** Durable positioning, compliance doctrine, and product
framing live in `docs/canon/` (this directory), never in a dated activity log
or a session memory file. Sprint-level logs, session summaries, and
in-progress status belong in GitHub issues or `public.agent_ops_log` — those
are the chronological record, not the source of truth for what the company
is or how it operates. When a chronological entry and canon disagree, canon
wins; update canon explicitly if it's actually wrong.

## No ZIP files

Never deliver or commit work as a ZIP archive. Commit real files to the
repo so they're diffable, greppable, and reviewable.

## LMS credential recovery (forgot-password)

Forgot the Winner Data LMS admin login (HTTP Basic Auth)? No CC session
needed: GitHub → this repo → Actions → **LMS Credential Reset (self-service
forgot-password)** → Run workflow. It generates a fresh username/password,
rotates it live on the Worker, the GitHub secrets, and the Supabase vault,
then emails the new credentials to everestcapital8@gmail.com. See
`.github/workflows/lms-credential-reset.yml` for the mechanics.
