// Minimal HTML page for GET /import (issue #19749 Part 1 scope: "Minimal upload form ... so
// Ariel can do it from a browser"). Mirrors linkPage.ts's pattern: the page itself is public
// (no X-CFO-Secret gate, same as GET /link), but the actual POST /import call it drives is
// gated -- the secret is entered into the form and forwarded as a query param, never persisted.

export interface ImportAccountOption {
  entity_code: string;
  mask: string;
  account_name: string;
  first_txn: string | null;
  last_txn: string | null;
  coverage_label: string;
}

// Issue #19770 scope item 3: "The upload form must let Ariel pick the target account from the
// four real accounts by mask -- not free-text -- and show which date range each account already
// covers so he can see exactly what to export." Replaces the old free-text entity+mask inputs
// with one <select> built from public.bank_engine_import_account_options() (real
// simplefin/manual-linked accounts only), each option showing its live coverage/gap.
export function renderImportPage(accounts: ImportAccountOption[]): string {
  const options = accounts
    .map(
      (a) =>
        `<option value="${escapeHtml(a.entity_code)}|${escapeHtml(a.mask)}" data-label="${escapeHtml(a.account_name)}">${escapeHtml(a.entity_code)} — ${escapeHtml(a.account_name)} — ${escapeHtml(a.coverage_label)}</option>`
    )
    .join("\n        ");
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Everest Bank Engine — Import bank file</title>
</head>
<body style="font-family: -apple-system, sans-serif; background:#020617; color:#e2e8f0; padding:2rem; max-width:34rem;">
  <h1>Everest Bank Engine</h1>
  <p>Import a Wells Fargo CSV or QFX/OFX export directly (bypasses Plaid production wait).</p>
  <form id="importForm">
    <label>Account<br/>
      <select name="account" required style="width:100%; padding:0.4rem;">
        <option value="">Select account…</option>
        ${options || '<option value="" disabled>No linked accounts found</option>'}
      </select>
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
      const selected = form.account.selectedOptions[0];
      if (!selected || !selected.value) { statusEl.textContent = "Select an account first."; return; }
      const [entityCode, mask] = selected.value.split("|");
      const accountLabel = selected.dataset.label || ("WF Checking " + mask);
      const fd = new FormData();
      fd.set("file", form.file.files[0]);
      const qs = new URLSearchParams({
        entity_code: entityCode,
        mask: mask,
        account_label: accountLabel,
        key: form.key.value,
      });
      statusEl.textContent = "Uploading…";
      try {
        const res = await fetch("/import?" + qs.toString(), { method: "POST", body: fd });
        const body = await res.json();
        statusEl.textContent = res.ok
          ? "Imported. connection_id=" + body.connection_id + " format=" + body.format + " parsed=" + body.parsed + " upserted=" + body.upserted + ". Pipeline + coverage ran -- see response body in devtools for details."
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
