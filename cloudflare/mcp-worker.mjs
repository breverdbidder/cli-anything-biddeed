// biddeed-mcp-production — Cloudflare Worker entry (#20025, EXIT VERCEL A)
// Serves mcp.biddeed.ai byte-equivalent to the retired Vercel function.
// Option 1 (preferred, per issue plan): reuse the existing Node http.Server
// from packages/biddeed-mcp/src/http.js unchanged, bound into the Worker
// fetch event via cloudflare:node's httpServerHandler. Zero duplicated
// routing logic between Vercel-era code and the Worker.
import { httpServerHandler } from 'cloudflare:node';
import { startHttp } from '../packages/biddeed-mcp/src/http.js';

const PORT = 8080;

await startHttp(PORT);

export default httpServerHandler({ port: PORT });
