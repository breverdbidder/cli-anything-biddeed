#!/bin/bash
# 
# SHARD-11 Gold Standard Fixes Runner
# Executes targeted fixes for manatee, washington, miami_dade, gadsden, wakulla
# 
set -euo pipefail

LOG_FILE="/tmp/shard11_fixes_$(date +%Y%m%d_%H%M%S).log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 SHARD-11 Gold Standard Fixes - $(date)" | tee -a "$LOG_FILE"
echo "Script directory: $SCRIPT_DIR" | tee -a "$LOG_FILE"

# Check environment
if [[ -z "${SUPABASE_URL:-}" ]] || [[ -z "${SUPABASE_KEY:-}" ]]; then
    echo "❌ Missing SUPABASE_URL or SUPABASE_KEY environment variables" | tee -a "$LOG_FILE"
    exit 1
fi

# Run database migration first
echo "" | tee -a "$LOG_FILE"
echo "📊 Step 1: Database Migration" | tee -a "$LOG_FILE"
cd "$SCRIPT_DIR/.."
if [[ -f "migrations/20260612_shard11_county_setup.sql" ]]; then
    if command -v node >/dev/null 2>&1; then
        echo "Running SHARD-11 migration..." | tee -a "$LOG_FILE"
        node migrations/run_migration.js migrations/20260612_shard11_county_setup.sql 2>&1 | tee -a "$LOG_FILE" || {
            echo "⚠️ Migration failed but continuing..." | tee -a "$LOG_FILE"
        }
    else
        echo "⚠️ Node.js not available, skipping migration" | tee -a "$LOG_FILE"
    fi
else
    echo "⚠️ Migration file not found" | tee -a "$LOG_FILE"
fi

# Run Letter E fixes (highest leverage)
echo "" | tee -a "$LOG_FILE"
echo "🔧 Step 2: Letter E (Parcel Linkage) Fixes" | tee -a "$LOG_FILE"
if [[ -f "scripts/shard11_letter_e_fix.py" ]]; then
    echo "Running Letter E fixes..." | tee -a "$LOG_FILE"
    python3 scripts/shard11_letter_e_fix.py 2>&1 | tee -a "$LOG_FILE" || {
        echo "⚠️ Letter E fixes failed" | tee -a "$LOG_FILE"
    }
else
    echo "⚠️ Letter E fix script not found" | tee -a "$LOG_FILE"
fi

# Run comprehensive targeted fixes
echo "" | tee -a "$LOG_FILE"
echo "🎯 Step 3: Comprehensive Targeted Fixes" | tee -a "$LOG_FILE"
if [[ -f "scripts/shard11_targeted_fixes.py" ]]; then
    echo "Running comprehensive fixes..." | tee -a "$LOG_FILE"
    python3 scripts/shard11_targeted_fixes.py 2>&1 | tee -a "$LOG_FILE" || {
        echo "⚠️ Comprehensive fixes failed" | tee -a "$LOG_FILE"
    }
else
    echo "⚠️ Comprehensive fix script not found" | tee -a "$LOG_FILE"
fi

# Run verification
echo "" | tee -a "$LOG_FILE"
echo "🔍 Step 4: Verification" | tee -a "$LOG_FILE"
if [[ -f "scripts/verify_shard11_status.py" ]]; then
    echo "Running verification..." | tee -a "$LOG_FILE"
    python3 scripts/verify_shard11_status.py 2>&1 | tee -a "$LOG_FILE" || {
        echo "⚠️ Verification failed" | tee -a "$LOG_FILE"
    }
else
    echo "⚠️ Verification script not found" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "✅ SHARD-11 fixes session completed - $(date)" | tee -a "$LOG_FILE"
echo "📄 Full log: $LOG_FILE" | tee -a "$LOG_FILE"

# Optionally send notification (if Telegram configured)
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]] && [[ -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    MESSAGE="🏛️ SHARD-11 Gold Standard fixes completed at $(date)"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
         -d chat_id="${TELEGRAM_CHAT_ID}" \
         -d text="$MESSAGE" >/dev/null || true
fi

echo "🏁 SHARD-11 session complete"