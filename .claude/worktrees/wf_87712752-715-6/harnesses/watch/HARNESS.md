# HARNESS: Claude Watch (Everest Edition)

> **Version:** 0.1.0
> **Status:** Session 1 Complete — DB + Edge Function
> **Spec:** ../docs/plans/WATCH-SPEC.md
> **Plan:** ../docs/plans/WATCH-PLAN.md

## Purpose

Real-time observability platform for Claude Code sessions. Three capabilities:
- **LIVE** — What is Claude Code doing RIGHT NOW (Supabase Realtime)
- **AUDIT** — Full session replay with diffs
- **HEALTH** — CLAUDE.md ecosystem status across 5 repos

## Directory Structure

```
harnesses/watch/
├── HARNESS.md                         ← This file
├── package.json                       ← Node.js harness config
├── tsconfig.json                      ← TypeScript config
├── src/
│   ├── types.ts                       ← Shared types (zero shell)
│   ├── install-hooks.ts               ← CLI: add/remove Claude Code hooks
│   ├── health-scan.ts                 ← Repo scanner (no execSync)
│   └── utils/
│       ├── classify.ts                ← File classification patterns
│       └── hash.ts                    ← SHA-256 hashing
├── supabase/
│   ├── migrations/
│   │   └── 20260319_watch_tables.sql  ← All DDL, RLS, views, cron
│   └── functions/
│       └── watch-ingest/
│           ├── index.ts               ← Deno edge function
│           └── deno.json              ← Deno imports
├── dashboard/                         ← React 18 + Vite (Sessions 3-4)
│   └── src/...
├── eval/
│   └── eval.json                      ← 25 AUTOLOOP assertions
└── .github/
    └── workflows/
        ├── deploy-dashboard.yml       ← CF Pages deploy
        ├── deploy-edge-function.yml   ← Supabase function deploy
        └── health-scan.yml            ← Nightly 2AM EST scan
```

## Security Controls (Zero Shell Policy)

- **ZERO `execSync`** in all source files — enforced, verify with grep
- **Zero filesystem exposure** — all data in Supabase PostgreSQL
- **Bearer token auth** — `WATCH_INGEST_TOKEN` not the service role key
- **Fire-and-forget hooks** — curl background `&`, never blocks Claude Code
- **Input validation** — edge function validates all required fields
- **50KB output cap** — tool_output truncated before insert
- **Rate limiting** — 100 events/minute per session_id (in-memory Map)

## Database Tables

| Table | Purpose | Retention |
|---|---|---|
| `watch_sessions` | One row per Claude Code invocation | 30 days |
| `watch_events` | Full tool call payloads | 30 days |
| `watch_health` | CLAUDE.md ecosystem snapshots | 90 days |

Views: `watch_sessions_live`, `watch_health_latest`, `watch_daily_stats`

## Sessions Progress

| Session | Goal | Status |
|---|---|---|
| 1 | DB + Edge Function foundation | ✅ COMPLETE |
| 2 | Hook installer + health scanner | ⏳ PENDING |
| 3 | Dashboard — auth + LIVE tab | ⏳ PENDING |
| 4 | Dashboard — AUDIT + HEALTH tabs | ⏳ PENDING |
| 5 | GHA workflows + CF Pages deploy | ⏳ PENDING |

## 7-Phase Build Pattern

This harness follows the cli-anything-biddeed 7-phase pattern:

1. **SPEC** — WATCH-SPEC.md (complete)
2. **PLAN** — WATCH-PLAN.md (complete)
3. **FOUNDATION** — Tables, RLS, edge function (Session 1 ✅)
4. **TOOLS** — Hook installer, health scanner (Session 2)
5. **INTERFACE** — Dashboard shell + LIVE tab (Session 3)
6. **INTEGRATION** — AUDIT + HEALTH tabs (Session 4)
7. **SHIP** — GHA workflows + CF Pages + AUTOLOOP (Session 5)

## Environment Variables Required

```bash
# Required for hook curl command (set in ~/.bashrc)
WATCH_TOKEN=<generated-token>

# Required for health scanner and edge function deploy
SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>

# Required in Supabase Edge Function secrets
WATCH_INGEST_TOKEN=<same-as-WATCH_TOKEN>
```

## Post-Deploy Manual Steps (2 minutes, done once)

1. `echo 'export WATCH_TOKEN="<printed-token>"' >> ~/.bashrc`
2. Install hooks per repo: `node harnesses/watch/dist/install-hooks.js`
3. Add CNAME in Cloudflare DNS: `watch` → `watch-biddeed.pages.dev`

## Edge Function Hook URL

```
https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/watch-ingest
```

Deploy command (requires Supabase CLI):
```bash
supabase functions deploy watch-ingest --project-ref mocerqjnksmhcjzxrewo
```
