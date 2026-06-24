#!/usr/bin/env bash
# repoeval_gates.sh — REPOEVAL batch evaluation gate
# Usage: repoeval_gates.sh <github_url> [<clone_dir>]
# Output: JSON to stdout with license, stars, LOC, and tier
# Exit: 0=success, 1=clone_failed, 2=repo_not_found
set -euo pipefail

REPO_URL="${1:?Usage: repoeval_gates.sh <github_url>}"
CLONE_BASE="${REPOEVAL_TMP:-/tmp/repoeval}"
REPO_SLUG=$(echo "$REPO_URL" | sed 's|https://github.com/||' | tr '/' '-')
LOCAL_PATH="${2:-$CLONE_BASE/$REPO_SLUG}"

mkdir -p "$CLONE_BASE"

# ── 1. Clone ──────────────────────────────────────────────────────────────────
if [ ! -d "$LOCAL_PATH/.git" ]; then
  git clone --depth 1 --quiet "$REPO_URL" "$LOCAL_PATH" 2>/tmp/repoeval_clone.log \
    || { echo "{\"error\":\"CLONE_FAILED\",\"url\":\"$REPO_URL\",\"log\":\"$(cat /tmp/repoeval_clone.log | head -3 | tr '\n' ' ')\"}" ; exit 1; }
fi

# ── 2. GitHub API stats ───────────────────────────────────────────────────────
API_SLUG=$(echo "$REPO_URL" | sed 's|https://github.com/||')
GH_HEADERS=(-H "Accept: application/vnd.github+json")
if [ -n "${GH_TOKEN:-}" ]; then
  GH_HEADERS+=(-H "Authorization: Bearer $GH_TOKEN")
fi
GH_META=$(curl -sf "${GH_HEADERS[@]}" "https://api.github.com/repos/$API_SLUG" 2>/dev/null || echo '{}')
STARS=$(echo "$GH_META" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('stargazers_count',0))" 2>/dev/null || echo 0)
FORKS=$(echo "$GH_META" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('forks_count',0))" 2>/dev/null || echo 0)
LAST_PUSH=$(echo "$GH_META" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('pushed_at','unknown'))" 2>/dev/null || echo "unknown")
DEFAULT_BRANCH=$(echo "$GH_META" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('default_branch','main'))" 2>/dev/null || echo "main")
GH_LICENSE=$(echo "$GH_META" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('license',{}) and d['license'].get('spdx_id','NONE') or 'NONE')" 2>/dev/null || echo "NONE")

# ── 3. License detection (5-tier) ─────────────────────────────────────────────
LICENSE_SPDX="$GH_LICENSE"
LICENSE_CONFIDENCE=0.90
LICENSE_DETECTOR="github_api"

# Verify/override from repo file
for f in LICENSE LICENSE.md LICENSE.txt LICENSE.rst COPYING COPYING.md; do
  if [ -f "$LOCAL_PATH/$f" ]; then
    CONTENT=$(head -5 "$LOCAL_PATH/$f" 2>/dev/null | tr '[:upper:]' '[:lower:]')
    if echo "$CONTENT" | grep -q "mit license\|permission is hereby granted"; then
      LICENSE_SPDX="MIT"; LICENSE_CONFIDENCE=0.98; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "apache license\|apache-2.0"; then
      LICENSE_SPDX="Apache-2.0"; LICENSE_CONFIDENCE=0.98; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "bsd 3-clause\|redistribution and use in source and binary"; then
      LICENSE_SPDX="BSD-3-Clause"; LICENSE_CONFIDENCE=0.95; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "bsd 2-clause"; then
      LICENSE_SPDX="BSD-2-Clause"; LICENSE_CONFIDENCE=0.95; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "gnu general public license.*version 3\|gpl.*v3"; then
      LICENSE_SPDX="GPL-3.0"; LICENSE_CONFIDENCE=0.95; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "gnu general public license.*version 2\|gpl.*v2"; then
      LICENSE_SPDX="GPL-2.0"; LICENSE_CONFIDENCE=0.95; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "gnu lesser general public\|lgpl"; then
      LICENSE_SPDX="LGPL-2.1"; LICENSE_CONFIDENCE=0.90; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "mozilla public license"; then
      LICENSE_SPDX="MPL-2.0"; LICENSE_CONFIDENCE=0.90; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "creative commons.*attribution.*4.0"; then
      LICENSE_SPDX="CC-BY-4.0"; LICENSE_CONFIDENCE=0.90; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "unlicense\|public domain"; then
      LICENSE_SPDX="Unlicense"; LICENSE_CONFIDENCE=0.90; LICENSE_DETECTOR="file_content"; break
    elif echo "$CONTENT" | grep -q "agpl\|affero"; then
      LICENSE_SPDX="AGPL-3.0"; LICENSE_CONFIDENCE=0.90; LICENSE_DETECTOR="file_content"; break
    fi
    LICENSE_DETECTOR="file_present_unrecognized"
    LICENSE_CONFIDENCE=0.50
    break
  fi
done

if [ "$LICENSE_SPDX" = "NONE" ] || [ "$LICENSE_SPDX" = "NOASSERTION" ]; then
  # Check package manifests
  if [ -f "$LOCAL_PATH/package.json" ]; then
    PKG_LIC=$(python3 -c "import json; d=json.load(open('$LOCAL_PATH/package.json')); print(d.get('license','NONE'))" 2>/dev/null || echo "NONE")
    if [ "$PKG_LIC" != "NONE" ] && [ "$PKG_LIC" != "null" ]; then
      LICENSE_SPDX="$PKG_LIC"; LICENSE_CONFIDENCE=0.80; LICENSE_DETECTOR="package_json"
    fi
  fi
fi

# Tier assignment
case "$LICENSE_SPDX" in
  MIT|Apache-2.0|BSD-3-Clause|BSD-2-Clause|Unlicense|CC0-1.0|ISC|"0BSD")
    TIER=4; TIER_NAME="PERMISSIVE_FREE" ;;
  LGPL-2.1|LGPL-3.0|MPL-2.0|EUPL-1.2)
    TIER=2; TIER_NAME="WEAK_COPYLEFT" ;;
  GPL-2.0|GPL-3.0|AGPL-3.0)
    TIER=1; TIER_NAME="COPYLEFT" ;;
  CC-BY-4.0|CC-BY-SA-4.0|CC-BY-3.0)
    TIER=3; TIER_NAME="ATTRIBUTION_REQUIRED" ;;
  NONE|NOASSERTION|"")
    TIER=0; TIER_NAME="REFERENCE_ONLY" ;;
  *)
    TIER=0; TIER_NAME="REFERENCE_ONLY" ;;
esac

# ── 4. LOC count ──────────────────────────────────────────────────────────────
LOC=$(find "$LOCAL_PATH" \
  \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.tsx" \
     -o -name "*.go" -o -name "*.rs" -o -name "*.java" -o -name "*.sh" \
     -o -name "*.rb" -o -name "*.swift" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" ! -path "*/vendor/*" \
  -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)

# ── 5. Skill / SKILL.md detection ─────────────────────────────────────────────
SKILL_MD_COUNT=$(find "$LOCAL_PATH" -name "SKILL.md" ! -path "*/.git/*" 2>/dev/null | wc -l)
HAS_CLAUDE_MD=$([ -f "$LOCAL_PATH/CLAUDE.md" ] && echo "true" || echo "false")
HAS_AGENTS_MD=$([ -f "$LOCAL_PATH/AGENTS.md" ] && echo "true" || echo "false")

# ── 6. Output JSON ────────────────────────────────────────────────────────────
python3 - <<PYEOF
import json
print(json.dumps({
    "url": "$REPO_URL",
    "slug": "$API_SLUG",
    "local_path": "$LOCAL_PATH",
    "license_spdx": "$LICENSE_SPDX",
    "license_confidence": float("${LICENSE_CONFIDENCE}"),
    "license_detector": "$LICENSE_DETECTOR",
    "tier": int("$TIER"),
    "tier_name": "$TIER_NAME",
    "stars": int("$STARS"),
    "forks": int("$FORKS"),
    "last_push": "$LAST_PUSH",
    "loc": int("$LOC"),
    "skill_md_count": int("$SKILL_MD_COUNT"),
    "has_claude_md": $HAS_CLAUDE_MD,
    "has_agents_md": $HAS_AGENTS_MD,
    "default_branch": "$DEFAULT_BRANCH"
}))
PYEOF
