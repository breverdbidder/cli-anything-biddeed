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
import { reprojectParcelBoundary, stateplaneZoneForCoNo } from "./geo.js";
import { computeBuildableEnvelope, generateSiteMassing } from "./site-massing.js";
import { exportSiteMassingDXF } from "./site-dxf.js";
import { fetchParcelForMassing, resolveZoneStandards } from "./site-massing-lookup.js";
import {
  createRun,
  updateRunStatus,
  saveOptions,
  getRun,
  getOption,
  saveDxf,
  signDxfUrl,
} from "./site-massing-persistence.js";

const ALL_LAYOUT_TYPES = ["single_family", "townhome_row", "multifamily_grid"];

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

/**
 * POST /site-massing/generate
 * body: { parcel_id: string, co_no: number, layout_types?: string[], stories?: number, created_by?: string }
 * Resolves the parcel (zw_parcels) + its zone's dimensional standards
 * (zoning_districts/zone_standards — see site-massing-lookup.js for the
 * jurisdiction-resolution caveat), runs the constraint solver across the
 * requested layout types, persists the run + top-5 options, and returns
 * them (geojson-free — footprints are State-Plane feet, see site-massing.js).
 * DXF is NOT generated here — see the /dxf route, generated on demand.
 */
async function handleSiteMassingGenerate(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }

  const { parcel_id, co_no, layout_types, stories, created_by } = body;
  if (!parcel_id || typeof co_no !== "number") {
    return json({ ok: false, error: 'Missing required "parcel_id" (string) and/or "co_no" (number)' }, 400);
  }
  const requestedTypes =
    Array.isArray(layout_types) && layout_types.length > 0 ? layout_types : ALL_LAYOUT_TYPES;
  for (const t of requestedTypes) {
    if (!ALL_LAYOUT_TYPES.includes(t)) {
      return json({ ok: false, error: `Unknown layout_type "${t}" — must be one of ${ALL_LAYOUT_TYPES.join(", ")}` }, 400);
    }
  }

  const zone = stateplaneZoneForCoNo(co_no);
  if (!zone) {
    return json(
      { ok: false, error: `co_no ${co_no} is not in the supported State Plane zone table — refusing to guess a CRS. See geo.js.` },
      422
    );
  }

  let parcel;
  try {
    parcel = await fetchParcelForMassing(env, { parcelId: parcel_id, coNo: co_no });
  } catch (err) {
    return json({ ok: false, error: `Parcel lookup failed: ${err.message}` }, 500);
  }
  if (!parcel) {
    return json({ ok: false, error: `No zw_parcels row for pin_clean=${parcel_id}, co_no=${co_no} with a non-null geom.` }, 404);
  }
  if (!parcel.zoning_code) {
    return json({ ok: false, error: `Parcel ${parcel_id} has no zoning_code in zw_parcels — cannot resolve dimensional standards.` }, 422);
  }

  let resolved;
  try {
    resolved = await resolveZoneStandards(env, {
      county: parcel.county,
      zoningCode: parcel.zoning_code,
      siteCity: parcel.site_city,
    });
  } catch (err) {
    return json({ ok: false, error: `Zone standards lookup failed: ${err.message}` }, 500);
  }
  if (!resolved) {
    return json(
      {
        ok: false,
        error: `No zone_standards found for zoning_code "${parcel.zoning_code}" in county "${parcel.county}" (checked site_city match and unincorporated fallback).`,
      },
      422
    );
  }

  let rings, partsDropped;
  try {
    ({ rings, partsDropped } = reprojectParcelBoundary(parcel.geom, zone.epsg));
  } catch (err) {
    return json({ ok: false, error: `Reprojection failed: ${err.message}` }, 500);
  }

  const zoningSnapshot = {
    zoning_code: parcel.zoning_code,
    epsg: zone.epsg,
    epsg_confidence: zone.confidence,
    jurisdiction: resolved.jurisdiction.name,
    jurisdiction_resolution_method: resolved.resolutionMethod,
    zoning_district_id: resolved.zoningDistrict.id,
    standards: resolved.standards,
    multipolygon_parts_dropped: partsDropped,
  };

  let run;
  try {
    run = await createRun(env, {
      parcelId: parcel_id,
      coNo: co_no,
      zoningSnapshot,
      parcelBoundaryGeoJSON: parcel.geom,
      createdBy: created_by,
    });
  } catch (err) {
    return json({ ok: false, error: `Failed to create run: ${err.message}` }, 500);
  }

  let pooled = [];
  let envelope = null;
  for (const layoutType of requestedTypes) {
    let result;
    try {
      result = generateSiteMassing(rings[0], resolved.standards, layoutType, stories ? { stories } : {});
    } catch (err) {
      await updateRunStatus(env, run.id, "failed").catch(() => {});
      return json({ ok: false, error: `Solver failed for layout_type "${layoutType}": ${err.message}` }, 500);
    }
    envelope = result.envelope; // same envelope across layout types (parcel + standards don't change)
    pooled.push(...result.options.map((o) => ({ ...o, _rawScore: o.score })));
  }

  pooled.sort((a, b) => b._rawScore - a._rawScore);
  const top5 = pooled.slice(0, 5).map((o, i) => ({ ...o, option_rank: i + 1 }));

  let saved = [];
  try {
    if (top5.length > 0) saved = await saveOptions(env, run.id, top5);
    await updateRunStatus(env, run.id, top5.length > 0 ? "completed" : "no_compliant_options");
  } catch (err) {
    return json({ ok: false, error: `Failed to persist options: ${err.message}` }, 500);
  }

  return json({
    ok: true,
    run_id: run.id,
    zoning_snapshot: zoningSnapshot,
    envelope: envelope
      ? { width_ft: envelope.widthFt, depth_ft: envelope.depthFt, parcel_area_sqft: envelope.parcelAreaSqft, envelope_fully_inside_parcel: envelope.envelopeFullyInsideParcel }
      : null,
    options: saved,
  });
}

/**
 * GET /site-massing/:run_id
 * Fetch a prior run + its persisted options.
 */
async function handleSiteMassingGetRun(runId, env) {
  try {
    const run = await getRun(env, runId);
    if (!run) return json({ ok: false, error: `No site_massing_runs row for id ${runId}` }, 404);
    return json({ ok: true, run });
  } catch (err) {
    return json({ ok: false, error: err.message }, 500);
  }
}

/**
 * GET /site-massing/:run_id/options/:option_id/dxf
 * Generates (or returns the cached) DXF for one option, as a signed
 * Storage URL. The envelope is recomputed deterministically from the run's
 * stored parcel_boundary + zoning_snapshot.standards (computeBuildableEnvelope
 * is a pure function of those two inputs) rather than persisted separately.
 */
async function handleSiteMassingDxf(runId, optionId, env) {
  let run, option;
  try {
    run = await getRun(env, runId);
    if (!run) return json({ ok: false, error: `No site_massing_runs row for id ${runId}` }, 404);
    option = await getOption(env, runId, optionId);
    if (!option) return json({ ok: false, error: `No site_massing_options row for id ${optionId} on run ${runId}` }, 404);
  } catch (err) {
    return json({ ok: false, error: err.message }, 500);
  }

  if (option.dxf_path) {
    try {
      const url = await signDxfUrl(env, option.dxf_path);
      return json({ ok: true, dxf_url: url, cached: true });
    } catch (err) {
      return json({ ok: false, error: `Failed to sign cached DXF: ${err.message}` }, 500);
    }
  }

  const zone = stateplaneZoneForCoNo(run.co_no);
  if (!zone) return json({ ok: false, error: `co_no ${run.co_no} has no supported State Plane zone.` }, 422);

  let rings;
  try {
    ({ rings } = reprojectParcelBoundary(run.parcel_boundary, zone.epsg));
  } catch (err) {
    return json({ ok: false, error: `Reprojection failed: ${err.message}` }, 500);
  }

  const standards = run.zoning_snapshot?.standards;
  if (!standards) return json({ ok: false, error: "Run's zoning_snapshot is missing .standards — cannot recompute envelope." }, 500);

  let envelope;
  try {
    envelope = computeBuildableEnvelope(rings[0], standards);
  } catch (err) {
    return json({ ok: false, error: `Envelope recomputation failed: ${err.message}` }, 500);
  }

  let dxfString;
  try {
    dxfString = exportSiteMassingDXF({
      parcelRingFt: rings[0],
      envelopeRingFt: envelope.ring,
      option,
      meta: { parcelId: run.parcel_id, epsg: zone.epsg, coNo: run.co_no },
    });
  } catch (err) {
    return json({ ok: false, error: `DXF export failed: ${err.message}` }, 500);
  }

  try {
    await saveDxf(env, runId, optionId, dxfString);
    const url = await signDxfUrl(env, `site-dxf/${runId}/${optionId}.dxf`);
    return json({ ok: true, dxf_url: url, cached: false });
  } catch (err) {
    return json({ ok: false, error: `Failed to save/sign DXF: ${err.message}` }, 500);
  }
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
      if (url.pathname === "/site-massing/generate" && request.method === "POST") {
        return await handleSiteMassingGenerate(request, env);
      }
      const dxfMatch = url.pathname.match(/^\/site-massing\/([^/]+)\/options\/([^/]+)\/dxf$/);
      if (dxfMatch && request.method === "GET") {
        return await handleSiteMassingDxf(dxfMatch[1], dxfMatch[2], env);
      }
      const runMatch = url.pathname.match(/^\/site-massing\/([^/]+)$/);
      if (runMatch && request.method === "GET") {
        return await handleSiteMassingGetRun(runMatch[1], env);
      }
      return json({ ok: false, error: "Not found" }, 404);
    } catch (err) {
      return json({ ok: false, error: `Unhandled: ${err.message}` }, 500);
    }
  },
};
