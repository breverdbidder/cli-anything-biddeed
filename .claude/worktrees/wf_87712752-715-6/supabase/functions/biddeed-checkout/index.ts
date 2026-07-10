// supabase/functions/biddeed-checkout/index.ts
//
// biddeed-checkout — creates a Stripe Checkout Session for a trial→paid
// upgrade (investor/pro/proplus). Called from the B2C page at
// biddeed.ai/biddeed-mcp/start/ when a trial user clicks "Upgrade".
//
// Request:  { api_key: string, tier: 'investor'|'pro'|'proplus' }
// Response: { url, session_id }
//
// SPRINT3 P0-3. EG14: no live product/price mutation — only reads existing
// stripe_products rows and creates a Checkout Session (no charge occurs until
// the customer completes the hosted Stripe page).

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}

const SELLABLE_TIERS = ["investor", "pro", "proplus"]; // enterprise = custom quote, not self-serve
const BASE_URL = "https://biddeed.ai/biddeed-mcp/start/";

async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Vault-first: get_vault_secret_mcp('stripe_secret_key') is the verified,
// deployed RPC (see 20260702_b2c_outbox_drain.sql corrective note — a prior
// sprint found `vault_secret` doesn't exist; this is the real one). Falls
// back to STRIPE_SECRET_KEY env only if the vault entry is ever removed.
async function resolveStripeKey(): Promise<string | null> {
  const { data, error } = await supabase.rpc("get_vault_secret_mcp", { p_name: "stripe_secret_key" });
  if (!error && data) return String(data);
  return Deno.env.get("STRIPE_SECRET_KEY") ?? null;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS });
  }
  if (req.method !== "POST") {
    return jsonRes({ error: "POST required" }, 405);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return jsonRes({ error: "invalid JSON body" }, 400);
  }

  const { api_key: apiKey, tier } = body;
  if (!apiKey || typeof apiKey !== "string") {
    return jsonRes({ error: "api_key required" }, 400);
  }
  if (!SELLABLE_TIERS.includes(tier)) {
    return jsonRes({ error: `tier must be one of: ${SELLABLE_TIERS.join(", ")}` }, 400);
  }

  const keyHash = await sha256Hex(apiKey);
  const { data: keyRows, error: keyErr } = await supabase
    .from("mcp_api_keys")
    .select("customer_id, key_prefix")
    .eq("key_hash", keyHash)
    .limit(1);
  if (keyErr || !keyRows?.length) {
    return jsonRes({ error: "invalid api_key" }, 401);
  }
  const { customer_id: customerId, key_prefix: keyPrefix } = keyRows[0];

  const { data: customerRows } = await supabase
    .from("mcp_customers")
    .select("email")
    .eq("customer_id", customerId)
    .limit(1);
  const email = customerRows?.[0]?.email ?? null;

  const { data: productRows, error: productErr } = await supabase
    .from("stripe_products")
    .select("stripe_price_id_monthly")
    .eq("tier_id", tier)
    .limit(1);
  const priceId = productRows?.[0]?.stripe_price_id_monthly;
  if (productErr || !priceId) {
    return jsonRes({ error: `no monthly price configured for tier '${tier}'` }, 500);
  }

  const stripeKey = await resolveStripeKey();
  if (!stripeKey) {
    return jsonRes({ error: "stripe key not configured (vault + env both empty)" }, 503);
  }

  const params = new URLSearchParams({
    mode: "subscription",
    "line_items[0][price]": priceId,
    "line_items[0][quantity]": "1",
    success_url: `${BASE_URL}?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${BASE_URL}?checkout=cancelled`,
    "metadata[customer_id]": customerId,
    "metadata[key_prefix]": keyPrefix,
    "metadata[tier_id]": tier,
    allow_promotion_codes: "true",
  });
  if (email) params.set("customer_email", email);

  const stripeRes = await fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${stripeKey}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: params,
  });

  if (!stripeRes.ok) {
    const errText = await stripeRes.text();
    console.error("stripe checkout.sessions.create failed:", stripeRes.status, errText.slice(0, 300));
    return jsonRes({ error: "stripe session creation failed" }, 502);
  }

  const session = await stripeRes.json();

  const { data: tierRow } = await supabase
    .from("mcp_subscription_tiers")
    .select("price_monthly_usd")
    .eq("tier_id", tier)
    .limit(1);
  const amountUsd = session.amount_total != null
    ? session.amount_total / 100
    : Number(tierRow?.[0]?.price_monthly_usd ?? 0);

  const { error: insertErr } = await supabase.from("stripe_checkout_sessions").insert({
    session_id: session.id,
    customer_id: customerId,
    tier_id: tier,
    billing_interval: "monthly",
    amount_usd: amountUsd,
    status: "pending",
    expires_at: session.expires_at ? new Date(session.expires_at * 1000).toISOString() : null,
  });
  if (insertErr) {
    console.error("stripe_checkout_sessions insert failed:", insertErr.message);
    return jsonRes({ error: "session created in Stripe but failed to record locally" }, 500);
  }

  return jsonRes({ url: session.url, session_id: session.id });
});
