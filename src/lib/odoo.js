/**
 * src/lib/odoo.js — JSON-RPC client for self-hosted Odoo 18 Community ("Projects" to
 * customers — never call it Odoo in anything customer-facing, see docs/infra/ODOO.md).
 *
 * Server-to-server only: the Worker talks to Odoo's /jsonrpc endpoint directly with a
 * scoped API key (ODOO_URL / ODOO_DB / ODOO_LOGIN / ODOO_API_KEY). No MCP — MCP
 * (breverdbidder/mcp-server-odoo, MPL-2.0) is for Ariel's own Claude Desktop/Code
 * access only, per the C10 licensing ruling in issue #20008; this file has nothing to
 * do with that server.
 *
 * NOT wired into src/worker.js's existing /chat/api/projects routes yet — Odoo isn't
 * deployed and reachable in this session (see docs/spec/20008.md for why), and wiring
 * a call to an unreachable service into the live production worker would break real
 * traffic. This module is self-contained and importable once Odoo is confirmed up.
 */

export class OdooClient {
  constructor(env) {
    this.url = (env.ODOO_URL || "").replace(/\/$/, "");
    this.db = env.ODOO_DB;
    this.login = env.ODOO_LOGIN;
    this.apiKey = env.ODOO_API_KEY;
    this._uid = null;
    if (!this.url || !this.db || !this.login || !this.apiKey) {
      throw new Error("OdooClient requires ODOO_URL, ODOO_DB, ODOO_LOGIN, ODOO_API_KEY");
    }
  }

  async _rpc(service, method, args) {
    const res = await fetch(`${this.url}/jsonrpc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "call",
        params: { service, method, args },
        id: crypto.randomUUID(),
      }),
    });
    if (!res.ok) {
      throw new Error(`odoo ${service}.${method} HTTP ${res.status}`);
    }
    const body = await res.json();
    if (body.error) {
      const msg = body.error.data?.message || body.error.message || JSON.stringify(body.error);
      throw new Error(`odoo ${service}.${method} failed: ${msg}`);
    }
    return body.result;
  }

  async authenticate() {
    if (this._uid) return this._uid;
    this._uid = await this._rpc("common", "authenticate", [this.db, this.login, this.apiKey, {}]);
    if (!this._uid) throw new Error("odoo authenticate failed — check ODOO_LOGIN/ODOO_API_KEY/ODOO_DB");
    return this._uid;
  }

  async execute(model, method, args = [], kwargs = {}) {
    const uid = await this.authenticate();
    return this._rpc("object", "execute_kw", [this.db, uid, this.apiKey, model, method, args, kwargs]);
  }

  searchRead(model, domain = [], fields = [], opts = {}) {
    return this.execute(model, "search_read", [domain, fields], opts);
  }

  create(model, values) {
    return this.execute(model, "create", [values]);
  }

  write(model, ids, values) {
    return this.execute(model, "write", [ids, values]);
  }
}

/** Every Odoo write from the Worker is logged to the existing agent_ops_log table
 * (dispatch_id/task/status/evidence/severity — same shape as workers/everest-bank-engine).
 * Never throws: a logging failure must not roll back or mask the underlying Odoo write. */
async function logOdooWrite(env, task, status, evidence, severity = "info") {
  try {
    const res = await fetch(`${env.SUPABASE_URL}/rest/v1/agent_ops_log`, {
      method: "POST",
      headers: {
        apikey: env.SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify({ dispatch_id: "20008", task, status, evidence, severity }),
    });
    if (!res.ok) console.error("agent_ops_log insert failed:", res.status, await res.text());
  } catch (err) {
    console.error("agent_ops_log insert threw:", err.message);
  }
}

/** Worker call 1/3 — create project.project. deed_budget's project.project override
 * (infra/odoo/addons/deed_budget/models/project_project.py) auto-creates the linked
 * account.analytic.account in the same RPC call. */
export async function createProjectWithAnalytic(client, env, { name, companyId, partnerId }) {
  const values = { name, company_id: companyId };
  if (partnerId) values.partner_id = partnerId;
  const projectId = await client.create("project.project", values);
  const [project] = await client.searchRead(
    "project.project", [["id", "=", projectId]], ["id", "name", "account_id"]
  );
  await logOdooWrite(env, "odoo_create_project", "VERIFIED", { projectId, analyticAccountId: project.account_id?.[0] });
  return { projectId, analyticAccountId: project.account_id?.[0] ?? null };
}

/** Worker call 2/3 — deed.budget.line (custom Community-safe budget model; Odoo 18
 * Community has no account_budget app — see docs/infra/ODOO.md licensing note). */
export async function addBudgetLine(client, env, { analyticAccountId, name, plannedAmount, dateFrom, dateTo }) {
  const lineId = await client.create("deed.budget.line", {
    analytic_account_id: analyticAccountId,
    name,
    planned_amount: plannedAmount,
    date_from: dateFrom,
    date_to: dateTo,
  });
  await logOdooWrite(env, "odoo_add_budget_line", "VERIFIED", { lineId, analyticAccountId, plannedAmount });
  return { lineId };
}

/** Worker call 3/3 — vendor bill (account.move, move_type=in_invoice), analytic
 * distribution tags the line to the project's analytic account, then posted. Posting
 * ("the draw") is what generates the account.analytic.line actuals deed.budget.line
 * reads for budget-vs-actual. */
export async function addVendorBill(client, env, { companyId, partnerId, analyticAccountId, invoiceLines, post = true }) {
  const moveId = await client.create("account.move", {
    move_type: "in_invoice",
    company_id: companyId,
    partner_id: partnerId,
    invoice_line_ids: invoiceLines.map((line) => [0, 0, {
      name: line.description,
      quantity: line.quantity ?? 1,
      price_unit: line.priceUnit,
      analytic_distribution: { [String(analyticAccountId)]: 100 },
    }]),
  });
  if (post) {
    await client.execute("account.move", "action_post", [[moveId]]);
  }
  await logOdooWrite(env, "odoo_add_vendor_bill", "VERIFIED", { moveId, analyticAccountId, posted: post });
  return { moveId, posted: post };
}
