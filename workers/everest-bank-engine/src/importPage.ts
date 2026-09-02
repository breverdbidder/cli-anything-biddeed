// Minimal HTML page for GET /import (issue #19749 Part 1 scope: "Minimal upload form ... so
// Ariel can do it from a browser"). Mirrors linkPage.ts's pattern: the page itself is public
// (no X-CFO-Secret gate, same as GET /link), but the actual POST /import call it drives is
// gated -- the secret is entered into the form and forwarded as a query param, never persisted.

export function renderImportPage(entities: Array<{ code: string; name: string }>): string {
  const options = entities
    .map((e) => `<option value="${escapeHtml(e.code)}">${escapeHtml(e.name)} (${escapeHtml(e.code)})</option>`)
    .join("\n        ");
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Everest Bank Engine — Import bank file</title>
</head>
<body style="font-family: -apple-system, sans-serif; background:#020617; color:#e2e8f0; padding:2rem; max-width:32rem;">
  <h1>Everest Bank Engine</h1>
  <p>Import a Wells Fargo CSV or QFX/OFX export directly (bypasses Plaid production wait).</p>
  <form id="importForm">
    <label>Entity<br/>
      <select name="entity_code" required style="width:100%; padding:0.4rem;">
        <option value="">Select entity…</option>
        ${options}
      </select>
    </label><br/><br/>
    <label>Account label<br/>
      <input type="text" name="account_label" placeholder="e.g. WF Checking 1234" style="width:100%; padding:0.4rem;" />
    </label><br/><br/>
    <label>Last 4 of account (mask)<br/>
      <input type="text" name="mask" required maxlength="4" pattern="[0-9]{4}" style="width:100%; padding:0.4rem;" />
    </label><br/><br/>
    <label>File (CSV or QFX/OFX)<br/>
      <input type="file" name="file" accept=".csv,.qfx,.ofx,.xml,text/csv" required />
    </label><br/><br/>
    <label>Shared secret (X-CFO-Secret)<br/>
      <input type="password" name="key" required style="width:100%; padding:0.4rem;" />
    </label><br/><br/>
    <button type="submit" style="background:#F59E0B; color:#020617; border:none; padding:0.6rem 1.2rem; font-weight:bold;">Import</button>
  </form>
  <p id="status"></p>
  <script>
    document.getElementById("importForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const form = ev.target;
      const statusEl = document.getElementById("status");
      const maskVal = form.mask.value;
      const fd = new FormData();
      fd.set("file", form.file.files[0]);
      const qs = new URLSearchParams({
        entity_code: form.entity_code.value,
        mask: maskVal,
        account_label: form.account_label.value || ("WF Checking " + maskVal),
        key: form.key.value,
      });
      statusEl.textContent = "Uploading…";
      try {
        const res = await fetch("/import?" + qs.toString(), { method: "POST", body: fd });
        const body = await res.json();
        statusEl.textContent = res.ok
          ? "Imported. connection_id=" + body.connection_id + " format=" + body.format + " parsed=" + body.parsed + " upserted=" + body.upserted
          : "Import failed: " + JSON.stringify(body);
      } catch (e) {
        statusEl.textContent = "Error: " + e;
      }
    });
  </script>
  <footer style="margin-top:3rem; font-size:0.85rem; color:#94a3b8;">
    <a href="/privacy" style="color:#F59E0B;">Privacy policy</a>
  </footer>
</body>
</html>`;
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
