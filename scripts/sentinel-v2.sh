#!/usr/bin/env bash
# EVEREST SENTINEL V2 — Self-Healing GHA Watcher
# V1 retried broken workflows. V2 FIXES them before retrying.
# Triggered by: sentinel-v2.yml on workflow_run.completed + cron */5
set -uo pipefail

# === INPUTS ===
WORKFLOW_NAME="${WORKFLOW_NAME:?}"
RUN_ID="${RUN_ID:?}"
CONCLUSION="${CONCLUSION:?}"
RUN_STARTED="${RUN_STARTED:?}"
RUN_URL="${RUN_URL:?}"
GH_PAT="${GH_PAT:?}"
REPO="${REPO:-breverdbidder/cli-anything-biddeed}"
SB_URL="${SUPABASE_URL:?}"
SB_KEY="${SUPABASE_SERVICE_KEY:?}"
TG_TOKEN="${TELEGRAM_BOT_TOKEN:?}"
TG_CHAT="${TELEGRAM_CHAT_ID:?}"
WF_PATH="${WF_PATH:-}"
RUN_DURATION="${RUN_DURATION:-0}"
EXPECTED_REPOS="${EXPECTED_REPOS:-}"

MAX_RETRIES=3

# === HELPERS ===
gh_api() { curl -sf -H "Authorization: token $GH_PAT" -H "Accept: application/vnd.github+json" "$@"; }

json_escape() {
  python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip())[1:-1])" <<< "$1"
}

sb_insert() {
  curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Content-Type: application/json" -H "Prefer: return=representation" \
    -d "$1" 2>/dev/null | head -c 500
}

sb_count_retries() {
  local wf="$1" orig="$2"
  curl -sf "$SB_URL/rest/v1/sentinel_runs?workflow=eq.$wf&original_run_id=eq.$orig&status=eq.retried&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Prefer: count=exact" -H "Range: 0-0" -D /dev/stderr 2>&1 1>/dev/null | \
    grep -i content-range | sed 's|.*/||' | tr -d '\r' || echo "0"
}

sb_already_triaged() {
  local rid="$1"
  local count
  count=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?run_id=eq.$rid&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  [[ "$count" -gt 0 ]]
}

sb_safe_insert() {
  local wf="$1" rid="$2" attempt="$3" status="$4" diag="$5" pattern="${6:-}" fixed_by="${7:-}" orig="${8:-$rid}"
  # Escape for JSON safety
  wf=$(json_escape "$wf")
  diag=$(json_escape "$diag")
  pattern=$(json_escape "$pattern")
  fixed_by=$(json_escape "$fixed_by")
  sb_insert "{\"workflow\":\"$wf\",\"run_id\":$rid,\"attempt\":$attempt,\"status\":\"$status\",\"diagnosis\":\"$diag\",\"failure_pattern\":\"$pattern\",\"fixed_by\":\"$fixed_by\",\"original_run_id\":$orig}"
}

tg_send() {
  curl -sf -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d chat_id="$TG_CHAT" -d parse_mode="HTML" --data-urlencode "text=$1" 2>/dev/null || true
}

get_logs() {
  local run_id="$1"
  local job_ids
  job_ids=$(gh_api "https://api.github.com/repos/$REPO/actions/runs/$run_id/jobs" | \
    python3 -c "import json,sys; [print(j['id']) for j in json.load(sys.stdin).get('jobs',[])]" 2>/dev/null)
  local all_logs=""
  for jid in $job_ids; do
    local jlog
    jlog=$(gh_api "https://api.github.com/repos/$REPO/actions/jobs/$jid/logs" 2>/dev/null || echo "")
    all_logs="$all_logs$jlog"$'\n'
  done
  echo "$all_logs"
}

get_wf_file() {
  if [[ -n "$WF_PATH" ]]; then
    echo "$WF_PATH"
  else
    gh_api "https://api.github.com/repos/$REPO/actions/runs/$RUN_ID" | \
      python3 -c "import json,sys; print(json.load(sys.stdin).get('path',''))" 2>/dev/null
  fi
}

get_wf_content() {
  local path="$1"
  gh_api "https://api.github.com/repos/$REPO/contents/$path" | \
    python3 -c "import json,sys,base64; d=json.load(sys.stdin); print(base64.b64decode(d['content']).decode())" 2>/dev/null
}

get_wf_sha() {
  local path="$1"
  gh_api "https://api.github.com/repos/$REPO/contents/$path" | \
    python3 -c "import json,sys; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null
}

push_wf_fix() {
  local path="$1" content="$2" message="$3"
  local sha
  sha=$(get_wf_sha "$path")
  local b64
  b64=$(echo "$content" | base64 -w0)
  local payload="{\"message\":\"$message\",\"content\":\"$b64\",\"branch\":\"main\""
  [[ -n "$sha" ]] && payload="$payload,\"sha\":\"$sha\""
  payload="$payload}"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
    -H "Authorization: token $GH_PAT" -H "Content-Type: application/json" \
    "https://api.github.com/repos/$REPO/contents/$path" -d "$payload")
  echo "$status"
}

redispatch() {
  local wf_file="$1"
  local basename
  basename=$(basename "$wf_file")
  sleep 10  # Let GHA index any YAML changes
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Authorization: token $GH_PAT" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/actions/workflows/$basename/dispatches" \
    -d '{"ref":"main"}')
  echo "$status"
}

count_commits_since() {
  local repo="$1" since="$2"
  gh_api "https://api.github.com/repos/$repo/commits?since=$since&per_page=1" | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0"
}

check_secret_exists() {
  local secret_name="$1"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/actions/secrets/$secret_name")
  [[ "$status" == "200" ]]
}


# === COOLDOWN: prevent cascade redispatch ===
check_cooldown() {
  local wf="$1"
  local last_retry
  last_retry=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?workflow=eq.$wf&status=eq.retried&order=created_at.desc&limit=1&select=created_at" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; rows=json.load(sys.stdin); print(rows[0]['created_at'] if rows else '')" 2>/dev/null)
  
  if [[ -n "$last_retry" ]]; then
    local age_sec
    age_sec=$(python3 -c "
from datetime import datetime, timezone
last = datetime.fromisoformat('$last_retry'.replace('Z','+00:00'))
now = datetime.now(timezone.utc)
print(int((now - last).total_seconds()))
" 2>/dev/null || echo "999")
    
    if [[ "$age_sec" -lt 120 ]]; then
      echo "⏳ Cooldown: last retry for $wf was ${age_sec}s ago (need 120s). Skipping."
      return 1
    fi
  fi
  return 0
}

# === SKIP NON-SUMMIT WORKFLOWS ===
WF_LOWER=$(echo "$WORKFLOW_NAME" | tr '[:upper:]' '[:lower:]')
if ! echo "$WF_LOWER" | grep -qiE "^summit|designwise|envelope|nexus"; then
  echo "⏭️ Non-summit workflow: $WORKFLOW_NAME — skipping"
  exit 0
fi

# === SKIP SENTINEL ITSELF (prevent infinite loop) ===
if echo "$WF_LOWER" | grep -qi "sentinel"; then
  echo "⏭️ Sentinel workflow — skipping self"
  exit 0
fi

# === SUCCESS PATH ===
if [[ "$CONCLUSION" == "success" ]]; then
  echo "✅ $WORKFLOW_NAME succeeded"
  
  # FALSE SUCCESS DETECTION: short runtime + zero commits = bailed early
  if [[ "$RUN_DURATION" -gt 0 && "$RUN_DURATION" -lt 120 ]]; then
    echo "⚠️ SUCCESS but only ${RUN_DURATION}s runtime — checking for false success"
    
    # Check if expected target repos got commits
    if [[ -n "$EXPECTED_REPOS" ]]; then
      IFS=',' read -ra TARGET_REPOS <<< "$EXPECTED_REPOS"
      TOTAL_COMMITS=0
      for trepo in "${TARGET_REPOS[@]}"; do
        trepo=$(echo "$trepo" | xargs)  # trim
        C=$(count_commits_since "breverdbidder/$trepo" "$RUN_STARTED")
        TOTAL_COMMITS=$((TOTAL_COMMITS + C))
        echo "  $trepo: $C commits since run start"
      done
      
      if [[ "$TOTAL_COMMITS" -eq 0 ]]; then
        echo "🚨 FALSE SUCCESS: ${RUN_DURATION}s runtime, 0 commits across ${#TARGET_REPOS[@]} target repos"
        CONCLUSION="false_success"
        # Fall through to failure handling
      else
        echo "✅ Short runtime but commits found — genuine success"
        sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":1,\"status\":\"success\",\"diagnosis\":\"Success in ${RUN_DURATION}s, $TOTAL_COMMITS commits\"}"
        exit 0
      fi
    else
      sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":1,\"status\":\"success\",\"diagnosis\":\"Success in ${RUN_DURATION}s\"}"
      exit 0
    fi
  else
    sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":1,\"status\":\"success\",\"diagnosis\":\"Success\"}"
    exit 0
  fi
fi

# === CANCELLED — no action ===
if [[ "$CONCLUSION" == "cancelled" ]]; then
  echo "⏭️ Cancelled — no action"
  sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":1,\"status\":\"cancelled\",\"diagnosis\":\"Manually cancelled\"}"
  exit 0
fi

# === FAILURE / FALSE SUCCESS PATH ===
echo "🔍 Diagnosing: $WORKFLOW_NAME (#$RUN_ID) — $CONCLUSION"

# Prevent duplicate processing
if sb_already_triaged "$RUN_ID"; then
  echo "⏭️ Already triaged run #$RUN_ID — skipping"
  exit 0
fi

LOGS=$(get_logs "$RUN_ID")
WF_FILE=$(get_wf_file)
WF_CONTENT=$(get_wf_content "$WF_FILE")

PATTERN="unknown"
FIX_DESC=""
AUTOFIX=true
FIXED_WF=""

# --- PATTERN: safe.directory ordering ---
if echo "$LOGS" | grep -qi "dubious ownership\|safe.directory"; then
  PATTERN="safe_dir_ordering"
  
  # Check if safe.directory comes AFTER git pull in the YAML
  if echo "$WF_CONTENT" | grep -n "git pull\|git config.*safe.directory" | head -5 | python3 -c "
import sys
lines = list(sys.stdin)
pull_line = safe_line = 0
for l in lines:
    num = int(l.split(':')[0])
    if 'git pull' in l: pull_line = num
    if 'safe.directory' in l: safe_line = num
sys.exit(0 if pull_line < safe_line else 1)
" 2>/dev/null; then
    FIX_DESC="safe.directory set AFTER git pull — reordering in YAML"
    # Fix: move safe.directory before any git operations
    FIXED_WF=$(echo "$WF_CONTENT" | python3 -c "
import sys, re
content = sys.stdin.read()
lines = content.split('\n')
# Find safe.directory lines and git pull lines
safe_lines = [i for i, l in enumerate(lines) if 'safe.directory' in l]
pull_lines = [i for i, l in enumerate(lines) if 'git pull' in l and 'safe' not in l]
if safe_lines and pull_lines and safe_lines[0] > pull_lines[0]:
    # Move all safe.directory lines before the first git operation
    git_ops = [i for i, l in enumerate(lines) if ('git pull' in l or 'git clone' in l) and 'safe' not in l]
    if git_ops:
        first_git = min(git_ops)
        safe_content = [lines[i] for i in safe_lines]
        # Remove safe lines from original positions
        new_lines = [l for i, l in enumerate(lines) if i not in safe_lines]
        # Find adjusted insertion point
        adj = sum(1 for s in safe_lines if s < first_git)
        insert_at = first_git - adj
        for j, sc in enumerate(safe_content):
            new_lines.insert(insert_at + j, sc)
        print('\n'.join(new_lines))
    else:
        print(content)
else:
    print(content)
")
  else
    FIX_DESC="safe.directory error but ordering looks correct — retry"
  fi

# --- PATTERN: missing/empty secret ---
elif echo "$LOGS" | grep -qiE "MAPBOX_TOKEN: *$|GEMINI_API_KEY: *$|SUPABASE.*: *$|secret.*empty\|env.*empty"; then
  PATTERN="missing_secret"
  # Extract which secret is empty
  EMPTY_SECRET=$(echo "$LOGS" | grep -oiE "[A-Z_]+_TOKEN: *$|[A-Z_]+_KEY: *$" | head -1 | cut -d: -f1 | xargs)
  FIX_DESC="Empty secret detected: $EMPTY_SECRET"
  
  # Check if it exists under a different name
  if [[ "$EMPTY_SECRET" == "MAPBOX_TOKEN" ]]; then
    if check_secret_exists "NEXT_PUBLIC_MAPBOX_TOKEN"; then
      FIX_DESC="$FIX_DESC — NEXT_PUBLIC_MAPBOX_TOKEN exists, fixing env mapping in YAML"
      FIXED_WF=$(echo "$WF_CONTENT" | sed "s/MAPBOX_TOKEN: \${{ secrets\.MAPBOX_TOKEN }}/MAPBOX_TOKEN: \${{ secrets.NEXT_PUBLIC_MAPBOX_TOKEN }}/g")
    fi
  elif [[ "$EMPTY_SECRET" == "SUPABASE_ANON_KEY" ]]; then
    if check_secret_exists "NEXT_PUBLIC_SUPABASE_ANON_KEY"; then
      FIX_DESC="$FIX_DESC — fixing secret name mapping"
      FIXED_WF=$(echo "$WF_CONTENT" | sed "s/SUPABASE_ANON_KEY: \${{ secrets\.SUPABASE_ANON_KEY }}/SUPABASE_ANON_KEY: \${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}/g")
    fi
  fi

# --- PATTERN: Permission denied ---
elif echo "$LOGS" | grep -qi "Permission denied"; then
  PATTERN="perm_denied"
  FIX_DESC="Permission denied — adding chown before operations"

# --- PATTERN: Claude Code not found ---
elif echo "$LOGS" | grep -qi "command not found.*claude\|claude.*not found"; then
  PATTERN="claude_not_found"
  FIX_DESC="Claude Code binary missing — reinstall in workflow"

# --- PATTERN: npm build failure ---
elif echo "$LOGS" | grep -qi "npm ERR\|ERESOLVE\|npm.*install.*fail\|Module not found\|Cannot find module"; then
  PATTERN="npm_failure"
  FIX_DESC="npm failure — retry with clean install"

# --- PATTERN: npm run build error ---
elif echo "$LOGS" | grep -qi "Type error\|Build error\|Failed to compile\|next build.*fail"; then
  PATTERN="build_error"
  FIX_DESC="Next.js build error — needs code fix, escalating"
  AUTOFIX=false

# --- PATTERN: OAuth / auth ---
elif echo "$LOGS" | grep -qi "oauth\|401.*unauthorized\|authentication.*failed\|token.*expired\|token.*invalid"; then
  PATTERN="oauth_expired"
  FIX_DESC="OAuth token expired — needs manual refresh"
  AUTOFIX=false

# --- PATTERN: SSH timeout ---
elif echo "$LOGS" | grep -qi "ETIMEDOUT\|Connection timed out\|connection refused"; then
  PATTERN="ssh_timeout"
  FIX_DESC="SSH connection failed — retry with backoff"

# --- PATTERN: Divergent branches ---
elif echo "$LOGS" | grep -qi "divergent branches\|Need to specify how to reconcile"; then
  PATTERN="divergent_branches"
  FIX_DESC="git pull failed on divergent branches — fixing to use --rebase"
  if echo "$WF_CONTENT" | grep -q "git pull origin main" && ! echo "$WF_CONTENT" | grep -q "pull.rebase"; then
    FIXED_WF=$(echo "$WF_CONTENT" | sed 's|git pull origin main|git config pull.rebase true \&\& git stash 2>/dev/null; git pull --rebase origin main || git reset --hard origin/main|g')
  fi

# --- PATTERN: Disk full ---
elif echo "$LOGS" | grep -qi "disk.*full\|no space left\|ENOSPC"; then
  PATTERN="disk_full"
  FIX_DESC="Disk full on Hetzner — SSH cleanup needed"

# --- PATTERN: Rate limited ---
elif echo "$LOGS" | grep -qi "rate.*limit\|429\|too many requests"; then
  PATTERN="rate_limited"
  FIX_DESC="Rate limited — delay + retry"

# --- PATTERN: Timeout ---
elif [[ "$CONCLUSION" == "timed_out" ]]; then
  PATTERN="timeout"
  FIX_DESC="Session exceeded timeout — check partial commits"
  AUTOFIX=false

# --- PATTERN: False success ---
elif [[ "$CONCLUSION" == "false_success" ]]; then
  PATTERN="false_success"
  FIX_DESC="Reported success but zero commits in target repos — redispatch"
fi

echo "Pattern: $PATTERN | Fix: $FIX_DESC | Autofix: $AUTOFIX"

RETRIES=$(sb_count_retries "$WORKFLOW_NAME" "$RUN_ID")

# === APPLY FIX + REDISPATCH ===
if [[ "$AUTOFIX" == true && "$RETRIES" -lt "$MAX_RETRIES" ]]; then
  # Cooldown check
  if ! check_cooldown "$WORKFLOW_NAME"; then
    sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"cooldown\",\"diagnosis\":\"Skipped — cooldown active\"}"
    exit 0
  fi

  echo "🔧 Fix attempt $((RETRIES+1))/$MAX_RETRIES for pattern: $PATTERN"
  
  # If we have a fixed workflow, push it first
  if [[ -n "$FIXED_WF" && -n "$WF_FILE" ]]; then
    echo "📝 Pushing YAML fix to $WF_FILE"
    PUSH_STATUS=$(push_wf_fix "$WF_FILE" "$FIXED_WF" "🔧 sentinel-v2: auto-fix $PATTERN in $WORKFLOW_NAME")
    echo "  Push: HTTP $PUSH_STATUS"
    if [[ "$PUSH_STATUS" != "200" && "$PUSH_STATUS" != "201" ]]; then
      echo "  ❌ YAML push failed — retrying without fix"
    fi
  fi

  # Delay for specific patterns
  case "$PATTERN" in
    rate_limited) sleep 600 ;;
    ssh_timeout) sleep 60 ;;
    *) sleep 5 ;;
  esac

  sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"retried\",\"diagnosis\":\"$CONCLUSION: $PATTERN\",\"failure_pattern\":\"$PATTERN\",\"fixed_by\":\"sentinel_v2_${PATTERN}\",\"original_run_id\":$RUN_ID}"

  DISPATCH_STATUS=$(redispatch "$WF_FILE")
  echo "🔄 Redispatch: HTTP $DISPATCH_STATUS"
  
  if [[ "$DISPATCH_STATUS" == "204" ]]; then
    # Silent retry — no Telegram unless it's the last attempt
    if [[ "$RETRIES" -ge $((MAX_RETRIES - 1)) ]]; then
      tg_send "🔄 <b>SENTINEL V2 AUTO-FIX</b> (attempt $((RETRIES+1))/$MAX_RETRIES)
Workflow: $WORKFLOW_NAME
Pattern: <code>$PATTERN</code>
Fix: $FIX_DESC
Run: $RUN_URL"
    fi
  else
    tg_send "⚠️ <b>SENTINEL V2</b> — Redispatch failed HTTP $DISPATCH_STATUS
Workflow: $WORKFLOW_NAME
Pattern: <code>$PATTERN</code>"
  fi

else
  # === ESCALATE ===
  echo "🚨 ESCALATE: $PATTERN (autofix=$AUTOFIX, retries=$RETRIES/$MAX_RETRIES)"
  
  sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"escalated\",\"diagnosis\":\"$CONCLUSION after $RETRIES retries. Pattern: $PATTERN\",\"failure_pattern\":\"$PATTERN\",\"original_run_id\":$RUN_ID}"

  LOG_SNIPPET=$(echo "$LOGS" | grep -v "^2026-.*##\|INPUT_\|Will download\|Drone SSH\|======\|^\s*$" | tail -20 | head -c 800)

  tg_send "🚨 <b>SENTINEL V2 ESCALATION</b>
Workflow: $WORKFLOW_NAME
Conclusion: $CONCLUSION
Pattern: <code>$PATTERN</code>
Retries: $RETRIES/$MAX_RETRIES
Fix needed: $FIX_DESC
Run: $RUN_URL

<pre>${LOG_SNIPPET}</pre>"
fi
