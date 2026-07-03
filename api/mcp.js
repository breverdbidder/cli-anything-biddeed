// BidDeed MCP — Vercel serverless HTTP handler
// Route: /api/mcp (biddeed.ai/api/mcp)
// Auth:  Authorization: Bearer bd_live_xxx
// Runtime: Node.js 20.x (Vercel)
// Note: imports from packages/biddeed-mcp so @modelcontextprotocol/sdk
//       resolves from packages/biddeed-mcp/node_modules (not root node_modules)

import { handleMcpRequest } from '../packages/biddeed-mcp/src/http.js';

export const config = { runtime: 'nodejs', maxDuration: 60 };

export default async function handler(req, res) {
  // CORS preflight
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type, Accept, mcp-session-id');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  await handleMcpRequest(req, res);
}
