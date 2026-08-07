// TEMP DIAGNOSTIC — fetches worker.js from GitHub server-side, attempts to parse (not execute) it via new Function(),
// returns the resulting SyntaxError message + surrounding snippet if invalid. Never exposes PAT or full source to caller.
Deno.serve(async (req: Request) => {
  try {
    const ghPat = Deno.env.get("EVEREST_GH_PAT_INLINE") ?? "";
    const r = await fetch(
      "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/contents/src/worker.js?ref=main",
      { headers: { Authorization: `Bearer ${ghPat}`, Accept: "application/vnd.github.raw+json", "User-Agent": "diag" } }
    );
    const src = await r.text();
    try {
      new Function(src);
      return new Response(JSON.stringify({ ok: true, message: "no syntax error" }), { headers: { "Content-Type": "application/json" } });
    } catch (e) {
      const msg = String(e);
      // Try to extract a position from V8's error if present, else just return message
      return new Response(JSON.stringify({ ok: false, error: msg, len: src.length }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
  } catch (outer) {
    return new Response(JSON.stringify({ ok: false, fatal: String(outer) }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
});
