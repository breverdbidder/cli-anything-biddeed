Deno.serve(async (_req: Request) => {
  try {
    const r = await fetch("https://biddeed.ai/chat");
    const html = await r.text();
    // extract the last (voice widget) inline <script> block
    const matches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    const results = [];
    for (const m of matches) {
      const scriptBody = m[1];
      try {
        new Function(scriptBody);
        results.push({ ok: true, len: scriptBody.length, preview: scriptBody.slice(0,80) });
      } catch (e) {
        results.push({ ok: false, len: scriptBody.length, error: String(e), preview: scriptBody.slice(0,80) });
      }
    }
    return new Response(JSON.stringify({ scriptCount: matches.length, results }, null, 2), { headers: { "Content-Type": "application/json" } });
  } catch (outer) {
    return new Response(JSON.stringify({ ok: false, fatal: String(outer) }), { status: 500 });
  }
});
