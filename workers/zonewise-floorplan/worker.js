/**
 * ZoneWise Floor Plan Worker
 * ---------------------------------------------------------------------------
 * Wraps @chanmeng666/archlang (MIT) as a white-labeled ZoneWise.AI API.
 * No third-party branding in the output — this is a thin HTTP layer over a
 * pure-JS compiler.
 *
 * KNOWN LIMITATION (read before wiring up PDF/PNG in production):
 *   - `compile()` -> SVG is zero-dependency and confirmed to run in the
 *     Workers V8 isolate (no fs/child_process). This is the reliable path.
 *   - PDF export uses the optional `pdfkit` dependency, which is
 *     Node-oriented. It MAY work with the `nodejs_compat` compatibility
 *     flag (enabled in wrangler.jsonc) but has not been verified in a real
 *     Workers runtime here — test with `wrangler dev` before depending on
 *     it in production.
 *   - PNG export uses `@resvg/resvg-js`, a native Rust binary. This CANNOT
 *     run in a Workers isolate under any compat flag. Do not attempt to
 *     wire this endpoint into the Worker — if PNG is needed, run it in a
 *     Node environment (e.g. a GitHub Actions job or a Node-based Supabase
 *     Edge Function) instead.
 *
 * Recommended split for the real deployment:
 *   - SVG + validate + schedule  -> this Worker (fast, edge, guaranteed)
 *   - PDF (if pdfkit doesn't pan out in Workers) + PNG -> a Node-capable
 *     backend (Supabase Edge Function or a small Node service), called
 *     from this Worker or directly from the frontend.
 */

import { compile, describe, toPdf } from "@chanmeng666/archlang";
import { checkZoningCompliance } from "./zoning.js";
import { savePlanVersion, getCurrentPlan, getPlanHistory, getParcelPlans } from "./persistence.js";
import MCP_SCHEMA from "./mcp-tool-schema.json" with { type: "json" };
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*", // tighten to zonewise.ai in production
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { ...CORS_HEADERS, "content-type": "application/json" },
  });
}

/**
 * POST /floorplan/compile
 * body: { source: string, width?: number, parcel_id?: string, parcel?: object }
 * Compiles .arch DSL source to SVG + a structured summary (rooms, doors,
 * windows, areas in m²). Returns compiler diagnostics either way so the
 * caller (Claude, or a future UI) can iterate on errors/warnings.
 *
 * If `parcel` (buildable-envelope constraints — see zoning.js) is provided,
 * also runs zoning compliance against THIS parcel's actual limits and
 * returns it as `zoning`. Omit `parcel` to skip this — compile still works
 * as a plain floor-plan compiler.
 */
async function handleCompile(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }

  const { source, width, parcel } = body;
  if (!source || typeof source !== "string") {
    return json({ ok: false, error: 'Missing required "source" (.arch DSL text)' }, 400);
  }

  let result;
  try {
    result = compile(source, width ? { width } : {});
  } catch (err) {
    return json({ ok: false, error: `Compiler threw: ${err.message}` }, 500);
  }

  if (result.errors.length > 0) {
    return json(
      { ok: false, errors: result.errors, warnings: result.warnings, svg: null },
      422
    );
  }

  let summary = null;
  try {
    summary = describe(source);
  } catch {
    // describe() failing doesn't invalidate a successful compile; svg still returns.
  }

  let zoning = null;
  if (parcel && summary) {
    try {
      zoning = checkZoningCompliance(summary, parcel);
    } catch (err) {
      zoning = { ok: false, error: `Zoning check threw: ${err.message}` };
    }
  }

  return json({
    ok: true,
    svg: result.svg,
    warnings: result.warnings,
    summary, // rooms[], doors[], windows[], totals{} — areas in m²
    zoning, // null if no `parcel` was passed — see zoning.js for the check definitions
  });
}

/**
 * POST /floorplan/check-zoning
 * body: { source: string, parcel: object }
 * Zoning compliance only — no SVG render. Useful for re-checking one plan
 * against several candidate parcels, or checking mid-edit without paying
 * for a full compile.
 */
async function handleCheckZoning(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }

  const { source, parcel } = body;
  if (!source || typeof source !== "string") {
    return json({ ok: false, error: 'Missing required "source"' }, 400);
  }
  if (!parcel || typeof parcel !== "object") {
    return json({ ok: false, error: 'Missing required "parcel" constraints object' }, 400);
  }

  let summary;
  try {
    summary = describe(source);
  } catch (err) {
    return json({ ok: false, error: `describe() threw: ${err.message}` }, 500);
  }

  const zoning = checkZoningCompliance(summary, parcel);
  return json(zoning, zoning.ok === false && zoning.error ? 400 : 200);
}

/**
 * POST /floorplan/save
 * body: { parcel_id: string, plan_name?: string, source: string, parcel?: object, created_by?: string }
 * Compiles + (optionally) zoning-checks the source, then saves it as a new
 * version via persistence.js. Returns the saved row. Requires
 * SUPABASE_URL / SUPABASE_SERVICE_KEY bindings — see persistence.js.
 */
async function handleSave(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }
  const { parcel_id, plan_name, source, parcel, created_by } = body;
  if (!parcel_id || !source) {
    return json({ ok: false, error: 'Missing required "parcel_id" and/or "source"' }, 400);
  }

  let result;
  try {
    result = compile(source, {});
  } catch (err) {
    return json({ ok: false, error: `Compiler threw: ${err.message}` }, 500);
  }
  if (result.errors.length > 0) {
    return json({ ok: false, errors: result.errors, warnings: result.warnings }, 422);
  }

  let summary = null;
  try {
    summary = describe(source);
  } catch {
    /* non-fatal */
  }

  let zoning = null;
  if (parcel && summary) {
    try {
      zoning = checkZoningCompliance(summary, parcel);
    } catch (err) {
      zoning = { ok: false, error: `Zoning check threw: ${err.message}` };
    }
  }

  try {
    const saved = await savePlanVersion(env, {
      parcelId: parcel_id,
      planName: plan_name,
      source,
      svg: result.svg,
      summary,
      zoningResult: zoning,
      compilerWarnings: result.warnings,
      createdBy: created_by,
    });
    return json({ ok: true, saved, zoning });
  } catch (err) {
    return json({ ok: false, error: `Save failed: ${err.message}` }, 500);
  }
}

/**
 * GET /floorplan/get?parcel_id=...&plan_name=...
 * Latest saved version of a plan.
 */
async function handleGet(url, env) {
  const parcelId = url.searchParams.get("parcel_id");
  const planName = url.searchParams.get("plan_name") || "default";
  if (!parcelId) return json({ ok: false, error: "Missing parcel_id query param" }, 400);

  try {
    const plan = await getCurrentPlan(env, parcelId, planName);
    return json({ ok: true, plan });
  } catch (err) {
    return json({ ok: false, error: err.message }, 500);
  }
}

/**
 * GET /floorplan/history?parcel_id=...&plan_name=...
 * Full version history, newest first.
 */
async function handleHistory(url, env) {
  const parcelId = url.searchParams.get("parcel_id");
  const planName = url.searchParams.get("plan_name") || "default";
  if (!parcelId) return json({ ok: false, error: "Missing parcel_id query param" }, 400);

  try {
    const history = await getPlanHistory(env, parcelId, planName);
    return json({ ok: true, history });
  } catch (err) {
    return json({ ok: false, error: err.message }, 500);
  }
}

/**
 * GET /floorplan/parcel-plans?parcel_id=...
 * All current (latest) named plans for a parcel.
 */
async function handleParcelPlans(url, env) {
  const parcelId = url.searchParams.get("parcel_id");
  if (!parcelId) return json({ ok: false, error: "Missing parcel_id query param" }, 400);

  try {
    const plans = await getParcelPlans(env, parcelId);
    return json({ ok: true, plans });
  } catch (err) {
    return json({ ok: false, error: err.message }, 500);
  }
}

/**
 * POST /floorplan/compile-pdf
 * body: { source: string }
 * CONCLUSION (tested via `wrangler dev` against the real workerd runtime,
 * not guessed): pdfkit does NOT work in Cloudflare Workers, even with
 * nodejs_compat and manual global shims. Two failures in sequence:
 *   1. `__dirname is not defined` — fixed with a call-time shim (see below).
 *   2. `no such file or directory, readAll '/data/Helvetica.afm'` — pdfkit
 *      reads its bundled font metric files via fs.readFileSync at runtime.
 *      Workers has no real filesystem; there is no reasonable shim for
 *      this without repackaging pdfkit's font data as embedded assets and
 *      patching its font loader — real engineering effort, not a config
 *      flag. Not attempted here.
 * RECOMMENDATION: generate PDF client-side from the SVG (e.g. jsPDF +
 * svg2pdf.js in the browser) instead of server-side in the Worker. This
 * endpoint is left in place, still correctly reporting the real failure,
 * as a regression check if a future ArchLang version changes its PDF
 * backend.
 */
async function handleCompilePdf(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }

  const { source } = body;
  if (!source || typeof source !== "string") {
    return json({ ok: false, error: 'Missing required "source"' }, 400);
  }

  let result;
  try {
    result = compile(source, {});
  } catch (err) {
    return json({ ok: false, error: `Compiler threw: ${err.message}` }, 500);
  }
  if (result.errors.length > 0) {
    return json({ ok: false, errors: result.errors }, 422);
  }
  if (!result.scene) {
    return json({ ok: false, error: "compile() returned no scene — cannot serialize to PDF." }, 500);
  }

  try {
    // pdfkit references CommonJS globals (__dirname/__filename) that don't
    // exist in the Workers ESM runtime, even under nodejs_compat. This is
    // a call-time reference, not an import-time one, so shimming here (vs.
    // at module top, which runs too late relative to hoisted imports) is
    // the correct place to attempt the fix.
    if (typeof globalThis.__dirname === "undefined") globalThis.__dirname = "/";
    if (typeof globalThis.__filename === "undefined") globalThis.__filename = "/worker.js";

    const pdfBytes = await toPdf(result.scene);
    // base64-encode for a clean JSON response; a real deployment would
    // more likely return the bytes directly with a pdf content-type.
    let binary = "";
    for (let i = 0; i < pdfBytes.length; i++) binary += String.fromCharCode(pdfBytes[i]);
    const base64 = btoa(binary);
    return json({ ok: true, pdf_base64: base64, bytes: pdfBytes.length });
  } catch (err) {
    return json(
      {
        ok: false,
        error: `toPdf() failed in this runtime: ${err.message}`,
        note: "This is the pdfkit-in-Workers compatibility question from the README — this error is the real answer, not a guess.",
      },
      500
    );
  }
}

/**
 * POST /floorplan/validate
 * body: { source: string }
 * Diagnostics only, no SVG — cheap fast-fail check while iterating on a
 * plan before requesting a full render.
 */
async function handleValidate(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }

  const { source } = body;
  if (!source || typeof source !== "string") {
    return json({ ok: false, error: 'Missing required "source"' }, 400);
  }

  let result;
  try {
    result = compile(source, {});
  } catch (err) {
    return json({ ok: false, error: `Compiler threw: ${err.message}` }, 500);
  }

  return json({
    ok: result.errors.length === 0,
    errors: result.errors,
    warnings: result.warnings,
  });
}

/**
 * GET /floorplan/schema
 * Serves the MCP-style tool schema (see mcp-tool-schema.json) so an
 * external agent/client can discover how to call this API. Not required
 * for Claude-in-chat usage (which calls source directly) — this is for a
 * future external MCP client wiring into ZoneWise.
 */
function handleSchema() {
  return json(MCP_SCHEMA);
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    try {
      if (url.pathname === "/floorplan/compile" && request.method === "POST") {
        return await handleCompile(request);
      }
      if (url.pathname === "/floorplan/check-zoning" && request.method === "POST") {
        return await handleCheckZoning(request);
      }
      if (url.pathname === "/floorplan/compile-pdf" && request.method === "POST") {
        return await handleCompilePdf(request);
      }
      if (url.pathname === "/floorplan/save" && request.method === "POST") {
        return await handleSave(request, env);
      }
      if (url.pathname === "/floorplan/get" && request.method === "GET") {
        return await handleGet(url, env);
      }
      if (url.pathname === "/floorplan/history" && request.method === "GET") {
        return await handleHistory(url, env);
      }
      if (url.pathname === "/floorplan/parcel-plans" && request.method === "GET") {
        return await handleParcelPlans(url, env);
      }
      if (url.pathname === "/floorplan/validate" && request.method === "POST") {
        return await handleValidate(request);
      }
      if (url.pathname === "/floorplan/schema" && request.method === "GET") {
        return handleSchema();
      }
      return json({ ok: false, error: "Not found" }, 404);
    } catch (err) {
      return json({ ok: false, error: `Unhandled: ${err.message}` }, 500);
    }
  },
};
