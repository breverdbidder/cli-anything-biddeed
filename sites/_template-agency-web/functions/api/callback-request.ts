// Cloudflare Pages Function: POST /api/callback-request
//
// Secondary/fallback intake path (issue #19602 Task 1): minimal capture for
// prospects who'd rather have a producer call them than use Canopy Connect,
// a dec-page upload, or the full quote form. Same TCPA consent basis and
// write pattern as functions/api/quote.ts, just a shorter required-field
// set (name, phone, best_time, consent).
import { createClient } from "@supabase/supabase-js";

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE: string;
  SUPABASE_TABLE: string;
}

interface CallbackPayload {
  name?: string;
  phone?: string;
  best_time?: string;
  tcpa_consent?: boolean;
  consent_version?: string;
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  let body: CallbackPayload;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body." }, 400);
  }

  const name = body.name?.toString().trim();
  const phone = body.phone?.toString().trim();
  const tcpaGiven = body.tcpa_consent === true;

  const errors: string[] = [];
  if (!name) errors.push("name is required");
  if (!phone) errors.push("phone is required");
  if (!tcpaGiven) errors.push("TCPA consent is required");

  if (errors.length > 0) {
    // Validation failed -- return before touching the DB. Zero writes on a
    // missing-consent submission, per DoD item 4.
    return jsonResponse({ error: "Validation failed", details: errors }, 400);
  }

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE || !env.SUPABASE_TABLE) {
    console.error("[callback-request.ts] Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE, or SUPABASE_TABLE env var");
    return jsonResponse({ error: "Server is not configured to accept requests right now." }, 500);
  }

  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For") ||
    null;
  const submittedAt = new Date().toISOString();

  const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
  });

  const { data, error } = await supabase
    .from(env.SUPABASE_TABLE)
    .insert({
      payload: {
        schema_version: "1.0",
        generated_at: submittedAt,
        applicant: {
          entity_name: { value: name, source: "callback_form" },
          contact_phone: { value: phone, source: "callback_form" },
        },
        callback: { best_time: body.best_time || null },
      },
      consent: {
        tcpa_given: true,
        consent_version: body.consent_version || null,
        ip,
        submitted_at: submittedAt,
        user_agent: request.headers.get("User-Agent") || null,
      },
      source: "callback_request",
      status: "new",
    })
    .select("id")
    .single();

  if (error) {
    console.error("[callback-request.ts] Supabase insert failed:", error.message);
    return jsonResponse({ error: "Could not save your request. Please call us instead." }, 500);
  }

  return jsonResponse({ ok: true, id: data.id }, 200);
};
