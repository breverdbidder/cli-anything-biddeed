// Supabase Edge Function: elevenlabs-upload-file
// Proxies a file upload into an active ElevenLabs conversation.
// Browser never sees the ElevenLabs API key.
// Client POSTs multipart/form-data: conversation_id (text field) + file
// Forwards to POST /v1/convai/conversations/:conversation_id/files with xi-api-key.
// Returns { file_id } on success.
// Max 20MB, PDF/image only (per ElevenLabs knowledge-base doc limits for this endpoint's file types).

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "https://biddeed.ai",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "content-type",
};
const MAX_BYTES = 20 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"]);

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "POST only" }), {
      status: 405, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  let conversationId = "";
  let file: File | null = null;

  try {
    const form = await req.formData();
    conversationId = String(form.get("conversation_id") ?? "");
    const f = form.get("file");
    if (f instanceof File) file = f;
  } catch {
    return new Response(JSON.stringify({ error: "invalid multipart form" }), {
      status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  if (!conversationId || !file) {
    return new Response(JSON.stringify({ error: "conversation_id and file required" }), {
      status: 400, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
  if (file.size > MAX_BYTES) {
    return new Response(JSON.stringify({ error: "file exceeds 20MB limit" }), {
      status: 413, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
  if (!ALLOWED_TYPES.has(file.type)) {
    return new Response(JSON.stringify({ error: `unsupported file type: ${file.type}. PDF and images only.` }), {
      status: 415, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  try {
    const { data: apiKey, error: vaultError } = await supabase.rpc(
      "get_vault_secret_mcp",
      { p_name: "elevenlabs_api_key" }
    );
    if (vaultError || !apiKey) throw new Error(`Vault lookup failed: ${vaultError?.message ?? "no key returned"}`);

    const upstreamForm = new FormData();
    upstreamForm.append("file", file, file.name);

    const elevenRes = await fetch(
      `https://api.elevenlabs.io/v1/convai/conversations/${encodeURIComponent(conversationId)}/files`,
      { method: "POST", headers: { "xi-api-key": apiKey }, body: upstreamForm }
    );

    if (!elevenRes.ok) {
      const body = await elevenRes.text();
      await supabase.from("deed_file_uploads").insert({
        conversation_id: conversationId, mime_type: file.type, size_bytes: file.size,
        status: "failed", error: `${elevenRes.status}: ${body.slice(0, 500)}`,
        origin: req.headers.get("origin"),
      });
      throw new Error(`ElevenLabs upload failed (${elevenRes.status}): ${body}`);
    }

    const { file_id } = await elevenRes.json();

    await supabase.from("deed_file_uploads").insert({
      conversation_id: conversationId, file_id, mime_type: file.type, size_bytes: file.size,
      status: "uploaded", origin: req.headers.get("origin"),
    });

    return new Response(JSON.stringify({ file_id }), {
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("elevenlabs-upload-file error:", err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500, headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});
