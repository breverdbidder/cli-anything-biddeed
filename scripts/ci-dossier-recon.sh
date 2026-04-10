#!/usr/bin/env bash
# CI Dossier Recon — per-competitor reconnaissance script
# SUMMIT #424 — Executed by ci-dossier-fanout.yml via SSH on Hetzner
# Usage: ./scripts/ci-dossier-recon.sh <competitor_slug>
set -euo pipefail

COMPETITOR_SLUG="${1:?Usage: ci-dossier-recon.sh <competitor_slug>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$REPO_ROOT/config/ci-dossiers/${COMPETITOR_SLUG}.yaml"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)

echo "=== CI Dossier Recon: $COMPETITOR_SLUG ==="
echo "Started: $TIMESTAMP"

# Validate config exists
if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: Config not found: $CONFIG_FILE"
  exit 1
fi

# Source environment
source /root/.firecrawl_env 2>/dev/null || true
export SUPABASE_URL="${SUPABASE_URL:-https://mocerqjnksmhcjzxrewo.supabase.co}"

# Parse config
DOMAIN=$(grep 'domain:' "$CONFIG_FILE" | head -1 | awk '{print $2}')
DISPLAY_NAME=$(grep 'display_name:' "$CONFIG_FILE" | head -1 | sed 's/.*display_name: //')
THREAT_LEVEL=$(grep 'threat_level:' "$CONFIG_FILE" | head -1 | awk '{print $2}')

echo "Domain: $DOMAIN"
echo "Threat: $THREAT_LEVEL"

# Mark recon started in Supabase
curl -s -X PATCH "$SUPABASE_URL/rest/v1/ci_dossiers?competitor_slug=eq.$COMPETITOR_SLUG" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"dossier_status\": \"running\", \"recon_started_at\": \"$TIMESTAMP\"}" || true

# === LAYER 0: Sitemap Discovery ===
echo ""
echo "--- Layer 0: Sitemap Discovery ---"
# This layer uses Firecrawl MCP map + robots.txt + XML sitemap parsing
# Executed via Claude Code session with Firecrawl MCP tools:
#   firecrawl_map(url=$DOMAIN)
#   robots.txt fetch
#   XML sitemap parse
# Results stored in ci_dossier_sitemaps + ci_dossier_urls

# === LAYER 1: Page Scraping ===
echo "--- Layer 1: Page Scraping ---"
# firecrawl_scrape for each discovered URL
# Markdown content + structured extraction stored in ci_dossier_urls

# === LAYER 2: Screenshot Capture ===
echo "--- Layer 2: Screenshot Capture ---"
# Desktop (1920x1080) + Mobile (375x812) screenshots
# Stored in ci-evidence/{competitor_slug}/screenshots/

# === LAYER 3: Feature Extraction ===
echo "--- Layer 3: Feature Extraction ---"
# LLM analysis of scraped content to extract features
# Stored in ci_dossier_features with patent claim mapping

# === LAYER 4: API Discovery ===
echo "--- Layer 4: API Discovery ---"
# Network capture analysis, JS bundle inspection
# Stored in ci_dossier_api_endpoints

# === LAYER 5: Chatbot Interrogation ===
echo "--- Layer 5: Chatbot Interrogation ---"
# If competitor has a chatbot, run interrogation script from config
# Stored in ci_dossier_interrogations

# === LAYER 6: Battle Card Generation ===
echo "--- Layer 6: Battle Card Generation ---"
# Synthesize all layers into competitive battle card
# Patent claim correlation + moat assessment

# === EG14 Gate ===
echo ""
echo "--- EG14 Quality Gate ---"
# 14-point evidence gate check
EG14_RUN=$(date +%s)

# Insert EG14 run record
curl -s -X POST "$SUPABASE_URL/rest/v1/ci_dossier_eg14_runs" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=minimal" \
  -d "{
    \"competitor_slug\": \"$COMPETITOR_SLUG\",
    \"run_number\": 1,
    \"verdict\": \"running\",
    \"started_at\": \"$TIMESTAMP\"
  }" || true

# The actual EG14 checks will be performed by Claude Code session
# evaluating: sitemap coverage, page scrape %, screenshot count,
# feature extraction, API discovery, battle card completeness, etc.

echo ""
echo "=== Recon scaffold complete for $COMPETITOR_SLUG ==="
echo "Full Layer 0-6 execution requires Claude Code session with Firecrawl MCP."
echo "This script initializes DB records and provides the execution framework."
