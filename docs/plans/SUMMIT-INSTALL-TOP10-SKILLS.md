# SUMMIT: Install Top 10 Skills — All Environments

## MISSION
Install the 10 assessed+approved skills across ALL BidDeed.AI repos AND configure for GitHub Actions, Hetzner CLI, and Claude Cowork. Zero human interaction after dispatch.

## CRITICAL RULES
- $10/session MAX. Batch operations.
- GitHub PAT4: `${{ secrets.GH_PAT4 }}`
- Do NOT use paid Claude API. This is pure git + npx operations.
- Every install MUST be verified with `ls -la .claude/skills/` after completion.
- Commit each repo separately with descriptive message.

---

## STEP 1: Install npx skills CLI

```bash
npm install -g skills
```

---

## STEP 2: Clone ALL target repos to workspace

```bash
mkdir -p ~/skills-install && cd ~/skills-install

REPOS=(
  cli-anything-biddeed
  biddeed-ai
  biddeed-ai-ui
  zonewise-web
  zonewise-scraper-v4
  brevard-bidder-scraper
  ai-tools-library
  tax-insurance-optimizer
  context-boot-mcp-server
  superpowers
)

for repo in "${REPOS[@]}"; do
  git clone "https://x-access-token:${{ secrets.GH_PAT4 }}@github.com/breverdbidder/${repo}.git" || true
done
```

---

## STEP 3: Install skills per repo

### 3A: cli-anything-biddeed (Agent HQ — gets 6 skills)
```bash
cd ~/skills-install/cli-anything-biddeed

npx skills add obra/superpowers -a claude-code \
  --skill dispatching-parallel-agents \
  --skill systematic-debugging \
  --skill subagent-driven-development \
  --skill test-driven-development

# Verify
ls -la .claude/skills/
```

### 3B: biddeed-ai (Core platform — gets 3 skills)
```bash
cd ~/skills-install/biddeed-ai

npx skills add supabase/agent-skills -a claude-code \
  --skill supabase-postgres-best-practices

npx skills add obra/superpowers -a claude-code \
  --skill systematic-debugging \
  --skill subagent-driven-development

ls -la .claude/skills/
```

### 3C: biddeed-ai-ui (Frontend — gets 3 skills)
```bash
cd ~/skills-install/biddeed-ai-ui

npx skills add vercel-labs/agent-skills -a claude-code \
  --skill vercel-react-best-practices

npx skills add coreyhaines31/marketingskills -a claude-code \
  --skill seo-audit

ls -la .claude/skills/
```

### 3D: zonewise-web (Frontend — gets 3 skills)
```bash
cd ~/skills-install/zonewise-web

npx skills add vercel-labs/agent-skills -a claude-code \
  --skill vercel-react-best-practices

npx skills add coreyhaines31/marketingskills -a claude-code \
  --skill seo-audit \
  --skill programmatic-seo

ls -la .claude/skills/
```

### 3E: zonewise-scraper-v4 (Scraping — gets 3 skills)
```bash
cd ~/skills-install/zonewise-scraper-v4

npx skills add firecrawl/cli -a claude-code \
  --skill firecrawl

npx skills add browser-use/browser-use -a claude-code \
  --skill browser-use

npx skills add obra/superpowers -a claude-code \
  --skill systematic-debugging

ls -la .claude/skills/
```

### 3F: brevard-bidder-scraper (Legacy scraper — gets 3 skills)
```bash
cd ~/skills-install/brevard-bidder-scraper

npx skills add firecrawl/cli -a claude-code \
  --skill firecrawl

npx skills add browser-use/browser-use -a claude-code \
  --skill browser-use

npx skills add obra/superpowers -a claude-code \
  --skill systematic-debugging

ls -la .claude/skills/
```

### 3G: ai-tools-library (SQL/Data — gets 2 skills)
```bash
cd ~/skills-install/ai-tools-library

npx skills add supabase/agent-skills -a claude-code \
  --skill supabase-postgres-best-practices

npx skills add obra/superpowers -a claude-code \
  --skill systematic-debugging

ls -la .claude/skills/
```

### 3H: tax-insurance-optimizer (Life OS — gets 2 skills)
```bash
cd ~/skills-install/tax-insurance-optimizer

npx skills add supabase/agent-skills -a claude-code \
  --skill supabase-postgres-best-practices

npx skills add obra/superpowers -a claude-code \
  --skill systematic-debugging

ls -la .claude/skills/
```

### 3I: context-boot-mcp-server (MCP — gets 2 skills)
```bash
cd ~/skills-install/context-boot-mcp-server

npx skills add obra/superpowers -a claude-code \
  --skill systematic-debugging \
  --skill subagent-driven-development

ls -la .claude/skills/
```

---

## STEP 4: Commit and push ALL repos

```bash
cd ~/skills-install

for repo in "${REPOS[@]}"; do
  cd ~/skills-install/${repo}
  git add -A
  if ! git diff --staged --quiet; then
    git config user.name "skills-scout[bot]"
    git config user.email "skills-scout@biddeed.ai"
    git commit -m "feat(skills): install top-10 assessed skills from skills.sh

Skills adopted per Agent 17 assessment (score 83-98, all ADOPT):
- supabase-postgres-best-practices (98)
- dispatching-parallel-agents (97)
- systematic-debugging (95)
- firecrawl (94)
- browser-use (92)
- vercel-react-best-practices (90)
- subagent-driven-development (89)
- test-driven-development (88)
- seo-audit (85)
- programmatic-seo (83)

Ref: docs/assessments/agent-17-skills-scout-assessment.docx"
    git push origin main
    echo "✅ Pushed: ${repo}"
  else
    echo "⏭️  No changes: ${repo}"
  fi
done
```

---

## STEP 5: Configure Hetzner Claude CLI global skills

Skills installed in repos are per-project. For Hetzner global availability:

```bash
# Global skills directory for Claude Code on Hetzner
mkdir -p ~/.claude/skills

# Symlink the most-used skills globally so they load in ANY project
GLOBAL_SKILLS=(
  systematic-debugging
  dispatching-parallel-agents
  subagent-driven-development
  test-driven-development
  supabase-postgres-best-practices
)

for skill in "${GLOBAL_SKILLS[@]}"; do
  # Copy from cli-anything-biddeed (HQ) to global
  cp -r ~/skills-install/cli-anything-biddeed/.claude/skills/${skill} \
    ~/.claude/skills/${skill} 2>/dev/null || \
  echo "⚠️ ${skill} not found in HQ, will be available per-project only"
done

echo "✅ Global skills installed at ~/.claude/skills/"
ls -la ~/.claude/skills/
```

---

## STEP 6: Configure Claude Cowork skills

Cowork reads from the same `.claude/skills/` directories. When Ariel opens Cowork and points it at any BidDeed repo folder, the skills are already there.

Additionally, set up Cowork global skills on Ariel's Mac:

```bash
# Cowork uses same path as Claude Code
# On Ariel's Mac (via remote or manual):
COWORK_SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$COWORK_SKILLS_DIR"

# These 5 core skills should be globally available in Cowork
# Copy SKILL.md files from any installed repo
for skill in systematic-debugging dispatching-parallel-agents subagent-driven-development test-driven-development supabase-postgres-best-practices; do
  mkdir -p "${COWORK_SKILLS_DIR}/${skill}"
  # Pull directly from GitHub
  curl -sL "https://raw.githubusercontent.com/breverdbidder/cli-anything-biddeed/main/.claude/skills/${skill}/SKILL.md" \
    -o "${COWORK_SKILLS_DIR}/${skill}/SKILL.md"
  echo "✅ Cowork global: ${skill}"
done
```

For Cowork to pick up project-specific skills (like firecrawl in zonewise-scraper-v4), Ariel just points Cowork at that repo folder — it auto-discovers `.claude/skills/`.

---

## STEP 7: Configure GitHub Actions access

GitHub Actions runners clone the repo including `.claude/skills/`. No extra config needed — skills are committed to the repos and travel with them.

For workflows that spin up Claude Code (like AgentRemote), the skills are available because they're in the repo's `.claude/skills/` directory.

Verify by checking any GitHub Actions run:

```bash
# In any workflow step:
ls -la .claude/skills/
# Should list the installed skills for that repo
```

---

## STEP 8: Verification matrix

After all installs, verify this matrix:

| Repo | Skills Count | Verify Command |
|---|---|---|
| cli-anything-biddeed | 4 | `ls .claude/skills/` → dispatching-parallel-agents, systematic-debugging, subagent-driven-development, test-driven-development |
| biddeed-ai | 3 | `ls .claude/skills/` → supabase-postgres-best-practices, systematic-debugging, subagent-driven-development |
| biddeed-ai-ui | 2 | `ls .claude/skills/` → vercel-react-best-practices, seo-audit |
| zonewise-web | 3 | `ls .claude/skills/` → vercel-react-best-practices, seo-audit, programmatic-seo |
| zonewise-scraper-v4 | 3 | `ls .claude/skills/` → firecrawl, browser-use, systematic-debugging |
| brevard-bidder-scraper | 3 | `ls .claude/skills/` → firecrawl, browser-use, systematic-debugging |
| ai-tools-library | 2 | `ls .claude/skills/` → supabase-postgres-best-practices, systematic-debugging |
| tax-insurance-optimizer | 2 | `ls .claude/skills/` → supabase-postgres-best-practices, systematic-debugging |
| context-boot-mcp-server | 2 | `ls .claude/skills/` → systematic-debugging, subagent-driven-development |
| Hetzner global | 5 | `ls ~/.claude/skills/` → 5 core skills |
| **TOTAL** | **29 skill installs across 10 repos + global** | |

If ANY verification fails, log to Supabase insights table and report in Telegram.

---

## STEP 9: Telegram notification

After all installs complete, send:

```
✅ SKILLS INSTALLED — Mar 12, 2026

📦 10 repos updated
🔧 29 skill installs total
🌐 5 global skills on Hetzner
🖥️ Cowork global skills configured
⚡ GitHub Actions: auto-available

TOP 10 SKILLS LIVE:
1. supabase-postgres (98) → 3 repos
2. dispatching-parallel-agents (97) → 1 repo + global
3. systematic-debugging (95) → 7 repos + global
4. firecrawl (94) → 2 repos
5. browser-use (92) → 2 repos
6. vercel-react-best-practices (90) → 2 repos
7. subagent-driven-development (89) → 3 repos + global
8. test-driven-development (88) → 1 repo + global
9. seo-audit (85) → 2 repos
10. programmatic-seo (83) → 1 repo

💰 Cost: $0.00

Next: skills-scout agent will auto-discover new skills daily.
```

---

## DONE CRITERIA
- [ ] All 10 repos cloned
- [ ] All skills installed (29 total installs)
- [ ] All repos committed and pushed
- [ ] Hetzner global ~/.claude/skills/ populated (5 skills)
- [ ] Cowork global skills configured
- [ ] Verification matrix passes (ls check on each repo)
- [ ] Telegram notification sent
- [ ] Zero errors in install log
