// BidDeed MCP — Streamable HTTP transport
// Deployed at: https://biddeed.ai/api/mcp
// Auth: Authorization: Bearer bd_live_xxx
import { createServer, handleToolCall } from './server.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { createServer as createHttpServer } from 'node:http';
import { get as sbGet, storagePut } from './supabase.js';
import { resolveApiKey, validateKey } from './auth.js';
import { isJwtLike } from './oauth.js';

// GTM-22 REPORT PDF ENDPOINT — GET /report/pdf. Delivers the same billable
// $25 artifact as the predict_auction_outcome tool (issue #12853) over plain
// HTTP for callers that want the raw PDF bytes rather than an MCP JSON-RPC
// envelope (dashboard downloads, the stripe-webhook redelivery path, etc).
// Deliberately routes through handleToolCall — the single canonical
// auth/cert-gate/billing/idempotency pipeline — rather than reimplementing
// any of that here, so this surface can never drift into a free bypass of
// the S5 charge or the Gold Standard cert gate.
const REPORT_PDF_ERROR_STATUS = {
  AUTH_ERROR: 401,
  COUNTY_NOT_CERTIFIED: 403,
  CERT_GATE_UNAVAILABLE: 503,
  PAYMENT_REQUIRED: 402,
  DUPLICATE_IN_FLIGHT: 409,
  AUCTION_NOT_FOUND: 404,
};

// Best-effort archival copy at exports/s5/{customer_id}/{mca_id}.pdf. Never
// allowed to block or fail the HTTP response — a storage outage must not
// turn into a failed report delivery for a customer who already paid.
async function storeReportPdfExport({ apiKey, caseNumber, county, pdfBuffer }) {
  let customerId = 'unknown';
  try {
    const credential = resolveApiKey(apiKey);
    if (!isJwtLike(credential)) {
      const record = await validateKey(credential);
      customerId = record.customer_id;
    }
  } catch {
    // best-effort — falls back to the 'unknown' customer folder below
  }

  let mcaId = `${county}-${caseNumber}`;
  try {
    const rows = await sbGet(`multi_county_auctions?case_number=eq.${encodeURIComponent(caseNumber)}&select=id&limit=1`);
    if (rows[0]?.id) mcaId = rows[0].id;
  } catch {
    // best-effort — falls back to the county-case composite path above
  }

  await storagePut('exports', `s5/${customerId}/${mcaId}.pdf`, pdfBuffer, 'application/pdf');
}

export async function handleReportPdfRequest(req, res, apiKey) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const caseNumber = url.searchParams.get('case_number');
  const county = url.searchParams.get('county');

  if (!caseNumber || !county) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'case_number and county query params are required' }));
    return;
  }

  const toolResponse = await handleToolCall(apiKey, 'predict_auction_outcome', { case_number: caseNumber, county });

  let payload;
  try {
    payload = JSON.parse(toolResponse.content?.[0]?.text ?? '{}');
  } catch {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Malformed report response' }));
    return;
  }

  if (toolResponse.isError || payload.error) {
    const status = REPORT_PDF_ERROR_STATUS[payload.code || payload.error] || 400;
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(payload));
    return;
  }

  if (!payload.pdf_base64) {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Report generated without a PDF artifact' }));
    return;
  }

  const pdfBuffer = Buffer.from(payload.pdf_base64, 'base64');

  storeReportPdfExport({ apiKey, caseNumber, county, pdfBuffer }).catch(err => {
    process.stderr.write(`[report/pdf] export storage failed (non-fatal): ${err.message}\n`);
  });

  res.writeHead(200, {
    'Content-Type': 'application/pdf',
    'Content-Disposition': `attachment; filename="biddeed-s5-${county}-${caseNumber}.pdf"`,
    'Content-Length': pdfBuffer.length,
  });
  res.end(pdfBuffer);
}

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

// RFC 9728 protected-resource metadata — tells MCP clients where to go for
// OAuth (WorkOS AuthKit). biddeed-mcp is the resource server ONLY; it never
// issues tokens itself.
export function buildProtectedResourceMetadata(resourceUrl) {
  return {
    resource: resourceUrl,
    authorization_servers: ['https://api.workos.com'],
    bearer_methods_supported: ['header'],
  };
}

function wwwAuthenticateHeader(resourceUrl) {
  // The metadata document is served at the origin root (see the
  // /.well-known/oauth-protected-resource handler below), not nested under
  // the resource path — resourceUrl already includes /api/mcp, so appending
  // the well-known suffix to it directly 404s.
  const metadataUrl = `${new URL(resourceUrl).origin}/.well-known/oauth-protected-resource`;
  return [
    'Bearer error="unauthorized"',
    'error_description="Authorization needed"',
    `resource_metadata="${metadataUrl}"`,
  ].join(', ');
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

// Exported for Vercel serverless handler (api/mcp.js)
export async function handleMcpRequest(req, res) {
  try {
    await handleRequest(req, res);
  } catch (err) {
    process.stderr.write(`[biddeed-mcp/http] Unhandled: ${err.message}\n`);
    if (!res.headersSent) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Internal server error' }));
    }
  }
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

  // RFC 9728 OAuth protected-resource metadata — resource server discovery
  if (req.method === 'GET' && path === '/.well-known/oauth-protected-resource') {
    const resourceUrl = process.env.MCP_PUBLIC_URL || 'https://biddeed.ai/api/mcp';
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(buildProtectedResourceMetadata(resourceUrl)));
    return;
  }

  // GET /report/pdf?case_number=...&county=... — same auth as /mcp
  if (req.method === 'GET' && path === '/report/pdf') {
    const apiKey = extractApiKey(req);
    if (!apiKey) {
      const resourceUrl = process.env.MCP_PUBLIC_URL || 'https://biddeed.ai/api/mcp';
      res.writeHead(401, {
        'Content-Type': 'application/json',
        'WWW-Authenticate': wwwAuthenticateHeader(resourceUrl),
      });
      res.end(JSON.stringify({
        error: 'Authorization required',
        hint: 'Set header: Authorization: Bearer bd_live_xxx (API key) or a WorkOS OAuth access token',
        get_key: 'https://biddeed.ai/dashboard',
      }));
      return;
    }
    await handleReportPdfRequest(req, res, apiKey);
    return;
  }

  // MCP over Streamable HTTP
  if (path === '/mcp' || path === '/api/mcp') {
    const apiKey = extractApiKey(req);
    if (!apiKey) {
      const resourceUrl = process.env.MCP_PUBLIC_URL || 'https://biddeed.ai/api/mcp';
      res.writeHead(401, {
        'Content-Type': 'application/json',
        'WWW-Authenticate': wwwAuthenticateHeader(resourceUrl),
      });
      res.end(JSON.stringify({
        error: 'Authorization required',
        hint: 'Set header: Authorization: Bearer bd_live_xxx (API key) or a WorkOS OAuth access token',
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
    endpoints: { mcp: '/mcp', health: '/health', report_pdf: '/report/pdf?case_number=...&county=...' },
  }));
}
