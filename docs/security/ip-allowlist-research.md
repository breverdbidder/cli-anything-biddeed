# Supabase IP Allowlist Research — 2026-08-03

**Verdict: BLOCKED. No network restriction applied.** Current live state confirmed
via `GET /v1/projects/mocerqjnksmhcjzxrewo/network-restrictions`:
`dbAllowedCidrs: ["0.0.0.0/0"]`, `dbAllowedCidrsV6: ["::/0"]`, `status: applied` —
i.e. the project is fully open today. This document is research only; nothing
was changed.

The brief's premise — "fetch Vercel egress IP ranges, fetch GitHub Actions IP
ranges, apply as a Supabase CIDR allowlist" — turned out to be wrong on two of
its three legs, independent of whether Anthropic's range could be found. Findings
below, per CC_META_PROMPT.md §2.3 (don't silently substitute a corrected query
and report green — show the work).

## 1. Vercel egress IPs — NOT fetchable, NOT static by default

The brief's endpoint, `https://www.vercel.com/api/edge-network/egress-ips`,
returns `404 Not Found` (confirmed live, 2026-08-03). It does not exist.

Checked Vercel's current docs instead
([Secure Compute](https://vercel.com/docs/networking/secure-compute),
[Static IPs](https://vercel.com/docs/networking/static-ips)):

> "By default, Vercel deployments can come from any IP address."

Static egress IPs are **not a default feature** — they are a paid add-on:

| Option | Tier | Price | What you get |
|---|---|---|---|
| Static IPs (shared pool) | Pro/Enterprise | **$100/mo per project** + private data transfer | Static IP pair per configured region, shared VPC |
| Secure Compute | Enterprise only | Custom pricing | Dedicated VPC, static IP pair, VPC peering |

No evidence in this repo that either is currently provisioned for `mcp.biddeed.ai`
(no `vercel_api_token` usage found in migrations/scripts referencing networking
config). Absent one of these add-ons, mcp.biddeed.ai's real outbound IP is drawn
from a large, shared, unpublished, dynamic AWS pool — there is no list to fetch.

**This directly collides with the brief's own NON-GOALS: "Do NOT purchase any
paid services."** Enabling Static IPs to make this deliverable possible would
itself violate that constraint. Flagging rather than deciding unilaterally to
spend $100/mo.

## 2. GitHub Actions IPs — technically fetchable, practically useless as an allowlist

`curl https://api.github.com/meta | jq '.actions'` works and returns real data —
but **7,297 CIDR blocks** (verified live 2026-08-03, `jq '.actions | length'` =
7297), because GitHub-hosted Actions runners share Azure's general-purpose public
IP space. Allowlisting this is close to allowlisting a meaningful slice of Azure's
public cloud:
- Provides negligible actual access control — the "restriction" would admit an
  enormous, constantly-reallocated pool that Microsoft controls, not GitHub.
- Azure churns these ranges regularly; a stored allowlist snapshot goes stale
  and either breaks CC dispatch runs (undercount) or silently widens again
  (if refreshed carelessly).
- Unclear whether Supabase's `dbAllowedCidrs` array has a practical size/request
  limit — no documented cap found, but a 7,297-entry array is unlikely to be
  what the platform's UI/API is designed around, and no other Supabase customer
  writeup describes doing this.

This is the same lane every `*/1`–`*/30` pg_cron job and every `cc-runner-ghonly.yml`
dispatch runs through (per FLEET-LANE-ROUTING.md and CC_META_PROMPT.md's own
credential-handling rule: "run any task that needs a credential INSIDE the GHA
runner"). Getting this wrong doesn't fail one integration — it can silently
break most of the always-on pipeline (acclaim-harvest, gold-standard-autopilot,
b2c-outbox-drain, etc. — 80+ active pg_cron jobs observed live).

## 3. Anthropic MCP egress IPs — actually published, this leg is fine on its own

Contrary to the brief's uncertainty, Anthropic does publish a stable outbound
range for MCP tool calls, per
[platform.claude.com/docs/en/api/ip-addresses](https://platform.claude.com/docs/en/api/ip-addresses)
(fetched live 2026-08-03):

- **Outbound (MCP tool calls, web search, web fetch): `160.79.104.0/21`**
- Inbound: `160.79.104.0/23` (IPv4), `2607:6bc0::/48` (IPv6) — not relevant here
- Phased-out (do not use): `34.162.46.92/32`, `34.162.102.82/32`,
  `34.162.136.91/32`, `34.162.142.92/32`, `34.162.183.95/32`

Caveat worth naming explicitly: this range covers Claude infrastructure making
*outbound* MCP tool calls to an external MCP server (e.g. a chat session with a
Supabase MCP connector configured). It does **not** cover this session's actual
access path — this session (and every CC dispatch) reaches Supabase via
`mgmt_sql.py` → the Supabase Management API, executed from inside a GitHub
Actions runner (see finding 2), not via an Anthropic-outbound MCP connection.
`ToolSearch` in this session found no registered Supabase MCP tool. If a
Supabase MCP connector is added to an interactive chat surface later, that
traffic would originate from `160.79.104.0/21` and would need this range
allowlisted — but that is a distinct access path from CC dispatch/GHA traffic.

## Why this is BLOCKED, not just partially done

Even with Anthropic's leg fully resolved, findings 1 and 2 mean there is no
CIDR set that is simultaneously (a) safe to apply without breaking production
(Vercel's real egress is unenumerable without the forbidden $100/mo purchase)
and (b) a meaningful security control (GitHub Actions' published range is too
broad to be one). Applying *any* restriction today, with the inputs currently
available, risks locking mcp.biddeed.ai or the CC/pg_cron fleet out of the DB —
exactly the failure mode the brief itself warned against ("DO NOT apply network
restrictions blindly and lock Claude out"), just via a different leg (Vercel/GHA)
than the one it anticipated (Anthropic).

## Recommendation (not executed — Ariel decision required)

1. Decide whether the $100/mo Vercel Static IPs add-on is worth it for
   `mcp.biddeed.ai` specifically. Without it, "restrict DB access to Vercel
   egress" is not achievable at all, at any effort level.
2. For CC/GHA-originated DB access, network-level restriction is the wrong tool
   given GitHub's IP range is too broad to be selective — the SECURITY DEFINER
   accessor pattern already in place (`cli_anything_get_secret`,
   `get_vault_secret_gated`, credential handling rules in CLAUDE.md) is the real
   control for that path, not a CIDR allowlist.
3. If a Supabase MCP connector is ever wired into an interactive Claude chat
   surface, `160.79.104.0/21` is the range to allowlist for *that* path
   specifically — worth revisiting then, independent of the Vercel/GHA blockers
   above.

## Negative test performed

`GET /v1/projects/mocerqjnksmhcjzxrewo/network-restrictions` before making any
change, confirming current state is fully open (`0.0.0.0/0` / `::/0`,
`status: applied`) — establishes the baseline this document did not alter.
