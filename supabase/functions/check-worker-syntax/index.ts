Deno.serve(async (_req: Request) => {
  const r = await fetch("https://biddeed.ai/chat");
  const html = await r.text();
  const matches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  const scriptBody = matches[1][1];
  // Bisect: find largest valid prefix by testing increasing lengths at line boundaries
  const lines = scriptBody.split("\n");
  let lastGoodLine = 0;
  let firstBadLine = -1;
  for (let i = 1; i <= lines.length; i++) {
    const attempt = lines.slice(0, i).join("\n") + "\n}"; // best-effort close in case we're inside a fn
    try {
      new Function(lines.slice(0,i).join("\n"));
      lastGoodLine = i;
    } catch (e) {
      if (firstBadLine === -1 && String(e).includes("identifier")) { firstBadLine = i; break; }
    }
  }
  const contextStart = Math.max(0, firstBadLine - 4);
  const contextLines = lines.slice(contextStart, firstBadLine + 2);
  return new Response(JSON.stringify({ totalLines: lines.length, firstBadLine, contextStart, context: contextLines }, null, 2), { headers: { "Content-Type": "application/json" } });
});
