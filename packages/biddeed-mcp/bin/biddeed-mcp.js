#!/usr/bin/env node
// BidDeed MCP Server — stdio entry point
// Usage: npx biddeed-mcp
// Env:   BIDDEED_API_KEY=bd_live_xxx
//        SUPABASE_URL=https://...
//        SUPABASE_SERVICE_ROLE_KEY=eyJ...  (or SUPABASE_KEY)
//        STRIPE_SECRET_KEY=sk_live_...     (optional, S5 metered billing)

import { startStdio } from '../src/server.js';

const apiKey = process.env.BIDDEED_API_KEY;
if (!apiKey) {
  process.stderr.write(
    '[biddeed-mcp] ERROR: BIDDEED_API_KEY not set.\n' +
    'Get your key at https://biddeed.ai/dashboard\n' +
    'Then set it in your MCP config:\n' +
    '  "env": { "BIDDEED_API_KEY": "bd_live_..." }\n'
  );
  process.exit(1);
}

startStdio(apiKey).catch(err => {
  process.stderr.write(`[biddeed-mcp] Fatal: ${err.message}\n`);
  process.exit(1);
});
