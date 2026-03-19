# PLAN: Claude Watch (Everest Edition)

> **Type:** Claude Code Handoff Plan
> **Spec:** SPEC.md (same directory)
> **Harness:** cli-anything-biddeed/harnesses/watch/
> **Estimated Sessions:** 5 Claude Code sessions
> **HITL Required:** 0 (one 30-second post-deploy manual step)
> **Cost:** $0

---

## PRE-FLIGHT CHECKLIST

Before starting Session 1, Claude Code MUST verify:

```bash
# 1. Confirm cli-anything-biddeed repo cloned
ls ~/repos/cli-anything-biddeed/harnesses/ || git clone git@github.com:breverdbidder/cli-anything-biddeed.git ~/repos/cli-anything-biddeed

# 2. Confirm Supabase CLI available
supabase --version || npm install -g supabase

# 3. Confirm Cloudflare Wrangler available
wrangler --version || npm install -g wrangler

# 4. Confirm PAT4 works
curl -s -H "Authorization: token $GITHUB_PAT" https://api.github.com/user | jq .login

# 5. Confirm Supabase credentials
curl -s "https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1/" \
  -H "apikey: $SUPABASE_ANON_KEY" | head -1
```

---

## SESSION 1: Database + Edge Function (Foundation)

**Goal:** Tables, RLS, views, cron, and edge function deployed to Supabase.
**Duration:** ~1 hour
**Context budget:** LOW — mostly SQL and one TypeScript file

### Step 1.1: Create harness directory structure

```bash
cd ~/repos/cli-anything-biddeed
mkdir -p harnesses/watch/{src/utils,supabase/migrations,supabase/functions/watch-ingest,dashboard/src,eval,.github/workflows}
```

### Step 1.2: Create migration file

File: `harnesses/watch/supabase/migrations/20260319_watch_tables.sql`

Copy EXACTLY from SPEC.md Section 2 — all tables, indexes, RLS policies, views, and cron job.

**Validation:**
```bash
# Dry-run the migration against Supabase
supabase db push --dry-run --db-url "postgresql://postgres:$SUPABASE_DB_PASSWORD@db.mocerqjnksmhcjzxrewo.supabase.co:5432/postgres"
```

### Step 1.3: Deploy migration

```bash
supabase db push --db-url "postgresql://postgres:$SUPABASE_DB_PASSWORD@db.mocerqjnksmhcjzxrewo.supabase.co:5432/postgres"
```

**NEVER-LIE RULE: After deploy, run:**
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name LIKE 'watch_%';
```
Must return: `watch_sessions`, `watch_events`, `watch_health`

### Step 1.4: Create edge function

File: `harnesses/watch/supabase/functions/watch-ingest/index.ts`

Implementation requirements (from SPEC Section 3):
- Deno runtime (Supabase Edge Functions)
- Validate `Authorization: Bearer $WATCH_INGEST_TOKEN`
- Parse body, extract repo from project_path
- Extract relative file_path from tool_input
- Extract diff for Edit tool calls
- Upsert session (INSERT on first event, UPDATE event_count + tool_breakdown)
- INSERT event
- On Stop: update session status + generate summary
- Cap output_data at 50KB, diff at 20KB
- Rate limit: reject if >100 events/minute for same session_id (use in-memory Map with TTL)
- Generic error responses only

File: `harnesses/watch/supabase/functions/watch-ingest/deno.json`
```json
{
  "imports": {
    "supabase": "https://esm.sh/@supabase/supabase-js@2"
  }
}
```

### Step 1.5: Generate and store ingest token

```bash
# Generate random token
WATCH_TOKEN=$(openssl rand -hex 32)
echo "WATCH_INGEST_TOKEN=$WATCH_TOKEN"

# Set as Supabase Edge Function secret
supabase secrets set WATCH_INGEST_TOKEN=$WATCH_TOKEN --project-ref mocerqjnksmhcjzxrewo
```

Save the token value — Ariel needs it in `~/.bashrc` as `WATCH_TOKEN`.

### Step 1.6: Deploy edge function

```bash
cd harnesses/watch
supabase functions deploy watch-ingest --project-ref mocerqjnksmhcjzxrewo
```

**Validation:**
```bash
# Should return 401 (no auth)
curl -s -o /dev/null -w "%{http_code}" \
  https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/watch-ingest

# Should return 401 (wrong token)
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer wrong" \
  https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/watch-ingest

# Should return 200 (valid payload)
curl -s -X POST \
  https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/watch-ingest \
  -H "Authorization: Bearer $WATCH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-001",
    "type": "PostToolUse",
    "tool_name": "Read",
    "project_path": "/home/user/repos/biddeed-ai",
    "tool_input": {"file_path": "/home/user/repos/biddeed-ai/src/index.ts"}
  }'

# Verify data landed
curl -s "https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1/watch_sessions?id=eq.test-001" \
  -H "apikey: $SUPABASE_SERVICE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_KEY"
```

### Step 1.7: Clean up test data

```sql
DELETE FROM watch_events WHERE session_id = 'test-001';
DELETE FROM watch_sessions WHERE id = 'test-001';
```

### Step 1.8: Commit

```bash
git add harnesses/watch/
git commit -m "feat(watch): foundation — tables, RLS, edge function deployed"
git push origin main
```

**Session 1 DONE gate:** Edge function returns 200 on valid payload, 401 on invalid auth, data visible in Supabase.

---

## SESSION 2: Hook Installer + Health Scanner

**Goal:** CLI tools for hook installation and brain scanning.
**Duration:** ~1 hour

### Step 2.1: Create shared types

File: `harnesses/watch/src/types.ts`

Define: HookPayload, LogicFile, HealthScanResult, ClassificationResult

### Step 2.2: Create file classification utilities

File: `harnesses/watch/src/utils/classify.ts`

Adapt from NirDiamant/claude-watch `brain-scanner.ts` (MIT):
- PROMPT_PATTERNS, RULES_PATTERNS, CONFIG_PATTERNS, DOCS_PATTERNS, STATE_PATTERNS
- CONTENT_SIGNALS (NEVER, ALWAYS, MUST density)
- SKIP_DIRS, INTERESTING_DIRS
- classifyFile() function
- **CRITICAL:** Zero `execSync`, zero `exec`, zero `child_process` imports

File: `harnesses/watch/src/utils/hash.ts`
```typescript
import { createHash } from 'crypto';
export function sha256(content: string): string {
  return createHash('sha256').update(content).digest('hex');
}
```

### Step 2.3: Create health scanner

File: `harnesses/watch/src/health-scan.ts`

- Reads env: `SCAN_TYPE`, `REPO_NAME`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- Walks project directory (cwd) using `fs.readdirSync` — NO shell commands
- Classifies files using `classify.ts`
- Computes SHA-256 hash per file
- Inserts results into `watch_health` via Supabase REST API
- Reports: "Scanned {repo}: {n} logic files ({critical} critical, {high} high)"

**Validation:**
```bash
cd ~/repos/biddeed-ai
SCAN_TYPE=nightly REPO_NAME=biddeed-ai \
  SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co \
  SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY \
  npx tsx ../cli-anything-biddeed/harnesses/watch/src/health-scan.ts
```

Then verify:
```sql
SELECT repo, COUNT(*), COUNT(*) FILTER (WHERE importance = 'critical')
FROM watch_health WHERE scan_type = 'nightly'
GROUP BY repo;
```

### Step 2.4: Create hook installer

File: `harnesses/watch/src/install-hooks.ts`

- CLI: `--global` flag, `--remove` flag, `--port` optional
- Reads `.claude/settings.json` (project or global)
- Adds PostToolUse, Notification, Stop hooks with fire-and-forget curl
- Idempotent — checks if hooks already exist before adding
- On `--remove` — only removes watch hooks, preserves others
- Warns if `$WATCH_TOKEN` env var not set

**Validation:**
```bash
# Install in test project
cd /tmp/test-project && mkdir -p .claude
node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js
cat .claude/settings.json  # verify hooks added

# Remove
node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js --remove
cat .claude/settings.json  # verify hooks removed
```

### Step 2.5: Create package.json + tsconfig

File: `harnesses/watch/package.json`
```json
{
  "name": "@biddeed/watch",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "health-scan": "tsx src/health-scan.ts",
    "install-hooks": "tsx src/install-hooks.ts"
  },
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.4.0",
    "tsx": "^4.7.0",
    "@types/node": "^20.0.0"
  }
}
```

Zero runtime dependencies — only Node.js built-ins (fs, path, crypto, https).

### Step 2.6: Commit

```bash
git add harnesses/watch/
git commit -m "feat(watch): hook installer + health scanner — zero shell execution"
git push origin main
```

**Session 2 DONE gate:** Health scanner produces results in Supabase. Hook installer adds/removes hooks cleanly.

---

## SESSION 3: Dashboard — Core Shell + LIVE Tab

**Goal:** React app with auth, layout, and real-time session monitoring.
**Duration:** ~2 hours (largest session)

### Step 3.1: Scaffold React app

```bash
cd harnesses/watch/dashboard
npm create vite@latest . -- --template react-ts
npm install @supabase/supabase-js recharts lucide-react date-fns
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### Step 3.2: Configure Tailwind with house brand

File: `tailwind.config.js` — extend with house brand colors
File: `src/styles/globals.css` — CSS custom properties from SPEC Section 6.2

### Step 3.3: Supabase client

File: `src/lib/supabase.ts`
```typescript
import { createClient } from '@supabase/supabase-js';
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const supabase = createClient(supabaseUrl, supabaseAnonKey);
```

### Step 3.4: Auth hook + Login page

File: `src/hooks/useAuth.ts` — magic link auth flow
File: `src/components/LoginPage.tsx` — house brand login screen

### Step 3.5: Layout with tab navigation

File: `src/App.tsx` — Router with auth guard
File: `src/components/Layout.tsx` — Desktop: sidebar + main. Mobile: bottom tabs.

Three tabs: 🔴 Live / 📋 Sessions / 🧠 Health

### Step 3.6: LIVE tab components

Files per SPEC Section 6.3.1:
- `src/components/live/ActiveSessionCards.tsx`
- `src/components/live/LiveEventStream.tsx`
- `src/components/live/ToolFrequencyChart.tsx`

File: `src/hooks/useRealtime.ts` — Supabase Realtime subscription

**CRITICAL:** The Realtime subscription must:
- Subscribe to INSERT on watch_events
- Filter by session_id for selected session
- Auto-scroll event stream
- Update session card counters

### Step 3.7: Build and test locally

```bash
cd harnesses/watch/dashboard
npm run dev
# Open http://localhost:5173
# Login with magic link
# In another terminal, send test events to edge function
# Verify events appear in real-time
```

### Step 3.8: Commit

```bash
git add harnesses/watch/dashboard/
git commit -m "feat(watch): dashboard shell + LIVE tab with Supabase Realtime"
git push origin main
```

**Session 3 DONE gate:** Dashboard loads, auth works, live events stream in real-time.

---

## SESSION 4: Dashboard — AUDIT + HEALTH Tabs

**Goal:** Complete all three dashboard views.
**Duration:** ~1.5 hours

### Step 4.1: AUDIT tab components

Files per SPEC Section 6.3.2:
- `src/components/audit/SessionTable.tsx` — sortable, clickable rows
- `src/components/audit/SessionTimeline.tsx` — vertical timeline with tool icons
- `src/components/audit/DiffViewer.tsx` — old_string → new_string with color coding
- `src/components/audit/FilterBar.tsx` — repo, date range, tool_name, file search

File: `src/hooks/useSessions.ts` — fetch sessions + events with filters

### Step 4.2: HEALTH tab components

Files per SPEC Section 6.3.3:
- `src/components/health/RepoSelector.tsx` — horizontal tabs for 5 repos + All
- `src/components/health/LogicFileTree.tsx` — collapsible tree with importance badges
- `src/components/health/ChangeTimeline.tsx` — recharts scatter plot, 90 days
- `src/components/health/HealthScoreCard.tsx` — per-repo summary card

### Step 4.3: Mobile responsive pass

- Test all three tabs at 375px width (iPhone SE)
- Bottom tab navigation must work
- Session timeline must be scrollable
- DiffViewer must horizontal-scroll on narrow screens

### Step 4.4: Build production bundle

```bash
cd harnesses/watch/dashboard
npm run build
ls -la dist/  # verify output
```

### Step 4.5: Commit

```bash
git add harnesses/watch/dashboard/
git commit -m "feat(watch): AUDIT + HEALTH tabs complete, mobile responsive"
git push origin main
```

**Session 4 DONE gate:** All three tabs functional with real data. Mobile layout works.

---

## SESSION 5: GHA Workflows + CF Pages Deploy + AUTOLOOP

**Goal:** Automated deployment pipeline, health scan cron, eval assertions.
**Duration:** ~1 hour

### Step 5.1: Cloudflare Pages deploy workflow

File: `harnesses/watch/.github/workflows/deploy-dashboard.yml`

```yaml
name: Deploy Watch Dashboard
on:
  push:
    branches: [main]
    paths: ['harnesses/watch/dashboard/**']
  workflow_dispatch: {}

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd harnesses/watch/dashboard && npm ci && npm run build
      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          accountId: ${{ secrets.CF_ACCOUNT_ID }}
          projectName: watch-biddeed
          directory: harnesses/watch/dashboard/dist
```

### Step 5.2: Edge function deploy workflow

File: `harnesses/watch/.github/workflows/deploy-edge-function.yml`

Triggers on push to `harnesses/watch/supabase/functions/**`
Deploys via `supabase functions deploy`

### Step 5.3: Health scan nightly workflow

File: `harnesses/watch/.github/workflows/health-scan.yml`

Per SPEC Section 5.2 — matrix strategy across 5 repos, runs at 2 AM EST.

### Step 5.4: Cloudflare Pages project setup

```bash
# Create CF Pages project
wrangler pages project create watch-biddeed --production-branch main

# Add custom domain
wrangler pages project set watch-biddeed --domain watch.biddeed.ai
```

Ariel: add CNAME record `watch` → `watch-biddeed.pages.dev` in Cloudflare DNS. (30 seconds.)

### Step 5.5: Create AUTOLOOP eval

File: `harnesses/watch/eval/eval.json` — 25 assertions per SPEC Section 8

### Step 5.6: Create HARNESS.md

File: `harnesses/watch/HARNESS.md` — 7-phase harness documentation following cli-anything-biddeed pattern.

### Step 5.7: Update CLAUDE.md in cli-anything-biddeed

Add watch harness to the active harnesses list.

### Step 5.8: Final commit + deploy

```bash
git add harnesses/watch/
git commit -m "feat(watch): GHA workflows + CF Pages + AUTOLOOP eval — v0.1.0 complete"
git push origin main
```

**Session 5 DONE gate:** Dashboard live at watch.biddeed.ai. Health scan runs nightly. All 25 eval assertions defined.

---

## POST-DEPLOY: Manual Steps (Ariel, 2 minutes total)

### 1. Set WATCH_TOKEN in shell (~30 seconds)

```bash
# Claude Code will output the generated token during Session 1
echo 'export WATCH_TOKEN="<generated-token>"' >> ~/.bashrc
source ~/.bashrc
```

### 2. Install hooks in each repo (~30 seconds per repo)

```bash
cd ~/repos/biddeed-ai && node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js
cd ~/repos/biddeed-ai-ui && node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js
cd ~/repos/cli-anything-biddeed && node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js
cd ~/repos/zonewise-scraper-v4 && node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js
cd ~/repos/zonewise-web && node ~/repos/cli-anything-biddeed/harnesses/watch/dist/install-hooks.js
```

### 3. Add CNAME in Cloudflare DNS (~30 seconds)

`watch` → `watch-biddeed.pages.dev` (CNAME, proxied)

### 4. Verify

Open watch.biddeed.ai → login → start any Claude Code session → see events stream live.

---

## RISK REGISTER

| Risk | Mitigation |
|---|---|
| Claude Code hook payload format changes | Edge function validates loosely, logs unknown fields to a _raw column |
| Supabase Realtime quota exceeded | 200 concurrent connections free tier, we use 1 (solo founder) |
| Large tool_output payloads bloat DB | 50KB cap in edge function, 30-day retention |
| Hook curl adds latency to Claude Code | Fire-and-forget async (`&` background) |
| Cloudflare Pages free tier limit | 500 builds/month, we deploy ~20/month max |
| Magic link emails go to spam | Add supabase sender to contacts once |

---

## SUCCESS CRITERIA

After all 5 sessions complete:

- [ ] watch.biddeed.ai loads and authenticates
- [ ] Claude Code sessions appear in LIVE tab within 2 seconds
- [ ] Full event replay works in AUDIT tab with diff viewer
- [ ] HEALTH tab shows CLAUDE.md ecosystem across 5 repos
- [ ] Nightly GHA health scan runs at 2 AM EST
- [ ] Security score: 95/100 (zero shell execution, zero filesystem exposure)
- [ ] Cost: $0/month ongoing
- [ ] HITL: zero during operation (hooks are fire-and-forget)
