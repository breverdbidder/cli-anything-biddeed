# SUMMIT: skills-scout

## MISSION
Build and deploy the skills-scout agent in cli-anything-biddeed. This agent autonomously discovers, scores, adopts, and syncs agent skills from skills.sh across the entire BidDeed.AI GitHub ecosystem. Cost: $0/month. Zero human-in-the-loop after deploy.

## CRITICAL RULES
- $10/session MAX. Batch operations. ONE attempt per approach.
- Use Gemini Flash for scoring (FREE). NEVER paid Claude API.
- GitHub PAT4: `${{ secrets.GH_PAT4 }}` (classic, no expiry, repo+workflow)
- Supabase URL: `mocerqjnksmhcjzxrewo.supabase.co`
- Supabase Service Role key ends with `...Tqp9nE` — pull from SUPABASE_CREDENTIALS.md or repo secrets
- Telegram alerts via existing bot token + chat ID in cli-anything-biddeed secrets
- NEVER use ANTHROPIC_API_KEY for any LLM calls
- Auto-skip review items after 7 days (zero human dependency)
- All vanilla Python + bash. No frameworks. Daniel Studio principle.

## REPO
`breverdbidder/cli-anything-biddeed`

Clone, branch `feat/skills-scout`, build, test, merge to main.

## STEP 1: SUPABASE MIGRATIONS

Run these against Supabase via REST API or supabase-py:

```sql
-- Table 1: Master skills catalog
CREATE TABLE IF NOT EXISTS skills_library (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_name TEXT NOT NULL,
    skill_repo TEXT NOT NULL,
    skill_source TEXT NOT NULL DEFAULT 'skills.sh',
    skills_sh_url TEXT,
    github_url TEXT,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'uncategorized',
    action_type TEXT NOT NULL DEFAULT 'install',
    tier INTEGER NOT NULL DEFAULT 1,
    community_installs INTEGER DEFAULT 0,
    community_rank INTEGER,
    relevance_score INTEGER DEFAULT 0,
    matching_repos TEXT[] DEFAULT '{}',
    scoring_reason TEXT,
    status TEXT NOT NULL DEFAULT 'discovered',
    adopted_at TIMESTAMPTZ,
    customized_at TIMESTAMPTZ,
    forked_repo TEXT,
    last_upstream_sha TEXT,
    last_upstream_check TIMESTAMPTZ,
    last_metrics_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(skill_name, skill_repo)
);

CREATE INDEX IF NOT EXISTS idx_skills_status ON skills_library(status);
CREATE INDEX IF NOT EXISTS idx_skills_score ON skills_library(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills_library(category);

ALTER TABLE skills_library ENABLE ROW LEVEL SECURITY;
CREATE POLICY "skills_read_all" ON skills_library FOR SELECT USING (true);
CREATE POLICY "skills_write_service" ON skills_library FOR ALL USING (
    current_setting('request.jwt.claims', true)::json->>'role' = 'service_role'
);

-- Table 2: Upstream sync tracking
CREATE TABLE IF NOT EXISTS skills_upstream_sync (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_id UUID REFERENCES skills_library(id) ON DELETE CASCADE,
    upstream_sha TEXT NOT NULL,
    change_type TEXT,
    change_summary TEXT,
    auto_merged BOOLEAN DEFAULT false,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_upstream_skill ON skills_upstream_sync(skill_id);

ALTER TABLE skills_upstream_sync ENABLE ROW LEVEL SECURITY;
CREATE POLICY "sync_read_all" ON skills_upstream_sync FOR SELECT USING (true);
CREATE POLICY "sync_write_service" ON skills_upstream_sync FOR ALL USING (
    current_setting('request.jwt.claims', true)::json->>'role' = 'service_role'
);

-- Table 3: Adoption audit log
CREATE TABLE IF NOT EXISTS skills_adoption_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_name TEXT NOT NULL,
    skill_repo TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_repos TEXT[] DEFAULT '{}',
    relevance_score INTEGER,
    commit_sha TEXT,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    cost_usd NUMERIC(6,4) DEFAULT 0.0000,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE skills_adoption_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "log_read_all" ON skills_adoption_log FOR SELECT USING (true);
CREATE POLICY "log_write_service" ON skills_adoption_log FOR ALL USING (
    current_setting('request.jwt.claims', true)::json->>'role' = 'service_role'
);
```

Verify all 3 tables exist before proceeding.

## STEP 2: FILE STRUCTURE

Create under `cli_anything/skills_scout/`:

```
cli_anything/skills_scout/
├── __init__.py
├── main.py          # click CLI: discover | sync | report | force-adopt
├── scraper.py       # httpx + BeautifulSoup → skills.sh leaderboard
├── scorer.py        # Gemini Flash relevance scoring + keyword fallback
├── adopter.py       # GitHub API fork + npx skills add
├── syncer.py        # Upstream SHA diff + auto-merge
├── reporter.py      # Telegram bot alerts
├── security.py      # SKILL.md malicious pattern scanner
└── config.py        # Constants, repo map, thresholds
```

## STEP 3: config.py

```python
"""Skills Scout configuration — repo maps, thresholds, constants."""

SKILLS_SH_URLS = [
    "https://skills.sh/",
    "https://skills.sh/trending",
    "https://skills.sh/hot",
]

# Score thresholds
AUTO_ADOPT_THRESHOLD = 80
REVIEW_THRESHOLD = 60
AUTO_SKIP_AFTER_DAYS = 7  # Zero human dependency

# Category → target repos mapping
CATEGORY_REPO_MAP = {
    "orchestration": ["cli-anything-biddeed", "biddeed-ai"],
    "frontend": ["biddeed-ai-ui", "zonewise-web"],
    "scraping": ["zonewise-scraper-v4", "brevard-bidder-scraper"],
    "data": ["biddeed-ai", "ai-tools-library", "tax-insurance-optimizer"],
    "security": [
        "cli-anything-biddeed", "biddeed-ai", "biddeed-ai-ui",
        "zonewise-web", "zonewise-scraper-v4", "context-boot-mcp-server",
        "ai-tools-library",
    ],
    "marketing": ["biddeed-ai-ui", "zonewise-web"],
    "mcp": ["context-boot-mcp-server"],
    "testing": ["cli-anything-biddeed", "biddeed-ai"],
    "devops": ["cli-anything-biddeed"],
}

# High-relevance keywords (+30 score each)
HIGH_KEYWORDS = [
    "supabase", "firecrawl", "scraping", "foreclosure", "real-estate",
    "spatial", "gis", "mapbox", "agent", "orchestration", "mcp",
]

# Medium-relevance keywords (+15 score each)
MEDIUM_KEYWORDS = [
    "react", "python", "debugging", "testing", "security", "github-actions",
    "cloudflare", "browser", "data-analysis", "seo", "automation",
]

# Low-relevance keywords (+5 score each)
LOW_KEYWORDS = [
    "typescript", "design", "marketing", "email", "pdf", "docx", "xlsx",
    "tailwind", "nextjs", "vue",
]

# Security: reject skills with these patterns in SKILL.md
CRITICAL_PATTERNS = [
    r"curl.*\|.*sh",
    r"rm\s+-rf\s+/",
    r"wget.*\|.*bash",
]

HIGH_PATTERNS = [
    r"\$\{?\w*KEY\w*\}?",
    r"eval\(",
    r"base64.*decode",
    r"(webhook|ngrok|requestbin)",
    r"exec\(",
]

GITHUB_ORG = "breverdbidder"
SKILLS_FORK_REPO = "biddeed-skills"  # All forked skills land here
```

## STEP 4: scraper.py

Scrape skills.sh leaderboard pages using httpx + BeautifulSoup.

Extract from each skill entry:
- `skill_name` (from the h3/link text)
- `skill_repo` (from the subtitle/link, format: owner/repo)
- `community_installs` (parse the K suffix, e.g. "31.8K" → 31800)
- `skills_sh_url` (full href)
- `rank` (position on leaderboard)

Compare against existing `skills_library` rows. INSERT new skills with `status='discovered'`. UPDATE install counts if changed >10%.

Rate limit: 2 second delay between page fetches. Max 10 pages per run.

Return list of newly discovered skill dicts.

## STEP 5: scorer.py

Score each newly discovered skill.

PRIMARY: Gemini Flash API (FREE tier)
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`
- API key from `GEMINI_API_KEY` env var
- Prompt asks for JSON response with: score (0-100), matching_repos, category, action (install/fork/skip), reason

FALLBACK: Keyword matching if Gemini fails or rate-limited
- Check skill_name + description against HIGH/MEDIUM/LOW keyword lists
- Sum points, cap at 100
- Infer category from highest-matching keyword group

UPDATE `skills_library` with: `relevance_score`, `matching_repos`, `category`, `action_type`, `scoring_reason`

Set status:
- score >= 80 → `status='pending_adoption'`
- score 60-79 → `status='pending_review'`
- score < 60 → `status='archived'`

## STEP 6: adopter.py

For skills with `status='pending_adoption'`:

1. **Security scan first** — call `security.py` check on the SKILL.md content fetched via GitHub raw URL. If REJECT → set `status='rejected'`, log to adoption_log, skip.

2. **Install method** — use GitHub API to:
   - Fetch SKILL.md content from source repo
   - For each `matching_repo` in breverdbidder org:
     - Create `.claude/skills/{skill_name}/SKILL.md` via GitHub Contents API (PUT)
     - Commit message: `feat(skills): auto-adopt {skill_name} from {skill_repo}`

3. **Update Supabase**:
   - `skills_library`: set `status='installed'`, `adopted_at=NOW()`
   - `skills_adoption_log`: INSERT success record
   - `skills_upstream_sync`: INSERT with current upstream commit SHA

4. **Auto-skip stale reviews**: Query `skills_library` where `status='pending_review' AND created_at < NOW() - INTERVAL '7 days'`. Set those to `status='auto_skipped'`.

## STEP 7: syncer.py

For all skills with `status='installed'` or `status='forked'`:

1. Fetch latest commit SHA from upstream repo via GitHub API:
   `GET /repos/{skill_repo}/commits?path=skills/{skill_name}/SKILL.md&per_page=1`

2. Compare against `skills_upstream_sync.upstream_sha`

3. If different:
   - Fetch the new SKILL.md content
   - Compare size/structure change:
     - Size delta < 20% → MINOR → auto-update in all target repos
     - Size delta >= 20% → MAJOR → create GitHub Issue + Telegram alert
   - INSERT new row in `skills_upstream_sync`
   - Update SKILL.md in all target repos via GitHub Contents API

4. Staleness check: Flag skills where upstream has no commits in 90 days.

## STEP 8: reporter.py

Send Telegram message via Bot API:

```
POST https://api.telegram.org/bot{token}/sendMessage
{
  "chat_id": "{chat_id}",
  "parse_mode": "HTML",
  "text": "<b>🔍 SKILLS SCOUT — {date}</b>\n\n📊 Scanned: {n}\n🆕 Discovered: {n}\n✅ Adopted: {n}\n👀 Review: {n}\n🔄 Synced: {n}\n⚠️ Diverged: {n}\n\n{details}\n\n💰 Cost: $0.00"
}
```

Include top 5 adoptions with skill name + target repos.
Include any review items (will auto-skip in 7 days).
Include any upstream divergence warnings.

## STEP 9: main.py

Click CLI with 4 modes:

```python
@click.command()
@click.option("--mode", type=click.Choice(["discover", "sync", "report", "force-adopt"]), default="discover")
def main(mode):
    if mode == "discover":
        # Phase 2 → 3 → 4 → 6
        new_skills = scrape_skills_sh()
        scored = score_skills(new_skills)
        adopted = adopt_skills(scored)
        send_report(new_skills, scored, adopted)
    elif mode == "sync":
        # Phase 5 → 6
        sync_results = check_upstream()
        send_sync_report(sync_results)
    elif mode == "report":
        # Phase 6 only
        send_status_report()
    elif mode == "force-adopt":
        # Re-score all pending, adopt eligible
        rescore_and_adopt()
```

## STEP 10: security.py

Scan SKILL.md content for malicious patterns:

```python
import re

def scan_skill(content: str) -> dict:
    """Returns {"safe": bool, "findings": [...], "severity": "ok|medium|high|critical"}"""
    findings = []
    for pattern in CRITICAL_PATTERNS:
        if re.search(pattern, content):
            findings.append({"pattern": pattern, "severity": "critical"})
    for pattern in HIGH_PATTERNS:
        if re.search(pattern, content):
            findings.append({"pattern": pattern, "severity": "high"})
    
    critical_count = sum(1 for f in findings if f["severity"] == "critical")
    high_count = sum(1 for f in findings if f["severity"] == "high")
    
    if critical_count > 0 or high_count > 2:
        return {"safe": False, "findings": findings, "severity": "critical"}
    elif high_count > 0:
        return {"safe": True, "findings": findings, "severity": "high"}
    return {"safe": True, "findings": [], "severity": "ok"}
```

Also reject if SKILL.md > 50KB.

## STEP 11: TESTS

Create `tests/test_skills_scout/` with:

- `test_scraper.py` — mock httpx responses, verify parsing of skill names/installs/repos
- `test_scorer.py` — test keyword fallback scoring with known skill names
- `test_security.py` — test malicious pattern detection with sample payloads
- `test_adopter.py` — mock GitHub API, verify SKILL.md placement path
- `test_syncer.py` — mock SHA comparison, verify MINOR vs MAJOR classification

Run all tests. All must pass before merge.

## STEP 12: GITHUB ACTIONS WORKFLOW

Create `.github/workflows/skills-scout.yml`:

```yaml
name: Skills Scout

on:
  schedule:
    - cron: '0 13 * * *'     # Daily 9AM EST (discovery)
    - cron: '0 14 * * 0'     # Sunday 10AM EST (upstream sync)
  workflow_dispatch:
    inputs:
      mode:
        description: 'Run mode'
        required: true
        default: 'discover'
        type: choice
        options:
          - discover
          - sync
          - report
          - force-adopt

env:
  SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
  SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
  GITHUB_PAT: ${{ secrets.GH_PAT4 }}
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}

jobs:
  scout:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install deps
        run: pip install httpx beautifulsoup4 supabase pyyaml click
      
      - name: Run Skills Scout
        run: python -m cli_anything.skills_scout.main --mode ${{ github.event.inputs.mode || (github.event.schedule == '0 14 * * 0' && 'sync') || 'discover' }}
      
      - name: Push adopted skills
        run: |
          git config user.name "skills-scout[bot]"
          git config user.email "skills-scout@biddeed.ai"
          git add -A
          git diff --staged --quiet || git commit -m "feat(skills): auto-adopt $(date +%Y-%m-%d)"
          git push
        env:
          GITHUB_TOKEN: ${{ secrets.GH_PAT4 }}
```

## STEP 13: VERIFY & FIRST RUN

1. Merge `feat/skills-scout` → `main`
2. Trigger `workflow_dispatch` with mode=`discover`
3. Watch GitHub Actions log
4. Verify Telegram notification received
5. Verify `skills_library` table populated in Supabase
6. Verify `.claude/skills/` directories created in target repos

## DONE CRITERIA
- [ ] 3 Supabase tables created with RLS
- [ ] All 8 Python modules built
- [ ] All tests passing
- [ ] GitHub Actions workflow deployed
- [ ] First discovery run completes
- [ ] Telegram notification sent with results
- [ ] At least 5 skills auto-adopted to target repos
- [ ] TODO.md updated with [x] marks
