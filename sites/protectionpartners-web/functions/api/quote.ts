// Cloudflare Pages Function: POST /api/quote
//
// Validates the Get-a-Quote FF submission, writes it to
// public.protection_partners_intake via the Supabase service role (RLS is ON
// with no anon policy -- this Function is the only write path), and -- if
// MOMENTUM_DELIVERY_URL is configured -- forwards the payload to the #19404
// delivery bridge. Absent that env var, the forward is skipped silently and
// logged to console, per the issue spec.
import { createClient } from "@supabase/supabase-js";

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE: string;
  MOMENTUM_DELIVERY_URL?: string;
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

  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE) {
    console.error("[quote.ts] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE env var");
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
    .from("protection_partners_intake")
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

  if (env.MOMENTUM_DELIVERY_URL) {
    try {
      await fetch(env.MOMENTUM_DELIVERY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: data.id, ...payloadRecord }),
      });
    } catch (deliveryError) {
      // Delivery to Momentum is best-effort -- the lead is already durably
      // stored in protection_partners_intake regardless of this outcome.
      console.error("[quote.ts] Momentum delivery hook failed:", deliveryError);
    }
  } else {
    console.log("[quote.ts] MOMENTUM_DELIVERY_URL not set -- skipping delivery hook.");
  }

  return jsonResponse({ ok: true, id: data.id }, 200);
};
