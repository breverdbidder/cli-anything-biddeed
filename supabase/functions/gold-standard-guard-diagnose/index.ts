// supabase/functions/gold-standard-guard-diagnose/index.ts
//
// COST-FIX-5 Deployment A. Gemini Flash reads a county's Gold Standard guard
// state and returns a structured blocker diagnosis in <5s at $0 marginal
// cost, so the fleet stops burning 6h Claude Code sessions on counties that
// are stuck at pass_count=10 for a reason no amount of re-running the loop
// will fix (missing guard row, adversarial-survival failure, etc).
//
// Only diagnosis.requires_code_fix=true results in a dispatched CC session,
// via the existing launch_claude_code_session() RPC (same path every other
// gold-standard launcher uses — correct max_attempts, @claude prefix, issue
// creation via everest_worker_phase1_create_issue()).
//
// Auth: X-Router-Key header validated via claude_router_validate_key(),
// the same gate claude-router already uses — no new secret surface.
//
// Request:  { county_slug, pass_count, parity_ok, denom_ok, letters_survived,
//              failing_letters, consecutive_non_gold }
// Response: { diagnosis, dispatched, dispatch_id? }

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Router-Key",
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

async function validateProxyKey(key: string): Promise<boolean> {
  const { data, error } = await supabase.rpc("claude_router_validate_key", { p_key: key });
  if (error) return false;
  return data === true;
}

// gemini-2.0-flash was retired by Google (confirmed live 2026-09-02: 404
// "model no longer available"). Switched to gemini-2.5-flash, the same model
// claude-router/index.ts already runs in production for this exact
// generateContent call shape. thinkingBudget:0 disables extended thinking so
// the small maxOutputTokens budget isn't consumed before the JSON answer —
// the failure mode the old 2.0 pin was originally chosen to avoid.
const GEMINI_MODEL = "gemini-2.5-flash";
const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models";

async function callGemini(apiKey: string, system: string, userText: string): Promise<string> {
  const isBearer = apiKey.startsWith("AQ.") || apiKey.startsWith("ya29.");
  const url = isBearer
    ? `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent`
    : `${GEMINI_BASE}/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

  const body = {
    contents: [{ role: "user", parts: [{ text: userText }] }],
    systemInstruction: { parts: [{ text: system }] },
    generationConfig: {
      maxOutputTokens: 500,
      temperature: 0.1,
      thinkingConfig: { thinkingBudget: 0 },
    },
  };

  const reqHeaders: Record<string, string> = { "content-type": "application/json" };
  if (isBearer) reqHeaders["Authorization"] = `Bearer ${apiKey}`;

  const res = await fetch(url, { method: "POST", headers: reqHeaders, body: JSON.stringify(body) });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
  if (!text) throw new Error("Gemini returned empty content (MAX_TOKENS or safety)");
  return text;
}

const BLOCKER_TYPES = ["missing_guard", "adversarial_failure", "criteria_fail", "data_gap"];

interface Diagnosis {
  blocker_type: string;
  specific_issue: string;
  requires_code_fix: boolean;
  recommended_action: string;
  confidence: number;
}

function parseDiagnosis(raw: string): Diagnosis | null {
  // Gemini sometimes wraps JSON in ```json fences despite instructions not to.
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/);
  const candidate = fenced ? fenced[1] : raw;
  const start = candidate.indexOf("{");
  const end = candidate.lastIndexOf("}");
  if (start === -1 || end === -1) return null;

  let parsed: any;
  try {
    parsed = JSON.parse(candidate.slice(start, end + 1));
  } catch {
    return null;
  }

  if (
    typeof parsed.blocker_type !== "string" ||
    !BLOCKER_TYPES.includes(parsed.blocker_type) ||
    typeof parsed.specific_issue !== "string" ||
    typeof parsed.requires_code_fix !== "boolean" ||
    typeof parsed.recommended_action !== "string" ||
    typeof parsed.confidence !== "number"
  ) {
    return null;
  }

  return {
    blocker_type: parsed.blocker_type,
    specific_issue: parsed.specific_issue,
    requires_code_fix: parsed.requires_code_fix,
    recommended_action: parsed.recommended_action,
    confidence: parsed.confidence,
  };
}

async function logOps(row: {
  dispatch_id: string;
  status: "VERIFIED" | "BLOCKED";
  evidence: string;
  severity: "info" | "warn" | "blocker";
}): Promise<void> {
  const { error } = await supabase.from("agent_ops_log").insert({
    dispatch_id: row.dispatch_id,
    task: "guard-diagnose",
    status: row.status,
    evidence: row.evidence,
    severity: row.severity,
  });
  if (error) console.error("agent_ops_log insert:", error.message);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS });
  }

  const url = new URL(req.url);

  if (url.pathname.endsWith("/health") && req.method === "GET") {
    return jsonRes({ status: "ok", service: "gold-standard-guard-diagnose" });
  }

  if (req.method !== "POST") {
    return jsonRes({ error: "POST required" }, 405);
  }

  const routerKey = req.headers.get("X-Router-Key") ?? req.headers.get("x-router-key") ?? "";
  if (!routerKey) {
    return jsonRes({ error: "missing X-Router-Key header" }, 401);
  }
  if (!(await validateProxyKey(routerKey))) {
    return jsonRes({ error: "invalid router key" }, 401);
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return jsonRes({ error: "invalid JSON body" }, 400);
  }

  const countySlug = body.county_slug;
  if (typeof countySlug !== "string" || !countySlug) {
    return jsonRes({ error: "county_slug is required" }, 400);
  }

  const input = {
    county_slug: countySlug,
    pass_count: body.pass_count ?? null,
    parity_ok: body.parity_ok ?? null,
    denom_ok: body.denom_ok ?? null,
    letters_survived: body.letters_survived ?? null,
    failing_letters: Array.isArray(body.failing_letters) ? body.failing_letters : [],
    consecutive_non_gold: body.consecutive_non_gold ?? null,
  };

  const systemPrompt = `You are a Gold Standard certification analyst for Florida county auction data.
Given the county status below, diagnose the SPECIFIC blocker preventing certification.
Return ONLY valid JSON, no markdown fences, no commentary: {
  "blocker_type": "missing_guard"|"adversarial_failure"|"criteria_fail"|"data_gap",
  "specific_issue": string,
  "requires_code_fix": boolean,
  "recommended_action": string,
  "confidence": number
}`;

  const userText = `County: ${input.county_slug}
pass_count: ${input.pass_count}
parity_ok: ${input.parity_ok}
denom_ok: ${input.denom_ok}
letters_survived: ${input.letters_survived}
failing_letters: ${JSON.stringify(input.failing_letters)}
consecutive_non_gold: ${input.consecutive_non_gold}`;

  // Tier cascade matching claude-router: T1 gemini_biddeed, T2 gemini_global.
  // Try each key as an actual attempt with fallthrough — a key existing in
  // vault does not mean the underlying Google credential is still valid
  // (T1 is an OAuth bearer token subject to expiry independent of vault
  // presence), so unlike a simple "first non-null key wins" this must
  // retry on failure, not just on a missing secret.
  const keyNames = ["gemini_api_key_biddeed", "gemini_api_key"];
  let diagnosis: Diagnosis | null = null;
  const attemptErrors: string[] = [];

  for (const keyName of keyNames) {
    const apiKey = await getVaultSecret(keyName);
    if (!apiKey) continue;
    try {
      const raw = await callGemini(apiKey, systemPrompt, userText);
      const parsed = parseDiagnosis(raw);
      if (!parsed) throw new Error(`unparseable diagnosis response: ${raw.slice(0, 300)}`);
      diagnosis = parsed;
      break;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      attemptErrors.push(`${keyName}: ${message}`);
    }
  }

  if (!diagnosis) {
    const message = attemptErrors.length ? attemptErrors.join(" | ") : "no Gemini credentials configured in vault";
    await logOps({
      dispatch_id: `guard-diagnose-${countySlug}`,
      status: "BLOCKED",
      evidence: `Gemini diagnosis failed: ${message}`,
      severity: "blocker",
    });
    // Fail open: no diagnosis means no dispatch, never a blind fallback launch.
    return jsonRes({ error: "diagnosis_failed", detail: message }, 502);
  }

  let dispatched = false;
  let dispatchId: string | null = null;

  if (diagnosis.requires_code_fix) {
    const title = `Gold Standard guard fix: ${countySlug} — ${diagnosis.blocker_type}`;
    const brief = `@claude

Gold Standard guard diagnosis (auto-generated by gold-standard-guard-diagnose, Gemini Flash, $0 cost).

County: ${countySlug}
Blocker type: ${diagnosis.blocker_type}
Specific issue: ${diagnosis.specific_issue}
Confidence: ${diagnosis.confidence}

Guard state at diagnosis time:
- pass_count: ${input.pass_count}
- parity_ok: ${input.parity_ok}
- denom_ok: ${input.denom_ok}
- letters_survived: ${input.letters_survived}
- failing_letters: ${JSON.stringify(input.failing_letters)}
- consecutive_non_gold: ${input.consecutive_non_gold}

Recommended action: ${diagnosis.recommended_action}

Fix the SPECIFIC blocker above, do not re-run the full 10-criteria loop blind.
Adversarially verify any claimed fix before closing out.`;

    const { data, error } = await supabase.rpc("launch_claude_code_session", {
      p_title: title,
      p_body: brief,
      p_repo: "breverdbidder/cli-anything-biddeed",
      p_priority: "p1",
      p_workflow: "cc-runner-ghonly.yml",
      p_dod_sql: null,
    });

    if (error) {
      await logOps({
        dispatch_id: `guard-diagnose-${countySlug}`,
        status: "BLOCKED",
        evidence: `launch_claude_code_session failed: ${error.message}`,
        severity: "blocker",
      });
      return jsonRes({ diagnosis, dispatched: false, dispatch_error: error.message }, 200);
    }

    dispatched = true;
    dispatchId = data?.[0]?.dispatch_id ?? null;
  }

  await logOps({
    dispatch_id: dispatchId ?? `guard-diagnose-${countySlug}`,
    status: "VERIFIED",
    evidence: `county=${countySlug} blocker_type=${diagnosis.blocker_type} requires_code_fix=${diagnosis.requires_code_fix} confidence=${diagnosis.confidence} dispatched=${dispatched}${dispatchId ? " dispatch_id=" + dispatchId : ""} — ${diagnosis.specific_issue}`,
    severity: diagnosis.requires_code_fix ? "blocker" : "info",
  });

  return jsonRes({ diagnosis, dispatched, dispatch_id: dispatchId });
});
