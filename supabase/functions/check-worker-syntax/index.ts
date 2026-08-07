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
    const dataUrl = "data:application/javascript," + encodeURIComponent(src);
    try {
      await import(dataUrl);
      return new Response(JSON.stringify({ ok: true, message: "module parses and evaluates cleanly", len: src.length }), { headers: { "Content-Type": "application/json" } });
    } catch (e) {
      return new Response(JSON.stringify({ ok: false, error: String(e), stack: (e as Error)?.stack?.slice(0,800), len: src.length }), { headers: { "Content-Type": "application/json" } });
    }
  } catch (outer) {
    return new Response(JSON.stringify({ ok: false, fatal: String(outer) }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
});
