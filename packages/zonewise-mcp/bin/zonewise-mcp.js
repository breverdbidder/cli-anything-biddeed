#!/usr/bin/env node
// ZoneWise MCP Server — stdio entry point
// Usage: npx zonewise-mcp
// Env:   BIDDEED_API_KEY=zw_live_xxx  (ZoneWise keys start with zw_live_)
//        SUPABASE_URL=https://...
//        SUPABASE_SERVICE_ROLE_KEY=eyJ...

import { startStdio } from '../src/server.js';

const apiKey = process.env.BIDDEED_API_KEY || process.env.ZONEWISE_API_KEY;
if (!apiKey) {
  process.stderr.write(
    '[zonewise-mcp] ERROR: BIDDEED_API_KEY not set.\n' +
    'ZoneWise keys start with zw_live_. Get yours at https://zonewise.ai/api\n'
  );
  process.exit(1);
}

startStdio(apiKey).catch(err => {
  process.stderr.write(`[zonewise-mcp] Fatal: ${err.message}\n`);
  process.exit(1);
});
