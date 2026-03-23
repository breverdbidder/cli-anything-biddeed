#!/usr/bin/env bash
# SENTINEL V2 PATROL — Scans for failed/stale SUMMITs every 5 minutes
# Feeds each into sentinel-v2.sh for triage + auto-fix
set -uo pipefail

REPO="${REPO:-breverdbidder/cli-anything-biddeed}"
SB_URL="${SUPABASE_URL:?}"
SB_KEY="${SUPABASE_SERVICE_KEY:?}"

echo "🛡️ SENTINEL V2 PATROL: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Manual triage for specific run
if [[ -n "${MANUAL_RUN_ID:-}" ]]; then
  echo "Manual triage for run $MANUAL_RUN_ID"
  RUN_DATA=$(curl -sf -H "Authorization: token $GH_PAT" \
    "https://api.github.com/repos/$REPO/actions/runs/$MANUAL_RUN_ID")
  
  WORKFLOW_NAME=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('name',''))")
  CONCLUSION=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('conclusion',''))")
  RUN_STARTED=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('run_started_at',''))")
  RUN_URL=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('html_url',''))")
  WF_PATH=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('path',''))")
  
  # Calculate duration
  RUN_UPDATED=$(echo "$RUN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('updated_at',''))")
  RUN_DURATION=$(python3 -c "
from datetime import datetime
s='$RUN_STARTED'; u='$RUN_UPDATED'
if s and u:
    start=datetime.fromisoformat(s.replace('Z','+00:00'))
    end=datetime.fromisoformat(u.replace('Z','+00:00'))
    print(int((end-start).total_seconds()))
else: print(0)
" 2>/dev/null || echo "0")

  # Determine expected target repos from workflow name
  EXPECTED_REPOS=""
  WF_LOWER=$(echo "$WORKFLOW_NAME" | tr '[:upper:]' '[:lower:]')
  if echo "$WF_LOWER" | grep -qi "zonewise-web\|core pages\|explorer\|heatmap"; then
    EXPECTED_REPOS="zonewise-web"
  elif echo "$WF_LOWER" | grep -qi "envelope\|conquest"; then
    EXPECTED_REPOS="cli-anything-biddeed"
  elif echo "$WF_LOWER" | grep -qi "nexus"; then
    EXPECTED_REPOS="everest-nexus"
  fi

  export WORKFLOW_NAME RUN_ID="$MANUAL_RUN_ID" CONCLUSION RUN_STARTED RUN_URL WF_PATH RUN_DURATION EXPECTED_REPOS
  bash scripts/sentinel-v2.sh
  exit $?
fi

# Get runs completed in last 10 minutes
SINCE=$(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-10M '+%Y-%m-%dT%H:%M:%SZ')
echo "Scanning completed runs since $SINCE"

RUNS=$(curl -sf -H "Authorization: token $GH_PAT" \
  "https://api.github.com/repos/$REPO/actions/runs?status=completed&per_page=20&created=%3E$SINCE" 2>/dev/null || echo '{"workflow_runs":[]}')

# Process — summit/designwise/envelope/nexus workflows only
echo "$RUNS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
keywords = ['summit', 'designwise', 'envelope', 'nexus', 'viral']
filtered = [r for r in runs if any(k in r.get('name','').lower() for k in keywords)]
# Skip sentinel itself
filtered = [r for r in filtered if 'sentinel' not in r.get('name','').lower()]
for r in filtered:
    started = r.get('run_started_at','')
    updated = r.get('updated_at','')
    dur = 0
    if started and updated:
        from datetime import datetime
        s = datetime.fromisoformat(started.replace('Z','+00:00'))
        u = datetime.fromisoformat(updated.replace('Z','+00:00'))
        dur = int((u - s).total_seconds())
    print(f'{r[\"id\"]}|{r[\"name\"]}|{r[\"conclusion\"]}|{started}|{r[\"html_url\"]}|{r.get(\"path\",\"\")}|{dur}')
" 2>/dev/null | while IFS='|' read -r rid rname rconc rstart rurl rpath rdur; do
  
  # Check if already triaged
  ALREADY=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?run_id=eq.$rid&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  
  if [[ "$ALREADY" -gt 0 ]]; then
    echo "  ⏭️ Already triaged: $rname (#$rid)"
    continue
  fi
  
  # Determine expected repos
  EXPECTED_REPOS=""
  RNAME_LOWER=$(echo "$rname" | tr '[:upper:]' '[:lower:]')
  if echo "$RNAME_LOWER" | grep -qi "zonewise-web\|core pages\|explorer\|heatmap"; then
    EXPECTED_REPOS="zonewise-web"
  elif echo "$RNAME_LOWER" | grep -qi "envelope\|conquest"; then
    EXPECTED_REPOS="cli-anything-biddeed"
  elif echo "$RNAME_LOWER" | grep -qi "nexus"; then
    EXPECTED_REPOS="everest-nexus"
  fi

  echo "  🔍 Triaging: $rname (#$rid) → $rconc [${rdur}s]"
  export WORKFLOW_NAME="$rname" RUN_ID="$rid" CONCLUSION="$rconc" RUN_STARTED="$rstart" RUN_URL="$rurl" WF_PATH="$rpath" RUN_DURATION="$rdur" EXPECTED_REPOS="$EXPECTED_REPOS"
  bash scripts/sentinel-v2.sh || echo "  ⚠️ Sentinel V2 returned non-zero for $rid"
  
done

# === STALE RUN DETECTION ===
echo "Scanning for stale in-progress runs..."
STALE_RUNS=$(curl -sf -H "Authorization: token $GH_PAT" \
  "https://api.github.com/repos/$REPO/actions/runs?status=in_progress&per_page=10" 2>/dev/null || echo '{"workflow_runs":[]}')

echo "$STALE_RUNS" | python3 -c "
import json, sys
from datetime import datetime, timezone
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
now = datetime.now(timezone.utc)
keywords = ['summit', 'designwise', 'envelope', 'nexus']
for r in runs:
    name = r.get('name','').lower()
    if not any(k in name for k in keywords): continue
    if 'sentinel' in name: continue
    started = datetime.fromisoformat(r['run_started_at'].replace('Z','+00:00'))
    age_min = int((now - started).total_seconds() / 60)
    if age_min > 115:
        print(f'{r[\"id\"]}|{r[\"name\"]}|stale_{age_min}min|{r[\"run_started_at\"]}|{r[\"html_url\"]}|{r.get(\"path\",\"\")}|{age_min * 60}')
" 2>/dev/null | while IFS='|' read -r rid rname rconc rstart rurl rpath rdur; do
  echo "  ⏰ Stale: $rname (#$rid) — $rconc"
  export WORKFLOW_NAME="$rname" RUN_ID="$rid" CONCLUSION="$rconc" RUN_STARTED="$rstart" RUN_URL="$rurl" WF_PATH="$rpath" RUN_DURATION="$rdur" EXPECTED_REPOS=""
  bash scripts/sentinel-v2.sh || echo "  ⚠️ Sentinel V2 returned non-zero for stale $rid"
done

echo "🛡️ SENTINEL V2 PATROL COMPLETE: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
