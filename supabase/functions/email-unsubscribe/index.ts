// supabase/functions/email-unsubscribe/index.ts
//
// GTM-5 (#20034): one-click unsubscribe endpoint for the biddeed-daily-digest
// (and any future) outbound email. Backs both the human-facing "Unsubscribe"
// link in the footer and the RFC 8058 List-Unsubscribe-Post one-click header
// (mail clients POST here with no user interaction, so this must be a plain
// unauthenticated endpoint -- the HMAC signature is the only gate, proving
// the link was minted by our own send, not guessed/enumerated).
//
// Writes ONLY to the new public.email_opt_outs table (additive, RLS on --
// see 20260905c_gtm5_digest_consent_20034.sql). Never touches lead_profiles:
// per intent guardrail #3, lead_profiles rows are never deleted, and the
// consent gate in scripts/biddeed-daily-digest.cjs checks email_opt_outs
// independently of lead_profiles.email_consent/marketing_consent so a stale
// or re-flipped consent flag can never override an explicit unsubscribe.
//
// Request:  GET  /email-unsubscribe?email=<addr>&sig=<hmac-hex>   (link click)
//           POST /email-unsubscribe?email=<addr>&sig=<hmac-hex>   (one-click, RFC 8058)
// Response: 200 text/html (GET) or 200 text/plain (POST) confirming opt-out.
// Bad/missing signature: 403, no row written -- prevents mass-unsubscribing
// arbitrary addresses that never received a signed link from us.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

async function hmacHex(secret: string, message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function html(body: string, status = 200): Response {
  return new Response(
    `<!DOCTYPE html><html><body style="font-family:Inter,Arial,sans-serif;background:#020617;color:#e2e8f0;padding:40px;text-align:center;">${body}</body></html>`,
    { status, headers: { "content-type": "text/html" } },
  );
}

Deno.serve(async (req: Request) => {
  if (req.method !== "GET" && req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const url = new URL(req.url);
  const email = url.searchParams.get("email")?.trim().toLowerCase();
  const sig = url.searchParams.get("sig");

  if (!email || !sig) {
    return html("Missing unsubscribe link parameters.", 400);
  }

  const { data: secret, error: secretErr } = await supabase.rpc("cli_anything_get_secret", {
    p_name: "cli_anything_shared_secret",
  });
  if (secretErr || !secret) {
    console.error("email-unsubscribe: could not load signing secret", secretErr?.message);
    return html("Unsubscribe is temporarily unavailable. Please try again shortly.", 500);
  }

  const expected = await hmacHex(secret, email);
  if (expected !== sig) {
    return html("This unsubscribe link is invalid.", 403);
  }

  const { error: upsertErr } = await supabase
    .from("email_opt_outs")
    .upsert(
      { email, source: "list_unsubscribe", reason: `${req.method} one-click unsubscribe` },
      { onConflict: "email", ignoreDuplicates: true },
    );

  if (upsertErr) {
    console.error("email-unsubscribe: opt-out write failed", upsertErr.message);
    return html("Something went wrong recording your unsubscribe. Please try again.", 500);
  }

  if (req.method === "POST") {
    return new Response("unsubscribed", { status: 200, headers: { "content-type": "text/plain" } });
  }
  return html("You're unsubscribed from BidDeed.AI emails. You won't receive any more digests.");
});
