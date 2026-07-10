# DAILY ACTION PLAN V2 — Intelligent Task Engine
# Date: March 29, 2026 | Status: SPEC → SUMMIT
# Problem: Current system is a dumb Nexus reader. No memory, no carryforward, no ML, no artifact tracking.

---

## PROBLEM STATEMENT

1. **No carryforward**: Yesterday's incomplete tasks don't auto-surface today with escalation
2. **No artifact tracking**: High-value deliverables (competitive analysis HTML, CI reports, specs) get buried in chat history
3. **No verification**: Tasks marked "done" aren't verified (Honesty Protocol violation)
4. **No ML prioritization**: Manual P0-P3 labels are static — no learning from patterns
5. **No cross-domain awareness**: Swimming, property, ecosystem tasks aren't weighted by deadline proximity
6. **Morning plan is text-only**: No links to artifacts, no context from yesterday's work

---

## NEW SUPABASE TABLES

### 1. artifact_vault
Tracks every deliverable created across Claude AI and Claude Code sessions.

```sql
CREATE TABLE artifact_vault (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  title TEXT NOT NULL,
  description TEXT,
  artifact_type TEXT NOT NULL, -- 'html','jsx','docx','spec','sql','script','report','analysis'
  domain TEXT NOT NULL, -- 'BIDDEED','ZONEWISE','GTM','MICHAEL','PROPERTY','PERSONAL','ECOSYSTEM'
  status TEXT DEFAULT 'created', -- 'created','deployed','buried','archived','superseded'
  deploy_url TEXT, -- where it lives (if deployed)
  source_chat_url TEXT, -- claude.ai chat link
  source_repo TEXT, -- github repo if committed
  source_path TEXT, -- file path in repo
  importance INTEGER DEFAULT 5, -- 1-10 ML-scored
  last_referenced TIMESTAMPTZ,
  tags TEXT[],
  metadata JSONB DEFAULT '{}'
);
```

### 2. task_carryforward
Tracks daily task lifecycle — what carried forward, how many days, escalation level.

```sql
CREATE TABLE task_carryforward (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  task_id TEXT NOT NULL, -- references nexus_tasks.task_id
  date DATE NOT NULL,
  status TEXT NOT NULL, -- 'new','carried','escalated','completed','dropped'
  carry_count INTEGER DEFAULT 0, -- how many days carried forward
  escalation_level INTEGER DEFAULT 0, -- 0=normal, 1=nudge, 2=warning, 3=critical
  verified BOOLEAN DEFAULT false, -- honesty protocol: was completion verified?
  verification_method TEXT, -- 'curl','db_query','visual','self_report'
  verification_proof TEXT, -- actual proof (curl output, screenshot URL, etc)
  ml_priority_score FLOAT, -- ML-calculated priority (0-100)
  ml_factors JSONB, -- what factors drove the score
  notes TEXT,
  UNIQUE(task_id, date)
);
```

### 3. daily_digest
Stores the full rendered digest for each day (searchable, auditable).

```sql
CREATE TABLE daily_digest (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  date DATE NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  digest_text TEXT NOT NULL, -- full Telegram message
  stats JSONB NOT NULL, -- {total, completed, carried, new, dropped, gha_health, ml_top5}
  artifacts_referenced UUID[], -- artifact_vault IDs mentioned
  domains_covered TEXT[], -- which domains had activity
  honesty_score FLOAT, -- % of completed tasks that were verified
  carryforward_count INTEGER, -- how many tasks carried from previous day
  streak_days INTEGER DEFAULT 0
);
```

---

## ML PRIORITY SCORING MODEL

### Features (per task):
```yaml
ml_features:
  time_pressure:
    sla_days_remaining: float  # negative = overdue
    carry_count: int           # days carried forward (higher = more urgent)
    domain_deadline_proximity: float  # e.g., Michael Futures Jul 29 = 122 days

  impact:
    domain_weight: float       # BIDDEED=1.0, MICHAEL=0.9, PROPERTY=0.8, etc.
    artifact_importance: float # if linked to high-value artifact
    blocker_count: int         # how many other tasks depend on this
    revenue_impact: float      # estimated $ impact (0-1 normalized)

  pattern:
    completion_rate_owner: float    # historical: how often does this owner complete tasks?
    avg_carry_days_domain: float    # historical: how long do tasks in this domain take?
    similar_task_completion: float  # embedding similarity to previously completed tasks
    time_of_day_fit: float         # is this task type best done morning/afternoon?

  context:
    is_shabbat_sensitive: bool     # must complete before Friday
    is_blocked: bool
    has_external_dependency: bool  # waiting on API key, person, etc.
    escalation_history: int        # previous escalations on this task
```

### Scoring formula (v1 — heuristic, upgradeable to XGBoost):
```python
def ml_priority_score(task, history):
    score = 50.0  # baseline

    # Time pressure (max +30)
    if task.sla_days_remaining is not None:
        if task.sla_days_remaining < 0:
            score += 30  # overdue
        elif task.sla_days_remaining < 3:
            score += 25
        elif task.sla_days_remaining < 7:
            score += 15
        elif task.sla_days_remaining < 14:
            score += 8

    # Carry penalty (+5 per day carried, max +20)
    score += min(task.carry_count * 5, 20)

    # Domain weight (+0-10)
    domain_weights = {"BIDDEED": 10, "ZONEWISE": 10, "MICHAEL": 9, "PROPERTY": 8, "GTM": 7, "ECOSYSTEM": 6, "PERSONAL": 4}
    score += domain_weights.get(task.domain, 5)

    # Blocker multiplier
    if task.blocker_count > 0:
        score += task.blocker_count * 3

    # Owner completion rate penalty
    if task.owner == "ariel" and history.ariel_completion_rate < 0.5:
        score += 5  # nudge harder for low completion

    # Shabbat sensitivity
    if task.is_shabbat_sensitive and is_thursday_or_friday():
        score += 10

    # Blocked tasks get deprioritized
    if task.is_blocked:
        score -= 20

    return min(max(score, 0), 100)
```

---

## UPGRADED daily_action_plan.py FLOW

```yaml
flow:
  1_load_yesterday:
    - Query task_carryforward WHERE date = yesterday
    - Identify: completed (verified?), still open, dropped
    - Calculate yesterday's honesty_score

  2_carryforward:
    - All open tasks from yesterday → carry_count += 1
    - If carry_count >= 3 → escalation_level += 1
    - If carry_count >= 7 → auto-escalate to P0
    - Insert into task_carryforward for today

  3_load_today:
    - Query nexus_tasks for new/queued/running/blocked
    - Merge with carryforward tasks (deduplicate)

  4_ml_score:
    - Run ml_priority_score() on every task
    - Sort by score descending
    - Top 5 = "MUST DO TODAY"

  5_artifact_check:
    - Query artifact_vault WHERE status != 'deployed' AND importance >= 7
    - Surface buried high-value artifacts as action items
    - "Deploy competitive-analysis.jsx to zonewise.ai/competitors"

  6_gha_health:
    - Same as current (check yesterday's GHA runs)
    - Add: per-repo breakdown

  7_honesty_audit:
    - Check honesty_violations WHERE resolved = false
    - Check tasks marked done yesterday without verification_proof

  8_build_message:
    - Section 1: YESTERDAY RESULTS (completed/carried/dropped + honesty %)
    - Section 2: MUST DO TODAY (ML top 5 with scores)
    - Section 3: ARIEL TASKS (owner=ariel, sorted by ML score)
    - Section 4: CLAUDE CODE QUEUE (top 5 by ML score)
    - Section 5: BURIED ARTIFACTS (undeployed high-value items)
    - Section 6: BLOCKED + HONESTY VIOLATIONS
    - Section 7: GHA HEALTH + STATS

  9_send:
    - Telegram (4K char limit, truncate intelligently)
    - Supabase daily_digest insert

  10_schedule_evening:
    - At 5 PM EST: run verification sweep
    - Check if today's "MUST DO" items were actually done
    - Pre-build tomorrow's carryforward
```

---

## ARTIFACT VAULT SEEDING

Seed with known high-value artifacts from chat history:

```sql
INSERT INTO artifact_vault (title, artifact_type, domain, status, importance, source_chat_url, tags) VALUES
('8-Competitor Analysis (Gridics/Zoneomics/TestFit/PropertyOnion/Algoma/ArkDesign/Reventure)', 'jsx', 'GTM', 'buried', 10, 'https://claude.ai/chat/7fb28289-1dc6-40ad-8d96-b13b0eea22b7', ARRAY['competitive-intel','investor','gtm']),
('Algoma Full CI Report (PRD/PRS/SWOT/Battle Card)', 'docx', 'GTM', 'buried', 9, 'https://claude.ai/chat/bd1df173-fb7e-4d71-a67e-ea31b8c29305', ARRAY['competitive-intel','algoma']),
('TestFit CI Report', 'docx', 'GTM', 'buried', 8, 'https://claude.ai/chat/4144bbb3-9386-4f21-8611-45e0ecba894e', ARRAY['competitive-intel','testfit']),
('ZoneWise 20 Data Phases Comparison', 'docx', 'ZONEWISE', 'buried', 9, 'https://claude.ai/chat/b2c0ea12-84c5-4f43-b2dc-0f018f1c7421', ARRAY['competitive-intel','data-phases','roadmap']),
('HONESTY-PROTOCOL.md', 'spec', 'ECOSYSTEM', 'deployed', 10, 'https://claude.ai/chat/64e02f30-1ac3-42fe-bfe1-7b8e9139bf29', ARRAY['protocol','enforcement']),
('AUTOLOOP L3 Spec', 'spec', 'ECOSYSTEM', 'deployed', 8, 'https://claude.ai/chat/f896c220-4c63-40d7-a808-66683974e8cd', ARRAY['autoloop','ml']),
('DesignWise V3 Spec', 'spec', 'ECOSYSTEM', 'created', 8, NULL, ARRAY['designwise','agents']),
('CODESEARCH Spec', 'spec', 'ECOSYSTEM', 'created', 7, 'https://claude.ai/chat/86396d07-a854-4579-95a0-2ed65ef3aca0', ARRAY['codesearch','search']);
```

---

## EVENING VERIFICATION SWEEP (5 PM EST)

New workflow: `daily-verification-sweep.yml`
- Cron: `0 21 * * *` (5 PM EDT = 21:00 UTC)
- Checks all tasks marked completed today
- For each: was verification_proof provided?
- If not: mark as UNVERIFIED, add to tomorrow's action plan
- Calculate daily honesty_score = verified_completions / total_completions

---

## SUCCESS CRITERIA

- [ ] artifact_vault table created with 8+ seeded artifacts
- [ ] task_carryforward table created
- [ ] daily_digest table created  
- [ ] ML priority scoring function operational
- [ ] Carryforward logic working (carry_count increments daily)
- [ ] Buried artifacts surface in morning plan
- [ ] Evening verification sweep runs at 5 PM
- [ ] Telegram message includes all 7 sections
- [ ] Yesterday's results section shows honesty %
