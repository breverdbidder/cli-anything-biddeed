# Dream Skill — Summit Dispatch Playbook

## Files Created

```yaml
deployment:
  SKILL.md: The Dream skill (goes to .claude/skills/dream/SKILL.md in each repo)
  deploy-dream-skill.sh: Deployment script (goes to cli-anything-biddeed/scripts/)
  deploy-dream.yml: GHA workflow (goes to cli-anything-biddeed/.github/workflows/)
  dream-health-check.sh: Sentinel patrol (goes to cli-anything-biddeed/scripts/)
  CLAUDEMD_PATCH.md: Session Hygiene addition for CLAUDE.md (apply manually or via Claude Code)

target_repos:
  - brevard-bidder-scraper
  - cli-anything-biddeed
  - biddeed-ai
  - zonewise-web
  - everest-nexus
```

## Summit Dispatch — One-Liner

SSH into Hetzner and run Claude Code to deploy:

```bash
# Option A: Direct deploy via script (fastest)
ssh claude@87.99.129.125 'cd ~/cli-anything-biddeed && \
  export GITHUB_TOKEN=$(cat /home/claude/.github_pat4) && \
  bash scripts/deploy-dream-skill.sh'

# Option B: Trigger GHA workflow (Summit pattern)
ssh claude@87.99.129.125 'curl -s -X POST \
  -H "Authorization: token $(cat /home/claude/.github_pat4)" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/deploy-dream.yml/dispatches" \
  -d '"'"'{"ref":"main","inputs":{"repos":"all"}}'"'"''

# Option C: Claude Code session (full autonomy)
ssh claude@87.99.129.125 'cd ~/cli-anything-biddeed && \
  claude --auto "Deploy Dream skill to all 5 repos. Files in /tmp/dream-skill/. \
  1) Copy deploy-dream-skill.sh to scripts/ \
  2) Copy deploy-dream.yml to .github/workflows/ \
  3) Copy dream-health-check.sh to scripts/ \
  4) Run deploy-dream-skill.sh \
  5) Patch CLAUDE.md Session Hygiene in all repos with Dream section \
  6) Add dream-health-check.sh to weekly-health.yml"'
```

## Sentinel Integration

Add to `sentinel-patrol.sh`:

```bash
# Dream skill health check
echo "--- Dream Skill ---"
bash scripts/dream-health-check.sh || FAILURES=$((FAILURES+1))
```

Add to `weekly-health.yml` jobs:

```yaml
  dream-health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check Dream Skill
        env:
          GITHUB_TOKEN: ${{ secrets.PAT4 }}
        run: bash scripts/dream-health-check.sh
```

## Post-Deploy Verification

```bash
# Verify all repos have the skill
for REPO in brevard-bidder-scraper cli-anything-biddeed biddeed-ai zonewise-web everest-nexus; do
  echo -n "$REPO: "
  curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: token $(cat /home/claude/.github_pat4)" \
    "https://api.github.com/repos/breverdbidder/${REPO}/contents/.claude/skills/dream/SKILL.md?ref=main"
  echo ""
done
```
