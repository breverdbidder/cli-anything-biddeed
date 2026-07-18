#!/usr/bin/env bash
# EVEREST SENTINEL PATROL — Scans for failed/stale workflows every 5 minutes
# V3: Monitors ALL workflows (not just SUMMIT), daily heartbeat
set -uo pipefail

REPO="${REPO:-breverdbidder/cli-anything-biddeed}"
SB_URL="${SUPABASE_URL:?}"
SB_KEY="${SUPABASE_SERVICE_KEY:?}"
TG_TOKEN="${TELEGRAM_BOT_TOKEN:?}"
TG_CHAT="${TELEGRAM_CHAT_ID:?}"

tg_send() {
  curl -sf -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d "chat_id=${TG_CHAT}" -d "parse_mode=HTML" -d "text=$1" >/dev/null 2>&1 || true
}

echo "🛡️ SENTINEL PATROL: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# ========================================
# DAILY HEARTBEAT (9 AM EST = 13:00-14:00 UTC)
# ========================================
HOUR_UTC=$(date -u '+%H')
MINUTE_UTC=$(date -u '+%M')

# Fire heartbeat once daily during the 13:00 UTC window (9 AM EST)
# Only on the first cron run of the hour (minute 0-4)
if [[ "$HOUR_UTC" == "13" && "$MINUTE_UTC" -lt "6" ]]; then
  # Check if heartbeat already sent today
  TODAY=$(date -u '+%Y-%m-%d')
  HB_EXISTS=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?workflow=eq.heartbeat&diagnosis=like.${TODAY}*&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [[ "$HB_EXISTS" -eq 0 ]]; then
    # Gather stats for heartbeat
    RUNS_24H=$(curl -s -H "Authorization: token $GH_PAT" \
      "https://api.github.com/repos/$REPO/actions/runs?per_page=100&created=>$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ')" 2>/dev/null)

    STATS=$(echo "$RUNS_24H" | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
total = len(runs)
success = len([r for r in runs if r.get('conclusion') == 'success'])
failed = len([r for r in runs if r.get('conclusion') == 'failure'])
skipped = len([r for r in runs if r.get('conclusion') == 'skipped'])
running = len([r for r in runs if r.get('status') == 'in_progress'])
# Top failures
from collections import Counter
fail_names = Counter(r['name'] for r in runs if r.get('conclusion') == 'failure')
top_fails = fail_names.most_common(5)
top_str = ', '.join(f'{n}({c})' for n,c in top_fails) if top_fails else 'none'
print(f'{total}|{success}|{failed}|{skipped}|{running}|{top_str}')
" 2>/dev/null || echo "?|?|?|?|?|error")

    IFS='|' read -r TOTAL SUCCESS FAILED SKIPPED RUNNING TOP_FAILS <<< "$STATS"

    tg_send "🏔️ <b>SENTINEL HEARTBEAT</b> — ${TODAY}

📊 Last 24h: ${TOTAL} runs
✅ Success: ${SUCCESS}
❌ Failed: ${FAILED}
⏭️ Skipped: ${SKIPPED}
🔄 Running: ${RUNNING}

🔥 Top failures: ${TOP_FAILS}

🛡️ Sentinel is alive and monitoring."

    # Log heartbeat
    curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
      -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"workflow\":\"heartbeat\",\"run_id\":0,\"attempt\":1,\"status\":\"healthy\",\"diagnosis\":\"${TODAY} — ${TOTAL} runs, ${FAILED} failed\"}" >/dev/null 2>&1

    echo "💓 Heartbeat sent"
  fi
fi

# ========================================
# MANUAL TRIAGE
# ========================================
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

# ========================================
# SCAN: ALL completed runs (last 10 min)
# ========================================
SINCE=$(date -u -d '10 minutes ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-10M '+%Y-%m-%dT%H:%M:%SZ')
echo "Scanning runs since $SINCE"

RUNS=$(curl -s -H "Authorization: token $GH_PAT" \
  "https://api.github.com/repos/$REPO/actions/runs?status=completed&per_page=30&created=%3E$SINCE" 2>/dev/null)

# --- SUMMIT runs → full triage via sentinel.sh ---
echo "$RUNS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
summit_runs = [r for r in runs if r.get('name','').lower().startswith('summit') or 'viral' in r.get('name','').lower()]
for r in summit_runs:
    print(f'{r[\"id\"]}|{r[\"name\"]}|{r[\"conclusion\"]}|{r[\"run_started_at\"]}|{r[\"html_url\"]}')
" 2>/dev/null | while IFS='|' read -r rid rname rconc rstart rurl; do

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

# --- NON-SUMMIT failures → batch alert ---
NON_SUMMIT_FAILS=$(echo "$RUNS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
# Exclude: SUMMIT, Sentinel, Task Lifecycle (noise), Repo Forensics (info)
SKIP = {'everest sentinel', 'everest sentinel v2', 'summit verifier', 'task lifecycle', 'repo forensics', 'coder task from issue'}
fails = []
for r in runs:
    name = r.get('name', '')
    name_lower = name.lower()
    conc = r.get('conclusion', '')
    if conc != 'failure':
        continue
    if name_lower.startswith('summit') or 'viral' in name_lower:
        continue
    if any(s in name_lower for s in SKIP):
        continue
    fails.append(f'{name}|{r[\"html_url\"]}')
for f in fails:
    print(f)
" 2>/dev/null)

if [[ -n "$NON_SUMMIT_FAILS" ]]; then
  FAIL_COUNT=$(echo "$NON_SUMMIT_FAILS" | wc -l)

  # Check if we already alerted these (avoid spam)
  FIRST_RUN_NAME=$(echo "$NON_SUMMIT_FAILS" | head -1 | cut -d'|' -f1)
  PATROL_KEY="patrol_$(date -u '+%Y%m%d%H%M' | cut -c1-11)"  # 10-min bucket

  ALREADY_ALERTED=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?workflow=eq.patrol_batch&diagnosis=like.${PATROL_KEY}*&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [[ "$ALREADY_ALERTED" -eq 0 ]]; then
    # Build failure list (max 8 lines)
    FAIL_LIST=$(echo "$NON_SUMMIT_FAILS" | head -8 | while IFS='|' read -r fname furl; do
      echo "• ${fname}"
    done)

    tg_send "⚠️ <b>PATROL: ${FAIL_COUNT} non-SUMMIT failures</b>

${FAIL_LIST}

<i>These are not auto-retried. Check if action needed.</i>"

    # Log batch alert
    curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
      -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"workflow\":\"patrol_batch\",\"run_id\":0,\"attempt\":1,\"status\":\"alerted\",\"diagnosis\":\"${PATROL_KEY} — ${FAIL_COUNT} non-SUMMIT failures\"}" >/dev/null 2>&1

    echo "  📢 Batch alert sent: $FAIL_COUNT failures"
  else
    echo "  ⏭️ Batch alert already sent this window"
  fi
fi

# ========================================
# STALE IN-PROGRESS RUNS (any workflow)
# ========================================
STALE_RUNS=$(curl -s -H "Authorization: token $GH_PAT" \
  "https://api.github.com/repos/$REPO/actions/runs?status=in_progress&per_page=10" 2>/dev/null)

echo "$STALE_RUNS" | python3 -c "
import json, sys
from datetime import datetime, timezone
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
now = datetime.now(timezone.utc)
for r in runs:
    started = datetime.fromisoformat(r['run_started_at'].replace('Z','+00:00'))
    age_min = int((now - started).total_seconds() / 60)
    if age_min > 115:
        print(f'{r[\"id\"]}|{r[\"name\"]}|stale_{age_min}min|{r[\"run_started_at\"]}|{r[\"html_url\"]}')
" 2>/dev/null | while IFS='|' read -r rid rname rconc rstart rurl; do

  ALREADY=$(curl -sf "$SB_URL/rest/v1/sentinel_runs?run_id=eq.$rid&status=eq.escalated&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [[ "$ALREADY" -gt 0 ]]; then
    continue
  fi

  echo "  ⏰ STALE RUN: $rname (#$rid) — $rconc"

  curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"workflow\":\"$rname\",\"run_id\":$rid,\"attempt\":1,\"status\":\"escalated\",\"diagnosis\":\"$rconc — approaching timeout\",\"failure_pattern\":\"stale_run\"}" >/dev/null 2>&1

  tg_send "⏰ <b>SENTINEL: STALE RUN</b>
Workflow: $rname
Running for: $rconc
Run: $rurl
Action: Approaching timeout. May need manual cancel + redispatch."
done

echo "🛡️ SENTINEL PATROL COMPLETE"

# ==============================
# CODER WORKSPACES HEALTH CHECK
# ==============================
check_coder_health() {
  CODER_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/v2/buildinfo 2>/dev/null || echo "000")
  if [ "$CODER_HEALTH" != "200" ]; then
    echo "⚠️ Coder server DOWN (HTTP $CODER_HEALTH)"
    cd /home/claude/coder && docker compose restart 2>/dev/null
    sleep 10
    CODER_RETRY=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/v2/buildinfo 2>/dev/null || echo "000")
    if [ "$CODER_RETRY" != "200" ]; then
      tg_send "⚠️ Coder server DOWN after restart (HTTP $CODER_RETRY)"
      curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
        -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
        -H "Content-Type: application/json" \
        -d '{"workflow":"coder_health","run_id":0,"attempt":1,"status":"escalated","diagnosis":"coder_down — restart_failed","failure_pattern":"coder_down"}' >/dev/null 2>&1
    else
      echo "✅ Coder server recovered after restart"
    fi
  fi
}

# Only run Coder health check on Hetzner
if [[ -z "${GITHUB_ACTIONS:-}" ]]; then
  check_coder_health
fi

# ==============================
# SECURITY SCAN MONITORING (SUMMIT #17 — Copilot Adoption Protocol)
# ==============================
check_security_scans() {
  SINCE_24H=$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ')

  BLOCKED=$(curl -sf "$SB_URL/rest/v1/security_scan_results?blocked=eq.true&created_at=gte.${SINCE_24H}&select=repo,pr_number,semgrep_critical,secrets_leaked" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null || echo "[]")

  BLOCKED_COUNT=$(echo "$BLOCKED" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  LEAKED_COUNT=$(echo "$BLOCKED" | python3 -c "import json,sys; print(len([r for r in json.load(sys.stdin) if r.get('secrets_leaked')]))" 2>/dev/null || echo "0")

  if [[ "$BLOCKED_COUNT" -gt 0 ]]; then
    SUMMARY=$(echo "$BLOCKED" | python3 -c "
import json, sys
rows = json.load(sys.stdin)
for r in rows[:8]:
    print(f\"• {r.get('repo')} PR#{r.get('pr_number')} — critical:{r.get('semgrep_critical',0)} secrets_leaked:{r.get('secrets_leaked')}\")
" 2>/dev/null)
    tg_send "🔒 <b>SENTINEL: ${BLOCKED_COUNT} blocked PR(s) in last 24h</b> (${LEAKED_COUNT} with leaked secrets)

${SUMMARY}"
  fi

  # Check which known src repos are missing security-scan.yml
  SRC_REPOS=(brevard-bidder-scraper cli-anything-biddeed everest-nexus zonewise-web cliproxy-gateway swimsquad-ai)
  MISSING=()
  for r in "${SRC_REPOS[@]}"; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token ${GH_PAT:-}" \
      "https://api.github.com/repos/breverdbidder/${r}/contents/.github/workflows/security-scan.yml" 2>/dev/null)
    if [[ "$CODE" != "200" ]]; then
      MISSING+=("$r ($CODE)")
    fi
  done
  if [[ "${#MISSING[@]}" -gt 0 ]]; then
    echo "⚠️ security-scan.yml missing/unreachable: ${MISSING[*]}"
  fi
}

# ==============================
# SESSION DECISION LOG COVERAGE (SUMMIT #17 — Copilot Adoption Protocol)
# ==============================
check_session_log_coverage() {
  SINCE_7D=$(date -u -d '7 days ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-7d '+%Y-%m-%dT%H:%M:%SZ')

  SESSIONS_7D=$(curl -sf "$SB_URL/rest/v1/chat_sessions?started_at=gte.${SINCE_7D}&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" -H "Prefer: count=exact" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  LOGS_7D=$(curl -sf "$SB_URL/rest/v1/session_decision_logs?session_started=gte.${SINCE_7D}&select=id" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [[ "$SESSIONS_7D" -gt 0 ]]; then
    COVERAGE_PCT=$(python3 -c "print(round(${LOGS_7D} / ${SESSIONS_7D} * 100, 1))" 2>/dev/null || echo "0")
    echo "📋 Session log coverage (7d): ${LOGS_7D}/${SESSIONS_7D} = ${COVERAGE_PCT}%"
    if python3 -c "exit(0 if ${COVERAGE_PCT} < 80 else 1)" 2>/dev/null; then
      tg_send "📋 <b>SENTINEL: session log coverage ${COVERAGE_PCT}%</b> (${LOGS_7D}/${SESSIONS_7D} sessions, last 7d)

Below 80% threshold — CC sessions are not writing session_decision_logs consistently."
    fi
  else
    echo "📋 No chat_sessions in last 7d — skipping coverage check"
  fi
}

check_security_scans
check_session_log_coverage

# ==============================
# BILLING CORRECTNESS (GTM-22 Task 3 — issue #12775)
# ==============================
# Three independent guards over the biddeed-mcp billing path:
#   1. charge_failure_rate > 2% over a rolling 15 min window (v_mcp_charge_failure_rate_15m)
#   2. any v_tool_billing_resolved row with disposition='UNKNOWN' (should always be zero)
#   3. v_mcp_server_reconcile.status <> 'OK' (declared/billing-map/deployed tool-count mismatch)
# Each alert debounces on a 10-min bucket via sentinel_runs, same pattern as PATROL_KEY above.
check_billing_correctness() {
  BUCKET_KEY="billing_$(date -u '+%Y%m%d%H%M' | cut -c1-11)"

  already_alerted() {
    local workflow="$1"
    curl -sf "$SB_URL/rest/v1/sentinel_runs?workflow=eq.${workflow}&diagnosis=like.${BUCKET_KEY}*&select=id" \
      -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
      python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0"
  }

  log_alert() {
    local workflow="$1" diagnosis="$2"
    curl -sf -X POST "$SB_URL/rest/v1/sentinel_runs" \
      -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" \
      -H "Content-Type: application/json" \
      -d "{\"workflow\":\"${workflow}\",\"run_id\":0,\"attempt\":1,\"status\":\"alerted\",\"diagnosis\":\"${BUCKET_KEY} — ${diagnosis}\"}" >/dev/null 2>&1
  }

  # --- 1. charge_failure_rate ---
  RATE_PCT=$(curl -sf "$SB_URL/rest/v1/v_mcp_charge_failure_rate_15m?select=charge_failure_rate_pct" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['charge_failure_rate_pct'] if d else 0)" 2>/dev/null || echo "0")
  echo "💳 charge_failure_rate (15m): ${RATE_PCT}%"
  if python3 -c "exit(0 if float(${RATE_PCT:-0}) > 2 else 1)" 2>/dev/null; then
    if [[ "$(already_alerted charge_failure_rate)" -eq 0 ]]; then
      tg_send "💳 <b>SENTINEL: charge_failure_rate ${RATE_PCT}%</b> (>2% threshold, rolling 15 min)

biddeed-mcp billing path is blocking/failing charges above threshold. Check mcp_charge_events for outcome breakdown."
      log_alert charge_failure_rate "${RATE_PCT}%"
    fi
  fi

  # --- 2. v_tool_billing_resolved UNKNOWN disposition ---
  UNKNOWN_COUNT=$(curl -sf "$SB_URL/rest/v1/v_tool_billing_resolved?disposition=eq.UNKNOWN&select=tool_name" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null | \
    python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  echo "💳 v_tool_billing_resolved UNKNOWN rows: ${UNKNOWN_COUNT}"
  if [[ "$UNKNOWN_COUNT" -gt 0 ]]; then
    if [[ "$(already_alerted billing_unknown_disposition)" -eq 0 ]]; then
      tg_send "💳 <b>SENTINEL: ${UNKNOWN_COUNT} tool(s) with disposition=UNKNOWN</b> in v_tool_billing_resolved

Every declared MCP tool must resolve to billable/non_billable_*. An UNKNOWN means a tool shipped without a billing disposition."
      log_alert billing_unknown_disposition "${UNKNOWN_COUNT} UNKNOWN rows"
    fi
  fi

  # --- 3. v_mcp_server_reconcile status ---
  RECONCILE=$(curl -sf "$SB_URL/rest/v1/v_mcp_server_reconcile?select=server_slug,status" \
    -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY" 2>/dev/null)
  BAD_RECONCILE=$(echo "$RECONCILE" | python3 -c "
import json, sys
rows = json.load(sys.stdin)
bad = [f\"{r['server_slug']}:{r['status']}\" for r in rows if r['status'] != 'OK']
print(','.join(bad))
" 2>/dev/null)
  echo "💳 v_mcp_server_reconcile non-OK: ${BAD_RECONCILE:-none}"
  if [[ -n "$BAD_RECONCILE" ]]; then
    if [[ "$(already_alerted mcp_server_reconcile)" -eq 0 ]]; then
      tg_send "💳 <b>SENTINEL: MCP server reconcile mismatch</b>: ${BAD_RECONCILE}

declared_tool_count / billing_map_tool_count / probed_tool_count disagree. Run a tool-list probe against the live endpoint."
      log_alert mcp_server_reconcile "${BAD_RECONCILE}"
    fi
  fi
}

check_billing_correctness
