// BidDeed Stripe webhook — Vercel serverless handler
// Route: /api/stripe/webhook (biddeed.ai/api/stripe/webhook)
// Runtime: Node.js 20.x (Vercel)
// Note: delegates to packages/biddeed-mcp so the `stripe` dependency resolves
// from packages/biddeed-mcp/node_modules (not root node_modules) — same
// pattern as api/mcp.js.
import { handleStripeWebhook } from '../../packages/biddeed-mcp/src/webhook.js';

export const config = { runtime: 'nodejs20.x', maxDuration: 30 };

export default async function handler(req, res) {
  await handleStripeWebhook(req, res);
}
