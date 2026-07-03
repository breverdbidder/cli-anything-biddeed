// supabase/functions/support-agent/index.ts
//
// SPRINT5 #1 — BidDeed/ZoneWise member support agent.
//
// Identity: support@zonewise.ai — an API-token-backed service identity, NOT a
// Claude seat. Answers member questions from a static docs corpus (RAG-lite —
// keyword overlap, no vector store) plus, if the caller supplies their own
// bd_ API key, READ-ONLY key status (tier / active / trial expiry). Routes
// generation through claude-router (T1 Gemini -> T2 Gemini -> T3 Claude OAuth).
//
// EG14 guard rails (see CLAUDE.md SPRINT5 #1 RULES):
//   - never performs account mutations
//   - never reveals another member's data — key lookups are scoped to the
//     exact key the caller supplied (hash match), never a prefix search
//   - never discusses keys beyond the caller's own prefix
//
// Request:  { session_id, message, locale?, member_key? }
// Response: { reply, escalated, model_tier }

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

async function getVaultSecret(name: string): Promise<string | null> {
  const { data, error } = await supabase.rpc("get_vault_secret_mcp", { p_name: name });
  if (error || data == null) return null;
  return String(data);
}

// ── Docs corpus (RAG-lite: keyword overlap over the P1 docs/privacy/support build) ──
// Sourced from docs/mcp/index.html, docs/mcp/privacy.html, docs/mcp/support.html,
// and supabase/migrations/20260702_b2c_trial_activation.sql (trial length/expiry).

const DOCS: Array<{ id: string; keywords: string[]; text: string }> = [
  {
    id: "trial-length",
    keywords: ["trial", "free trial", "expire", "expiry", "how long", "days"],
    text: "Trial keys (prefix bd_trial_) are Investor-tier and are valid for 30 days from " +
      "activation. After expiry there is a 7-day read-only grace period before the key is " +
      "hard-cutoff. Upgrade any time at https://biddeed.ai/biddeed-mcp/start/?checkout=1.",
  },
  {
    id: "pricing-tiers",
    keywords: ["tier", "pricing", "price", "cost", "upgrade", "plan", "free", "investor", "pro"],
    text: "Tiers: free (S1 Discovery + S6 Market Data, $0.05/call), investor (adds S2 " +
      "Qualification $0.40/call + S7 Property Intel $0.25/call), pro (adds S3 Fusion " +
      "$5.00/call + S4 Monitoring + S5 Shapira Formula $25.00/call, CERT required). " +
      "Upgrade at https://biddeed.ai/upgrade or https://biddeed.ai/biddeed-mcp/start/?checkout=1.",
  },
  {
    id: "auth",
    keywords: ["api key", "auth", "authenticate", "bd_live", "oauth", "workos", "invalid key"],
    text: "Authenticate with `Authorization: Bearer bd_live_xxx` (issued per customer) or a " +
      "WorkOS AuthKit OAuth 2.1 + PKCE access token. BidDeed MCP only validates OAuth tokens " +
      "(JWKS + exp/nbf) — it never issues them. `AUTH_ERROR: Invalid API key` usually means a " +
      "typo, revoked key, or wrong env var name (should be BIDDEED_API_KEY).",
  },
  {
    id: "quickstart",
    keywords: ["quickstart", "setup", "install", "connect", "mcp server", "claude desktop", "cursor"],
    text: "stdio clients (Claude Desktop, Cursor): npx -y biddeed-mcp with BIDDEED_API_KEY env " +
      "var. Streamable HTTP (Claude web/connectors): POST https://biddeed.ai/api/mcp with " +
      "Authorization: Bearer bd_live_xxx or a WorkOS token. Get a key at biddeed.ai/dashboard.",
  },
  {
    id: "privacy-data",
    keywords: ["privacy", "data", "collect", "store", "train", "sell", "retention", "delete"],
    text: "We collect account data (email, name, tier, WorkOS user ID) and tool-call metadata " +
      "(tool name, county/parcel params, latency, cache hits) for billing and reliability — " +
      "never full request/response bodies. We do not train models on your queries, do not sell " +
      "tool-call data, and do not store your MCP client's conversation history. Billing/usage " +
      "records are kept while the account is active plus required financial recordkeeping. " +
      "Contact support@biddeed.ai for access/correction/deletion requests.",
  },
  {
    id: "common-issues",
    keywords: ["error", "not working", "broken", "cert_required", "stream requires", "issue"],
    text: "`Stream sX requires Y tier` means your tier doesn't unlock that revenue stream — " +
      "upgrade at biddeed.ai/upgrade. `CERT_REQUIRED` on predict_auction_outcome means the " +
      "county hasn't passed Gold Standard certification (8+ letters) — use underwrite_deal " +
      "(S3) instead. Expired OAuth tokens need re-authentication via WorkOS AuthKit.",
  },
  {
    id: "support-contact",
    keywords: ["contact", "human", "help", "support email", "talk to someone"],
    text: "Email support@biddeed.ai for general support/billing/key issues (1 business day " +
      "response target), or partners@biddeed.ai for local partner referrals. Auth/billing " +
      "blocking issues are prioritized.",
  },
];

function retrieveContext(message: string): string {
  const lower = message.toLowerCase();
  const scored = DOCS.map((d) => ({
    d,
    score: d.keywords.reduce((acc, kw) => (lower.includes(kw) ? acc + 1 : acc), 0),
  }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
  if (scored.length === 0) return "";
  return scored.map((s) => `- ${s.d.text}`).join("\n");
}

// ── Member state (READ-ONLY — never mutate, never expose beyond caller's own key) ──

async function hashKey(apiKey: string): Promise<string> {
  const data = new TextEncoder().encode(apiKey);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function lookupMember(memberKey: string): Promise<{ prefix: string; summary: string } | null> {
  if (!memberKey || !memberKey.startsWith("bd_")) return null;
  const hash = await hashKey(memberKey);
  const { data, error } = await supabase
    .from("mcp_api_keys")
    .select("tier, is_active, revoked_at, expires_at, key_prefix")
    .eq("key_hash", hash)
    .limit(1);
  if (error || !data || data.length === 0) return null;
  const rec = data[0];
  const status = rec.revoked_at ? "revoked" : rec.is_active ? "active" : "inactive";
  const expiry = rec.expires_at ? `, expires ${rec.expires_at}` : "";
  return {
    prefix: rec.key_prefix,
    summary: `Caller's key (${rec.key_prefix}...): tier=${rec.tier}, status=${status}${expiry}.`,
  };
}

// ── Rate limiting (per session_id, DB-backed — best effort per-IP is not tracked, no ip column) ──

async function isRateLimited(sessionId: string): Promise<boolean> {
  const since = new Date(Date.now() - 60_000).toISOString();
  const { count, error } = await supabase
    .from("support_conversations")
    .select("id", { count: "exact", head: true })
    .eq("session_id", sessionId)
    .eq("role", "user")
    .gte("created_at", since);
  if (error) return false;
  return (count ?? 0) >= 10;
}

// ── Escalation email (Resend, verified sender from vault) ──

async function sendEscalationEmail(sessionId: string, locale: string, lastMessage: string): Promise<void> {
  try {
    const apiKey = await getVaultSecret("resend_api_key");
    const from = await getVaultSecret("resend_from_address");
    if (!apiKey || !from) return;
    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        from,
        to: ["support@zonewise.ai"],
        subject: `[support-agent] Escalation — session ${sessionId}`,
        text: `Locale: ${locale}\nSession: ${sessionId}\n\nLast member message:\n${lastMessage}\n\n` +
          `The support agent could not resolve this or the member asked for a human. ` +
          `Reply directly to the member via their original channel.`,
      }),
    });
  } catch (err) {
    console.error("resend escalation failed:", err instanceof Error ? err.message : String(err));
  }
}

// ── claude-router ──

const ROUTER_URL = `${SUPABASE_URL}/functions/v1/claude-router`;

async function callRouter(system: string, message: string): Promise<{ text: string; tier: string | null } | null> {
  const key = await getVaultSecret("router_proxy_key");
  if (!key) return null;
  try {
    const res = await fetch(ROUTER_URL, {
      method: "POST",
      headers: { "content-type": "application/json", "X-Router-Key": key },
      body: JSON.stringify({
        messages: [{ role: "user", content: message }],
        system,
        max_tokens: 500,
        source: "support-agent",
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.text) return null;
    return { text: data.text, tier: data.tier ?? null };
  } catch {
    return null;
  }
}

const LOCALES = ["en", "he", "ru", "fr", "zh"];

// ── Handler ──

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

  const sessionId: string = typeof body.session_id === "string" ? body.session_id.slice(0, 128) : "";
  const message: string = typeof body.message === "string" ? body.message.slice(0, 2000) : "";
  const locale: string = LOCALES.includes(body.locale) ? body.locale : "en";
  const memberKey: string | undefined = typeof body.member_key === "string" ? body.member_key : undefined;

  if (!sessionId || !message) {
    return jsonRes({ error: "session_id and message are required" }, 400);
  }

  if (await isRateLimited(sessionId)) {
    return jsonRes({ error: "rate_limited", reply: "You're sending messages too quickly — please wait a moment." }, 429);
  }

  const member = memberKey ? await lookupMember(memberKey) : null;

  await supabase.from("support_conversations").insert({
    session_id: sessionId,
    member_key_prefix: member?.prefix ?? null,
    role: "user",
    content: message,
    locale,
  });

  const wantsHuman = /\b(human|real person|representative|talk to (a |an )?(agent|person))\b/i.test(message);

  const docsContext = retrieveContext(message);
  const system = [
    "You are the BidDeed.AI / ZoneWise member support agent (support@zonewise.ai).",
    "Answer ONLY from the context below. If the context doesn't cover the question, say you don't know and that you're looping in a human.",
    "NEVER perform account mutations (no key creation/revocation/tier changes/refunds) — you are read-only.",
    "NEVER reveal any member's data other than the caller's own key, and only what is given to you below.",
    `Respond in locale '${locale}' if you are able to, otherwise respond in English.`,
    "If you cannot resolve the question, or the member is asking for a human, start your reply with the exact token [ESCALATE] followed by a short apology.",
    docsContext ? `\nContext:\n${docsContext}` : "\nContext: (no matching docs found for this question)",
    member ? `\nMember state (read-only, caller's own key only):\n${member.summary}` : "",
  ].join("\n");

  const routerResult = await callRouter(system, message);

  let reply: string;
  let modelTier: string | null;
  let escalated = wantsHuman;

  if (routerResult) {
    reply = routerResult.text;
    modelTier = routerResult.tier;
    if (reply.startsWith("[ESCALATE]")) {
      escalated = true;
      reply = reply.replace("[ESCALATE]", "").trim();
    }
  } else {
    reply = "I'm having trouble reaching our answer engine right now. I've flagged this for a " +
      "human on our team — they'll follow up at support@biddeed.ai.";
    modelTier = null;
    escalated = true;
  }

  if (escalated) {
    await sendEscalationEmail(sessionId, locale, message);
  }

  await supabase.from("support_conversations").insert({
    session_id: sessionId,
    member_key_prefix: member?.prefix ?? null,
    role: "assistant",
    content: reply,
    locale,
    model_tier: modelTier,
  });

  return jsonRes({ reply, escalated, model_tier: modelTier });
});
