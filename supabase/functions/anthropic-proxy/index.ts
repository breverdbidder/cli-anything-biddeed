// supabase/functions/anthropic-proxy/index.ts
//
// Anthropic Messages API-compatible HTTP proxy. Translates between
// the Messages API surface (used by anthropics/claude-code-action and
// any other Anthropic SDK consumer) and the in-Postgres Smart Router
// (ecu_route_chat_llm), which enforces:
//   1. Claude Max OAuth bearer is tier 1
//   2. Gemini 2.5 Flash (free) is tier 2 fallback
//   3. ANTHROPIC_API_KEY is BLOCKED per ariel-rule
//
// Caller authentication uses a router-issued bearer token
// (ROUTER_PROXY_KEY), not Anthropic's. The proxy key lives in
// vault.router_proxy_key and is validated inside the Postgres
// wrapper function.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers":
    "Content-Type, Authorization, x-api-key, anthropic-version, anthropic-beta, x-stainless-arch, x-stainless-lang, x-stainless-os, x-stainless-package-version, x-stainless-runtime, x-stainless-runtime-version",
};

function jsonResponse(body: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...CORS_HEADERS, ...extra },
  });
}

function errorResponse(type: string, message: string, status = 400): Response {
  return jsonResponse({ type: "error", error: { type, message } }, status);
}

function extractProxyKey(req: Request): string | null {
  const xApiKey = req.headers.get("x-api-key");
  if (xApiKey && xApiKey.trim()) return xApiKey.trim();

  const auth = req.headers.get("authorization");
  if (auth && /^bearer\s+/i.test(auth)) {
    return auth.replace(/^bearer\s+/i, "").trim();
  }
  return null;
}

/**
 * Convert a complete non-streaming Anthropic Messages API response
 * into an SSE event stream that mimics streaming. Used when the
 * caller sets `stream: true` but the underlying router only
 * returned a full response (Gemini and PG-side Claude are both
 * synchronous today).
 */
function asAnthropicSSE(response: any): Response {
  const encoder = new TextEncoder();
  const msgId = response.id ?? `msg_${crypto.randomUUID().replace(/-/g, "")}`;
  const model = response.model ?? "unknown";
  const usage = response.usage ?? { input_tokens: 0, output_tokens: 0 };
  const content: any[] = Array.isArray(response.content) ? response.content : [];
  const stopReason = response.stop_reason ?? "end_turn";

  const stream = new ReadableStream({
    start(controller) {
      const emit = (event: string, data: unknown) => {
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      };

      emit("message_start", {
        type: "message_start",
        message: {
          id: msgId,
          type: "message",
          role: "assistant",
          model,
          content: [],
          stop_reason: null,
          stop_sequence: null,
          usage: { input_tokens: usage.input_tokens ?? 0, output_tokens: 0 },
        },
      });

      content.forEach((block, idx) => {
        if (block.type === "text") {
          emit("content_block_start", {
            type: "content_block_start",
            index: idx,
            content_block: { type: "text", text: "" },
          });
          emit("content_block_delta", {
            type: "content_block_delta",
            index: idx,
            delta: { type: "text_delta", text: block.text ?? "" },
          });
          emit("content_block_stop", { type: "content_block_stop", index: idx });
        } else if (block.type === "tool_use") {
          emit("content_block_start", {
            type: "content_block_start",
            index: idx,
            content_block: {
              type: "tool_use",
              id: block.id,
              name: block.name,
              input: {},
            },
          });
          emit("content_block_delta", {
            type: "content_block_delta",
            index: idx,
            delta: {
              type: "input_json_delta",
              partial_json: JSON.stringify(block.input ?? {}),
            },
          });
          emit("content_block_stop", { type: "content_block_stop", index: idx });
        }
      });

      emit("message_delta", {
        type: "message_delta",
        delta: { stop_reason: stopReason, stop_sequence: null },
        usage: { output_tokens: usage.output_tokens ?? 0 },
      });

      emit("message_stop", { type: "message_stop" });
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "connection": "keep-alive",
      "x-accel-buffering": "no",
      ...CORS_HEADERS,
    },
  });
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const url = new URL(req.url);

  // Health check
  if (url.pathname.endsWith("/health") && req.method === "GET") {
    return jsonResponse({
      status: "ok",
      service: "anthropic-proxy",
      router: "ecu_route_chat_llm",
      ariel_rule: "anthropic_api_key BLOCKED at router level",
    });
  }

  // Main endpoint
  if (!url.pathname.endsWith("/v1/messages")) {
    return errorResponse(
      "not_found",
      `${url.pathname} not supported. POST /v1/messages or GET /health.`,
      404,
    );
  }

  if (req.method !== "POST") {
    return errorResponse("method_not_allowed", `${req.method} not allowed`, 405);
  }

  const proxyKey = extractProxyKey(req);
  if (!proxyKey) {
    return errorResponse(
      "authentication_error",
      "missing x-api-key or Authorization: Bearer header",
      401,
    );
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return errorResponse("invalid_request_error", "request body is not valid JSON", 400);
  }

  const wantsStream = body?.stream === true;

  const { data, error } = await supabase.rpc("anthropic_messages_proxy", {
    p_request: body,
    p_proxy_key: proxyKey,
  });

  if (error) {
    console.error("anthropic_messages_proxy RPC error:", error);
    return errorResponse("api_error", error.message ?? "router_rpc_failed", 502);
  }

  // Error envelope from the wrapper function
  if (data?.error) {
    const errType = data.error.type ?? "api_error";
    const httpStatus =
      errType === "authentication_error" ? 401 :
      errType === "invalid_request_error" ? 400 :
      errType.startsWith("API_ERROR_") ? 502 :
      500;
    return jsonResponse(data, httpStatus);
  }

  if (wantsStream) {
    return asAnthropicSSE(data);
  }

  return jsonResponse(data, 200);
});
