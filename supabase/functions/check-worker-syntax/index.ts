Deno.serve(async (_req: Request) => {
  try {
    const r = await fetch("https://biddeed.ai/chat");
    const html = await r.text();
    const matches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    const results = [];
    for (const m of matches) {
      const scriptBody = m[1];
      try {
        new Function(scriptBody);
        results.push({ ok: true, len: scriptBody.length });
      } catch (e) {
        results.push({ ok: false, len: scriptBody.length, error: String(e) });
      }
    }
    return new Response(JSON.stringify({ scriptCount: matches.length, results }, null, 2), { headers: { "Content-Type": "application/json" } });
  } catch (outer) {
    return new Response(JSON.stringify({ ok: false, fatal: String(outer) }), { status: 500 });
  }
});
