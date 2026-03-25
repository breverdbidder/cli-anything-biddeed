#!/usr/bin/env bash
# deploy-dream-skill.sh — Push Dream skill to all ecosystem repos
# Dispatched via Summit on Hetzner 87.99.129.125
# Uses PAT4 for GitHub API operations

set -euo pipefail

GITHUB_TOKEN="${GITHUB_TOKEN:-$PAT4}"
OWNER="breverdbidder"
BRANCH="main"
SKILL_PATH=".claude/skills/dream/SKILL.md"
COMMIT_MSG="feat: deploy Dream memory consolidation skill [sentinel-ok]"

# All repos with CLAUDE.md deployed
REPOS=(
  "brevard-bidder-scraper"
  "cli-anything-biddeed"
  "biddeed-ai"
  "zonewise-web"
  "everest-nexus"
)

SKILL_CONTENT=$(cat <<'SKILL_EOF'
# Dream: Memory Consolidation Skill

> Invoke: `/dream` (project) | `/dream user` (user-level) | `/dream all` (both)

Reflective pass over Claude Code's auto-memory files. Synthesizes recent learnings into durable, well-organized memories so future sessions orient fast.

---

## Scope Resolution

```yaml
project:
  memory_dir: .claude/memories/
  index_file: .claude/memories/MEMORY.md
  transcripts_dir: .claude/transcripts/
  index_max_lines: 150

user:
  memory_dir: ~/.claude/memories/
  index_file: ~/.claude/memories/MEMORY.md
  transcripts_dir: ~/.claude/transcripts/
  index_max_lines: 200
```

**Flag behavior:**
- `/dream` → project scope only (default)
- `/dream user` → user scope only
- `/dream all` → project first, then user

---

## Phase 1 — Orient

1. `ls` the memory directory to see what exists
2. Read `${INDEX_FILE}` — understand current index
3. Skim existing topic files to avoid creating duplicates
4. If `logs/` or `sessions/` subdirs exist, review recent entries

---

## Phase 2 — Gather Recent Signal

Priority order:

1. **Daily logs** (`logs/YYYY/MM/YYYY-MM-DD.md`) if present
2. **Drifted memories** — facts that contradict current codebase/state
3. **Transcript search** — narrow grep ONLY, never read whole files:

```bash
grep -rn "<narrow_term>" ${TRANSCRIPTS_DIR}/ --include="*.jsonl" | tail -50
```

### NEVER-LIE Rule
- Only consolidate VERIFIED facts
- If uncertain, grep transcripts to confirm before writing
- Wrong memory = worse than no memory

---

## Phase 3 — Consolidate

For each thing worth remembering, write or update a memory file at the top level of the memory directory. Follow auto-memory conventions from system prompt.

### Focus:
- **Merge** new signal into existing topic files (no near-duplicates)
- **Absolute dates** — convert "yesterday", "last week", "next Friday" to absolute ISO dates
- **Delete contradictions** — if investigation disproves old memory, fix at source
- **Context compression** — Mermaid for flows, YAML for state, prose for NOTHING

### Classification:

```yaml
actions:
  duplicate: merge into existing file, delete duplicate
  contradiction: keep newer fact, delete older, log change
  stale: delete if >30 days with no transcript reference
  relative_date: convert to absolute ISO date
  verbose: compress to YAML/Mermaid, remove prose
  code_convention: belongs in CLAUDE.md or .claude/rules/, NOT memory
  sensitive: never store tokens/keys/passwords in memory
```

---

## Phase 4 — Prune & Index

Update `${INDEX_FILE}` to stay under `${INDEX_MAX_LINES}` lines.

### Rules:
- Index = pointers with one-line descriptions, NOT content dumps
- Remove pointers to stale/wrong/superseded memories
- Demote verbose entries: gist in index, detail in topic file
- Add pointers to newly important memories
- Resolve contradictions — if two files disagree, fix the wrong one

---

## Output

Return structured YAML summary:

```yaml
dream_summary:
  scope: project|user|all
  date: YYYY-MM-DD
  consolidated: [merged files]
  updated: [modified files]
  pruned: [deleted/removed files]
  unchanged: [kept as-is]
  issues_found:
    duplicates: N
    contradictions: N
    stale: N
    relative_dates: N
    verbose: N
  index_lines_before: N
  index_lines_after: N
```

If nothing changed, say so.

---

## Integration
- Runs AFTER session work, BEFORE /compact or session kill
- Complements 50% context rule: dream keeps memory lean between sessions
- Does NOT touch CLAUDE.md or .claude/rules/ (Layer 1-3) — memory only
- Safe to run nightly via AUTOLOOP
SKILL_EOF
)

ENCODED_CONTENT=$(echo "$SKILL_CONTENT" | base64 -w 0)

echo "=== Dream Skill Deployment ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Repos: ${#REPOS[@]}"
echo ""

SUCCESS=0
FAILED=0

for REPO in "${REPOS[@]}"; do
  echo "--- Deploying to ${OWNER}/${REPO} ---"
  
  # Check if file already exists (need SHA for update)
  EXISTING=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/${OWNER}/${REPO}/contents/${SKILL_PATH}?ref=${BRANCH}" 2>/dev/null)
  
  SHA=$(echo "$EXISTING" | grep -o '"sha":"[^"]*"' | head -1 | cut -d'"' -f4)
  
  if [ -n "$SHA" ]; then
    # Update existing file
    PAYLOAD=$(cat <<EOF
{
  "message": "${COMMIT_MSG}",
  "content": "${ENCODED_CONTENT}",
  "sha": "${SHA}",
  "branch": "${BRANCH}"
}
EOF
)
  else
    # Create new file
    PAYLOAD=$(cat <<EOF
{
  "message": "${COMMIT_MSG}",
  "content": "${ENCODED_CONTENT}",
  "branch": "${BRANCH}"
}
EOF
)
  fi

  RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
    -H "Authorization: token ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/${OWNER}/${REPO}/contents/${SKILL_PATH}" \
    -d "$PAYLOAD" 2>/dev/null)
  
  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  
  if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "201" ]]; then
    echo "  ✅ ${REPO}: deployed (HTTP ${HTTP_CODE})"
    ((SUCCESS++))
  else
    echo "  ❌ ${REPO}: FAILED (HTTP ${HTTP_CODE})"
    echo "  Response: $(echo "$RESPONSE" | head -1 | cut -c1-200)"
    ((FAILED++))
  fi
done

echo ""
echo "=== Deployment Summary ==="
echo "Success: ${SUCCESS}/${#REPOS[@]}"
echo "Failed: ${FAILED}/${#REPOS[@]}"

if [ "$FAILED" -gt 0 ]; then
  echo "⚠️ Some deployments failed — check logs above"
  exit 1
fi

echo "✅ Dream skill deployed to all repos"
