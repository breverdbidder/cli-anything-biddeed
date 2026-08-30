// Cloudflare Pages Function: POST /api/quote
//
// Validates the manual Get-a-Quote FF submission and writes it to the
// agency's intake table (env.SUPABASE_TABLE) via the Supabase service role
// (RLS is ON with no anon policy -- this Function is the only write path for
// the manual-form path; /api/canopy-complete and /api/canopy-webhook are the
// other two write paths, for the Canopy Connect flow).
//
// The prior AMS delivery-webhook forward (issue #19405 v1) is retired as of
// issue #19600 -- Mariam chose EZLynx + Canopy Connect instead. There is no
// equivalent forward here on purpose; EZLynx has no public write API, and
// the real integration path (Canopy's EZLynx Marketplace connector) lives
// entirely inside Canopy's own dashboard, not in this codebase. See README.
import { createClient } from "@supabase/supabase-js";

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE: string;
  SUPABASE_TABLE: string;
}

interface QuotePayload {
  schema_version?: string;
  source?: string;
  product_line?: string;
  applicant?: {
    entity_name?: { value?: string | null };
    contact_phone?: { value?: string | null };
    [key: string]: unknown;
  };
  property?: Record<string, unknown>;
  quote_request?: Record<string, unknown>;
  consent?: {
    tcpa_given?: boolean;
    consent_version?: string;
  };
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env } = context;

  let body: QuotePayload;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON body." }, 400);
  }

  const entityName = body.applicant?.entity_name?.value?.toString().trim();
  const contactPhone = body.applicant?.contact_phone?.value?.toString().trim();
  const tcpaGiven = body.consent?.tcpa_given === true;

  const errors: string[] = [];
  if (!entityName) errors.push("applicant.entity_name.value is required");
  if (!contactPhone) errors.push("applicant.contact_phone.value is required");
  if (!tcpaGiven) errors.push("TCPA consent is required");

  if (errors.length > 0) {
    return jsonResponse({ error: "Validation failed", details: errors }, 400);
  }

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE || !env.SUPABASE_TABLE) {
    console.error("[quote.ts] Missing SUPABASE_URL, SUPABASE_SERVICE_ROLE, or SUPABASE_TABLE env var");
    return jsonResponse({ error: "Server is not configured to accept submissions right now." }, 500);
  }

  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For") ||
    null;
  const submittedAt = new Date().toISOString();

  const consentRecord = {
    tcpa_given: true,
    consent_version: body.consent?.consent_version || null,
    ip,
    submitted_at: submittedAt,
    user_agent: request.headers.get("User-Agent") || null,
  };

  const payloadRecord = {
    schema_version: body.schema_version || "1.0",
    generated_at: submittedAt,
    product_line: body.product_line || null,
    applicant: body.applicant || {},
    property: body.property || {},
    quote_request: body.quote_request || {},
  };

  const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE, {
    auth: { persistSession: false },
  });

  const { data, error } = await supabase
    .from(env.SUPABASE_TABLE)
    .insert({
      payload: payloadRecord,
      consent: consentRecord,
      source: "website",
      status: "new",
    })
    .select("id")
    .single();

  if (error) {
    console.error("[quote.ts] Supabase insert failed:", error.message);
    return jsonResponse({ error: "Could not save your request. Please call us instead." }, 500);
  }

  return jsonResponse({ ok: true, id: data.id }, 200);
};
