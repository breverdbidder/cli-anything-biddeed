#!/usr/bin/env bash
# ============================================================================
# cli_anything.envelope.sh — 3D Building Envelope Agent Squad
# ============================================================================
# HARNESS.md 7-Phase Pipeline: INIT → FETCH → TRANSFORM → VALIDATE → LOAD → REPORT → ARCHIVE
# Part of: breverdbidder/cli-anything-biddeed
# Squad: 5 agents, LangGraph orchestration, Supabase persistence
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="envelope-3d"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_DIR="${SCRIPT_DIR}/logs/${PROJECT}"
DATA_DIR="${SCRIPT_DIR}/data/${PROJECT}"
REPORTS_DIR="${SCRIPT_DIR}/reports/${PROJECT}"

# Supabase config
SUPABASE_URL="${SUPABASE_URL:-https://mocerqjnksmhcjzxrewo.supabase.co}"
SUPABASE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"

# Agent registry
declare -A AGENTS=(
  ["scout"]="Agent 1: Zoning Scout — Municipal GIS setback extraction"
  ["surveyor"]="Agent 2: Parcel Surveyor — BCPAO geometry + lot dimensions"
  ["architect"]="Agent 3: Envelope Architect — Compute buildable volume"
  ["renderer"]="Agent 4: Visual Renderer — Three.js 3D envelope generation"
  ["inspector"]="Agent 5: QA Inspector — Data validation + coverage reporting"
  ["analyst"]="Agent 6: CMA Analyst — Highest-and-Best-Use + market valuation"
  ["reporter"]="Agent 7: Report Producer — CMA reports + auction day briefs"
)

mkdir -p "${LOG_DIR}" "${DATA_DIR}" "${REPORTS_DIR}"

# ============================================================================
# PHASE 1: INIT
# ============================================================================
phase_init() {
  echo "━━━ PHASE 1: INIT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🏔️  ENVELOPE SQUAD ACTIVATED — ${TIMESTAMP}"
  echo ""
  echo "AGENT ROSTER:"
  for agent in scout surveyor architect cma renderer inspector; do
    echo "  ✦ ${AGENTS[$agent]}"
  done
  echo ""
  
  # Verify Supabase connectivity
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    "${SUPABASE_URL}/rest/v1/envelope_cache?select=count&limit=1" \
    -H "apikey: ${SUPABASE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_KEY}" 2>/dev/null || echo "000")
  
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "406" ]; then
    echo "✅ Supabase: Connected"
  else
    echo "⚠️  Supabase: envelope_cache table may not exist yet (HTTP ${HTTP_CODE})"
    echo "   → Agent Scout will create schema on first run"
  fi
  
  # Check target municipality
  TARGET_MUNICIPALITY="${1:-all}"
  echo "🎯 Target: ${TARGET_MUNICIPALITY}"
  echo ""
}

# ============================================================================
# PHASE 2: FETCH (Agents 1 + 2 in parallel)
# ============================================================================
phase_fetch() {
  echo "━━━ PHASE 2: FETCH ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  echo "🔍 Agent SCOUT: Fetching zoning setbacks..."
  node "${SCRIPT_DIR}/agents/scout/zoning_scout.js" \
    --municipality "${TARGET_MUNICIPALITY}" \
    --output "${DATA_DIR}/zoning_raw.jsonl" \
    2>&1 | tee "${LOG_DIR}/scout_${TIMESTAMP}.log" &
  SCOUT_PID=$!
  
  echo "📐 Agent SURVEYOR: Fetching parcel geometry..."
  node "${SCRIPT_DIR}/agents/surveyor/parcel_surveyor.js" \
    --municipality "${TARGET_MUNICIPALITY}" \
    --output "${DATA_DIR}/geometry_raw.jsonl" \
    2>&1 | tee "${LOG_DIR}/surveyor_${TIMESTAMP}.log" &
  SURVEYOR_PID=$!
  
  # Wait for both agents
  wait $SCOUT_PID && echo "  ✅ Scout complete" || echo "  ❌ Scout failed"
  wait $SURVEYOR_PID && echo "  ✅ Surveyor complete" || echo "  ❌ Surveyor failed"
  echo ""
}

# ============================================================================
# PHASE 3: TRANSFORM (Agent 3)
# ============================================================================
phase_transform() {
  echo "━━━ PHASE 3: TRANSFORM ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  echo "🏗️  Agent ARCHITECT: Computing building envelopes..."
  node "${SCRIPT_DIR}/agents/architect/envelope_compute.js" \
    --zoning "${DATA_DIR}/zoning_raw.jsonl" \
    --geometry "${DATA_DIR}/geometry_raw.jsonl" \
    --output "${DATA_DIR}/envelopes_computed.jsonl" \
    2>&1 | tee "${LOG_DIR}/architect_${TIMESTAMP}.log"
  
  COMPUTED=$(wc -l < "${DATA_DIR}/envelopes_computed.jsonl" 2>/dev/null || echo "0")
  echo "  📊 Envelopes computed: ${COMPUTED}"
  echo ""
}

# ============================================================================
# PHASE 4: VALIDATE (Agent 5)
# ============================================================================
phase_validate() {
  echo "━━━ PHASE 4: VALIDATE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  echo "🔎 Agent INSPECTOR: Validating envelope data..."
  node "${SCRIPT_DIR}/agents/inspector/qa_inspector.js" \
    --input "${DATA_DIR}/envelopes_computed.jsonl" \
    --report "${REPORTS_DIR}/qa_report_${TIMESTAMP}.json" \
    2>&1 | tee "${LOG_DIR}/inspector_${TIMESTAMP}.log"
  echo ""
}

# ============================================================================
# PHASE 5: CMA ANALYSIS (Agent 6)
# ============================================================================
phase_cma() {
  echo "━━━ PHASE 5: CMA ANALYSIS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  echo "📊 Agent CMA: Running Comparative Market Analysis + HBU..."
  node "${SCRIPT_DIR}/agents/analyst/cma_analyst.js" \
    --envelopes "${DATA_DIR}/envelopes_computed.jsonl" \
    --output "${DATA_DIR}/cma_reports.jsonl" \
    --supabase-url "${SUPABASE_URL}" \
    --supabase-key "${SUPABASE_KEY}" \
    2>&1 | tee "${LOG_DIR}/cma_${TIMESTAMP}.log"
  echo ""
}

# ============================================================================
# PHASE 6: LOAD (Supabase upsert)
# ============================================================================
phase_load() {
  echo "━━━ PHASE 6: LOAD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  echo "💾 Loading envelopes to Supabase envelope_cache..."
  node "${SCRIPT_DIR}/agents/loader/supabase_loader.js" \
    --input "${DATA_DIR}/envelopes_computed.jsonl" \
    --table "envelope_cache" \
    --supabase-url "${SUPABASE_URL}" \
    --supabase-key "${SUPABASE_KEY}" \
    2>&1 | tee "${LOG_DIR}/loader_${TIMESTAMP}.log"

  echo "💾 Loading CMA reports to Supabase cma_reports..."
  node "${SCRIPT_DIR}/agents/loader/supabase_loader.js" \
    --input "${DATA_DIR}/cma_reports.jsonl" \
    --table "cma_reports" \
    --supabase-url "${SUPABASE_URL}" \
    --supabase-key "${SUPABASE_KEY}" \
    2>&1 | tee -a "${LOG_DIR}/loader_${TIMESTAMP}.log"
  echo ""
}

# ============================================================================
# PHASE 6: REPORT (Agent 4 + summary)
# ============================================================================
phase_report() {
  echo "━━━ PHASE 7: REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  echo "🎨 Agent RENDERER: Generating sample 3D renders..."
  node "${SCRIPT_DIR}/agents/renderer/render_samples.js" \
    --input "${DATA_DIR}/envelopes_computed.jsonl" \
    --output "${REPORTS_DIR}/renders/" \
    --count 5 \
    2>&1 | tee "${LOG_DIR}/renderer_${TIMESTAMP}.log"
  
  echo "📄 Agent REPORTER: Generating CMA reports + auction brief..."
  node "${SCRIPT_DIR}/agents/reporter/report_producer.js" \
    --input "${DATA_DIR}/cma_reports.jsonl" \
    --envelopes "${DATA_DIR}/envelopes_computed.jsonl" \
    --output "${REPORTS_DIR}/cma/" \
    --limit 25 \
    2>&1 | tee "${LOG_DIR}/reporter_${TIMESTAMP}.log"
  
  # Summary
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════════╗"
  echo "║  ENVELOPE SQUAD — MISSION REPORT                                   ║"
  echo "╠══════════════════════════════════════════════════════════════════════╣"
  
  ZONING_COUNT=$(wc -l < "${DATA_DIR}/zoning_raw.jsonl" 2>/dev/null || echo "0")
  GEOMETRY_COUNT=$(wc -l < "${DATA_DIR}/geometry_raw.jsonl" 2>/dev/null || echo "0")
  COMPUTED_COUNT=$(wc -l < "${DATA_DIR}/envelopes_computed.jsonl" 2>/dev/null || echo "0")
  CMA_COUNT=$(wc -l < "${DATA_DIR}/cma_reports.jsonl" 2>/dev/null || echo "0")
  
  printf "║  🔍 Scout:     %-8s parcels with zoning data                   ║\n" "${ZONING_COUNT}"
  printf "║  📐 Surveyor:  %-8s parcels with geometry                      ║\n" "${GEOMETRY_COUNT}"
  printf "║  🏗️  Architect: %-8s envelopes computed                        ║\n" "${COMPUTED_COUNT}"
  printf "║  📊 CMA:       %-8s parcels with HBU analysis                  ║\n" "${CMA_COUNT}"
  printf "║  🎨 Renderer:  5 sample 3D renders generated                     ║\n"
  printf "║  📄 Reporter:  CMA reports + auction brief generated               ║\n"
  printf "║  🔎 Inspector: QA report at reports/                             ║\n"
  echo "╚══════════════════════════════════════════════════════════════════════╝"
  echo ""
}

# ============================================================================
# PHASE 8: ARCHIVE
# ============================================================================
phase_archive() {
  echo "━━━ PHASE 8: ARCHIVE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  ARCHIVE_NAME="${PROJECT}_${TIMESTAMP//[:T]/_}.tar.gz"
  tar -czf "${SCRIPT_DIR}/archives/${ARCHIVE_NAME}" \
    -C "${SCRIPT_DIR}" \
    "data/${PROJECT}" "logs/${PROJECT}" "reports/${PROJECT}" 2>/dev/null
  
  echo "📦 Archived: archives/${ARCHIVE_NAME}"
  echo "🏔️  ENVELOPE SQUAD — MISSION COMPLETE"
  echo ""
}

# ============================================================================
# MAIN — Execute all phases
# ============================================================================
main() {
  phase_init "${1:-all}"
  phase_fetch
  phase_transform
  phase_validate
  phase_cma
  phase_load
  phase_report
  phase_archive
}

# Run with municipality filter: ./cli_anything.envelope.sh palm_bay
main "$@"
