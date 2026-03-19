#!/usr/bin/env bash
# EVEREST SENTINEL — Self-Healing SUMMIT System
# No mission fails silently. No human in the loop.
# Triggered by: sentinel.yml on every workflow_run completion
set -euo pipefail

# === INPUTS (from GHA) ===
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
HETZNER_IP="${HETZNER_IP:-87.99.129.125}"

MAX_RETRIES=3

# === HELPERS ===
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
    grep -i content-range | sed 's|.*/||' | tr -d '' || echo "0"
}

tg_send() {
  curl -sf -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d "chat_id=${TG_CHAT}" -d "parse_mode=HTML" -d "text=$1" >/dev/null 2>&1 || true
}

get_logs() {
  local run="$1"
  curl -sL -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/actions/runs/$run/logs" -o /tmp/run-logs.zip 2>/dev/null
  cd /tmp && rm -f *.txt && unzip -o run-logs.zip 2>/dev/null || true
  cat /tmp/*.txt /tmp/*/*.txt 2>/dev/null || echo "NO_LOGS"
}

get_duration_seconds() {
  local run="$1"
  curl -s -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/actions/runs/$run/timing" 2>/dev/null | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('run_duration_ms',0)//1000)" 2>/dev/null || echo "0"
}

get_workflow_file() {
  curl -s -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/actions/runs/$RUN_ID" 2>/dev/null | \
    python3 -c "import json,sys; print(json.load(sys.stdin).get('path','').split('/')[-1])" 2>/dev/null || echo ""
}

check_commits_since() {
  local since="$1"
  curl -s -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/commits?since=$since&per_page=5" 2>/dev/null | \
    python3 -c "import json,sys; cc=json.load(sys.stdin); print(len([c for c in cc if 'Claude' in c.get('commit',{}).get('author',{}).get('name','') or 'claude' in c.get('commit',{}).get('author',{}).get('name','')]))" 2>/dev/null || echo "0"
}

redispatch() {
  local wf_file="$1"
  curl -s -X POST -H "Authorization: token $GH_PAT" -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$REPO/actions/workflows/$wf_file/dispatches" \
    -d '{"ref":"main"}' -w "%{http_code}" 2>/dev/null
}

# === SKIP non-summit workflows ===
if [[ ! "$WORKFLOW_NAME" =~ ^[Ss]ummit ]]; then
  echo "Not a Summit workflow ($WORKFLOW_NAME). Skipping."
  exit 0
fi

echo "🛡️ SENTINEL: Triaging $WORKFLOW_NAME (run $RUN_ID, conclusion: $CONCLUSION)"

# === PHASE 1: SUCCESS PATH ===
if [[ "$CONCLUSION" == "success" ]]; then
  DURATION=$(get_duration_seconds "$RUN_ID")
  CLAUDE_COMMITS=$(check_commits_since "$RUN_STARTED")
  WF_FILE=$(get_workflow_file)

  # Silent failure detection: success exit but too fast or no commits
  if [[ "$CLAUDE_COMMITS" -eq 0 && "$DURATION" -lt 3600 ]]; then
    echo "⚠️ FALSE POSITIVE: Completed in ${DURATION}s with 0 Claude commits"
    LOGS=$(get_logs "$RUN_ID")
    
    # Check for known silent failures
    PATTERN="unknown"
    FIX=""
    
    if echo "$LOGS" | grep -qi "Permission denied"; then
      PATTERN="perm_denied"
      FIX="Fix file permissions: chown claude:claude"
    elif echo "$LOGS" | grep -qi "command not found"; then
      PATTERN="path_missing"
      FIX="Fix PATH: ensure /home/claude/.npm-global/bin in PATH"
    elif echo "$LOGS" | grep -qi "dubious ownership\|safe.directory"; then
      PATTERN="git_safe_dir"
      FIX="Add git safe.directory config"
    elif echo "$LOGS" | grep -qi "oauth\|401.*unauthorized\|token.*expired"; then
      PATTERN="oauth_expired"
      FIX="OAuth token expired — needs re-auth"
    elif echo "$LOGS" | grep -qi "ETIMEDOUT\|Connection timed out\|ssh.*timeout"; then
      PATTERN="ssh_timeout"
      FIX="SSH timeout — retry with backoff"
    fi

    RETRIES=$(sb_count_retries "$WORKFLOW_NAME" "$RUN_ID")
    
    if [[ "$RETRIES" -lt "$MAX_RETRIES" && "$PATTERN" != "oauth_expired" ]]; then
      echo "🔄 Auto-retry $((RETRIES+1))/$MAX_RETRIES for pattern: $PATTERN"
      sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"retried\",\"diagnosis\":\"Silent failure: ${DURATION}s, 0 commits\",\"failure_pattern\":\"$PATTERN\",\"fixed_by\":\"sentinel_auto_retry\",\"original_run_id\":$RUN_ID}"
      
      DISPATCH_STATUS=$(redispatch "$WF_FILE")
      tg_send "🔄 <b>SENTINEL AUTO-RETRY</b>
Workflow: $WORKFLOW_NAME
Pattern: $PATTERN
Attempt: $((RETRIES+1))/$MAX_RETRIES
Diagnosis: Completed in ${DURATION}s with 0 commits
Fix: $FIX
Run: $RUN_URL"
    else
      echo "🚨 ESCALATE: Max retries reached or unrecoverable"
      sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"escalated\",\"diagnosis\":\"Silent failure after $RETRIES retries. Pattern: $PATTERN\",\"failure_pattern\":\"$PATTERN\",\"original_run_id\":$RUN_ID}"
      
      tg_send "🚨 <b>SENTINEL ESCALATION</b>
Workflow: $WORKFLOW_NAME
Status: FAILED after $MAX_RETRIES retries
Pattern: $PATTERN
Diagnosis: ${DURATION}s runtime, 0 Claude commits
Last fix attempted: $FIX
Logs: $RUN_URL"
    fi
  else
    # Genuine success
    if [[ "$CLAUDE_COMMITS" -eq 0 ]]; then echo "⚠️ WARNING: Success but 0 Claude commits in ${DURATION}s — possible no-op"; fi; echo "✅ HEALTHY: ${DURATION}s runtime, $CLAUDE_COMMITS Claude commits"
    sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":1,\"status\":\"healthy\",\"diagnosis\":\"Success: ${DURATION}s, $CLAUDE_COMMITS commits\"}"
    
    tg_send "✅ <b>SUMMIT COMPLETE</b>
Workflow: $WORKFLOW_NAME
Duration: $((DURATION/60))m ${DURATION}s
Claude Commits: $CLAUDE_COMMITS
Run: $RUN_URL"
  fi
  exit 0
fi

# === PHASE 2: EXPLICIT FAILURE PATH ===
if [[ "$CONCLUSION" == "failure" || "$CONCLUSION" == "timed_out" || "$CONCLUSION" == "cancelled" ]]; then
  LOGS=$(get_logs "$RUN_ID")
  WF_FILE=$(get_workflow_file)
  
  # Pattern matching
  PATTERN="unknown"
  FIX=""
  AUTOFIX=true
  
  if echo "$LOGS" | grep -qi "Permission denied"; then
    PATTERN="perm_denied"
    FIX="chown + move env to /home/claude/"
  elif echo "$LOGS" | grep -qi "command not found.*claude\|claude.*not found"; then
    PATTERN="claude_not_found"
    FIX="Reinstall claude-code + fix PATH"
  elif echo "$LOGS" | grep -qi "dubious ownership\|safe.directory"; then
    PATTERN="git_safe_dir"
    FIX="git config --global safe.directory"
  elif echo "$LOGS" | grep -qi "npm ERR\|ERESOLVE\|npm.*install.*fail"; then
    PATTERN="npm_failure"
    FIX="Clear npm cache + retry"
  elif echo "$LOGS" | grep -qi "oauth\|401.*unauthorized\|authentication.*failed\|token.*expired\|token.*invalid"; then
    PATTERN="oauth_expired"
    FIX="OAuth token needs refresh"
    AUTOFIX=false
  elif echo "$LOGS" | grep -qi "ETIMEDOUT\|Connection timed out\|connection refused"; then
    PATTERN="ssh_timeout"
    FIX="Network issue — retry with backoff"
  elif echo "$LOGS" | grep -qi "disk.*full\|no space left\|ENOSPC"; then
    PATTERN="disk_full"
    FIX="Disk full on Hetzner — needs cleanup"
    AUTOFIX=false
  elif echo "$LOGS" | grep -qi "rate.*limit\|429\|too many requests"; then
    PATTERN="rate_limited"
    FIX="Rate limited — retry in 10 minutes"
  elif [[ "$CONCLUSION" == "timed_out" ]]; then
    PATTERN="timeout"
    FIX="Session exceeded timeout — check if partial work committed"
  elif [[ "$CONCLUSION" == "cancelled" ]]; then
    PATTERN="cancelled"
    FIX="Manually cancelled — no action"
    AUTOFIX=false
  fi

  RETRIES=$(sb_count_retries "$WORKFLOW_NAME" "$RUN_ID")

  if [[ "$AUTOFIX" == true && "$RETRIES" -lt "$MAX_RETRIES" ]]; then
    echo "🔄 Auto-retry $((RETRIES+1))/$MAX_RETRIES for pattern: $PATTERN"
    sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"retried\",\"diagnosis\":\"Failed: $CONCLUSION. Pattern: $PATTERN\",\"failure_pattern\":\"$PATTERN\",\"fixed_by\":\"sentinel_auto_retry\",\"original_run_id\":$RUN_ID}"
    
    # Wait before retry if rate limited
    if [[ "$PATTERN" == "rate_limited" ]]; then
      sleep 600
    elif [[ "$PATTERN" == "ssh_timeout" ]]; then
      sleep 60
    fi
    
    DISPATCH_STATUS=$(redispatch "$WF_FILE")
    tg_send "🔄 <b>SENTINEL AUTO-RETRY</b>
Workflow: $WORKFLOW_NAME
Conclusion: $CONCLUSION
Pattern: $PATTERN
Attempt: $((RETRIES+1))/$MAX_RETRIES
Fix: $FIX
Run: $RUN_URL"
  else
    echo "🚨 ESCALATE: $PATTERN (autofix=$AUTOFIX, retries=$RETRIES)"
    sb_insert "{\"workflow\":\"$WORKFLOW_NAME\",\"run_id\":$RUN_ID,\"attempt\":$((RETRIES+1)),\"status\":\"escalated\",\"diagnosis\":\"$CONCLUSION after $RETRIES retries. Pattern: $PATTERN\",\"failure_pattern\":\"$PATTERN\",\"original_run_id\":$RUN_ID}"
    
    # Extract last 30 lines of useful log
    LOG_SNIPPET=$(echo "$LOGS" | grep -v "^2026-.*##\|INPUT_\|Will download\|Drone SSH\|======\|^\s*$" | tail -20 | head -c 800)
    
    tg_send "🚨 <b>SENTINEL ESCALATION</b>
Workflow: $WORKFLOW_NAME
Conclusion: $CONCLUSION
Pattern: $PATTERN
Retries: $RETRIES/$MAX_RETRIES
Fix needed: $FIX
Run: $RUN_URL

<code>${LOG_SNIPPET}</code>"
  fi
fi
