#!/usr/bin/env bash
# dream-health-check.sh — Sentinel patrol for Dream skill presence
# Add to sentinel-patrol.sh or run standalone in weekly-health.yml

set -euo pipefail

GITHUB_TOKEN="${GITHUB_TOKEN:-$PAT4}"
OWNER="breverdbidder"
SKILL_PATH=".claude/skills/dream/SKILL.md"

REPOS=(
  "brevard-bidder-scraper"
  "cli-anything-biddeed"
  "biddeed-ai"
  "zonewise-web"
  "everest-nexus"
)

echo "=== Dream Skill Health Check ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

HEALTHY=0
MISSING=0
REPORT=""

for REPO in "${REPOS[@]}"; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/${OWNER}/${REPO}/contents/${SKILL_PATH}?ref=main" 2>/dev/null)
  
  if [ "$HTTP_CODE" = "200" ]; then
    REPORT="${REPORT}✅ ${REPO}\n"
    ((HEALTHY++))
  else
    REPORT="${REPORT}❌ ${REPO} (HTTP ${HTTP_CODE})\n"
    ((MISSING++))
  fi
done

echo -e "$REPORT"
echo "Healthy: ${HEALTHY}/${#REPOS[@]}"

if [ "$MISSING" -gt 0 ]; then
  echo "⚠️ DRIFT DETECTED: ${MISSING} repos missing Dream skill"
  # Sentinel auto-repair: re-deploy to missing repos
  if [ "${AUTO_REPAIR:-false}" = "true" ]; then
    echo "🔧 Auto-repair enabled — triggering re-deploy..."
    # Trigger the deploy workflow
    curl -s -X POST \
      -H "Authorization: token ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github.v3+json" \
      "https://api.github.com/repos/${OWNER}/cli-anything-biddeed/actions/workflows/deploy-dream.yml/dispatches" \
      -d '{"ref":"main","inputs":{"repos":"all"}}' || echo "Failed to trigger re-deploy"
  fi
  exit 1
fi

echo "✅ Dream skill healthy across all repos"
