#!/usr/bin/env python3
# CONFIDENTIAL — Trade Secret of Everest Capital USA
# Protected under DTSA (18 U.S.C. § 1836) and FUTSA (Fla. Stat. § 688)
"""Modal: SUMMIT-B V4 Stacked Ensemble Inference endpoint.

Exposes POST /score and GET /health for BidDeed.AI predict_auction_outcome.
Primary inference runtime — called by ensemble-model.js in the MCP server.

Architecture: XGBoost + LightGBM + CatBoost → Random Forest meta-learner
AUC: 0.9468  |  Trained: 2026-08-02  |  Source: ensemble.pkl in model_artifacts

Deploy:  modal deploy modal/ensemble_scorer.py
Secrets: everest-secrets (SUPABASE_URL, SUPABASE_SERVICE_KEY, ENSEMBLE_WORKER_SECRET)
Modal SDK: 1.5.x  (keep_warm→min_containers, allow_concurrent_inputs→max_inputs)
"""

import modal

app = modal.App("biddeed-ensemble-scorer")

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "scikit-learn==1.5.2",
    "xgboost==2.1.1",
    "lightgbm==4.5.0",
    "catboost==1.2.7",
    "numpy==1.26.4",
    "requests==2.32.3",
    "fastapi==0.115.0",
    "uvicorn==0.30.6",
)

secrets       = modal.Secret.from_name("everest-secrets")
MODEL_VERSION = "v4.0-20260802-015242"


@app.function(
    image=image,
    secrets=[secrets],
    timeout=60,
    min_containers=1,   # keep 1 warm — eliminates cold starts
    max_inputs=10,      # concurrent requests per container
)
@modal.asgi_app()
def serve():
    import os, pickle, base64
    import numpy as np
    import requests as req
    from fastapi import FastAPI, HTTPException, Request

    web      = FastAPI()
    _model   = {}   # mutable cache: {"ensemble": <loaded model>}

    def load_ensemble():
        if "ensemble" in _model:
            return _model["ensemble"]
        sb_url = os.environ["SUPABASE_URL"]
        sb_key = os.environ["SUPABASE_SERVICE_KEY"]
        r = req.get(
            f"{sb_url}/rest/v1/model_artifacts",
            headers={"Authorization": f"Bearer {sb_key}", "apikey": sb_key},
            params={
                "select":        "artifact_b64",
                "artifact_name": "eq.ensemble.pkl",
                "model_version": f"eq.{MODEL_VERSION}",
                "limit":         "1",
            },
            timeout=30,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            raise RuntimeError(f"ensemble.pkl not found for {MODEL_VERSION}")
        _model["ensemble"] = pickle.loads(base64.b64decode(rows[0]["artifact_b64"]))
        return _model["ensemble"]

    @web.get("/health")
    async def health():
        return {
            "status":        "ok",
            "model_version": MODEL_VERSION,
            "model_loaded":  "ensemble" in _model,
        }

    @web.post("/score")
    async def score(request: Request):
        body        = await request.json()
        auth_secret = os.environ.get("ENSEMBLE_WORKER_SECRET", "")
        if not auth_secret or body.get("auth_secret") != auth_secret:
            raise HTTPException(status_code=401, detail="Unauthorized")

        fv = body.get("feature_vector")
        if not isinstance(fv, list) or len(fv) != 13:
            raise HTTPException(status_code=400, detail="feature_vector must be 13 floats")

        mdl = load_ensemble()
        X   = np.array([fv], dtype=np.float32)

        if isinstance(mdl, dict):
            xgb_prob  = float(mdl["xgb"].predict_proba(X)[0][1])
            lgbm_prob = float(mdl["lgbm"].predict_proba(X)[0][1])
            catb_prob = float(mdl["catb"].predict_proba(X)[0][1])
            meta_X    = np.array([[xgb_prob, lgbm_prob, catb_prob]], dtype=np.float32)
            prob      = float(mdl["rf_meta"].predict_proba(meta_X)[0][1])
        else:
            prob      = float(mdl.predict_proba(X)[0][1])
            xgb_prob  = lgbm_prob = catb_prob = None

        return {
            "probability":   prob,
            "base_learners": {
                "xgb_prob":  xgb_prob,
                "lgbm_prob": lgbm_prob,
                "catb_prob": catb_prob,
            },
            "meta_learner":  "rf",
            "model_version": MODEL_VERSION,
            "auc":           0.9468,
            "method":        "v4_pkl_modal",
        }

    return web


@app.local_entrypoint()
def main():
    print("Deploy: modal deploy modal/ensemble_scorer.py")
    print("Then verify: curl https://<modal-url>/health")
