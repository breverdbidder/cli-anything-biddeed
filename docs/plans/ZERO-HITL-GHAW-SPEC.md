# ZERO-HITL: gh-aw + SUMMIT Integration

## Handoff: Claude AI Architect → Claude Code
**Date:** 2026-03-23
**Priority:** P0
**Estimated Sessions:** 3 (S1 immediate, S2 next day, S3 day after)
**Human Involvement Required:** ZERO

---

## VERIFIED STATE (as of 2026-03-23 10:00 EST)

### ANTHROPIC_API_KEY Status
```yaml
brevard-bidder-scraper:  FOUND  # updated 2026-02-27
cli-anything-biddeed:    FOUND
biddeed-ai:              MISSING  # ACTION: copy from env
zonewise-web:            FOUND
zonewise-scraper-v4:     FOUND
everest-nexus:           MISSING  # ACTION: copy from env
```

### GH_PAT Status
```yaml
brevard-bidder-scraper:  FOUND  # updated 2026-03-11
cli-anything-biddeed:    FOUND
biddeed-ai:              FOUND
zonewise-web:            MISSING  # ACTION: copy from env
zonewise-scraper-v4:     FOUND
everest-nexus:           FOUND
```

### CLAUDE_OAUTH_B64 Status
```yaml
cli-anything-biddeed:    FOUND
zonewise-web:            FOUND
everest-nexus:           FOUND
# Others use ANTHROPIC_API_KEY directly
```

### Infrastructure
```yaml
gh-aw-version:     v0.62.5  # released 2026-03-21
hetzner-ip:        87.99.129.125
sentinel-status:   HEALTHY  # last success 2026-03-23T09:42:06Z
gha-runner:        GitHub-hosted (ubuntu-latest)
pat4:              $GH_PAT (repo secret, classic, no expiry)
```

---

## SESSION 1: Foundation (Immediate)

### S1.1 — Fix Missing Secrets
```bash
# On Hetzner (via SSH-action or direct), read ANTHROPIC_API_KEY from env
# Then set on missing repos using gh CLI

# biddeed-ai
gh secret set ANTHROPIC_API_KEY --repo breverdbidder/biddeed-ai --body "$ANTHROPIC_API_KEY"

# everest-nexus
gh secret set ANTHROPIC_API_KEY --repo breverdbidder/everest-nexus --body "$ANTHROPIC_API_KEY"

# zonewise-web (missing GH_PAT)
gh secret set GH_PAT --repo breverdbidder/zonewise-web --body "$GH_PAT"
```
**Verify:** `gh secret list --repo breverdbidder/<repo>` confirms all 3.

### S1.2 — Install gh-aw CLI on Hetzner
```bash
gh extension install github/gh-aw
gh aw --version  # expect v0.62.5+
```

### S1.3 — Deploy Sentinel Noise Filter
Edit `cli-anything-biddeed/scripts/sentinel.sh`:
```
# CHANGE: Only send Telegram for ESCALATION events (3x retry exhausted)
# SUPPRESS: successful auto-heals, false positives (0 commits), info-level
# Add filter function:
should_alert() {
  local event_type="$1"
  case "$event_type" in
    escalation|oauth_expired|critical_failure) return 0 ;;  # ALERT
    *) return 1 ;;  # SUPPRESS
  esac
}
```
**Verify:** Trigger a non-critical event, confirm no Telegram. Trigger escalation, confirm Telegram fires.

### S1.4 — Deploy Core gh-aw Workflows (3 workflows × 6 repos)

#### Workflow 1: Continuous Doc Sync
Create `.github/workflows/doc-sync-agent.md` in each repo:
```markdown
---
engine: claude
on:
  push:
    branches: [main]
    paths:
      - "src/**"
      - "scripts/**"
      - "*.py"
      - "*.js"
      - "*.ts"
permissions:
  contents: read
  pull-requests: read
safe-outputs:
  create-pull-request:
    title-prefix: "[docs] "
    labels: [documentation, auto-generated]
    auto-merge: true
---

## Continuous Documentation Sync

When code changes are pushed, review and update documentation to stay in sync.

### What to check
- README.md accuracy vs current code
- CLAUDE.md directives match actual pipeline behavior
- SKILL.md files reflect current capabilities
- API docs match function signatures
- Inline code comments for complex logic

### Rules
- Only open a PR if changes are needed
- Keep changes minimal and focused
- Preserve existing formatting and style
- Never modify code files, only documentation
- If unsure about a change, skip it
```

Then compile:
```bash
cd /path/to/repo
gh aw compile .github/workflows/doc-sync-agent.md
git add .github/workflows/doc-sync-agent.md .github/workflows/doc-sync-agent.lock.yml
git commit -m "feat: add gh-aw continuous doc sync agent"
git push
```

#### Workflow 2: Issue Auto-Triage
Create `.github/workflows/issue-triage-agent.md`:
```markdown
---
engine: claude
on:
  issues:
    types: [opened, reopened]
permissions:
  contents: read
  issues: read
safe-outputs:
  add-labels:
    allowed-labels:
      - bug
      - feature
      - question
      - documentation
      - P0-critical
      - P1-high
      - P2-medium
      - P3-low
  add-comment:
    max-comments: 1
---

## Issue Triage Agent

Analyze new issues and apply appropriate labels.

### Label Rules
- P0-critical: Security vulnerabilities, data loss, production down
- P1-high: Broken core functionality, blocking workflows
- P2-medium: Non-blocking bugs, performance issues
- P3-low: Nice-to-haves, cosmetic issues
- bug/feature/question/documentation: Type classification

### Process
1. Read the issue title and body
2. Check for duplicates in recent issues
3. Apply priority label (P0-P3)
4. Apply type label (bug/feature/question/documentation)
5. Add a brief comment explaining the triage decision

### Rules
- Be concise in comments (2-3 sentences max)
- If unclear, label as P2-medium and question
- Never close issues automatically
- For P0-critical, also mention @breverdbidder in comment
```

#### Workflow 3: CI Failure Analyzer
Create `.github/workflows/ci-failure-agent.md`:
```markdown
---
engine: claude
on:
  workflow_run:
    workflows: ["*"]
    types: [completed]
    conclusions: [failure]
permissions:
  contents: read
  issues: read
  actions: read
safe-outputs:
  create-issue:
    title-prefix: "[ci-fix] "
    labels: [ci-failure, auto-diagnosed]
    close-older-issues: true
---

## CI Failure Analyzer

When a CI workflow fails, diagnose the root cause and create an issue with the proposed fix.

### Process
1. Read the failed workflow logs
2. Identify the root cause (test failure, dependency issue, build error, timeout, flaky test)
3. Create an issue with:
   - Summary of what failed
   - Root cause analysis
   - Proposed fix (with code snippets if applicable)
   - Link to the failed run

### Rules
- Don't create issues for known flaky tests (check if similar issue exists)
- Include the exact error message
- If the fix is obvious (typo, missing dep), include the exact fix
- If complex, describe the investigation path
- Never propose fixes you're not confident about
```

**Deploy to all 6 repos:**
```bash
REPOS="brevard-bidder-scraper cli-anything-biddeed biddeed-ai zonewise-web zonewise-scraper-v4 everest-nexus"
for repo in $REPOS; do
  cd /home/claude/$repo  # or clone if needed
  # Copy workflow files
  # gh aw compile each
  # git add, commit, push
done
```

**Verify each:** `gh aw status --repo breverdbidder/<repo>` shows 3 workflows registered.

---

## SESSION 2: Auto-Merge + Digest Upgrade

### S2.1 — PR Auto-Merge Gate
Create `.github/workflows/pr-gate-agent.md` in all 6 repos:
```markdown
---
engine: claude
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: read
safe-outputs:
  add-labels:
    allowed-labels:
      - auto-merge-low
      - auto-merge-medium
      - needs-human-review
  add-comment:
    max-comments: 1
---

## PR Risk Classification Gate

Classify PRs by risk level and apply merge strategy.

### Risk Tiers
- LOW (auto-merge): Only docs, deps (patch), style, comments, tests, CI config
- MEDIUM (merge after CI): Non-critical code changes, refactors, non-domain logic
- HIGH (human review): Domain logic (auction/zoning/scraping), security, DB schema, auth, secrets, API contracts

### Process
1. Review changed files and diff
2. Classify risk tier
3. Apply label: auto-merge-low, auto-merge-medium, or needs-human-review
4. Comment with 1-line risk explanation

### Rules
- When in doubt, classify higher (MEDIUM over LOW, HIGH over MEDIUM)
- Any change to .env, secrets, auth, or DB migrations = always HIGH
- Changes to CLAUDE.md or .claude/rules/ = MEDIUM minimum
```

Then configure branch protection to auto-merge on `auto-merge-low` label:
```bash
# Enable auto-merge for repos
gh api repos/breverdbidder/<repo>/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["BidDeed-CI"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews=null
```

### S2.2 — Nexus Digest v2
Update `everest-nexus` digest workflow to absorb:
- gh-aw workflow run results (query GHA API for `doc-sync-agent`, `issue-triage-agent`, `ci-failure-agent`, `pr-gate-agent` runs)
- Sentinel status (query `sentinel_runs` table, only show escalations)
- ZoneWise `county_conquest_status` deltas
- Auction pipeline status

Modify the existing 9AM/5PM digest Supabase function or GHA workflow to include a new section:
```
## Automation Health
- Doc Sync: X PRs merged, Y pending
- Issue Triage: X issues labeled today
- CI Failures: X diagnosed, Y fix PRs open
- PR Gate: X auto-merged, Y awaiting review
- Sentinel: All clear / [ESCALATION details]
```

**Verify:** Trigger manual digest, confirm new sections appear.

---

## SESSION 3: Remaining Workflows + Soak Test

### S3.1 — Dependency Guardian
Create `.github/workflows/dep-guardian-agent.md` (all 6 repos):
```markdown
---
engine: claude
on:
  schedule:
    - cron: "0 8 * * 1"  # Monday 8AM UTC (3AM EST)
permissions:
  contents: read
safe-outputs:
  create-pull-request:
    title-prefix: "[deps] "
    labels: [dependencies, auto-generated]
    auto-merge: true
---

## Weekly Dependency Guardian

Check for outdated or vulnerable dependencies and open update PRs.

### Process
1. Check package.json / requirements.txt for outdated packages
2. Check for known security advisories (npm audit / pip-audit)
3. For patch updates: open PR with auto-merge
4. For minor/major: open PR labeled needs-human-review
5. Include changelog summary for each update

### Rules
- Never update multiple major versions in one PR
- Security patches always get their own PR
- Include the advisory ID for security updates
- Test that lockfile resolves correctly
```

### S3.2 — Changelog Automation
Create `.github/workflows/changelog-agent.md` (all 6 repos):
```markdown
---
engine: claude
on:
  release:
    types: [published]
permissions:
  contents: read
safe-outputs:
  create-pull-request:
    title-prefix: "[changelog] "
    labels: [changelog, auto-generated]
    auto-merge: true
---

## Release Changelog Generator

Generate changelog entries from commits since the last release.

### Process
1. Get commits between current and previous release tag
2. Categorize: Features, Fixes, Docs, Refactors, CI/Ops
3. Write concise changelog entry
4. Update CHANGELOG.md (prepend new entry)
5. Open PR with the update

### Style
- Use conventional commit prefixes
- Link to PRs where available
- Keep entries to one line each
- Group by category
```

### S3.3 — Validation Checklist
After all workflows deployed, run full system check:

```bash
# 1. Verify all workflows compiled
for repo in $REPOS; do
  echo "=== $repo ==="
  gh aw status --repo breverdbidder/$repo
done

# 2. Verify secrets
for repo in $REPOS; do
  echo "=== $repo ==="
  gh secret list --repo breverdbidder/$repo | grep -E "ANTHROPIC|GH_PAT"
done

# 3. Trigger test runs
for repo in $REPOS; do
  gh aw run doc-sync-agent --repo breverdbidder/$repo
done

# 4. Check Sentinel still healthy
curl -s "https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1/sentinel_runs?order=created_at.desc&limit=1" \
  -H "apikey: $SUPABASE_ANON_KEY" | jq '.[] | {status, created_at}'

# 5. Verify Telegram noise filter (should NOT fire for test runs)
# Check Telegram bot - expect silence for non-escalation events
```

### S3.4 — Update CLAUDE.md in All Repos
Add to CLAUDE.md in each repo:
```markdown
## gh-aw Integration (Mar 23, 2026)

### Active Agentic Workflows
- `doc-sync-agent.md` — Auto-updates docs on code push (auto-merge)
- `issue-triage-agent.md` — Labels new issues P0-P3 + type
- `ci-failure-agent.md` — Diagnoses CI failures, opens fix issues
- `pr-gate-agent.md` — Classifies PR risk: LOW/MEDIUM/HIGH
- `dep-guardian-agent.md` — Weekly dependency updates (Monday 3AM EST)
- `changelog-agent.md` — Auto-changelog on release

### Merge Strategy
- LOW risk: auto-merge (docs, deps patch, style, tests)
- MEDIUM risk: merge after CI green
- HIGH risk: needs-human-review label → Ariel reviews

### Engine
All workflows use `engine: claude` with ANTHROPIC_API_KEY secret.
```

### S3.5 — Update Memory Edits
After full deployment verified, update memory with exact state.

---

## SUCCESS CRITERIA

```yaml
secrets_complete:
  - ANTHROPIC_API_KEY in all 6 repos
  - GH_PAT in all 6 repos
  
workflows_deployed:
  - doc-sync-agent: 6 repos, compiled, test run passed
  - issue-triage-agent: 6 repos, compiled, test run passed
  - ci-failure-agent: 6 repos, compiled, test run passed
  - pr-gate-agent: 6 repos, compiled, test run passed
  - dep-guardian-agent: 6 repos, compiled, test run passed
  - changelog-agent: 6 repos, compiled, test run passed
  
sentinel_updated:
  - Noise filter active (only escalation alerts)
  - Test: non-critical event → no Telegram
  - Test: escalation event → Telegram fires

nexus_digest_v2:
  - Automation Health section in 9AM/5PM digest
  - Shows gh-aw run results + sentinel status

claude_md_updated:
  - All 6 repos have gh-aw section
  
ariel_daily_time:
  - Target: ≤3 minutes (digest scan + rare HIGH PR)
  - Measured: track for 1 week post-deployment
```

---

## ESCALATION (only if needed)
If any of these fail after 3 retries, log to Supabase `insights` table and include in next Nexus digest. Do NOT notify Ariel via Telegram unless it's a secret/auth issue requiring dashboard access.

---

## DISPATCH COMMAND
```bash
# Summit dispatch to Claude Code on Hetzner
# Session 1: Foundation (S1.1-S1.4)
# Estimated: 2-3 hours
# Auto-mode: enabled
# Context: this spec file
```
