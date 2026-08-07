// TEMP DIAGNOSTIC — fetches worker.js server-side, attempts to parse (not execute) via new Function(),
// returns SyntaxError message if invalid. PAT never leaves the server, source never returned to caller.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (_req: Request) => {
  try {
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const { data: ghPat, error } = await supabase.rpc("get_vault_secret_mcp", { p_name: "everest_gh_pat" });
    if (error || !ghPat) throw new Error(`vault lookup failed: ${error?.message}`);

    const r = await fetch(
      "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/contents/src/worker.js?ref=main",
      { headers: { Authorization: `Bearer ${ghPat}`, Accept: "application/vnd.github.raw+json", "User-Agent": "diag" } }
    );
    const src = await r.text();
    try {
      new Function(src);
      return new Response(JSON.stringify({ ok: true, message: "no syntax error", len: src.length }), { headers: { "Content-Type": "application/json" } });
    } catch (e) {
      return new Response(JSON.stringify({ ok: false, error: String(e), len: src.length }), { headers: { "Content-Type": "application/json" } });
    }
  } catch (outer) {
    return new Response(JSON.stringify({ ok: false, fatal: String(outer) }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
});
