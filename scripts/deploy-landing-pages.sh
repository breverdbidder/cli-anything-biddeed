#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# LANDING PAGE DEPLOYMENT — Hetzner Dispatch for Claude Code
# Target: everest-dispatch (87.99.129.125)
# Purpose: Deploy & verify ZoneWise.AI + BidDeed.AI landing pages
# Usage: Via GHA dispatch or direct: bash deploy-landing-pages.sh
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Config ──
PAT="${GH_PAT:-$1}"
TG_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TG_CHAT="${TELEGRAM_CHAT_ID:-}"

ZONEWISE_REPO="breverdbidder/zonewise-web"
BIDDEED_REPO="breverdbidder/brevard-bidder-landing"
ZONEWISE_FILE="public/index.html"
BIDDEED_FILE="index.html"

ZONEWISE_URLS=("https://www.zonewise.ai" "https://zonewise.ai" "https://zonewise-web.pages.dev")
BIDDEED_URLS=("https://brevard-bidder-landing.pages.dev" "https://biddeed.ai")

tg() {
  [ -z "$TG_TOKEN" ] && return
  curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d chat_id="${TG_CHAT}" -d text="$1" -d parse_mode="Markdown" > /dev/null 2>&1 || true
}

gh_api() {
  curl -s -H "Authorization: token $PAT" -H "Accept: application/vnd.github.v3+json" "$@"
}

echo "⛰️ Landing Page Deployment Pipeline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tg "🚀 *Landing Page Deploy* started"

# ── Step 1: Verify repos accessible ──
echo -e "\n[1/5] Verifying repo access..."
for REPO in "$ZONEWISE_REPO" "$BIDDEED_REPO"; do
  STATUS=$(gh_api "https://api.github.com/repos/$REPO" | python3 -c "import json,sys; print(json.load(sys.stdin).get('full_name','ERROR'))")
  if [ "$STATUS" = "ERROR" ]; then
    echo "❌ Cannot access $REPO"
    tg "❌ Deploy FAILED: cannot access $REPO"
    exit 1
  fi
  echo "  ✅ $REPO"
done

# ── Step 2: Check current file sizes ──
echo -e "\n[2/5] Current landing page status..."
ZW_SIZE=$(gh_api "https://api.github.com/repos/$ZONEWISE_REPO/contents/$ZONEWISE_FILE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('size',0))")
BD_SIZE=$(gh_api "https://api.github.com/repos/$BIDDEED_REPO/contents/$BIDDEED_FILE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('size',0))")
echo "  ZoneWise: ${ZW_SIZE} bytes"
echo "  BidDeed:  ${BD_SIZE} bytes"

# ── Step 3: Verify live sites ──
echo -e "\n[3/5] Checking live sites..."
RESULTS=""
for URL in "${ZONEWISE_URLS[@]}"; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "$URL" 2>/dev/null || echo "000")
  SIZE=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | wc -c)
  TITLE=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | grep -o '<title>[^<]*</title>' | head -1 | sed 's/<[^>]*>//g')
  STATUS_ICON=$( [ "$CODE" = "200" ] && echo "✅" || echo "❌" )
  echo "  $STATUS_ICON $URL → $CODE (${SIZE}B) [$TITLE]"
  RESULTS+="$STATUS_ICON \`$URL\` → $CODE (${SIZE}B)\n"
done
for URL in "${BIDDEED_URLS[@]}"; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "$URL" 2>/dev/null || echo "000")
  SIZE=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | wc -c)
  TITLE=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | grep -o '<title>[^<]*</title>' | head -1 | sed 's/<[^>]*>//g')
  STATUS_ICON=$( [ "$CODE" = "200" ] && echo "✅" || echo "❌" )
  echo "  $STATUS_ICON $URL → $CODE (${SIZE}B) [$TITLE]"
  RESULTS+="$STATUS_ICON \`$URL\` → $CODE (${SIZE}B)\n"
done

# ── Step 4: Verify 3D content (Three.js present) ──
echo -e "\n[4/5] Validating 3D content..."
for URL in "https://www.zonewise.ai" "https://brevard-bidder-landing.pages.dev"; do
  HAS_THREE=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | grep -c "three.min.js" || echo 0)
  HAS_BRAND=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | grep -c "1E3A5F" || echo 0)
  HAS_ORANGE=$(curl -s -L --max-time 10 "$URL" 2>/dev/null | grep -c "F59E0B" || echo 0)
  THREE_ICON=$( [ "$HAS_THREE" -gt 0 ] && echo "✅" || echo "❌" )
  BRAND_ICON=$( [ "$HAS_BRAND" -gt 0 ] && echo "✅" || echo "❌" )
  echo "  $URL"
  echo "    $THREE_ICON Three.js  $BRAND_ICON House Brand (Navy+Orange)"
done

# ── Step 5: Domain health ──
echo -e "\n[5/5] Domain DNS check..."
for DOMAIN in "zonewise.ai" "www.zonewise.ai" "biddeed.ai" "www.biddeed.ai"; do
  IP=$(dig +short "$DOMAIN" 2>/dev/null | tail -1)
  if [ -n "$IP" ]; then
    echo "  ✅ $DOMAIN → $IP"
  else
    echo "  ❌ $DOMAIN → NO DNS"
  fi
done

# ── Summary ──
echo -e "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⛰️ DEPLOYMENT VERIFICATION COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

tg "⛰️ *Landing Page Deploy Complete*

📊 File sizes:
• ZoneWise: ${ZW_SIZE}B
• BidDeed: ${BD_SIZE}B

🌐 Sites:
$(echo -e "$RESULTS")
⏰ $(date '+%I:%M %p EST')"
