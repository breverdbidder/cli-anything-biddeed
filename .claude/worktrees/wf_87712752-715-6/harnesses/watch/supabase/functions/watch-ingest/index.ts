// Claude Watch — watch-ingest Edge Function
// Deno runtime (Supabase Edge Functions)
// Security: bearer token auth, no shell, no secrets in responses

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MAX_OUTPUT_BYTES = 50 * 1024; // 50KB
const MAX_DIFF_BYTES = 20 * 1024;   // 20KB
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 100;

// In-memory rate limiter: session_id → { count, resetAt }
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(sessionId: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(sessionId);
  if (!entry || now > entry.resetAt) {
    rateLimitMap.set(sessionId, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }
  entry.count++;
  if (entry.count > RATE_LIMIT_MAX) return false;
  return true;
}

function extractRepo(projectPath: string): string {
  if (!projectPath) return "unknown";
  const parts = projectPath.replace(/\/$/, "").split("/");
  return parts[parts.length - 1] || "unknown";
}

function extractFilePath(toolInput: Record<string, unknown>, projectPath: string): string | null {
  const raw = (toolInput?.file_path || toolInput?.path || toolInput?.filePath) as string | undefined;
  if (!raw) return null;
  if (projectPath && raw.startsWith(projectPath)) {
    return raw.slice(projectPath.length).replace(/^\//, "");
  }
  return raw;
}

function extractDiff(toolName: string, toolInput: Record<string, unknown>): string | null {
  if (toolName !== "Edit") return null;
  const oldStr = toolInput?.old_string as string | undefined;
  const newStr = toolInput?.new_string as string | undefined;
  if (!oldStr && !newStr) return null;
  const diff = `--- old\n+++ new\n-${oldStr ?? ""}\n+${newStr ?? ""}`;
  return diff.length > MAX_DIFF_BYTES ? diff.slice(0, MAX_DIFF_BYTES) : diff;
}

function generateSummary(toolBreakdown: Record<string, number>): string {
  const parts = Object.entries(toolBreakdown)
    .sort(([, a], [, b]) => b - a)
    .map(([tool, count]) => `${tool} (${count})`)
    .slice(0, 5);
  return `Tools used: ${parts.join(", ")}`;
}

Deno.serve(async (req: Request) => {
  // Only POST
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  // Auth
  const token = Deno.env.get("WATCH_INGEST_TOKEN");
  const authHeader = req.headers.get("authorization") ?? "";
  if (!token || authHeader !== `Bearer ${token}`) {
    return new Response("Unauthorized", { status: 401 });
  }

  // Parse body
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return new Response("Bad request", { status: 400 });
  }

  // Validate required fields
  const sessionId = body.session_id as string | undefined;
  if (!sessionId) {
    return new Response("Bad request", { status: 400 });
  }

  const hookType = (body.type as string) || "PostToolUse";
  if (!["PostToolUse", "Notification", "Stop"].includes(hookType)) {
    return new Response("Bad request", { status: 400 });
  }

  // Rate limit
  if (!checkRateLimit(sessionId)) {
    return new Response("Too many requests", { status: 429 });
  }

  const toolName = (body.tool_name as string) || null;
  const projectPath = (body.project_path as string) || "";
  const toolInput = (body.tool_input as Record<string, unknown>) || {};
  const rawOutput = (body.tool_output as string) || null;

  const repo = extractRepo(projectPath);
  const filePath = extractFilePath(toolInput, projectPath);
  const diff = toolName ? extractDiff(toolName, toolInput) : null;

  let outputData: string | null = null;
  if (rawOutput) {
    const encoded = new TextEncoder().encode(rawOutput);
    outputData = encoded.length > MAX_OUTPUT_BYTES
      ? new TextDecoder().decode(encoded.slice(0, MAX_OUTPUT_BYTES)) + "...[truncated]"
      : rawOutput;
  }

  // Supabase client with service role (bypasses RLS)
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, serviceKey);

  try {
    // Check if session exists
    const { data: existingSession } = await supabase
      .from("watch_sessions")
      .select("id, event_count, tool_breakdown")
      .eq("id", sessionId)
      .single();

    if (!existingSession) {
      // First event for this session — insert
      const { error: insertErr } = await supabase.from("watch_sessions").insert({
        id: sessionId,
        repo,
        status: "active",
        event_count: 1,
        tool_breakdown: toolName ? { [toolName]: 1 } : {},
      });
      if (insertErr) throw insertErr;
    } else {
      // Update event_count and tool_breakdown
      const breakdown: Record<string, number> = existingSession.tool_breakdown || {};
      if (toolName) breakdown[toolName] = (breakdown[toolName] || 0) + 1;

      const updatePayload: Record<string, unknown> = {
        event_count: (existingSession.event_count || 0) + 1,
        tool_breakdown: breakdown,
      };

      if (hookType === "Stop") {
        updatePayload.status = "completed";
        updatePayload.ended_at = new Date().toISOString();
        updatePayload.summary = generateSummary(breakdown);
      }

      const { error: updateErr } = await supabase
        .from("watch_sessions")
        .update(updatePayload)
        .eq("id", sessionId);
      if (updateErr) throw updateErr;
    }

    // Insert event
    const { error: eventErr } = await supabase.from("watch_events").insert({
      session_id: sessionId,
      hook_type: hookType,
      tool_name: toolName,
      file_path: filePath,
      input_data: Object.keys(toolInput).length > 0 ? toolInput : null,
      output_data: outputData,
      diff,
    });
    if (eventErr) throw eventErr;

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return new Response("Internal server error", { status: 500 });
  }
});
