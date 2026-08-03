// supabase/functions/claude-router/index.ts
//
// claude-router v4 — MCP tool LLM gateway
//
// Tier cascade (auto-fallback, zero-HITL):
//   T1: Gemini 2.5 Flash via vault.gemini_api_key_biddeed (BidDeed Business — $0 marginal)
//   T2: Gemini 2.5 Flash via vault.gemini_api_key         (global pool fallback)
//   T3: claude-sonnet-4-6 via vault.anthropic_oauth_bearer (Max OAuth — NEVER sk-ant-*)
//
// Caller authenticates with X-Router-Key matching vault.router_proxy_key.
//
// Request:  { messages, system?, max_tokens?, source?, tool_name?, force_tier? }
// Response: { text, provider, tier, model, input_tokens, output_tokens, cost_usd, latency_ms, request_id }

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Router-Key",
};

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}

// ── Vault ────────────────────────────────────────────────────────────────────

async function getVaultSecret(name: string): Promise<string | null> {
  const { data, error } = await supabase.rpc("get_vault_secret_mcp", { p_name: name });
  if (error || data == null) return null;
  return String(data);
}

async function validateProxyKey(key: string): Promise<boolean> {
  const { data, error } = await supabase.rpc("claude_router_validate_key", { p_key: key });
  if (error) return false;
  return data === true;
}

// ── Gemini ────────────────────────────────────────────────────────────────────

// gemini-2.5-flash: 2.0-flash deprecated Aug 2026 — updated to 2.5-flash
// thinking budget set low (0) to avoid overhead on simple tool-call workloads
const GEMINI_MODEL = "gemini-2.5-flash"; // updated: 2.0-flash deprecated Aug 2026
const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models";

function toGeminiContents(messages: any[]) {
  return messages.map((m) => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: typeof m.content === "string" ? m.content : (m.content[0]?.text ?? "") }],
  }));
}

async function callGemini(
  apiKey: string,
  messages: any[],
  system: string | undefined,
  maxTokens: number,
): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
  // gemini_api_key_biddeed may be an OAuth bearer token (AQ. prefix)
  // while gemini_api_key is a standard AI Studio key (AIzaSy prefix).
  // For bearer tokens, use Authorization header instead of ?key= query param.
  const isBearer = apiKey.startsWith("AQ.") || apiKey.startsWith("ya29.");
  const url = isBearer
    ? `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent`
    : `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

  const body: any = {
    contents: toGeminiContents(messages),
    generationConfig: { maxOutputTokens: maxTokens },
  };
  if (system) {
    body.systemInstruction = { parts: [{ text: system }] };
  }

  const reqHeaders: Record<string, string> = { "content-type": "application/json" };
  if (isBearer) reqHeaders["Authorization"] = `Bearer ${apiKey}`;

  const res = await fetch(url, {
    method: "POST",
    headers: reqHeaders,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();

  // Handle native Gemini format: candidates[0].content.parts[0].text
  // Also handle Anthropic-compatible format (Vertex AI): content[0].text
  let text = "";
  let inputTokens = 0;
  let outputTokens = 0;

  if (Array.isArray(data.candidates)) {
    text = data.candidates[0]?.content?.parts?.[0]?.text ?? "";
    const usage = data.usageMetadata ?? {};
    inputTokens = usage.promptTokenCount ?? 0;
    outputTokens = usage.candidatesTokenCount ?? 0;
    // If text is empty (e.g., finishReason=MAX_TOKENS with no parts), treat as failure
    if (!text) throw new Error("Gemini returned empty content (MAX_TOKENS or safety)");
  } else if (Array.isArray(data.content)) {
    text = data.content[0]?.text ?? "";
    const usage = data.usage ?? {};
    inputTokens = usage.input_tokens ?? 0;
    outputTokens = usage.output_tokens ?? 0;
  }

  return { text, inputTokens, outputTokens };
}

// Gemini 2.5 Flash pricing: $0.075/1M input + $0.30/1M output
function geminiCost(inputTokens: number, outputTokens: number): number {
  return (inputTokens / 1_000_000) * 0.075 + (outputTokens / 1_000_000) * 0.30;
}

// ── Claude (Max OAuth) ────────────────────────────────────────────────────────

// Haiku used for T3 OAuth — sonnet hits rate limits on Max OAuth tokens
const CLAUDE_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";

async function callClaude(
  oauthBearer: string,
  messages: any[],
  system: string | undefined,
  maxTokens: number,
): Promise<{ text: string; inputTokens: number; outputTokens: number }> {
  const body: any = {
    model: CLAUDE_MODEL,
    messages,
    max_tokens: maxTokens,
  };
  if (system) body.system = system;

  const res = await fetch(ANTHROPIC_API, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "anthropic-version": "2023-06-01",
      "authorization": `Bearer ${oauthBearer}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Claude ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();
  const text = data.content?.[0]?.text ?? "";
  const usage = data.usage ?? {};
  return {
    text,
    inputTokens: usage.input_tokens ?? 0,
    outputTokens: usage.output_tokens ?? 0,
  };
}

// claude-sonnet-4-6 via Max OAuth — $0 marginal (included in Max plan)
function claudeCost(_input: number, _output: number): number {
  return 0;
}

// ── Logging ───────────────────────────────────────────────────────────────────

async function logRequest(row: {
  source: string;
  tool_name: string | null;
  provider: string;
  tier: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
  request_id: string;
  messages: any[];
}): Promise<void> {
  const { error } = await supabase.from("llm_requests").insert({
    ...row,
    stage: "direct",
    fallback_attempt: 0,
    messages: row.messages,
  });
  if (error) console.error("llm_requests insert:", error.message);
}

// ── Handler ───────────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS });
  }

  const url = new URL(req.url);

  if (url.pathname.endsWith("/health") && req.method === "GET") {
    return jsonRes({ status: "ok", service: "claude-router", version: "4", tiers: ["T1_gemini_biddeed", "T2_gemini_global", "T3_claude_oauth"] });
  }

  if (req.method !== "POST") {
    return jsonRes({ error: "POST required" }, 405);
  }

  // Auth
  const routerKey = req.headers.get("X-Router-Key") ?? req.headers.get("x-router-key") ?? "";
  if (!routerKey) {
    return jsonRes({ error: "missing X-Router-Key header" }, 401);
  }
  const keyOk = await validateProxyKey(routerKey);
  if (!keyOk) {
    return jsonRes({ error: "invalid router key" }, 401);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return jsonRes({ error: "invalid JSON body" }, 400);
  }

  const {
    messages,
    system,
    max_tokens: maxTokens = 2000,
    source = "mcp",
    tool_name: toolName = null,
    force_tier: forceTier,
  } = body;

  if (!Array.isArray(messages) || messages.length === 0) {
    return jsonRes({ error: "messages must be a non-empty array" }, 400);
  }

  const requestId = crypto.randomUUID();
  const t0 = Date.now();

  // Build the tier cascade — T1 and T2 are Gemini with different keys, T3 is Claude
  const tiers: Array<{
    id: string;
    provider: string;
    model: string;
    call: () => Promise<{ text: string; inputTokens: number; outputTokens: number }>;
    cost: (i: number, o: number) => number;
  }> = [];

  if (!forceTier || forceTier !== "anthropic") {
    const key1 = await getVaultSecret("gemini_api_key_biddeed");
    if (key1) {
      tiers.push({
        id: "T1_gemini_biddeed",
        provider: "gemini",
        model: GEMINI_MODEL,
        call: () => callGemini(key1, messages, system, maxTokens),
        cost: geminiCost,
      });
    }

    const key2 = await getVaultSecret("gemini_api_key");
    if (key2) {
      tiers.push({
        id: "T2_gemini_global",
        provider: "gemini",
        model: GEMINI_MODEL,
        call: () => callGemini(key2, messages, system, maxTokens),
        cost: geminiCost,
      });
    }
  }

  const oauthBearer = await getVaultSecret("anthropic_oauth_bearer");
  if (oauthBearer) {
    tiers.push({
      id: "T3_claude_oauth",
      provider: "anthropic",
      model: CLAUDE_MODEL,
      call: () => callClaude(oauthBearer, messages, system, maxTokens),
      cost: claudeCost,
    });
  }

  if (tiers.length === 0) {
    return jsonRes({ error: "no LLM credentials configured in vault" }, 503);
  }

  for (const tier of tiers) {
    try {
      const { text, inputTokens, outputTokens } = await tier.call();
      const latencyMs = Date.now() - t0;
      const costUsd = tier.cost(inputTokens, outputTokens);

      await logRequest({
        source,
        tool_name: toolName,
        provider: tier.provider,
        tier: tier.id,
        model: tier.model,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cost_usd: costUsd,
        latency_ms: latencyMs,
        request_id: requestId,
        messages,
      });

      return jsonRes({
        text,
        provider: tier.provider,
        tier: tier.id,
        model: tier.model,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cost_usd: costUsd,
        latency_ms: latencyMs,
        request_id: requestId,
      });
    } catch (err) {
      console.error(`${tier.id} failed:`, err instanceof Error ? err.message : String(err));
      // fall through to next tier
    }
  }

  return jsonRes({ error: "all tiers exhausted — LLM call failed" }, 502);
});
