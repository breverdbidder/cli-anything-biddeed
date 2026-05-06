# cli_anything router

Postgres-native, zero-HITL agent dispatch for the Everest Capital ecosystem.
36 voltagent subagents (cherry-picked in PR #7422, merge `99995d6`) wired
through the canonical Smart Router (`public.ecu_route_chat_llm`).

## Hard rule

**NEVER use `vault.anthropic_api_key`.** Per-token Anthropic billing is
banned across the ecosystem. The only acceptable Claude path is:

```yaml
TIER_1_PRIMARY:  anthropic_oauth_bearer  # Max OAuth — required
TIER_2_FALLBACK: gemini_api_key          # Gemini 2.5 Flash
BLOCKED:         anthropic_api_key       # Removed from vault 2026-05-06
```

`public.ecu_invoke_claude` is patched to read **only**
`anthropic_oauth_bearer`. If it's missing, the function returns a
structured `BLOCKED_no_oauth_bearer` error and the router falls through
to Gemini. There is no api_key fallback path in the function body.

## Architecture

```
chat / summit_dispatch / ecu_chat / cron
        │
        ▼
cli_anything.invoke_sync(namespace, task)
        │
        ├─ budget_check(source) ──► block on hard cap
        ├─ INSERT cli_anything.tasks  (status='dispatching')
        │
        ▼
public.ecu_route_chat_llm(messages, system_prompt)
        │
        ├─ TIER_1: ecu_invoke_claude  ──► HTTP api.anthropic.com via Max OAuth
        │       │                          (extensions.http, sync)
        │       └─ on failure ▼
        ├─ TIER_2: ecu_invoke_gemini  ──► HTTP generativelanguage.googleapis.com
        │
        ▼
public.llm_requests / public.llm_responses / public.ecu_router_decisions
        │
        ▼
UPDATE cli_anything.tasks  (status, response_text, response_usage, error)
update_agent_health(...)   (auto-quarantine after 5 failures)
```

## Usage

### Explicit invocation

```sql
SELECT * FROM cli_anything.invoke_sync(
  p_namespace := 'cli_anything.qasec.security-auditor',
  p_task      := 'Audit the auth flow at biddeed-gw',
  p_source    := 'biddeed'
);
```

### Auto-route (zero-HITL)

```sql
-- Picks the best agent automatically via ts_rank + namespace boost
SELECT * FROM cli_anything.auto_invoke(
  'analyze postgres index strategy for ZW_PARCELS'
);
```

### Parallel fan-out

```sql
SELECT * FROM cli_anything.parallel_invoke(
  'review architecture decisions in compliance_agent',
  3  -- top-3 agents
);
```

### Health and budget

```sql
SELECT * FROM cli_anything.v_agent_health
WHERE health_state IN ('DEGRADED','QUARANTINED');

SELECT * FROM cli_anything.v_budget_today;
```

## Source attribution

Every task carries a `source` column. The Smart Router logs to
`public.llm_requests` with the same source. Allowed values:
`cli_anything | ecu_chat | summit_dispatch | cairn_supervisor | biddeed |
zonewise | property360 | compliance_agent | manual | other`.

This means a single agent can be called from multiple ecosystem entry
points and Ariel can audit which surface drove which spend:

```sql
SELECT source, count(*), sum((response_usage->>'cost_cents')::numeric) AS cents
FROM cli_anything.tasks
WHERE created_at::date = current_date
GROUP BY source ORDER BY 3 DESC;
```

## Budget caps

| scope            | soft (¢) | hard (¢) |
|------------------|---------:|---------:|
| global           |    1000  |    1500  |
| ecu_chat         |     200  |     400  |
| summit_dispatch  |     500  |     800  |
| cli_anything     |     300  |     500  |

`budget_check(scope)` is called before every invocation. If the global
hard cap or scope hard cap is hit, the task is recorded as `failed` with
`error='BUDGET_EXCEEDED'` and no LLM call is made.

## Auto-quarantine

`cli_anything.update_agent_health(namespace, succeeded, cost_cents)` runs
after every invocation. After 5 consecutive failures an agent is flipped
to `quarantined=true` and excluded from `pick_agents` / `auto_invoke` /
`parallel_invoke`. To rehabilitate:

```sql
UPDATE cli_anything.agents
SET quarantined=false, quarantine_reason=NULL, consecutive_failures=0
WHERE namespace = 'cli_anything.<slug>.<name>';
```

## Unblock checklist

To make the system actually return responses (not just block-and-log):

```yaml
step_1:
  what: Load Max OAuth bearer into vault
  cmd:  SELECT vault.create_secret('<MAX_OAUTH_BEARER>', 'anthropic_oauth_bearer');
  outcome: TIER_1_PRIMARY goes live

step_2:
  what: Fix gemini_api_key project access in GCP console
  where: https://console.cloud.google.com — re-enable Generative Language API
  outcome: TIER_2_FALLBACK becomes viable

verify:
  SELECT * FROM public.ecu_router_check_secrets();
  -- expected: anthropic_oauth_bearer CONFIGURED
```

## 36 agents (PR #7422)

Categorized at `agents/external/voltagent-{lang,infra,qasec,data,devx,domain,biz,meta}/`.
See `agent-roster.md` for the full list with namespaces.

## R-rule alignment

- **R1** (never delegate): zero-HITL via auto_invoke; supervisor pattern only
- **R2** (REPOEVAL ≥75): voltagent scored 78 ADOPT / 92 REFERENCE — see REPOEVAL row `1bfee785`
- **R3** (≤10 open Summits): N/A — this is operational, not summit work
- **R4** (mem citations): every agent .md ends with `<!-- mem-cite: src=...; sha=...; license=MIT -->`
- **R5** (zero stale TTLs): tasks have `dispatched_at` + `completed_at`; auto-quarantine handles drift

## Honesty V3 disclosure

```yaml
schema:                 VERIFIED  # applied to mocerqjnksmhcjzxrewo
function_bodies:        VERIFIED  # extracted via pg_get_functiondef
api_key_path_removed:   VERIFIED  # vault.anthropic_api_key DELETED 2026-05-06
                                  # ecu_invoke_claude reads only oauth_bearer
smart_router_e2e:       VERIFIED  # task_id 25cbf3eb confirms full pipeline
end_to_end_response:    BLOCKED   # needs vault.anthropic_oauth_bearer (human)
                                  # OR fixed Gemini project access (human)
agents_invokable:       VERIFIED  # 36 active, 0 quarantined, picker scored
```
