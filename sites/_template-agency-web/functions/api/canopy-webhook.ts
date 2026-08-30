// Cloudflare Pages Function: POST /api/canopy-webhook
//
// Server-side completion path for Canopy Connect, registered on Canopy's
// dashboard (Settings -> Webhooks) or via their Webhooks API -- a manual
// step, see README. Canopy documents these event_type values: AUTH_STATUS,
// POLICY_AVAILABLE, POLICIES_AVAILABLE, COMPLETE, ERROR,
// MONITORING_RECONNECT, DATA_UPDATED, SERVICING_WAITING_FOR_CONSUMER_CONFIRMATION,
// MONITORING_EVENTS. Every payload carries a pull_id
// (https://docs.usecanopy.com/reference/about-webhooks).
//
// This upserts by pull_id so it's a no-op-safe complement to the client-side
// /api/canopy-complete callback -- whichever fires first creates the row,
// the other just updates status/payload.
//
// Known gap (flagged, not fixed): Canopy's public docs do not specify a
// webhook signing/verification mechanism. Do not treat this endpoint as
// trusted-by-default in production -- ask Canopy support for their signing
// scheme before relying on this for anything beyond a best-effort status
// mirror, and prefer the client-side /api/canopy-complete write as the
// source of truth for "a lead exists."
import { createClient } from "@supabase/supabase-js";

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE: string;
  SUPABASE_TABLE: string;
}

interface CanopyWebhookPayload {
  event_type?: string;
  pull_id?: string;
  pull?: { pull_id?: string; [key: string]: unknown };
  [key: string]: unknown;
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const STATUS_BY_EVENT: Record<string, string> = {
  AUTH_STATUS: "connecting",
  POLICY_AVAILABLE: "enriching",
  POLICIES_AVAILABLE: "enriched",
  COMPLETE: "complete",
  ERROR: "error",
  MONITORING_RECONNECT: "needs_reconnect",
  DATA_UPDATED: "enriched",
  SERVICING_WAITING_FOR_CONSUMER_CONFIRMATION: "awaiting_confirmation",
  MONITORING_EVENTS: "enriched",
};

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  let body: CanopyWebhookPayload;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body." }, 400);
  }

  const pullId = (body.pull_id || body.pull?.pull_id)?.toString().trim();
  if (!pullId) {
    return jsonResponse({ error: "Validation failed", details: ["pull_id is required"] }, 400);
  }

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE || !env.SUPABASE_TABLE) {
    console.error("[canopy-webhook.ts] Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE, or SUPABASE_TABLE env var");
    return jsonResponse({ error: "Server is not configured right now." }, 500);
  }

  const submittedAt = new Date().toISOString();
  const status = STATUS_BY_EVENT[body.event_type || ""] || "new";
  const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
  });

  const { error } = await supabase.from(env.SUPABASE_TABLE).upsert(
    {
      pull_id: pullId,
      payload: { pull_id: pullId, canopy_webhook_event: body.event_type || null, canopy_webhook_payload: body },
      consent: { basis: "canopy_connect_authentication", captured_at: submittedAt },
      source: "canopy_connect",
      status,
    },
    { onConflict: "pull_id", ignoreDuplicates: false }
  );

  if (error) {
    console.error("[canopy-webhook.ts] Supabase upsert failed:", error.message);
    return jsonResponse({ error: "Could not process webhook." }, 500);
  }

  return jsonResponse({ ok: true }, 200);
};
