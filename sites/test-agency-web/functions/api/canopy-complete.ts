// Cloudflare Pages Function: POST /api/canopy-complete
//
// Client-side completion callback for the Canopy Connect "Pull" widget
// (CanopyConnectWidget.astro calls this from the `authenticationSuccess`
// event). This is our own parallel record -- the actual EZLynx push happens
// separately, inside Canopy's EZLynx Marketplace connector on Canopy's own
// servers, not through this endpoint. See README's EZLynx integration note.
//
// Deliberately does NOT enforce the site's TCPA marketing-contact consent
// gate the way /api/quote does: authorizing a Canopy Connect pull is Canopy's
// own carrier-authentication consent flow, a different consent basis than
// "call/text me for marketing." Documented as a deviation in README.
import { createClient } from "@supabase/supabase-js";

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE: string;
  SUPABASE_TABLE: string;
}

interface CanopyCompletePayload {
  pull_id?: string;
  metadata?: Record<string, unknown> | null;
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  let body: CanopyCompletePayload;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body." }, 400);
  }

  const pullId = body.pull_id?.toString().trim();
  if (!pullId) {
    return jsonResponse({ error: "Validation failed", details: ["pull_id is required"] }, 400);
  }

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE || !env.SUPABASE_TABLE) {
    console.error("[canopy-complete.ts] Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE, or SUPABASE_TABLE env var");
    return jsonResponse({ error: "Server is not configured right now." }, 500);
  }

  const submittedAt = new Date().toISOString();
  const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
  });

  // Upsert on pull_id: a webhook (functions/api/canopy-webhook.ts) may have
  // already created this row if Canopy's server-side event beat the
  // client-side callback here, or vice versa.
  const { data, error } = await supabase
    .from(env.SUPABASE_TABLE)
    .upsert(
      {
        pull_id: pullId,
        payload: { pull_id: pullId, canopy_metadata: body.metadata || null, generated_at: submittedAt },
        consent: { basis: "canopy_connect_authentication", captured_at: submittedAt },
        source: "canopy_connect",
        status: "new",
      },
      { onConflict: "pull_id", ignoreDuplicates: false }
    )
    .select("id")
    .single();

  if (error) {
    console.error("[canopy-complete.ts] Supabase upsert failed:", error.message);
    return jsonResponse({ error: "Could not save your connection. Please use the quote form instead." }, 500);
  }

  return jsonResponse({ ok: true, id: data.id }, 200);
};
