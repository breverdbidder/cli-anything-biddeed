// claude-router v4 client for zonewise-mcp
// All LLM calls in this MCP server go through the Smart Router — never api.anthropic.com directly.
// ROUTER_PROXY_KEY is read from env at call time (never hardcoded).

const ROUTER_URL =
  process.env.CLAUDE_ROUTER_URL ||
  'https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/claude-router';

/**
 * Call the claude-router v4 Smart Router.
 *
 * @param {Array<{role: string, content: string}>} messages
 * @param {{ system?: string, max_tokens?: number, tool_name?: string, force_tier?: string }} opts
 * @returns {Promise<{text: string, provider: string, tier: string, model: string, ...} | null>}
 *   Returns null if ROUTER_PROXY_KEY is unset or the call fails — callers must handle graceful fallback.
 */
export async function callRouter(messages, opts = {}) {
  const key = process.env.ROUTER_PROXY_KEY;
  if (!key) return null;

  const { system, max_tokens = 2000, tool_name, force_tier } = opts;

  let res;
  try {
    res = await fetch(ROUTER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Router-Key': key,
      },
      body: JSON.stringify({
        messages,
        system,
        max_tokens,
        source: 'mcp',
        tool_name: tool_name || null,
        force_tier: force_tier || undefined,
      }),
    });
  } catch {
    return null;
  }

  if (!res.ok) return null;

  let data;
  try {
    data = await res.json();
  } catch {
    return null;
  }

  // Normalize: router may return {text} (v4 format) or Anthropic {content} format (v7 compat)
  const text = data.text ?? data.content?.[0]?.text ?? null;
  if (!text) return null;

  return {
    text,
    tier: data.tier ?? null,
    model: data.model ?? null,
    provider: data.provider ?? (data.type === 'message' ? 'gemini' : null),
    input_tokens: data.input_tokens ?? data.usage?.input_tokens ?? 0,
    output_tokens: data.output_tokens ?? data.usage?.output_tokens ?? 0,
    cost_usd: data.cost_usd ?? 0,
    latency_ms: data.latency_ms ?? null,
    request_id: data.request_id ?? data.id ?? null,
  };
}
