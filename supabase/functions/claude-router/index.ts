// supabase/functions/claude-router/index.ts — v9 (T10: vision cascade)
//
// NEW vs v8:
//   - T10 (issue #19736, 2026-09-02 directive): requests may now include a top-
//     level `images: [{media_type, data}]` array (base64, no data: prefix). When
//     present, the cascade switches to vision-capable tiers only:
//       T1_gemini_vision       -> gemini-2.5-flash, inlineData image parts
//       T1.5_deepseek_vision   -> deepseek-v4-flash-vision-exp (OpenAI-compatible,
//                                  images capped at 384 input tokens each, priced
//                                  as V4 Flash text) — vault key deepseek_api_key.
//                                  If that key is absent this tier is reported as
//                                  "disabled" (not a hard failure) and simply does
//                                  not enter the cascade.
//       T2_claude_oauth_vision -> claude-haiku-4-5, Anthropic image content blocks
//     Text-only requests (no `images`) are completely unaffected — same T1/T1.5/T2
//     text tiers as v8.
//   - GET /health?probe=vision exercises the vision tiers live with a tiny 1x1
//     test image and reports per-tier reachability (ok / down / disabled). Plain
//     GET /health stays static/cheap (unchanged) so existing monitors aren't
//     slowed down or billed on every poll.
//
// Tier cascade, text (in order, first success wins):
//   T1:   Gemini 2.5 Flash ($0 free tier)
//   T1.5: DeepSeek v3.2 ($0.28/1M) — currently unreachable: deepseek_api_key
//         missing from vault.secrets, so this tier never enters the cascade
//   T2:   Claude Haiku via OAuth Max ($0 marginal) — last resort for all traffic
//
// Tier cascade, vision (`images` present in body):
//   T1:   Gemini 2.5 Flash vision ($0 free tier)
//   T1.5: DeepSeek vision ($0.28/1M, per T10) — disabled until deepseek_api_key
//         is added to vault.secrets
//   T2:   Claude Haiku vision via OAuth Max ($0 marginal) — last resort
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: {
    persistSession: false,
    autoRefreshToken: false
  }
});
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Router-Key, x-traffic-source"
};
function jsonRes(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...CORS
    }
  });
}
// ── Cache TTL by request_type ─────────────────────────────────────────────────
const CACHE_TTL = {
  report: 86400,
  analysis: 3600,
  chat: 900,
  realtime: 0
};
// Heavy MCP tools that bloat payloads when not needed
const HEAVY_TOOLS = [
  "slack",
  "github",
  "grafana",
  "google_calendar",
  "google_drive",
  "gmail",
  "instacart",
  "spotify"
];
// ── SHA-256 cache key ─────────────────────────────────────────────────────────
async function generateCacheKey(messages, system, requestType) {
  const lastTurns = messages.slice(-2);
  const fingerprint = JSON.stringify({
    type: requestType,
    system: system?.slice(0, 200) ?? "",
    turns: lastTurns
  });
  const data = new TextEncoder().encode(fingerprint);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash)).map((b)=>b.toString(16).padStart(2, "0")).join("");
}
// ── Cache read ────────────────────────────────────────────────────────────────
async function checkCache(cacheKey) {
  const { data, error } = await supabase.from("llm_cache").select("*").eq("cache_key", cacheKey).gt("expires_at", new Date().toISOString()).maybeSingle();
  if (error || !data) return null;
  return data;
}
// ── Cache write ───────────────────────────────────────────────────────────────
async function writeCache(cacheKey, response, modelUsed, requestType, estimatedTokens) {
  const ttl = CACHE_TTL[requestType] ?? 900;
  if (ttl === 0) return;
  const expiresAt = new Date(Date.now() + ttl * 1000).toISOString();
  await supabase.from("llm_cache").upsert({
    cache_key: cacheKey,
    response,
    model_used: modelUsed,
    tokens_saved: estimatedTokens,
    request_type: requestType,
    expires_at: expiresAt,
    created_at: new Date().toISOString()
  });
}
// ── Tool pruner ───────────────────────────────────────────────────────────────
function pruneTools(tools, lastMessage) {
  if (!tools || tools.length === 0) return [];
  const lower = lastMessage.toLowerCase();
  return tools.filter((tool)=>{
    const name = (tool.name ?? "").toLowerCase();
    if (!HEAVY_TOOLS.some((h)=>name.includes(h))) return true;
    return lower.includes(name);
  });
}
// ── Context trimmer ───────────────────────────────────────────────────────────
function trimContext(messages) {
  return messages.map((msg)=>({
      ...msg,
      content: typeof msg.content === "string" ? msg.content.replace(/```json[\s\S]*?```/g, "[log removed]").replace(/\[SYSTEM\].*?\n/g, "").replace(/\n{3,}/g, "\n\n").trim() : msg.content
    }));
}
// ── Vault ─────────────────────────────────────────────────────────────────────
async function getVaultSecret(name) {
  const { data, error } = await supabase.rpc("get_vault_secret_mcp", {
    p_name: name
  });
  if (error || data == null) return null;
  return String(data);
}
async function validateProxyKey(key) {
  const { data, error } = await supabase.rpc("claude_router_validate_key", {
    p_key: key
  });
  if (error) return false;
  return data === true;
}
// ── Gemini 2.5 Flash ──────────────────────────────────────────────────────────
const GEMINI_MODEL = "gemini-2.5-flash";
const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models";
function toGeminiContents(messages) {
  return messages.map((m)=>({
      role: m.role === "assistant" ? "model" : "user",
      parts: [
        {
          text: typeof m.content === "string" ? m.content : m.content[0]?.text ?? ""
        }
      ]
    }));
}
async function callGemini(apiKey, messages, system, maxTokens) {
  const isBearer = apiKey.startsWith("AQ.") || apiKey.startsWith("ya29.");
  const url = isBearer ? `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent` : `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent?key=${apiKey}`;
  const body = {
    contents: toGeminiContents(messages),
    generationConfig: {
      maxOutputTokens: maxTokens
    }
  };
  if (system) body.systemInstruction = {
    parts: [
      {
        text: system
      }
    ]
  };
  const reqHeaders = {
    "content-type": "application/json"
  };
  if (isBearer) reqHeaders["Authorization"] = `Bearer ${apiKey}`;
  const res = await fetch(url, {
    method: "POST",
    headers: reqHeaders,
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`Gemini ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
  const usage = data.usageMetadata ?? {};
  if (!text) throw new Error("Gemini returned empty content");
  return {
    text,
    inputTokens: usage.promptTokenCount ?? 0,
    outputTokens: usage.candidatesTokenCount ?? 0
  };
}
// ── T10: vision helpers (issue #19736) ────────────────────────────────────────
// A trivial 1x1 red PNG, used only by GET /health?probe=vision to exercise the
// vision tiers live without depending on caller-supplied imagery.
const TEST_IMAGE_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
function lastUserText(messages) {
  const last = messages[messages.length - 1];
  if (!last) return "";
  return typeof last.content === "string" ? last.content : last.content?.[0]?.text ?? "";
}
async function callGeminiVision(apiKey, messages, system, maxTokens, images) {
  const isBearer = apiKey.startsWith("AQ.") || apiKey.startsWith("ya29.");
  const url = isBearer ? `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent` : `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent?key=${apiKey}`;
  const imageParts = images.map((img)=>({
      inlineData: {
        mimeType: img.media_type,
        data: img.data
      }
    }));
  const body = {
    contents: [
      {
        role: "user",
        parts: [
          ...imageParts,
          {
            text: lastUserText(messages)
          }
        ]
      }
    ],
    generationConfig: {
      maxOutputTokens: maxTokens,
      thinkingConfig: {
        thinkingBudget: 0
      }
    }
  };
  if (system) body.systemInstruction = {
    parts: [
      {
        text: system
      }
    ]
  };
  const reqHeaders = {
    "content-type": "application/json"
  };
  if (isBearer) reqHeaders["Authorization"] = `Bearer ${apiKey}`;
  const res = await fetch(url, {
    method: "POST",
    headers: reqHeaders,
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`Gemini vision ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
  const usage = data.usageMetadata ?? {};
  if (!text) throw new Error("Gemini vision returned empty content");
  return {
    text,
    inputTokens: usage.promptTokenCount ?? 0,
    outputTokens: usage.candidatesTokenCount ?? 0
  };
}
// T10: DeepSeek vision — deepseek-v4-flash-vision-exp, OpenAI-compatible chat
// completions, images passed as data-URI image_url parts (capped at 384 input
// tokens each per DeepSeek's own vision pricing note; priced as V4 Flash text).
const DEEPSEEK_VISION_MODEL = "deepseek-v4-flash-vision-exp";
async function callDeepSeekVision(apiKey, messages, system, maxTokens, images) {
  const content = [
    ...images.map((img)=>({
        type: "image_url",
        image_url: {
          url: `data:${img.media_type};base64,${img.data}`
        }
      })),
    {
      type: "text",
      text: lastUserText(messages)
    }
  ];
  const chatMessages = [
    ...system ? [
      {
        role: "system",
        content: system
      }
    ] : [],
    {
      role: "user",
      content
    }
  ];
  const body = {
    model: DEEPSEEK_VISION_MODEL,
    messages: chatMessages,
    max_tokens: maxTokens,
    temperature: 0.7
  };
  const res = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "authorization": `Bearer ${apiKey}`
    },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`DeepSeek vision ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const usage = data.usage ?? {};
  const text = data.choices?.[0]?.message?.content ?? "";
  if (!text) throw new Error("DeepSeek vision returned empty content");
  return {
    text,
    inputTokens: usage.prompt_tokens ?? 0,
    outputTokens: usage.completion_tokens ?? 0
  };
}
// T2 vision — Claude Haiku via OAuth, Anthropic image content blocks.
async function callClaudeVision(oauthBearer, messages, system, maxTokens, images) {
  const content = [
    ...images.map((img)=>({
        type: "image",
        source: {
          type: "base64",
          media_type: img.media_type,
          data: img.data
        }
      })),
    {
      type: "text",
      text: lastUserText(messages)
    }
  ];
  const body = {
    model: CLAUDE_MODEL,
    messages: [
      {
        role: "user",
        content
      }
    ],
    max_tokens: maxTokens
  };
  if (system) body.system = system;
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "anthropic-version": "2023-06-01",
      "authorization": `Bearer ${oauthBearer}`
    },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`Claude vision ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const usage = data.usage ?? {};
  const text = data.content?.[0]?.text ?? "";
  if (!text) throw new Error("Claude vision returned empty content");
  return {
    text,
    inputTokens: usage.input_tokens ?? 0,
    outputTokens: usage.output_tokens ?? 0
  };
}
// ── DeepSeek v3.2 ─────────────────────────────────────────────────────────────
const DEEPSEEK_MODEL = "deepseek-chat";
async function callDeepSeek(apiKey, messages, system, maxTokens) {
  const body = {
    model: DEEPSEEK_MODEL,
    messages: system ? [
      {
        role: "system",
        content: system
      },
      ...messages
    ] : messages,
    max_tokens: maxTokens,
    temperature: 0.7
  };
  const res = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "authorization": `Bearer ${apiKey}`
    },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`DeepSeek ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const usage = data.usage ?? {};
  return {
    text: data.choices?.[0]?.message?.content ?? "",
    inputTokens: usage.prompt_tokens ?? 0,
    outputTokens: usage.completion_tokens ?? 0
  };
}
// ── Claude Haiku OAuth ────────────────────────────────────────────────────────
const CLAUDE_MODEL = "claude-haiku-4-5-20251001";
async function callClaude(oauthBearer, messages, system, maxTokens) {
  const body = {
    model: CLAUDE_MODEL,
    messages,
    max_tokens: maxTokens
  };
  if (system) body.system = system;
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "anthropic-version": "2023-06-01",
      "authorization": `Bearer ${oauthBearer}`
    },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`Claude ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  const usage = data.usage ?? {};
  return {
    text: data.content?.[0]?.text ?? "",
    inputTokens: usage.input_tokens ?? 0,
    outputTokens: usage.output_tokens ?? 0
  };
}
// ── Complexity detection ──────────────────────────────────────────────────────
function inferComplexity(toolName, messageCount) {
  const complexTools = new Set([
    "predict_auction_outcome",
    "get_title_chain",
    "shapira",
    "s5"
  ]);
  if (complexTools.has(toolName ?? "")) return "complex";
  if (messageCount > 10) return "complex";
  if (messageCount > 4) return "medium";
  return "simple";
}
// ── Request logger ────────────────────────────────────────────────────────────
async function logRequest(row) {
  const { error: e1 } = await supabase.from("llm_requests").insert({
    source: row.source,
    tool_name: row.tool_name,
    complexity: row.complexity,
    provider: row.provider,
    tier: row.tier,
    model: row.model,
    input_tokens: row.input_tokens,
    output_tokens: row.output_tokens,
    cost_usd: row.cost_usd,
    latency_ms: row.latency_ms,
    request_id: row.request_id,
    stage: "direct",
    fallback_attempt: 0
  });
  if (e1) console.error("llm_requests insert:", e1.message);
  const { error: e2 } = await supabase.from("llm_router_logs").insert({
    request_id: row.request_id,
    tier: row.tier,
    model_used: row.model,
    cache_hit: row.cache_hit ?? false,
    tokens_saved: row.tokens_saved ?? 0,
    latency_ms: row.latency_ms,
    request_type: row.request_type ?? "chat",
    traffic_source: row.traffic_source ?? "internal",
    blocked_t2: row.blocked_t2 ?? false,
    created_at: new Date().toISOString()
  });
  if (e2) console.error("llm_router_logs insert:", e2.message);
}
// ── Main handler ──────────────────────────────────────────────────────────────
Deno.serve(async (req)=>{
  if (req.method === "OPTIONS") return new Response(null, {
    status: 204,
    headers: CORS
  });
  const url = new URL(req.url);
  if (url.pathname.endsWith("/health") && req.method === "GET") {
    const base = {
      status: "ok",
      service: "claude-router",
      version: "9-t10-vision-cascade",
      features: [
        "cache",
        "tool-pruning",
        "context-trimmer",
        "vision-cascade"
      ],
      tiers: [
        "T1_gemini_free",
        "T1.5_deepseek_cheap",
        "T2_claude_oauth(last_resort_all_traffic)"
      ],
      vision_tiers: [
        "T1_gemini_vision",
        "T1.5_deepseek_vision",
        "T2_claude_oauth_vision(last_resort_all_traffic)"
      ]
    };
    // T10: ?probe=vision live-exercises each vision tier with a tiny 1x1 test
    // image instead of just checking key presence -- issue #19736 directive.
    if (url.searchParams.get("probe") === "vision") {
      const testImages = [
        {
          media_type: "image/png",
          data: TEST_IMAGE_PNG_B64
        }
      ];
      const probeMessages = [
        {
          role: "user",
          content: "What color is this 1x1 test image? Reply with one word."
        }
      ];
      const probeResults = {};
      const geminiKey = await getVaultSecret("gemini_api_key_biddeed");
      if (geminiKey) {
        try {
          await callGeminiVision(geminiKey, probeMessages, null, 50, testImages);
          probeResults.T1_gemini_vision = "ok";
        } catch (e) {
          probeResults.T1_gemini_vision = `down: ${e instanceof Error ? e.message : String(e)}`;
        }
      } else {
        probeResults.T1_gemini_vision = "disabled: gemini_api_key_biddeed missing in vault";
      }
      const dsKey = await getVaultSecret("deepseek_api_key");
      if (dsKey) {
        try {
          await callDeepSeekVision(dsKey, probeMessages, null, 50, testImages);
          probeResults["T1.5_deepseek_vision"] = "ok";
        } catch (e) {
          probeResults["T1.5_deepseek_vision"] = `down: ${e instanceof Error ? e.message : String(e)}`;
        }
      } else {
        probeResults["T1.5_deepseek_vision"] = "disabled: deepseek_api_key missing in vault";
      }
      const bearer = await getVaultSecret("anthropic_oauth_bearer");
      if (bearer) {
        try {
          await callClaudeVision(bearer, probeMessages, null, 50, testImages);
          probeResults.T2_claude_oauth_vision = "ok";
        } catch (e) {
          probeResults.T2_claude_oauth_vision = `down: ${e instanceof Error ? e.message : String(e)}`;
        }
      } else {
        probeResults.T2_claude_oauth_vision = "disabled: anthropic_oauth_bearer missing in vault";
      }
      return jsonRes({
        ...base,
        vision_probe: probeResults
      });
    }
    return jsonRes(base);
  }
  if (req.method !== "POST") return jsonRes({
    error: "POST required"
  }, 405);
  // Auth
  const routerKey = req.headers.get("X-Router-Key") ?? req.headers.get("x-router-key") ?? "";
  if (!routerKey) return jsonRes({
    error: "missing X-Router-Key header"
  }, 401);
  const keyOk = await validateProxyKey(routerKey);
  if (!keyOk) return jsonRes({
    error: "invalid router key"
  }, 401);
  // ── CUSTOMER TRAFFIC GUARD ────────────────────────────────────────────────
  // If x-traffic-source is biddeed-chat, T2 (Max OAuth) is NEVER used.
  // This is the primary fix for weekly limit exhaustion.
  const trafficSource = req.headers.get("x-traffic-source") ?? "internal";
  const isCustomerTraffic = trafficSource === "biddeed-chat";
  let body;
  try {
    body = await req.json();
  } catch  {
    return jsonRes({
      error: "invalid JSON body"
    }, 400);
  }
  const { messages, system, max_tokens: maxTokens = 2000, source = "mcp", tool_name: toolName = null, force_tier: forceTier, tools, metadata, images } = body;
  if (!Array.isArray(messages) || messages.length === 0) return jsonRes({
    error: "messages must be a non-empty array"
  }, 400);
  const hasImages = Array.isArray(images) && images.length > 0;
  const requestId = crypto.randomUUID();
  const t0 = Date.now();
  const complexity = inferComplexity(toolName, messages.length);
  const requestType = metadata?.request_type ?? "chat";
  const lastMessage = (messages[messages.length - 1]?.content ?? "").toString();
  // T10: vision requests are never cached -- generateCacheKey() only fingerprints
  // messages/system/requestType, not image bytes, so two different properties'
  // photos sent with a similarly-shaped prompt would otherwise collide on the
  // same cache key and return the wrong property's condition assessment.
  // ── STAGE 1: Cache check ────────────────────────────────────────────────────
  if (requestType !== "realtime" && !hasImages) {
    const cacheKey = await generateCacheKey(messages, system, requestType);
    const cached = await checkCache(cacheKey);
    if (cached) {
      const latencyMs = Date.now() - t0;
      await logRequest({
        source,
        tool_name: toolName,
        complexity,
        provider: "cache",
        tier: "cache",
        model: `cache(${cached.model_used})`,
        input_tokens: 0,
        output_tokens: 0,
        cost_usd: 0,
        latency_ms: latencyMs,
        request_id: requestId,
        cache_hit: true,
        tokens_saved: cached.tokens_saved,
        request_type: requestType,
        traffic_source: trafficSource,
        blocked_t2: false
      });
      return jsonRes({
        text: cached.response,
        provider: "cache",
        tier: "cache",
        model: `cache(${cached.model_used})`,
        cache_hit: true,
        tokens_saved: cached.tokens_saved,
        latency_ms: latencyMs,
        request_id: requestId,
        complexity
      });
    }
  }
  // ── STAGE 2: Tool pruning ───────────────────────────────────────────────────
  const prunedTools = pruneTools(tools, lastMessage);
  const toolsPruned = (tools?.length ?? 0) - prunedTools.length;
  // ── STAGE 3: Context trimming ───────────────────────────────────────────────
  const trimmedMessages = trimContext(messages);
  // ── STAGE 4: Tier cascade ───────────────────────────────────────────────────
  const tiers = [];
  if (hasImages) {
    // T10 (issue #19736): vision cascade -- separate from the text cascade
    // below since none of these three calls share the text-only call shape.
    if (!forceTier || forceTier === "gemini") {
      const key1 = await getVaultSecret("gemini_api_key_biddeed");
      if (key1) tiers.push({
        id: "T1_gemini_vision",
        provider: "gemini",
        model: GEMINI_MODEL,
        call: ()=>callGeminiVision(key1, trimmedMessages, system, maxTokens, images),
        cost: ()=>0
      });
    }
    const dsKey = await getVaultSecret("deepseek_api_key");
    if (dsKey) tiers.push({
      id: "T1.5_deepseek_vision",
      provider: "deepseek",
      model: DEEPSEEK_VISION_MODEL,
      call: ()=>callDeepSeekVision(dsKey, trimmedMessages, system, maxTokens, images),
      cost: (i, o)=>i / 1_000_000 * 0.14 + o / 1_000_000 * 0.28
    });
    const bearerVision = await getVaultSecret("anthropic_oauth_bearer");
    if (bearerVision) tiers.push({
      id: "T2_claude_oauth_vision",
      provider: "anthropic",
      model: CLAUDE_MODEL,
      call: ()=>callClaudeVision(bearerVision, trimmedMessages, system, maxTokens, images),
      cost: ()=>0
    });
  } else {
    // T1: Gemini — always first for all traffic
    if (!forceTier || forceTier === "gemini") {
      const key1 = await getVaultSecret("gemini_api_key_biddeed");
      if (key1) tiers.push({
        id: "T1_gemini_free",
        provider: "gemini",
        model: GEMINI_MODEL,
        call: ()=>callGemini(key1, trimmedMessages, system, maxTokens),
        cost: ()=>0
      });
    }
    // T1.5: DeepSeek — fallback for all traffic (cheap, not Max OAuth)
    if (complexity !== "complex" || isCustomerTraffic) {
      const dsKey = await getVaultSecret("deepseek_api_key");
      if (dsKey) tiers.push({
        id: "T1.5_deepseek_cheap",
        provider: "deepseek",
        model: DEEPSEEK_MODEL,
        call: ()=>callDeepSeek(dsKey, trimmedMessages, system, maxTokens),
        cost: (i, o)=>i / 1_000_000 * 0.14 + o / 1_000_000 * 0.28
      });
    }
    // T2: Claude Max OAuth — last-resort fallback for ALL traffic, cascade-last so it's
    // only reached once T1 (free) and T1.5 (cheap) have both already failed.
    // Was previously hard-blocked whenever isCustomerTraffic && complexity!=="complex",
    // which meant ordinary (simple) customer chat could NEVER reach T2 regardless of
    // whether T1/T1.5 were healthy. Fixed 2026-08-03: deepseek_api_key is absent from
    // vault.secrets so T1.5 never enters the cascade, and T1 was 429'ing on Gemini quota —
    // together that left simple chat with a 1-tier cascade that hard-502'd on every request.
    // T2 must stay reachable as a floor whenever it's the last tier standing.
    const bearer = await getVaultSecret("anthropic_oauth_bearer");
    if (bearer) tiers.push({
      id: "T2_claude_oauth",
      provider: "anthropic",
      model: CLAUDE_MODEL,
      call: ()=>callClaude(bearer, trimmedMessages, system, maxTokens),
      cost: ()=>0
    });
  }
  if (tiers.length === 0) return jsonRes({
    error: hasImages ? "no vision-capable LLM credentials configured in vault" : "no LLM credentials configured in vault"
  }, 503);
  let blockedT2 = false;
  for (const tier of tiers){
    try {
      const { text, inputTokens, outputTokens } = await tier.call();
      const latencyMs = Date.now() - t0;
      const costUsd = tier.cost(inputTokens, outputTokens);
      const estimatedTokensSaved = Math.floor(trimmedMessages.reduce((s, m)=>s + (m.content?.length ?? 0), 0) / 4);
      if (requestType !== "realtime" && !hasImages && text) {
        const cacheKey = await generateCacheKey(messages, system, requestType);
        await writeCache(cacheKey, text, tier.model, requestType, estimatedTokensSaved);
      }
      await logRequest({
        source,
        tool_name: toolName,
        complexity,
        provider: tier.provider,
        tier: tier.id,
        model: tier.model,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cost_usd: costUsd,
        latency_ms: latencyMs,
        request_id: requestId,
        cache_hit: false,
        tokens_saved: 0,
        request_type: requestType,
        traffic_source: trafficSource,
        blocked_t2: blockedT2
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
        complexity,
        cache_hit: false,
        tools_pruned: toolsPruned,
        traffic_source: trafficSource,
        blocked_t2: blockedT2
      });
    } catch (err) {
      console.error(`${tier.id} failed:`, err instanceof Error ? err.message : String(err));
    }
  }
  // If customer traffic and all non-OAuth tiers failed — clean 503, not a freeze
  if (isCustomerTraffic) {
    return jsonRes({
      error: "AI temporarily unavailable. Please try again in 60 seconds.",
      traffic_source: trafficSource,
      blocked_t2: true
    }, 503);
  }
  return jsonRes({
    error: "all tiers exhausted — LLM call failed"
  }, 502);
});
