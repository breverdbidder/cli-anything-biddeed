# NowCerts MCP Server Audit — ReduceMyIns/Nowcerts

**Verdict: HARD_REJECT the OSS-adopt path. Own thin client (already built —
`pipelines/winnerdata/momentum_delivery.py`).**

## What was actually checked (live, 2026-08-24)

The parent issue names the audit target as "github ReduceMyIns/Nowcerts (also
ReduceMyIns/Nowcerts-mcp on glama.ai)" claiming "96+ NowCerts endpoints as 100+ MCP tools,
MIT license per glama mirror." Neither of those exact names exists. Live search of the
`ReduceMyIns` GitHub org and GitHub's repository search API found one plausible match:

```
gh api repos/ReduceMyIns/nowcerts-mcp-server-v3
```

| Field | Value |
|---|---|
| Full name | `ReduceMyIns/nowcerts-mcp-server-v3` |
| Description | "Complete NowCerts MCP Server v3.0 with EZLynx integration, comprehensive search, fuzzy matching, and 50+ lines of business support" |
| **Size** | **0 bytes** |
| **Pushed at** | 2025-09-27T08:28:24Z (repo created, never pushed to since) |
| Branches | `[]` (none) |
| Forks | `[]` (none — nothing to recover a snapshot from) |
| License (GitHub API) | `null` |

**This repository is empty.** `gh api repos/.../git/trees/...` and the contents API both
fail because there is no commit history at all, not because of a permissions issue. The
description's claim of "96+ endpoints," "50+ lines of business," and EZLynx integration
describes code that does not exist at this URL.

A parallel check of glama.ai's registry (`https://glama.ai/mcp/servers?query=nowcerts`)
returned **zero results** for "nowcerts" — no glama mirror of this or any NowCerts MCP
server is currently indexed. The brief's "glama mirror" claim for a license/tool-count
number could not be independently verified because the page it would need to exist on
does not.

**Conclusion: there is no code to audit.** License gate, credential handling, and endpoint
coverage cannot be evaluated against a repository with zero commits. This is the audit
finding, not a gap in this session's research.

### License gate (per CLAUDE.md License V2 policy)

N/A — cannot apply AGPL/GPL/SSPL/BUSL = HARD_REJECT gate to a repository with no LICENSE
file and no source. The `null` license shown by the GitHub API for an empty repo is not
evidence of permissive licensing; it's evidence of nothing being there to license.

### Credential handling

N/A for the same reason — there is no client code to trace whether/how a NowCerts
password-grant credential would flow through the server.

### Endpoint coverage vs. our mapping needs

N/A — zero endpoints implemented (zero code).

### Momentum Rate / rating-submission endpoints

Cannot be answered from this repo. Answered instead from the **public NowCerts API
surface** (see below): rating submission is out of scope for the Zapier-facing endpoint
family this bridge uses. No `Zapier/*` endpoint in the public Postman collection
(`ReduceMyIns/Nowcerts-API`, 130 documented calls, api version 2.1.5) submits a rating
request or returns a bindable quote — the closest primitives are `Zapier/InsertQuote`
(records a quote that already exists elsewhere) and `PushJsonQuoteApplications` (pushes a
prebuilt quote application object, not a rating call). Everything this delivery bridge
does — `InsertProspect`, `SimpleCustomField/Insert`, `InsertTask` — is prefill/CRM data
entry, not rating. **Conclusion: rating is Quotelinq-prefill-only, consistent with the
parent issue's framing** — the producer or Quotelinq reads the Prospect + custom fields
this bridge writes and originates the actual rate quote through Momentum Rate's own UI/
API, which this bridge does not call.

## What was found instead (useful, real, and reused)

Two real repositories under the same org turned out to be directly useful, and are what
`pipelines/winnerdata/momentum_delivery.py` actually sources its endpoint contract from
(see `FF_TO_MOMENTUM_MAPPING.md` for the field-by-field mapping):

### 1. `ReduceMyIns/Nowcerts-API` — public Postman collection

Real content: `postman/collections/14647412-...json`, 332KB, "NowCerts Api - Version:
2.1.5", 130 documented requests including `POST /token`, `POST /Zapier/InsertProspect`,
`POST /Zapier/InsertTask`, `POST /Zapier/UpdateTask`, `GET /CustomFieldsList`, `POST
/SimpleCustomField/Insert`, `GET /CustomFieldValuesList`, `GET /ProspectStatusList`. No
LICENSE file (README is a two-line stub: "Nowcerts API documentation") — this is API
*documentation*, not software, so the AGPL/GPL/SSPL/BUSL gate doesn't apply to it the way
it would to adopted code; it was used as a reference contract only, no code copied.

### 2. `ReduceMyIns/n8n-nodes-momentum` — MIT-licensed, real shipped code

A working n8n community node (`nodes/Momentum/Momentum.node.ts`, 5.6KB), `LICENSE.md` is
the standard n8n community-node MIT template ("Copyright 2022 n8n"). Confirms the Postman
collection isn't stale: it independently implements the identical `/token` password-grant
flow and calls `/Zapier/InsertProspect`, `/Zapier/InsertInsured`, `/Zapier/InsertPolicy`,
`/Zapier/InsertTask` with matching body shapes. Notably **thin** — no custom-field support,
no search/dedupe, no idempotency, four hardcoded operations with no error-recovery beyond
surfacing the raw NowCerts error body. It's real evidence the contract works, not something
substantial enough to adopt wholesale (REPOEVAL below explains why).

## REPOEVAL — `ReduceMyIns/n8n-nodes-momentum` (the only real, licensed candidate found)

| Dimension | Score | Note |
|---|---|---|
| Security | 6/10 | MIT, no dependency red flags, but credentials flow through n8n's generic credential store with no scoping/rotation support of its own. |
| Value | 3/10 | Covers 4 of the ~10 operations this bridge needs (no custom fields, no search, no idempotency, no lead_activity/Supabase integration — those are 100% of what makes this a *bridge* rather than a demo). |
| Stability | 4/10 | Single-maintainer n8n community node, last updated 2025-09-25, no tests in the repo, one file. |
| Integration | 2/10 | It's an n8n node, not a Python library — would require standing up an n8n instance and a workflow-JSON translation layer to reuse inside `cli-anything-biddeed`'s Python pipeline, for a net loss versus writing ~150 lines of `urllib` directly (which is what this issue did). |
| Cost | 8/10 | Free/MIT, but the integration cost above dominates. |

**Weighted: EVAL-tier, not ADOPT** — real and useful as a *contract reference* (used for
exactly that in `FF_TO_MOMENTUM_MAPPING.md`), but adopting it wholesale would cost more
than the ~150-line thin client this issue already shipped, and it's missing every piece
(custom fields, idempotent search, lead_activity logging) that this bridge actually needs.

## Recommendation: own thin client (implemented)

**Own-thin-client**, not fork-and-pin. There is no upstream OSS NowCerts MCP server to pin
to (§ "What was actually checked" — the named repo is empty). `n8n-nodes-momentum` is real
but not MCP, not Python, and not close enough to this bridge's shape to be worth wrapping.
`pipelines/winnerdata/momentum_delivery.py`'s `NowCertsClient` class (~80 lines: token,
find_prospect, insert_prospect, insert_custom_field, insert_task) is deliberately minimal
and sources every endpoint shape from the two real artifacts above rather than guessing.

If a genuine, non-empty NowCerts MCP server appears later (re-check
`ReduceMyIns/nowcerts-mcp-server-v3` periodically — it may get real commits pushed to it,
or search glama.ai again once real code exists to index), re-run this audit against actual
source before reconsidering. Target deployment name if that ever happens and a fork is
warranted: `mcp.winnerdataai.ai` (not deployed by this issue — audit only, per Non-Goals).
