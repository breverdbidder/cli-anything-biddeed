#!/usr/bin/env node
// BidDeed MCP Server — HTTP entry point
// Usage: npx biddeed-mcp-http
// Or:    PORT=3000 npx biddeed-mcp-http
// Env:   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
//        STRIPE_SECRET_KEY (optional, S5 metered billing)
//        BIDDEED_API_KEY not needed — callers pass Bearer token

import { startHttp } from '../src/http.js';

const port = parseInt(process.env.PORT || '3000', 10);
startHttp(port).catch(err => {
  process.stderr.write(`[biddeed-mcp-http] Fatal: ${err.message}\n`);
  process.exit(1);
});
