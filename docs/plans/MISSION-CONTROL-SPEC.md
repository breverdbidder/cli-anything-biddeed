# Mission Control — watch.biddeed.ai
## Design Specification v1.0

**Author:** Claude AI Architect
**Date:** Mar 22, 2026
**Status:** APPROVED — All 7 decisions locked
**Deploys to:** watch.biddeed.ai (Vercel Pro, existing project)
**Repo:** breverdbidder/cli-anything-biddeed → harnesses/watch/

---

## Decisions Log

```yaml
decisions:
  D1_location: watch.biddeed.ai (expand Claude Watch S3 → Mission Control)
  D2_ingestion: Hybrid (instant for P0/blockers, session summary for rest)
  D3_notifications: Event-driven Telegram via @BidDeedAI_bot
  D4_repos: All 50 repos under breverdbidder org (tiered)
  D5_escalation: P0 repeats every 2hr, accountability alert at 4hr
  D6_digest: Twice daily 9AM + 5PM EST
  D7_priority: Auto-assign with Telegram override (/bump /demote commands)
```

---

## Problem Statement

35+ open items across 7 projects discovered from 10 chat sessions. No persistent tracking. Tasks go stale between sessions. No visibility into Claude Code session outputs. 50 GitHub repos with no unified health view. ADHD-optimized accountability requires persistent, automated follow-up — not manual tracking.

---

## Architecture

```mermaid
graph TD
    subgraph Ingestion
        CA[Claude AI Chat] -->|instant P0/blocker| API[Supabase REST API]
        CA -->|end-of-session summary| API
        CC[Claude Code on Hetzner] -->|watch hooks S2| API
        GH[GitHub Webhooks] -->|push/PR/CI events| EF[Edge Function: gh-webhook]
        EF --> API
    end

    subgraph Storage[Supabase Tables]
        API --> TR[task_registry]
        API --> TL[task_logs]
        API --> RS[repo_status]
        API --> CS[chat_sessions]
        API --> NL[notifications_log]
    end

    subgraph Scheduling
        CRON1[pg_cron 5min] -->|staleness scan| TR
        CRON2[pg_cron 9AM/5PM EST] -->|digest builder| NL
        CRON3[pg_cron 2hr] -->|P0 escalation check| TR
    end

    subgraph Dashboard[watch.biddeed.ai]
        TR --> UI[Next.js Dashboard]
        RS --> UI
        CS --> UI
        UI -->|Supabase Realtime| WS[Live Updates]
    end

    subgraph Notifications
        TR -->|P0/blocked/complete| TG[@BidDeedAI_bot]
        RS -->|CI fail/stale repo| TG
        CRON2 -->|digest| TG
        CRON3 -->|P0 escalation| TG
        TG -->|/bump /demote /done /skip| TR
    end
```

---

## Priority System

```yaml
priorities:
  P0_CRITICAL:
    sla: Same session
    color: "#EF4444"
    icon: "🔴"
    telegram:
      on_create: INSTANT
      on_stale_2hr: REPEAT reminder
      on_stale_4hr: ACCOUNTABILITY escalation
      on_resolve: INSTANT "✅ RESOLVED"
    dashboard: Red pulse animation, pinned to top

  P1_HIGH:
    sla: Same day (24hr)
    color: "#F59E0B"
    icon: "🟠"
    telegram:
      on_create: INSTANT (one-time)
      on_stale_24hr: Reminder
      on_resolve: INSTANT "✅ Done"
    dashboard: Orange badge, sorted after P0

  P2_MEDIUM:
    sla: This week (72hr)
    color: "#EAB308"
    icon: "🟡"
    telegram:
      on_create: Silent (batched into digest)
      on_stale_72hr: Included in next digest as "stale"
      on_resolve: Silent
    dashboard: Yellow, normal sort

  P3_LOW:
    sla: Backlog (30 days)
    color: "#6B7280"
    icon: "⚪"
    telegram:
      on_create: Silent
      on_stale_30d: Auto-archive suggestion in digest
      on_resolve: Silent
    dashboard: Gray, collapsed by default
```

### Auto-Assignment Rules

```yaml
auto_priority_rules:
  P0:
    - status == "blocked"
    - owner == "Ariel" AND task contains "blocker"
    - CI failed on Tier 1 repo
    - Sentinel alert (system down)
  P1:
    - Summit dispatched
    - owner == "Ariel" (any action item)
    - architectural decision made
    - new spec/plan created
    - CI failed on Tier 2 repo
  P2:
    - Claude Code session task (routine)
    - repo staleness > 7 days (Tier 1/2)
    - feature implementation queued
  P3:
    - documentation updates
    - repo staleness (Tier 3)
    - nice-to-have improvements
    - deferred items
```

### Telegram Override Commands

```yaml
bot_commands:
  /bump <task_id>: Increase priority by 1 level (P2→P1, P1→P0)
  /demote <task_id>: Decrease priority by 1 level
  /done <task_id>: Mark task complete
  /skip <task_id>: Mark task skipped/deferred
  /tasks: List active tasks grouped by priority
  /p0: List P0 items only
  /stale: List stale items past SLA
  /digest: Force immediate digest
```

---

## Data Model

### Existing Tables (UTCC building now)

```yaml
task_registry:
  # As defined in UTCC spec — adding columns:
  new_columns:
    priority: TEXT DEFAULT 'P2' CHECK (P0, P1, P2, P3)
    project: TEXT  # designwise, utcc, zonewise, youtube, infra, michael, personal
    owner: TEXT DEFAULT 'Claude Code'
    sla_deadline: TIMESTAMPTZ  # auto-computed from priority
    escalation_count: INT DEFAULT 0
    last_escalated_at: TIMESTAMPTZ
    source_chat_id: TEXT  # links to chat_sessions
    auto_priority: BOOLEAN DEFAULT true  # false if manually overridden

task_logs:
  # As defined in UTCC spec — no changes
```

### New Tables

```sql
-- repo_status: GitHub repo health tracking
CREATE TABLE repo_status (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    repo_name TEXT UNIQUE NOT NULL,
    tier TEXT CHECK (tier IN ('core', 'active', 'monitored')) NOT NULL,
    last_push_at TIMESTAMPTZ,
    last_push_by TEXT,
    last_ci_status TEXT CHECK (last_ci_status IN ('success', 'failure', 'pending', 'none')),
    last_ci_url TEXT,
    last_ci_at TIMESTAMPTZ,
    open_prs INT DEFAULT 0,
    open_issues INT DEFAULT 0,
    default_branch TEXT DEFAULT 'main',
    stale_days INT DEFAULT 0,
    health_score INT DEFAULT 100,  -- 100=healthy, <50=needs attention
    topics JSONB DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_repo_tier ON repo_status(tier);
CREATE INDEX idx_repo_stale ON repo_status(stale_days DESC);

-- chat_sessions: Claude AI + Claude Code session tracking
CREATE TABLE chat_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    title TEXT,
    source TEXT CHECK (source IN ('claude_ai', 'claude_code', 'telegram')) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    tasks_created INT DEFAULT 0,
    tasks_completed INT DEFAULT 0,
    key_decisions JSONB DEFAULT '[]',
    summary TEXT,
    chat_url TEXT
);
CREATE INDEX idx_chat_source ON chat_sessions(source);
CREATE INDEX idx_chat_started ON chat_sessions(started_at DESC);

-- notifications_log: Audit trail for all Telegram messages
CREATE TABLE notifications_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id TEXT,
    repo_name TEXT,
    priority TEXT,
    notification_type TEXT CHECK (notification_type IN (
        'task_created', 'task_completed', 'task_blocked',
        'escalation', 'accountability', 'digest',
        'ci_failure', 'repo_stale', 'override'
    )),
    message TEXT NOT NULL,
    telegram_msg_id BIGINT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered BOOLEAN DEFAULT false
);
CREATE INDEX idx_notif_type ON notifications_log(notification_type);
CREATE INDEX idx_notif_sent ON notifications_log(sent_at DESC);
```

---

## Repo Tiering

```yaml
tier_core:  # Deep tracking: CI, PRs, issues, commits, staleness 7d
  - cli-anything-biddeed
  - zonewise-web
  - biddeed-ai
  - biddeed-ai-ui
  - claude-code-telegram-control
  - life-os
  - cliproxy-gateway

tier_active:  # Commit monitoring + CI status, staleness 14d
  - zonewise
  - goviralbitch
  - superpowers
  - zonewise-landing
  - biddeed-landing
  - brevard-bidder-landing
  - zonewise-desktop

tier_monitored:  # Staleness alerts only, 30d threshold
  # Remaining 36 repos
  # Auto-detected: any repo not in core/active
```

---

## Scheduled Jobs (pg_cron)

```yaml
cron_jobs:
  staleness_scan:
    schedule: "*/5 * * * *"  # Every 5 min
    action: |
      UPDATE repo_status SET stale_days = EXTRACT(DAY FROM NOW() - last_push_at)::INT;
      -- Flag repos past threshold by tier

  p0_escalation:
    schedule: "0 */2 * * *"  # Every 2 hours
    action: |
      SELECT tasks where priority='P0' AND status NOT IN ('success','cancelled','skipped')
        AND created_at < NOW() - INTERVAL '2 hours'
        AND (last_escalated_at IS NULL OR last_escalated_at < NOW() - INTERVAL '2 hours');
      -- For each: send Telegram escalation, increment escalation_count
      -- If escalation_count >= 2 (4hr): send ACCOUNTABILITY alert

  morning_digest:
    schedule: "0 14 * * *"  # 9 AM EST = 14:00 UTC
    action: Build and send digest via edge function

  evening_digest:
    schedule: "0 22 * * *"  # 5 PM EST = 22:00 UTC
    action: Build and send digest via edge function

  repo_sync:
    schedule: "0 */6 * * *"  # Every 6 hours
    action: |
      GitHub API: fetch all breverdbidder repos
      Update repo_status: last_push, CI status, open PRs/issues
      Detect new repos → auto-add as tier_monitored
```

---

## Dashboard Pages (Next.js)

```yaml
pages:
  /:  # Command Center home
    - Priority strip: P0 count (red) | P1 count (orange) | P2 (yellow) | P3 (gray)
    - Active tasks table: filterable by project, owner, priority, status
    - Real-time updates via Supabase Realtime subscription
    - Ariel Action Items callout box (owner=Ariel, not completed)

  /repos:
    - Repo health grid: 50 cards grouped by tier
    - Each card: name, last push, CI badge, stale indicator, health score
    - Click → repo detail (recent commits, open PRs, CI runs)

  /sessions:
    - Timeline of Claude AI + Claude Code sessions
    - Each session: title, tasks created/completed, key decisions, duration
    - Link to chat URL where available

  /notifications:
    - Notification audit log
    - Filter by type, priority, date
    - Delivery status tracking

  /settings:
    - Repo tier management (drag-drop between tiers)
    - Priority auto-rule configuration
    - Notification preferences
    - Telegram connection status
```

---

## Ingestion Protocol (for Claude AI sessions)

### During Chat — Instant Push
```bash
# Claude AI calls this when P0/blocker/dispatch occurs
SUPABASE_URL="https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY="<service_role_key>"

curl -s -X POST "$SUPABASE_URL/rest/v1/task_registry" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  -d '{
    "task_id": "mc-<timestamp>-<short_hash>",
    "description": "...",
    "task_type": "claude_code",
    "platform": "biddeed",
    "priority": "P0",
    "owner": "Ariel",
    "project": "designwise",
    "status": "blocked",
    "triggered_by": "claude_ai",
    "source_chat_id": "..."
  }'
```

### End of Chat — Session Summary Push
```bash
# Bulk upsert all open items from session
# Called as final action before session ends
curl -s -X POST "$SUPABASE_URL/rest/v1/chat_sessions" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "chat-<uuid>",
    "title": "...",
    "source": "claude_ai",
    "tasks_created": 5,
    "tasks_completed": 2,
    "key_decisions": ["D1: ...", "D2: ..."],
    "summary": "..."
  }'

# Then upsert each task
# ON CONFLICT (task_id) DO UPDATE for existing tasks
```

---

## Brand

```yaml
brand:
  primary: "#1E3A5F"
  accent: "#F59E0B"
  background: "#020617"
  font: Inter
  p0_color: "#EF4444"
  p1_color: "#F59E0B"
  p2_color: "#EAB308"
  p3_color: "#6B7280"
  success: "#10B981"
  hover: "#D97706"
```
