// Supabase Edge Function: elevenlabs-signed-url
// Purpose: browser never sees the ElevenLabs API key. Client POSTs { agent_id },
// this function pulls the key from Supabase Vault and exchanges it for a
// short-lived signed WebSocket URL.
// Vault secret: elevenlabs_api_key (must be a real sk_ key, not a key ID)
// RPC: get_vault_secret_mcp(p_name text)  -- arg is p_name, NOT secret_name

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "https://biddeed.ai",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "POST only" }), {
      status: 405, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
  try {
    const { agent_id } = await req.json();
    if (!agent_id) {
      return new Response(JSON.stringify({ error: "agent_id required" }), {
        status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );
    const { data: apiKey, error: vaultError } = await supabase.rpc(
      "get_vault_secret_mcp", { p_name: "elevenlabs_api_key" }
    );
    if (vaultError || !apiKey) {
      throw new Error(`Vault lookup failed: ${vaultError?.message ?? "no key returned"}`);
    }
    const elevenRes = await fetch(
      `https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=${encodeURIComponent(agent_id)}`,
      { headers: { "xi-api-key": apiKey } }
    );
    if (!elevenRes.ok) {
      const body = await elevenRes.text();
      throw new Error(`ElevenLabs signed-url failed (${elevenRes.status}): ${body}`);
    }
    const { signed_url } = await elevenRes.json();
    supabase.from("widget_session_log").insert({
      agent_id, origin: req.headers.get("origin"),
    }).then(() => {}, () => {});
    return new Response(JSON.stringify({ signed_url }), {
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("elevenlabs-signed-url error:", err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});
