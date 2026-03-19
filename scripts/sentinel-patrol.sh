#!/usr/bin/env bash
# EVEREST SENTINEL PATROL — Scans for failed/stale SUMMITs every 5 minutes
# Feeds each into sentinel.sh for triage
set -uo pipefail

REPO="${REPO:-breverdbidder/cli-anything-biddeed}"
SB_URL="${SUPABASE_URL:?}"
SB_KEY="${SUPABASE_SERVICE_KEY:?}"

echo "🛡️ SENTINEL PATROL: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# If manual run_id provided, triage just that one
if [[ -n "${MANUAL_RUN_ID:-}" ]]; then
  echo "Manual triage for run $MANUAL_RUN_ID"
  RUN_DATA=$(curl -s -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/actions/runs/$MANUAL_RUN_ID")
  
  WORKFLOW_NAME=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('name',''))")
  CONCLUSION=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('conclusion',''))")
  RUN_STARTED=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('run_started_at',''))")
  RUN_URL=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('html_url',''))")
  
  export WORKFLOW_NAME RUN_ID="$MANUAL_RUN_ID" CONCLUSION RUN_STARTED RUN_URL
  bash scripts/sentinel.sh
  exit $?
fi

# Get runs completed in last 10 minutes (covers 5-min cron with overlap)
SINCE=$(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-10M '+%Y-%m-%dT%H:%M:%SZ')

echo "Scanning runs since $SINCE"

# Fetch recent completed runs
RUNS=$(curl -s -H "Authorization: token $GH_PAT" \
  "https://api.github.com/repos/$REPO/actions/runs?status=completed&per_page=20&created=%3E$SINCE" 2>/dev/null)

# Also fetch in-progress runs that might be stale (running > 2 hours)
STALE_SINCE=$(date -u -d '120 minutes ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-120M '+%Y-%m-%dT%H:%M:%SZ')
STALE_RUNS=$(curl -s -H "Authorization: token $GH_PAT" \
  "https://api.github.com/repos/$REPO/actions/runs?status=in_progress&per_page=10" 2>/dev/null)

# Process completed runs — only summit/viral workflows
echo "$RUNS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
summit_runs = [r for r in runs if r.get('name','').lower().startswith('summit') or 'viral' in r.get('name','').lower()]
for r in summit_runs:
    print(f'{r[\"id\"]}|{r[\"name\"]}|{r[\"conclusion\"]}|{r[\"run_started_at\"]}|{r[\"html_url\"]}')
" 2>/dev/null | while IFS='|' read -r rid rname rconc rstart rurl; do
  
  # Check if already triaged in sentinel_runs
  ALREADY=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?run_id=eq.$rid&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  
  if [[ "$ALREADY" -gt 0 ]]; then
    echo "  ⏭️ Already triaged: $rname (#$rid)"
    continue
  fi
  
  echo "  🔍 Triaging: $rname (#$rid) → $rconc"
  export WORKFLOW_NAME="$rname" RUN_ID="$rid" CONCLUSION="$rconc" RUN_STARTED="$rstart" RUN_URL="$rurl"
  bash scripts/sentinel.sh || echo "  ⚠️ Sentinel returned non-zero for $rid"
  
done

# Process stale in-progress runs
echo "$STALE_RUNS" | python3 -c "
import json, sys
from datetime import datetime, timezone, timedelta
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
now = datetime.now(timezone.utc)
for r in runs:
    if not (r.get('name','').lower().startswith('summit') or 'viral' in r.get('name','').lower()):
        continue
    started = datetime.fromisoformat(r['run_started_at'].replace('Z','+00:00'))
    age_min = int((now - started).total_seconds() / 60)
    if age_min > 115:  # Close to 120min timeout
        print(f'{r[\"id\"]}|{r[\"name\"]}|stale_{age_min}min|{r[\"run_started_at\"]}|{r[\"html_url\"]}')
" 2>/dev/null | while IFS='|' read -r rid rname rconc rstart rurl; do
  
  ALREADY=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?run_id=eq.$rid&status=eq.escalated&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  
  if [[ "$ALREADY" -gt 0 ]]; then
    continue
  fi
  
  echo "  ⏰ STALE RUN: $rname (#$rid) — $rconc"
  
  # Log to Supabase
  curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"workflow\":\"$rname\",\"run_id\":$rid,\"attempt\":1,\"status\":\"escalated\",\"diagnosis\":\"$rconc — approaching timeout\",\"failure_pattern\":\"stale_run\"}" >/dev/null 2>&1
  
  # Alert
  curl -sf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" -d "parse_mode=HTML" \
    -d "text=⏰ <b>SENTINEL: STALE RUN</b>
Workflow: $rname
Running for: $rconc
Run: $rurl
Action: Approaching timeout. May need manual cancel + redispatch." >/dev/null 2>&1 || true
done

echo "🛡️ SENTINEL PATROL COMPLETE"
