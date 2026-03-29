#!/bin/bash
# MODAL SETUP — One-time, 2 minutes
# Run from your machine (not GHA)

set -e

echo "=== EVEREST MODAL SETUP ==="

# 1. Install Modal
pip install modal --break-system-packages -q

# 2. Authenticate (opens browser)
modal token new

# 3. Create secrets
echo "Creating Modal secrets from environment..."
modal secret create everest-secrets \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_KEY="$SUPABASE_KEY" \
  GH_PAT="$GH_PAT" \
  TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
  TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID"

# 4. Deploy (creates the cron schedule)
cd "$(dirname "$0")/.."
modal deploy scripts/modal_executor.py

echo ""
echo "=== DONE ==="
echo "Modal executor deployed. Running every 2 hours."
echo "Up to 3 tasks dispatched in parallel per cycle."
echo "Shabbat-aware: pauses Friday sunset → Saturday havdalah + 10min."
echo "Monitor: https://modal.com/apps/everest-executor"
echo ""
echo "Test manually: modal run scripts/modal_executor.py"
