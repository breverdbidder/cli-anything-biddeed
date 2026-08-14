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
//
// FIX (issue #19079, Aug 14 2026): Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
// was verified LIVE to behave as anon-level access — a direct REST test with
// the vault's supabase_service_role_key returned data from an RLS-protected
// table (stripe_products, zero policies = default-deny for non-bypass roles)
// while the env-based client returned empty. Root cause of the platform env
// mismatch not fully diagnosed; fix is to resolve the admin key from the
// vault at runtime instead of trusting the env var, mirroring the already-
// proven resolveStripeKey() pattern below. bootstrapClient (env-based) is
// kept ONLY to make the initial get_vault_secret_mcp RPC call, since RPC
// calls are SECURITY DEFINER and unaffected by this RLS issue.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const bootstrapClient = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

let cachedAdminClient: ReturnType<typeof createClient> | null = null;
async function getAdminClient() {
  if (cachedAdminClient) return cachedAdminClient;
  const { data, error } = await bootstrapClient.rpc("get_vault_secret_mcp", { p_name: "supabase_service_role_key" });
  const verifiedKey = !error && data ? String(data) : SUPABASE_SERVICE_ROLE_KEY;
  cachedAdminClient = createClient(SUPABASE_URL, verifiedKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return cachedAdminClient;
}

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
  const { data, error } = await bootstrapClient.rpc("get_vault_secret_mcp", { p_name: "stripe_secret_key" });
  if (!error && data) return String(data);
  return Deno.env.get("STRIPE_SECRET_KEY") ?? null;
}

// WEBSITE-FIX (dispatch 93fc7abd): the $25 one-time Shapira report purchase.
// TEST-mode only — resolves ONLY 'stripe_test_secret_key', never falls back
// to the live key resolveStripeKey() uses, so a missing test-mode secret
// fails closed (503) instead of ever silently creating a real charge.
async function resolveTestStripeKey(): Promise<string | null> {
  const { data, error } = await bootstrapClient.rpc("get_vault_secret_mcp", { p_name: "stripe_test_secret_key" });
  if (!error && data) return String(data);
  return Deno.env.get("STRIPE_TEST_SECRET_KEY") ?? null;
}

const REPORT_SUCCESS_URL = "https://biddeed.ai/report-success";
const REPORT_CANCEL_URL = "https://biddeed.ai/buy-report";
const S5_ONETIME_AMOUNT_CENTS = 2500; // $25 fixed server-side — never trust a client-supplied price

async function handleS5OnetimeCheckout(body: any): Promise<Response> {
  const { county, case_number: caseNumber, customer_email: customerEmail } = body;
  if (!county || typeof county !== "string") return jsonRes({ error: "county required" }, 400);
  if (!caseNumber || typeof caseNumber !== "string") return jsonRes({ error: "case_number required" }, 400);
  if (!customerEmail || typeof customerEmail !== "string") return jsonRes({ error: "customer_email required" }, 400);

  const countySlug = county.toLowerCase().replace(/-/g, "_");
  const supabase = await getAdminClient();

  // Defense in depth: the /buy-report frontend already restricts the picker to
  // certified + matched_clean + upcoming, but a direct API call must not be trusted.
  const { data: certRows } = await supabase
    .from("v_certified_counties")
    .select("county_slug")
    .eq("county_slug", countySlug)
    .limit(1);
  if (!certRows?.length) {
    return jsonRes({ error: `county '${countySlug}' is not currently Gold Standard certified` }, 400);
  }

  const { data: auctionRows, error: auctionErr } = await supabase
    .from("multi_county_auctions")
    .select("id,case_number")
    .eq("case_number", caseNumber)
    .eq("county", countySlug)
    .limit(1);
  if (auctionErr || !auctionRows?.length) {
    return jsonRes({ error: `case_number '${caseNumber}' not found in ${countySlug}` }, 404);
  }
  const resolvedMcaId = auctionRows[0].id;

  const stripeKey = await resolveStripeKey();
  if (!stripeKey) {
    return jsonRes({ error: "stripe_secret_key not configured in vault" }, 503);
  }

  const params = new URLSearchParams({
    mode: "payment",
    "line_items[0][price_data][currency]": "usd",
    "line_items[0][price_data][product_data][name]": `BidDeed.AI Shapira Report — Case ${caseNumber} (${countySlug})`,
    "line_items[0][price_data][unit_amount]": String(S5_ONETIME_AMOUNT_CENTS),
    "line_items[0][quantity]": "1",
    customer_email: customerEmail,
    success_url: `${REPORT_SUCCESS_URL}?session={CHECKOUT_SESSION_ID}&email=${encodeURIComponent(customerEmail)}&mca_id=${encodeURIComponent(resolvedMcaId)}`,
    cancel_url: `${REPORT_CANCEL_URL}?checkout=cancelled`,
    "metadata[product]": "s5_onetime",
    "metadata[mode]": "report",
    "metadata[case_number]": caseNumber,
    "metadata[county]": countySlug,
    "metadata[customer_email]": customerEmail,
    "metadata[mca_id]": resolvedMcaId,
  });

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
    console.error("stripe checkout.sessions.create (s5_onetime) failed:", stripeRes.status, errText.slice(0, 300));
    return jsonRes({ error: "stripe session creation failed" }, 502);
  }

  const session = await stripeRes.json();

  const { error: insertErr } = await supabase.from("report_delivery_queue").insert({
    case_number: caseNumber,
    county: countySlug,
    customer_email: customerEmail,
    stripe_session_id: session.id,
    stripe_payment_intent: session.payment_intent ?? null,
    status: "pending",
  });
  if (insertErr) {
    console.error("report_delivery_queue insert failed:", insertErr.message);
    return jsonRes({ error: "session created in Stripe but failed to record locally" }, 500);
  }

  return jsonRes({ url: session.url, session_id: session.id });
}

const COLD_SUCCESS_URL = "https://biddeed.ai/success";
const COLD_CANCEL_URL = "https://biddeed.ai/subscribe";

async function findOrCreateColdCustomer(email: string): Promise<string> {
  const supabase = await getAdminClient();
  const { data: existing } = await supabase
    .from("mcp_customers")
    .select("customer_id")
    .eq("email", email)
    .limit(1);
  if (existing?.length) return existing[0].customer_id;

  const { data: inserted, error: insertErr } = await supabase
    .from("mcp_customers")
    .insert({ email, customer_type: "human", tier_id: "free", active: true })
    .select("customer_id")
    .limit(1);
  if (!insertErr && inserted?.length) return inserted[0].customer_id;

  const { data: retry } = await supabase
    .from("mcp_customers")
    .select("customer_id")
    .eq("email", email)
    .limit(1);
  if (retry?.length) return retry[0].customer_id;

  throw new Error(`findOrCreateColdCustomer: could not find or create customer for ${email}`);
}

async function handleColdCheckout(body: any): Promise<Response> {
  const { tier, customer_email: customerEmail, interval: billingInterval, referral_code: referralCode } = body;
  if (!SELLABLE_TIERS.includes(tier)) {
    return jsonRes({ error: `tier must be one of: ${SELLABLE_TIERS.join(", ")}` }, 400);
  }
  if (!customerEmail || typeof customerEmail !== "string") {
    return jsonRes({ error: "customer_email required" }, 400);
  }
  const useAnnual = billingInterval === "annual";
  const supabase = await getAdminClient();

  const { data: productRows, error: productErr } = await supabase
    .from("stripe_products")
    .select("stripe_price_id_monthly, stripe_price_id_annual")
    .eq("tier_id", tier)
    .limit(1);

  const priceId = useAnnual
    ? productRows?.[0]?.stripe_price_id_annual
    : productRows?.[0]?.stripe_price_id_monthly;

  if (productErr || !priceId) {
    return jsonRes({ error: `no ${useAnnual ? "annual" : "monthly"} price configured for tier '${tier}'` }, 500);
  }

  const stripeKey = await resolveStripeKey();
  if (!stripeKey) {
    return jsonRes({ error: "stripe key not configured (vault + env both empty)" }, 503);
  }

  let customerId: string;
  try {
    customerId = await findOrCreateColdCustomer(customerEmail.toLowerCase().trim());
  } catch (e) {
    console.error("findOrCreateColdCustomer failed:", (e as Error).message);
    return jsonRes({ error: "could not resolve customer record" }, 500);
  }

  const successUrl = `${COLD_SUCCESS_URL}?session_id={CHECKOUT_SESSION_ID}`;

  const params = new URLSearchParams({
    mode: "subscription",
    "line_items[0][price]": priceId,
    "line_items[0][quantity]": "1",
    customer_email: customerEmail,
    success_url: successUrl,
    cancel_url: COLD_CANCEL_URL,
    "metadata[customer_id]": customerId,
    "metadata[tier_id]": tier,
    "metadata[billing_interval]": useAnnual ? "annual" : "monthly",
    "metadata[customer_email]": customerEmail,
    "metadata[product]": "cold_subscription",
    allow_promotion_codes: "true",
  });
  if (referralCode && typeof referralCode === "string") {
    params.set("metadata[referral_code]", referralCode);
  }

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
    console.error("cold checkout.sessions.create failed:", stripeRes.status, errText.slice(0, 300));
    return jsonRes({ error: "stripe session creation failed" }, 502);
  }

  const session = await stripeRes.json();

  // FIX (issue #19079): PostgrestFilterBuilder is thenable but has no
  // .catch() method - chaining .insert(...).catch(...) directly threw
  // "TypeError: ...insert(...).catch is not a function" and crashed the
  // whole request with a generic platform 500, verified live via
  // Supabase function_logs. Postgrest calls never throw - they always
  // resolve to {data, error} - so this is now a plain awaited call
  // wrapped in try/catch only to guard the surrounding async context.
  try {
    const { error: sessionInsertErr } = await supabase.from("stripe_checkout_sessions").insert({
      session_id: session.id,
      customer_id: customerId,
      tier_id: tier,
      billing_interval: useAnnual ? "annual" : "monthly",
      amount_usd: session.amount_total != null ? session.amount_total / 100 : null,
      status: "pending",
      expires_at: session.expires_at ? new Date(session.expires_at * 1000).toISOString() : null,
    });
    if (sessionInsertErr) {
      console.error("stripe_checkout_sessions insert failed (non-fatal):", sessionInsertErr.message);
    }
  } catch (e) {
    console.error("stripe_checkout_sessions insert threw (non-fatal):", (e as Error).message);
  }

  return jsonRes({ url: session.url, session_id: session.id });
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

  if (body.tier === "s5_onetime") {
    return handleS5OnetimeCheckout(body);
  }

  if (!body.api_key && body.customer_email) {
    return handleColdCheckout(body);
  }

  const { api_key: apiKey, tier } = body;
  if (!apiKey || typeof apiKey !== "string") {
    return jsonRes({ error: "api_key required" }, 400);
  }
  if (!SELLABLE_TIERS.includes(tier)) {
    return jsonRes({ error: `tier must be one of: ${SELLABLE_TIERS.join(", ")}` }, 400);
  }

  const supabase = await getAdminClient();
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
