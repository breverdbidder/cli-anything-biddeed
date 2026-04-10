#!/usr/bin/env bash
# Setup Firecrawl MCP server on Hetzner (run via SSH or directly on Hetzner)
# SUMMIT #424 — CI Dossier Infrastructure
set -euo pipefail

echo "=== Firecrawl MCP Server Registration ==="

# Source Firecrawl API key
if [ -f /root/.firecrawl_env ]; then
  source /root/.firecrawl_env
fi

if [ -z "${FIRECRAWL_API_KEY:-}" ]; then
  echo "ERROR: FIRECRAWL_API_KEY not set. Source /root/.firecrawl_env or export it."
  exit 1
fi

echo "API key found: ${FIRECRAWL_API_KEY:0:8}..."

# Register MCP server
claude mcp add firecrawl \
  -e FIRECRAWL_API_KEY="$FIRECRAWL_API_KEY" \
  -- npx -y firecrawl-mcp

echo "=== Verifying MCP Registration ==="
claude mcp list

echo ""
echo "Firecrawl MCP server registered. Available tools:"
echo "  - firecrawl_search"
echo "  - firecrawl_scrape"
echo "  - firecrawl_map"
echo "  - firecrawl_crawl"
echo "  - firecrawl_extract"
echo "  - firecrawl_interact"
echo "  - firecrawl_browser_execute"
echo ""
echo "Done."
