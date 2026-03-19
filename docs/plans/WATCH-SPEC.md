# SPEC: Claude Watch (Everest Edition)

> **Status:** APPROVED — Ready for Claude Code execution
> **Author:** AI Architect (Claude Opus 4.6)
> **Approved by:** Ariel Shapira — March 19, 2026
> **Harness:** cli-anything-biddeed/harnesses/watch/
> **Dashboard:** watch.biddeed.ai (Cloudflare Pages)
> **Security Target:** 95/100

---

## 1. OVERVIEW

Real-time observability platform for Claude Code sessions. Three capabilities:

| Capability | Description | Data Source |
|---|---|---|
| **LIVE** | What is Claude Code doing RIGHT NOW | Supabase Realtime subscriptions on watch_events |
| **AUDIT** | What DID it do (full session replay with diffs) | watch_events + watch_sessions tables |
| **HEALTH** | CLAUDE.md ecosystem status across 5 repos | watch_health table, GHA nightly + session-start |

Zero cost. Zero middleware servers. Zero shell execution. Zero filesystem exposure.

---

## 2. DATA MODEL

### 2.1 Table: `watch_sessions`

Tracks each Claude Code invocation as a session.

```sql
CREATE TABLE watch_sessions (
    id TEXT PRIMARY KEY,                    -- Claude Code session_id from hook payload
    repo TEXT NOT NULL,                     -- repo name extracted from project_path
    branch TEXT,                            -- git branch if available
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'stale')),
    summary TEXT,                           -- auto-generated: "Edited 4 files, ran 12 bash commands"
    event_count INT DEFAULT 0,
    tool_breakdown JSONB DEFAULT '{}'::jsonb -- {"Write": 12, "Edit": 8, "Bash": 5}
);

CREATE INDEX idx_ws_status ON watch_sessions(status, started_at DESC);
CREATE INDEX idx_ws_repo ON watch_sessions(repo, started_at DESC);
```

### 2.2 Table: `watch_events`

Full tool call payloads. This is the heavy table — 30-day retention.

```sql
CREATE TABLE watch_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES watch_sessions(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hook_type TEXT NOT NULL
        CHECK (hook_type IN ('PostToolUse', 'Notification', 'Stop')),
    tool_name TEXT,                         -- Write, Edit, Bash, Read, TodoRead, etc.
    file_path TEXT,                         -- extracted from tool_input (first match of file_path|path|filePath)
    input_data JSONB,                       -- full tool_input payload
    output_data TEXT,                       -- tool_output (string, can be large)
    diff TEXT,                              -- extracted for Edit: "--- old\n+++ new\n-old_string\n+new_string"
    duration_ms INT
);

CREATE INDEX idx_we_session ON watch_events(session_id, ts ASC);
CREATE INDEX idx_we_ts ON watch_events(ts DESC);
CREATE INDEX idx_we_tool ON watch_events(tool_name, ts DESC);
CREATE INDEX idx_we_file ON watch_events(file_path) WHERE file_path IS NOT NULL;
```

### 2.3 Table: `watch_health`

CLAUDE.md ecosystem snapshots across all repos.

```sql
CREATE TABLE watch_health (
    id BIGSERIAL PRIMARY KEY,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scan_type TEXT NOT NULL CHECK (scan_type IN ('nightly', 'session_start')),
    repo TEXT NOT NULL,                     -- repo name
    file_path TEXT NOT NULL,               -- relative path within repo
    category TEXT NOT NULL
        CHECK (category IN ('prompt', 'rules', 'config', 'docs', 'state')),
    content_hash TEXT NOT NULL,            -- SHA-256 for change detection
    signals TEXT[],                        -- why classified: ['contains NEVER rules', 'in .claude/ directory']
    importance TEXT DEFAULT 'normal'
        CHECK (importance IN ('critical', 'high', 'normal')),
    line_count INT,
    size_bytes INT,
    content_preview TEXT                   -- first 500 chars
);

CREATE INDEX idx_wh_repo ON watch_health(repo, scanned_at DESC);
CREATE INDEX idx_wh_scan ON watch_health(scan_type, scanned_at DESC);
CREATE UNIQUE INDEX idx_wh_latest ON watch_health(repo, file_path, scan_type, scanned_at DESC);
```

### 2.4 RLS Policies

```sql
-- Enable RLS on all tables
ALTER TABLE watch_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_health ENABLE ROW LEVEL SECURITY;

-- Edge function uses service_role key for inserts (bypasses RLS)
-- Dashboard uses anon/authenticated key for reads

-- Read: authenticated users only
CREATE POLICY "auth_read" ON watch_sessions FOR SELECT
    USING (auth.role() = 'authenticated');
CREATE POLICY "auth_read" ON watch_events FOR SELECT
    USING (auth.role() = 'authenticated');
CREATE POLICY "auth_read" ON watch_health FOR SELECT
    USING (auth.role() = 'authenticated');

-- No public access, no insert/update/delete from client
```

### 2.5 Data Retention (pg_cron)

```sql
-- Run nightly at 3 AM EST (8 AM UTC)
SELECT cron.schedule('watch-retention', '0 8 * * *', $$
    -- Events: 30-day retention
    DELETE FROM watch_events WHERE ts < NOW() - INTERVAL '30 days';
    -- Sessions: 30-day retention (CASCADE deletes events)
    DELETE FROM watch_sessions WHERE ended_at < NOW() - INTERVAL '30 days';
    -- Stale sessions: mark active sessions with no events in 30 min
    UPDATE watch_sessions SET status = 'stale', ended_at = NOW()
        WHERE status = 'active'
        AND started_at < NOW() - INTERVAL '30 minutes'
        AND id NOT IN (
            SELECT DISTINCT session_id FROM watch_events
            WHERE ts > NOW() - INTERVAL '30 minutes'
        );
    -- Health: 90-day retention
    DELETE FROM watch_health WHERE scanned_at < NOW() - INTERVAL '90 days';
$$);
```

### 2.6 Views (Dashboard Helpers)

```sql
-- Active sessions with latest event info
CREATE VIEW watch_sessions_live AS
SELECT
    s.*,
    e.tool_name AS last_tool,
    e.file_path AS last_file,
    e.ts AS last_event_at
FROM watch_sessions s
LEFT JOIN LATERAL (
    SELECT tool_name, file_path, ts
    FROM watch_events
    WHERE session_id = s.id
    ORDER BY ts DESC LIMIT 1
) e ON true
WHERE s.status = 'active';

-- Latest health scan per repo per file
CREATE VIEW watch_health_latest AS
SELECT DISTINCT ON (repo, file_path)
    *
FROM watch_health
WHERE scan_type = 'nightly'
ORDER BY repo, file_path, scanned_at DESC;

-- Daily session stats (last 30 days)
CREATE VIEW watch_daily_stats AS
SELECT
    DATE(started_at) AS day,
    COUNT(*) AS session_count,
    SUM(event_count) AS total_events,
    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))/60)::INT AS avg_duration_min
FROM watch_sessions
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(started_at)
ORDER BY day DESC;
```

---

## 3. EDGE FUNCTION: `watch-ingest`

### 3.1 Purpose

Receives Claude Code hook payloads via HTTPS POST, validates, transforms, inserts into Supabase.

### 3.2 Auth

- Bearer token: `WATCH_INGEST_TOKEN` stored as Supabase Edge Function secret
- NOT the Supabase service role key
- Validation: `if (req.headers.authorization !== 'Bearer ' + WATCH_INGEST_TOKEN) return 401`

### 3.3 Payload Transform Logic

Claude Code hook payload (input):
```json
{
  "session_id": "abc-123",
  "type": "PostToolUse",
  "tool_name": "Edit",
  "project_path": "/home/user/repos/biddeed-ai",
  "tool_input": {
    "file_path": "/home/user/repos/biddeed-ai/src/index.ts",
    "old_string": "const x = 1;",
    "new_string": "const x = 2;"
  },
  "tool_output": "File edited successfully"
}
```

Transformed output (our schema):
```json
{
  "session_id": "abc-123",
  "hook_type": "PostToolUse",
  "tool_name": "Edit",
  "file_path": "src/index.ts",
  "input_data": { "file_path": "...", "old_string": "...", "new_string": "..." },
  "output_data": "File edited successfully",
  "diff": "--- old\n+++ new\n-const x = 1;\n+const x = 2;"
}
```

### 3.4 Edge Function Logic

```
1. Validate Authorization header
2. Parse JSON body
3. Extract repo name from project_path (last segment)
4. Extract file_path from tool_input (file_path || path || filePath), make relative to project_path
5. Extract diff for Edit tool calls (old_string → new_string)
6. Upsert session:
   - If session_id not in watch_sessions → INSERT with repo, status='active'
   - Always → UPDATE event_count = event_count + 1, update tool_breakdown
7. INSERT into watch_events
8. If hook_type = 'Stop':
   - UPDATE session status = 'completed', ended_at = NOW()
   - Generate summary from tool_breakdown
9. Return 200 {ok: true}
```

### 3.5 Error Handling

- Invalid JSON → 400 (no details leaked)
- Invalid token → 401 (no details leaked)
- Missing session_id → 400
- DB insert failure → 500 with generic message (log internally)
- NEVER expose stack traces, query details, or secrets in response

---

## 4. HOOK INSTALLATION

### 4.1 CLI Command

```bash
# From cli-anything-biddeed
node harnesses/watch/dist/install-hooks.js [--global]
```

### 4.2 Behavior

1. Read existing `.claude/settings.json` (project or global)
2. Check if watch hooks already installed (idempotent)
3. Add PostToolUse, Notification, Stop hooks
4. Write back to settings.json
5. Verify `$WATCH_TOKEN` env var exists — warn if missing

### 4.3 Hook Command Template

```bash
curl -sf -X POST https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/watch-ingest \
  -H "Authorization: Bearer $WATCH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(cat)" \
  >/dev/null 2>&1 &
```

Key details:
- `-sf` = silent + fail silently (never block Claude Code)
- `>/dev/null 2>&1 &` = fire-and-forget async (never add latency to Claude Code)
- `$WATCH_TOKEN` resolved at runtime from env

### 4.4 Uninstall

```bash
node harnesses/watch/dist/install-hooks.js --remove
```

Removes only watch hooks, preserves all other hooks.

---

## 5. HEALTH SCANNER

### 5.1 Salvaged Logic (from NirDiamant/claude-watch, MIT)

Adapted from `brain-scanner.ts` with security hardening:
- **ZERO `execSync` calls** — no git operations, no shell at all
- File classification uses same pattern matching (PROMPT_PATTERNS, RULES_PATTERNS, etc.)
- Content signal detection (NEVER/ALWAYS/MUST density scoring)
- SHA-256 content hashing for change detection
- Max 100KB per file, max depth 4, same SKIP_DIRS

### 5.2 Nightly GHA Workflow

```yaml
name: watch-health-scan
on:
  schedule:
    - cron: '0 7 * * *'  # 2 AM EST = 7 AM UTC
  workflow_dispatch: {}

jobs:
  scan:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        repo:
          - biddeed-ai
          - biddeed-ai-ui
          - cli-anything-biddeed
          - zonewise-scraper-v4
          - zonewise-web
    steps:
      - uses: actions/checkout@v4
        with:
          repository: breverdbidder/${{ matrix.repo }}
          token: ${{ secrets.PAT4 }}
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npx tsx harnesses/watch/src/health-scan.ts
        env:
          SCAN_TYPE: nightly
          REPO_NAME: ${{ matrix.repo }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
```

### 5.3 Session-Start Delta

When Claude Code starts a session in any repo, the PostToolUse hook on the first event triggers a lightweight delta scan:
- Edge function checks: is this the first event for this session_id?
- If yes, trigger a Supabase Edge Function `watch-health-delta` that:
  - Fetches latest nightly scan for this repo
  - Compares against current file hashes (passed from the first hook payload's project_path)
  - Inserts only changed files with scan_type = 'session_start'

**Simplification:** The delta scan can be deferred to Phase 2. Nightly-only is sufficient for MVP.

---

## 6. DASHBOARD: watch.biddeed.ai

### 6.1 Tech Stack

| Layer | Choice |
|---|---|
| Framework | React 18 + Vite |
| Styling | Tailwind CSS (house brand) |
| Auth | @supabase/supabase-js (magic link) |
| Realtime | Supabase Realtime (subscribe to watch_events inserts) |
| Charts | Recharts |
| Icons | Lucide React |
| Hosting | Cloudflare Pages (free) |
| Domain | watch.biddeed.ai (CNAME to CF Pages) |

### 6.2 Brand Application

```css
/* House brand mandatory */
--color-primary: #1E3A5F;     /* Navy */
--color-accent: #F59E0B;      /* Orange CTA */
--color-bg: #020617;          /* Slate 950 */
--color-surface: #0F172A;     /* Slate 900 */
--color-text: #E2E8F0;        /* Slate 200 */
--color-text-muted: #94A3B8;  /* Slate 400 */
--color-success: #22C55E;     /* Green 500 */
--color-danger: #EF4444;      /* Red 500 */
--font-family: 'Inter', sans-serif;
```

### 6.3 Views

#### 6.3.1 LIVE Tab (🔴)

**Purpose:** What is Claude Code doing RIGHT NOW

**Components:**
- `ActiveSessionCards` — Grid of active sessions showing: repo name, session duration (live counter), last tool used, last file touched, event count
- `LiveEventStream` — Scrolling feed of events for selected session (Supabase Realtime subscription). Each event shows: timestamp, tool_name icon, file_path, one-line summary
- `CurrentFileIndicator` — Highlights which file is currently being edited with a pulse animation
- `ToolFrequencyChart` — Small recharts bar showing tool distribution for active session

**Realtime subscription:**
```typescript
supabase
  .channel('watch-live')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'watch_events'
  }, (payload) => {
    // Append to event stream
    // Update session card counters
  })
  .subscribe()
```

#### 6.3.2 AUDIT Tab (📋)

**Purpose:** What DID Claude Code do (session replay)

**Components:**
- `SessionTable` — Sortable table: repo, started_at, duration, event_count, status, tool_breakdown mini-chart. Click row to expand.
- `SessionTimeline` — Vertical timeline of all events in selected session. Shows: tool icon, file_path, timestamp, expandable input/output.
- `DiffViewer` — For Edit events, shows side-by-side old_string → new_string with syntax highlighting (use `<pre>` with Tailwind prose classes, no heavy dependency).
- `SessionSummary` — Top-of-detail card: "This session edited 4 files across 45 minutes. Tools: Edit (12), Bash (8), Write (3), Read (22)."
- `FilterBar` — Filter by repo, date range, tool_name, file_path search.

#### 6.3.3 HEALTH Tab (🧠)

**Purpose:** CLAUDE.md ecosystem status across 5 repos

**Components:**
- `RepoSelector` — Horizontal tab bar with all 5 repos + "All" option
- `LogicFileTree` — Collapsible tree of logic files per repo, categorized (prompts → rules → config → docs → state). Shows importance badges (🔴 critical, 🟡 high, ⚪ normal).
- `ChangeTimeline` — Shows when logic files changed over time. X-axis = last 90 days, Y-axis = repos. Dots on changes, colored by importance.
- `FilePreview` — Click any file in the tree to see content_preview. Link to GitHub source.
- `CrossRepoSearch` — Text search across all content_preview fields. Uses Supabase `textSearch` (not AI — zero cost).
- `HealthScoreCard` — Per repo: total logic files, critical rules count, last scan time, files changed since last nightly.

### 6.4 Auth Flow

1. User lands on watch.biddeed.ai → sees login screen
2. Enter email → magic link sent
3. Click link → authenticated session
4. RLS ensures only authenticated users read data
5. Only Ariel's email whitelisted (Supabase auth config)

### 6.5 Responsive Design

- Desktop: Three-panel layout (sidebar + main + detail)
- Tablet: Two-panel (sidebar collapses to icons)
- Mobile: Single panel with bottom tab navigation (LIVE / AUDIT / HEALTH)

Mobile is critical — checking from phone during `claude remote-control` sessions.

---

## 7. SECURITY CONTROLS

| # | Control | Implementation |
|---|---|---|
| 1 | Auth (dashboard) | Supabase magic link + RLS, single email whitelist |
| 2 | Auth (ingestion) | Bearer token, NOT service role key |
| 3 | No shell execution | Zero `execSync` or `exec` calls in entire codebase |
| 4 | No filesystem exposure | All data in Supabase PostgreSQL |
| 5 | Input validation | Edge function validates: JSON parse, required fields, type checks |
| 6 | String length limits | tool_output capped at 50KB, diff at 20KB, content_preview at 500 chars |
| 7 | Rate limiting | Edge function: max 100 events/minute per session_id |
| 8 | Data retention | 30-day events/sessions, 90-day health, auto-purge via pg_cron |
| 9 | HTTPS everywhere | Supabase (TLS) + Cloudflare Pages (TLS) |
| 10 | No secrets in code | WATCH_TOKEN in env, service key in GHA secrets |
| 11 | Error opacity | Generic error messages, no stack traces or query details |
| 12 | Cascading deletes | ON DELETE CASCADE prevents orphaned events |
| 13 | Async hooks | Fire-and-forget curl, never blocks Claude Code |
| 14 | CORS locked | Dashboard origin only on Supabase |

---

## 8. AUTOLOOP EVAL ASSERTIONS

File: `harnesses/watch/eval/eval.json` — 25 binary assertions

```
EDGE FUNCTION:
1. Returns 401 for missing Authorization header
2. Returns 401 for invalid bearer token
3. Returns 400 for non-JSON body
4. Returns 400 for missing session_id
5. Returns 200 for valid PostToolUse payload
6. Creates session on first event for new session_id
7. Increments event_count on subsequent events
8. Sets status='completed' on Stop hook_type
9. Generates summary on session completion
10. Extracts relative file_path from absolute path
11. Extracts diff from Edit tool input
12. Caps output_data at 50KB

DATABASE:
13. RLS blocks unauthenticated SELECT on watch_sessions
14. RLS blocks unauthenticated SELECT on watch_events
15. RLS allows authenticated SELECT on watch_sessions
16. Foreign key cascade deletes events when session deleted
17. pg_cron retention deletes events older than 30 days

HEALTH SCANNER:
18. Classifies CLAUDE.md as category='rules'
19. Classifies .cursorrules as category='prompt'
20. Detects NEVER keyword as importance='critical'
21. Skips node_modules directory
22. Computes consistent SHA-256 for same content
23. Caps file scan at 100KB

DASHBOARD:
24. Login page renders without auth
25. Session list requires authentication
```

---

## 9. FILE TREE (Complete)

```
cli-anything-biddeed/
└── harnesses/
    └── watch/
        ├── HARNESS.md                         # 7-phase harness doc
        ├── package.json
        ├── tsconfig.json
        ├── src/
        │   ├── install-hooks.ts               # CLI: add/remove hooks in settings.json
        │   ├── health-scan.ts                 # Brain scanner (secured, no shell)
        │   ├── utils/
        │   │   ├── classify.ts                # File classification patterns
        │   │   └── hash.ts                    # SHA-256 hashing
        │   └── types.ts                       # Shared types
        ├── supabase/
        │   ├── migrations/
        │   │   └── 20260319_watch_tables.sql  # All tables, indexes, RLS, views, cron
        │   └── functions/
        │       └── watch-ingest/
        │           ├── index.ts               # Edge function handler
        │           └── deno.json              # Deno config for edge function
        ├── dashboard/
        │   ├── package.json
        │   ├── tsconfig.json
        │   ├── vite.config.ts
        │   ├── tailwind.config.js
        │   ├── index.html
        │   └── src/
        │       ├── main.tsx
        │       ├── App.tsx                    # Router: Login / Live / Audit / Health
        │       ├── lib/
        │       │   └── supabase.ts            # Supabase client init
        │       ├── hooks/
        │       │   ├── useAuth.ts
        │       │   ├── useRealtime.ts         # Supabase Realtime subscription
        │       │   └── useSessions.ts         # Session data fetching
        │       ├── components/
        │       │   ├── Layout.tsx             # Shell: sidebar + tabs + mobile nav
        │       │   ├── LoginPage.tsx
        │       │   ├── live/
        │       │   │   ├── ActiveSessionCards.tsx
        │       │   │   ├── LiveEventStream.tsx
        │       │   │   └── ToolFrequencyChart.tsx
        │       │   ├── audit/
        │       │   │   ├── SessionTable.tsx
        │       │   │   ├── SessionTimeline.tsx
        │       │   │   ├── DiffViewer.tsx
        │       │   │   └── FilterBar.tsx
        │       │   └── health/
        │       │       ├── RepoSelector.tsx
        │       │       ├── LogicFileTree.tsx
        │       │       ├── ChangeTimeline.tsx
        │       │       └── HealthScoreCard.tsx
        │       └── styles/
        │           └── globals.css            # House brand tokens
        ├── eval/
        │   └── eval.json                      # 25 AUTOLOOP assertions
        └── .github/
            └── workflows/
                ├── deploy-dashboard.yml       # CF Pages deploy on push
                ├── deploy-edge-function.yml   # Supabase function deploy
                └── health-scan.yml            # Nightly 2AM EST scan
```
