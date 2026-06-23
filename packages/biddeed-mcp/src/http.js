// BidDeed MCP — Streamable HTTP transport
// Deployed at: https://biddeed.ai/api/mcp
// Auth: Authorization: Bearer bd_live_xxx
import { createServer } from './server.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createServer as createHttpServer } from 'node:http';

function extractApiKey(req) {
  const auth = req.headers['authorization'];
  if (auth && auth.startsWith('Bearer ')) return auth.slice(7).trim();
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);
    return url.searchParams.get('api_key') || null;
  } catch {
    return null;
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf-8');
      if (!raw) { resolve(undefined); return; }
      try { resolve(JSON.parse(raw)); } catch (e) { reject(e); }
    });
    req.on('error', reject);
  });
}

export async function startHttp(port = parseInt(process.env.PORT || '3000', 10)) {
  const httpServer = createHttpServer(async (req, res) => {
    try {
      await handleRequest(req, res);
    } catch (err) {
      process.stderr.write(`[biddeed-mcp/http] Unhandled: ${err.message}\n`);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Internal server error' }));
      }
    }
  });

  httpServer.listen(port, '0.0.0.0', () => {
    process.stderr.write(`[biddeed-mcp] HTTP MCP server on :${port}\n`);
    process.stderr.write(`[biddeed-mcp] Endpoint: http://0.0.0.0:${port}/mcp\n`);
  });

  return httpServer;
}

async function handleRequest(req, res) {
  const path = (req.url || '/').split('?')[0];

  // Health / info
  if (req.method === 'GET' && (path === '/health' || path === '/')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      service: 'biddeed-mcp',
      version: '1.0.0',
      tools: 25,
      endpoint: '/mcp',
      docs: 'https://biddeed.ai/docs/mcp',
    }));
    return;
  }

  // MCP over Streamable HTTP
  if (path === '/mcp' || path === '/api/mcp') {
    const apiKey = extractApiKey(req);
    if (!apiKey) {
      res.writeHead(401, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        error: 'Authorization required',
        hint: 'Set header: Authorization: Bearer bd_live_xxx',
        get_key: 'https://biddeed.ai/dashboard',
      }));
      return;
    }

    // Parse body before connecting transport
    let body;
    if (req.method === 'POST') {
      try {
        body = await readBody(req);
      } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON body' }));
        return;
      }
    }

    const mcpServer = createServer(apiKey);
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless — no session state between calls
    });

    await mcpServer.connect(transport);
    await transport.handleRequest(req, res, body);
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    error: 'Not found',
    endpoints: { mcp: '/mcp', health: '/health' },
  }));
}
