# CANON — Winner Data / BidDeed / ZoneWise

**Status:** canonical. Authored Aug 24 2026 (Ariel Shapira, ratified via chat,
recorded live in `public.unified_context` key `winnerdata_canon_v1`).

## Override rule

**Canon overrides any log, memory line, or prior chat.** If a statement in a
dated activity log, a session memory file, a Slack/chat message, or a prior CC
session's output conflicts with a file in this directory, **canon wins** — do
not re-derive positioning, avatars, or compliance posture from the log. Update
canon explicitly (with owner sign-off) if it needs to change; never let it
drift back to whatever the most recent chronological entry says.

This directory exists because positioning drift already cost real cycles:
Winner Data was repeatedly mis-described by a single downstream vertical it
serves (see [`01_WINNER_DATA_CANON.md`](01_WINNER_DATA_CANON.md#what-it-is-not)
for the specific mis-descriptions) because the correct framing was buried
inside a 14KB dated activity log instead of living somewhere durable and
load-bearing. The fix is canon-at-top, in three places: this repo
(`docs/canon/`), the mirrored copy in `everest-battle-cards/canon/`, and the
live DB row (`public.unified_context.winnerdata_canon_v1`).

## Files

| File | Covers |
|---|---|
| [`01_WINNER_DATA_CANON.md`](01_WINNER_DATA_CANON.md) | What Winner Data is / is not, buyer + subject avatars, moat, proof points, positioning frame, pricing |
| [`02_COMPLIANCE_DOCTRINE.md`](02_COMPLIANCE_DOCTRINE.md) | B2B-only data-sales doctrine, statutory hooks (Fla. Stat. 501.1377), contract shape, schema rule |
| [`03_PRODUCT_AVATAR_MAP.md`](03_PRODUCT_AVATAR_MAP.md) | Substrate → generator → three product faces, Fact Finder vertical map, signal sources |
| [`04_OPERATING_RULES.md`](04_OPERATING_RULES.md) | Honesty Protocol V3 tags, MCP-live claims, dispatch routing, license doctrine, memory discipline |

## Provenance

Recorded live in Supabase `public.unified_context`:

```
project_name = 'winnerdata'
category      = 'canon'
key           = 'winnerdata_canon_v1'
source        = 'Ariel Shapira, Aug 24 2026; canon overrides any log or prior chat'
```

Query to re-verify: `SELECT * FROM public.unified_context WHERE key = 'winnerdata_canon_v1';`
