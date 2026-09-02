// Minimal HTML page for GET /link (scope item 1). This route itself sits behind the same
// X-CFO-Secret / ?key= gate as every other route (see index.ts) -- the key is only ever
// embedded into markup that was already returned to a caller who proved they hold it.

export function renderLinkPage(entityCode: string, key: string): string {
  const safeEntity = JSON.stringify(entityCode);
  const safeKey = JSON.stringify(key);
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Everest Bank Engine — Link a bank account</title>
  <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
</head>
<body style="font-family: -apple-system, sans-serif; background:#020617; color:#e2e8f0; padding:2rem;">
  <h1>Everest Bank Engine</h1>
  <p>Entity: <code>${entityCode}</code></p>
  <p id="status">Requesting link token…</p>
  <script>
    const ENTITY_CODE = ${safeEntity};
    const KEY = ${safeKey};
    const statusEl = document.getElementById("status");

    async function main() {
      const tokenRes = await fetch("/link/token", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CFO-Secret": KEY },
        body: JSON.stringify({ entity_code: ENTITY_CODE }),
      });
      if (!tokenRes.ok) {
        statusEl.textContent = "Failed to create link token: " + (await tokenRes.text());
        return;
      }
      const { link_token } = await tokenRes.json();

      const handler = Plaid.create({
        token: link_token,
        onSuccess: async (public_token, metadata) => {
          statusEl.textContent = "Exchanging public token…";
          const exchangeRes = await fetch("/link/exchange", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CFO-Secret": KEY },
            body: JSON.stringify({
              public_token,
              entity_code: ENTITY_CODE,
              institution_name: metadata.institution ? metadata.institution.name : null,
            }),
          });
          const body = await exchangeRes.json();
          statusEl.textContent = exchangeRes.ok
            ? "Linked. connection_id=" + body.connection_id + " accounts=" + body.accounts_count
            : "Exchange failed: " + JSON.stringify(body);
        },
        onExit: (err) => {
          statusEl.textContent = err ? "Exited with error: " + JSON.stringify(err) : "Exited.";
        },
      });
      statusEl.textContent = "Opening Plaid Link…";
      handler.open();
    }

    main().catch((e) => { statusEl.textContent = "Error: " + e; });
  </script>
</body>
</html>`;
}
