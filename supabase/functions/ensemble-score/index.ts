// ensemble-score — Supabase Edge Function (Deno)
// V4 Stacked Ensemble ONNX inference: XGBoost + LightGBM + CatBoost + RF meta-learner
//
// Called by MCP ensemble-model.js instead of running onnxruntime-node locally.
// Uses onnxruntime-web (WASM) — no native binaries, works in Deno Edge runtime.
//
// POST /functions/v1/ensemble-score
// Body: { features: float32[13] }
// Returns: { probability, xgb_prob, lgbm_prob, catb_prob, model_version, auc }
//
// Auth: Supabase service-role JWT (internal only — never exposed to customers)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import * as ort from "https://esm.sh/onnxruntime-web@1.20.1/dist/ort.node.min.mjs";

const MODEL_VERSION = "v4.0-20260802-015242";
const ARTIFACTS = ["xgb_base.onnx", "lgbm_base.onnx", "catb_base.onnx", "rf_meta.onnx"];

// Module-level cache — persists across warm invocations
let _sessions: Record<string, ort.InferenceSession> | null = null;

async function getSessions(): Promise<Record<string, ort.InferenceSession>> {
  if (_sessions) return _sessions;

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  const loaded: Record<string, ort.InferenceSession> = {};

  for (const name of ARTIFACTS) {
    const { data, error } = await supabase
      .from("model_artifacts")
      .select("artifact_b64")
      .eq("model_version", MODEL_VERSION)
      .eq("artifact_name", name)
      .single();

    if (error || !data?.artifact_b64) {
      throw new Error(`ONNX artifact missing: ${name} — ${error?.message}`);
    }

    // Decode base64 → Uint8Array → InferenceSession
    const binary = Uint8Array.from(atob(data.artifact_b64), (c) => c.charCodeAt(0));
    loaded[name] = await ort.InferenceSession.create(binary);
  }

  _sessions = loaded;
  return _sessions;
}

Deno.serve(async (req: Request) => {
  // CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "https://mcp.biddeed.ai",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
      },
    });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "POST only" }), { status: 405 });
  }

  // Auth: require service-role JWT (internal MCP calls only)
  const auth = req.headers.get("Authorization") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  if (!auth.includes(serviceKey.slice(-20))) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), { status: 401 });
  }

  let features: number[];
  try {
    const body = await req.json();
    features = body.features;
    if (!Array.isArray(features) || features.length !== 13) {
      throw new Error("features must be float32[13]");
    }
  } catch (e) {
    return new Response(JSON.stringify({ error: `Bad request: ${e.message}` }), { status: 400 });
  }

  try {
    const sess = await getSessions();
    const input13 = new ort.Tensor("float32", new Float32Array(features), [1, 13]);

    // Run 3 base learners in parallel
    const [xgbOut, lgbmOut, catbOut] = await Promise.all([
      sess["xgb_base.onnx"].run({ float_input: input13 }),
      sess["lgbm_base.onnx"].run({ float_input: input13 }),
      sess["catb_base.onnx"].run({ features: input13 }), // CatBoost input name
    ]);

    const xgbProb  = (xgbOut["probabilities"].data  as Float32Array)[1];
    const lgbmProb = (lgbmOut["probabilities"].data as Float32Array)[1];
    const catbProb = (catbOut["probabilities"].data as Float32Array)[1];

    // RF meta-learner
    const metaInput = new ort.Tensor("float32", new Float32Array([xgbProb, lgbmProb, catbProb]), [1, 3]);
    const rfOut = await sess["rf_meta.onnx"].run({ meta_input: metaInput });
    const ensembleProb = (rfOut["output_probability"].data as Float32Array)[1];

    return new Response(JSON.stringify({
      probability:  Number(ensembleProb.toFixed(4)),
      xgb_prob:     Number(xgbProb.toFixed(4)),
      lgbm_prob:    Number(lgbmProb.toFixed(4)),
      catb_prob:    Number(catbProb.toFixed(4)),
      model_version: MODEL_VERSION,
      auc:          0.9468,
    }), {
      headers: { "Content-Type": "application/json" },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: e.message, stack: e.stack?.slice(0, 500) }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
