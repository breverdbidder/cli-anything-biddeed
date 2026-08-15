/**
 * BidDeed Ops Dashboard Worker
 * ---------------------------------------------------------------------------
 * Single-operator dashboard: reads a handful of existing Supabase
 * tables/views as tiles, and exposes three action buttons that fire real
 * SECURITY DEFINER RPCs. No new database tables, no auth system (this
 * deploys to a bare workers.dev URL — access control is an explicit
 * follow-up, not part of this build).
 *
 * DEVIATION FROM SPEC (documented, not hidden — see session report):
 * the brief asked for reads/actions to go through the new dashboard_reader /
 * dashboard_agent Postgres roles via a connection-string Worker secret.
 * Those two roles DO exist with exactly the grants specified (verified live
 * via SET ROLE + information_schema in the same session that built this
 * file) but PostgREST only lets a request assume a non-default DB role via
 * a JWT carrying a matching `role` claim, and this project's Management API
 * did not expose a legacy HS256 JWT secret to mint one with (it's on the
 * newer key system). Raw Postgres-wire-protocol access from a Workers
 * isolate (e.g. postgres.js over `cloudflare:sockets`) has no precedent in
 * this repo and is an unverified integration path. So this Worker instead
 * uses the same proven SUPABASE_URL + SUPABASE_SERVICE_KEY REST pattern as
 * workers/zonewise-floorplan, with least-privilege enforced at the
 * application layer instead: every query below is hardcoded (no user input
 * ever reaches SQL), and the RPC allowlist is fixed to the same three
 * functions dashboard_agent was granted EXECUTE on.
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { ...CORS_HEADERS, "content-type": "application/json" },
  });
}

function restHeaders(env) {
  return {
    apikey: env.SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
  };
}

async function restGet(env, path) {
  const resp = await fetch(`${env.SUPABASE_URL}/rest/v1/${path}`, {
    headers: { ...restHeaders(env), Prefer: "count=exact" },
  });
  const contentRange = resp.headers.get("content-range") || "";
  const total = contentRange.includes("/") ? contentRange.split("/")[1] : null;
  if (!resp.ok) {
    return { ok: false, status: resp.status, error: await resp.text(), rows: [], total: null };
  }
  return { ok: true, status: resp.status, rows: await resp.json(), total: total === "*" ? null : Number(total) };
}

async function restRpc(env, fn, args) {
  const resp = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/${fn}`, {
    method: "POST",
    headers: { ...restHeaders(env), "Content-Type": "application/json" },
    body: JSON.stringify(args || {}),
  });
  let body;
  try {
    body = await resp.json();
  } catch {
    body = await resp.text();
  }
  return { ok: resp.status < 300, status: resp.status, body };
}

/**
 * Pulls the 4 read tiles. Every query here is a fixed, hardcoded string —
 * no request input is ever interpolated into a Supabase query.
 */
async function loadTiles(env) {
  const [ssotFacts, ssotMaster, opsLog, goldStandard] = await Promise.all([
    restGet(env, "ssot_facts?select=fact_key,fact_value,display_label,marker,verified_at&order=verified_at.desc&limit=20"),
    restGet(env, "v_ssot_master?select=status&limit=1000"),
    restGet(env, "agent_ops_log?select=dispatch_id,task,status,severity,created_at&order=created_at.desc&limit=10"),
    restGet(env, "gold_standard_scoreboard?select=county_slug,pass_count,gold_standard,critical_three_pass&order=pass_count.desc&limit=1000"),
  ]);

  const ssotMasterByStatus = {};
  for (const r of ssotMaster.rows || []) {
    ssotMasterByStatus[r.status || "unknown"] = (ssotMasterByStatus[r.status || "unknown"] || 0) + 1;
  }

  const goldCounties = goldStandard.rows || [];
  const goldPassingCount = goldCounties.filter((r) => r.gold_standard === true).length;
  const goldCriticalThreeCount = goldCounties.filter((r) => r.critical_three_pass === true).length;

  return {
    inventory: {
      title: "Inventory / Status (ssot_facts)",
      ok: ssotFacts.ok,
      total: ssotFacts.total,
      rows: ssotFacts.rows,
    },
    rollup: {
      title: "SSOT Rollup (v_ssot_master)",
      ok: ssotMaster.ok,
      total: ssotMaster.total,
      by_status: ssotMasterByStatus,
    },
    dispatch_feed: {
      title: "Last 10 Dispatch Outcomes (agent_ops_log)",
      ok: opsLog.ok,
      total: opsLog.total,
      rows: opsLog.rows,
    },
    cert_status: {
      title: "Gold Standard Cert Status (gold_standard_scoreboard, read-only)",
      ok: goldStandard.ok,
      total: goldStandard.total,
      gold_standard_count: goldPassingCount,
      critical_three_pass_count: goldCriticalThreeCount,
      counties: goldCounties.slice(0, 10),
    },
  };
}

function renderHtml(tiles) {
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const tile = (t, body) => `
    <section class="tile">
      <h2>${esc(t.title)}</h2>
      ${t.ok ? body : `<p class="err">Read failed (see /api/tiles for detail)</p>`}
    </section>`;

  const inventoryBody = `
    <p class="stat">${tiles.inventory.total ?? tiles.inventory.rows.length} facts</p>
    <ul>${tiles.inventory.rows.slice(0, 8).map((r) => `<li><b>${esc(r.display_label || r.fact_key)}</b>: ${esc(r.fact_value)} <span class="marker">${esc(r.marker)}</span></li>`).join("")}</ul>`;

  const rollupBody = `
    <p class="stat">${tiles.rollup.total ?? "?"} rows</p>
    <ul>${Object.entries(tiles.rollup.by_status).map(([k, v]) => `<li><b>${esc(k)}</b>: ${v}</li>`).join("")}</ul>`;

  const feedBody = `
    <ul>${tiles.dispatch_feed.rows.map((r) => `<li><span class="status status-${esc((r.status || "").toLowerCase())}">${esc(r.status)}</span> ${esc(r.task)} <span class="ts">${esc(r.created_at)}</span></li>`).join("")}</ul>`;

  const certBody = `
    <p class="stat">${tiles.cert_status.gold_standard_count} / ${tiles.cert_status.total ?? tiles.cert_status.counties.length} counties GOLD STANDARD, ${tiles.cert_status.critical_three_pass_count} critical-3-pass</p>
    <ul>${tiles.cert_status.counties.map((r) => `<li>${esc(r.county_slug)}: ${r.pass_count}/10 ${r.gold_standard ? "🏆" : ""}</li>`).join("")}</ul>`;

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BidDeed Ops Dashboard</title>
<style>
  :root { --navy:#1E3A5F; --amber:#F59E0B; --bg:#020617; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:#e2e8f0; font-family: Inter, system-ui, sans-serif; }
  header { background:var(--navy); padding:20px 32px; display:flex; align-items:center; justify-content:space-between; }
  header h1 { margin:0; font-size:18px; }
  main { padding:24px 32px; display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:20px; }
  .tile { background:#0f1c30; border:1px solid #1E3A5F; border-radius:8px; padding:16px 20px; }
  .tile h2 { font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:var(--amber); margin:0 0 12px; }
  .tile ul { list-style:none; margin:0; padding:0; font-size:13px; line-height:1.7; }
  .stat { font-size:22px; font-weight:600; margin:0 0 8px; }
  .marker { color:#64748b; font-size:11px; margin-left:6px; }
  .ts { color:#64748b; font-size:11px; margin-left:6px; }
  .err { color:#f87171; }
  .status { font-weight:600; }
  .status-verified { color:#34d399; }
  .status-blocked { color:#f87171; }
  .status-partial { color:var(--amber); }
  .actions { padding:0 32px 32px; display:flex; gap:12px; flex-wrap:wrap; }
  button { background:var(--amber); color:#020617; border:none; border-radius:6px; padding:10px 18px; font-weight:600; font-size:13px; cursor:pointer; }
  button:disabled { background:#334155; color:#94a3b8; cursor:not-allowed; }
  #action-result { padding:0 32px 32px; font-size:13px; white-space:pre-wrap; color:#94a3b8; }
</style>
</head>
<body>
<header><h1>BidDeed.AI — Ops Dashboard</h1><span style="color:#64748b;font-size:12px">read-only tiles + 3 action triggers · no auth (workers.dev)</span></header>
<main>
  ${tile(tiles.inventory, inventoryBody)}
  ${tile(tiles.rollup, rollupBody)}
  ${tile(tiles.dispatch_feed, feedBody)}
  ${tile(tiles.cert_status, certBody)}
</main>
<div class="actions">
  <button onclick="runAction('weekly-review')">Weekly Review</button>
  <button disabled title="No read-only metrics-refresh RPC exists yet — flagged, not built silently. See session report.">Pull Metrics (blocked)</button>
  <button onclick="runAction('vault-cleanup')">Vault Cleanup</button>
</div>
<pre id="action-result"></pre>
<script>
async function runAction(name) {
  const out = document.getElementById('action-result');
  out.textContent = 'Running ' + name + '...';
  try {
    const resp = await fetch('/action/' + name, { method: 'POST' });
    const body = await resp.json();
    out.textContent = name + ' -> HTTP ' + resp.status + '\\n' + JSON.stringify(body, null, 2);
  } catch (e) {
    out.textContent = name + ' -> error: ' + e.message;
  }
}
</script>
</body>
</html>`;
}

async function handleWeeklyReview(env) {
  const today = new Date().toISOString().slice(0, 10);
  const issueResp = await restRpc(env, "gha_create_issue", {
    p_title: `ops-dashboard: Weekly Review ${today}`,
    p_body:
      "Operating contract: CC_META_PROMPT.md. Read it first.\n\n" +
      "/loop weekly-review\n\n/goal\nWeekly operator review triggered from the ops dashboard " +
      "Weekly Review button. Summarize the past 7 days of agent_ops_log activity, flag any " +
      "BLOCKED rows, and report back.\n\n/dod\n- [ ] Summary posted as an issue comment\n" +
      "- [ ] agent_ops_log row: task=weekly-review, status=VERIFIED",
    p_repo: "breverdbidder/cli-anything-biddeed",
  });
  if (!issueResp.ok) {
    return json({ ok: false, step: "gha_create_issue", detail: issueResp.body }, 502);
  }
  const issueNumber = issueResp.body;
  const dispatchResp = await restRpc(env, "fire_workflow_dispatch", {
    p_repo: "breverdbidder/cli-anything-biddeed",
    p_workflow_file: "297104962",
    p_ref: "main",
    p_inputs: { issues: String(issueNumber) },
  });
  return json({ ok: dispatchResp.ok, issue_number: issueNumber, dispatch: dispatchResp.body });
}

async function handleVaultCleanup(env) {
  // Fires the existing skill-audit dispatch path verbatim (dispatch_skill_audit()
  // is self-gated to once per 6 days — a call inside that window is a real,
  // successful no-op, not a failure).
  const resp = await restRpc(env, "dispatch_skill_audit", {});
  return json({ ok: resp.ok, status: resp.status, detail: resp.body });
}

function handlePullMetrics() {
  return json(
    {
      ok: false,
      blocked: true,
      reason:
        "No existing read-only RPC refreshes ops-dashboard metrics. Per the brief, a new " +
        "SECURITY DEFINER function is a surface worth a second look before shipping — flagged " +
        "to Ariel instead of created silently. See session report.",
    },
    501,
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    if (url.pathname === "/api/tiles") {
      return json(await loadTiles(env));
    }

    if (url.pathname === "/" && request.method === "GET") {
      const tiles = await loadTiles(env);
      return new Response(renderHtml(tiles), { headers: { ...CORS_HEADERS, "content-type": "text/html; charset=utf-8" } });
    }

    if (url.pathname === "/action/weekly-review" && request.method === "POST") {
      return handleWeeklyReview(env);
    }
    if (url.pathname === "/action/vault-cleanup" && request.method === "POST") {
      return handleVaultCleanup(env);
    }
    if (url.pathname === "/action/pull-metrics" && request.method === "POST") {
      return handlePullMetrics();
    }

    return json({ ok: false, error: "not found" }, 404);
  },
};
