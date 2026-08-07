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
"""

import modal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app    = modal.App("biddeed-ensemble-scorer")
web    = FastAPI()

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

_ensemble = None

def _load_ensemble():
    global _ensemble
    if _ensemble is not None:
        return _ensemble
    import os, pickle, base64, requests as req
    sb_url = os.environ["SUPABASE_URL"]
    sb_key = os.environ["SUPABASE_SERVICE_KEY"]
    r = req.get(
        f"{sb_url}/rest/v1/model_artifacts",
        headers={"Authorization": f"Bearer {sb_key}", "apikey": sb_key},
        params={
            "select":           "artifact_b64",
            "artifact_name":    "eq.ensemble.pkl",
            "model_version":    f"eq.{MODEL_VERSION}",
            "limit":            "1",
        },
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f"ensemble.pkl not found for {MODEL_VERSION}")
    _ensemble = pickle.loads(base64.b64decode(rows[0]["artifact_b64"]))
    return _ensemble


@web.get("/health")
async def health():
    return {"status": "ok", "model_version": MODEL_VERSION, "model_loaded": _ensemble is not None}


@web.post("/score")
async def score(request: Request):
    import os, numpy as np
    body = await request.json()

    # Auth
    auth_secret = os.environ.get("ENSEMBLE_WORKER_SECRET", "")
    if not auth_secret or body.get("auth_secret") != auth_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    fv = body.get("feature_vector")
    if not isinstance(fv, list) or len(fv) != 13:
        raise HTTPException(status_code=400, detail="feature_vector must be 13 floats")

    ensemble = _load_ensemble()
    X = np.array([fv], dtype=np.float32)

    if isinstance(ensemble, dict):
        xgb_prob  = float(ensemble["xgb"].predict_proba(X)[0][1])
        lgbm_prob = float(ensemble["lgbm"].predict_proba(X)[0][1])
        catb_prob = float(ensemble["catb"].predict_proba(X)[0][1])
        meta_X    = np.array([[xgb_prob, lgbm_prob, catb_prob]], dtype=np.float32)
        ensemble_prob = float(ensemble["rf_meta"].predict_proba(meta_X)[0][1])
    else:
        ensemble_prob = float(ensemble.predict_proba(X)[0][1])
        xgb_prob = lgbm_prob = catb_prob = None

    return {
        "probability":   ensemble_prob,
        "base_learners": {"xgb_prob": xgb_prob, "lgbm_prob": lgbm_prob, "catb_prob": catb_prob},
        "meta_learner":  "rf",
        "model_version": MODEL_VERSION,
        "auc":           0.9468,
        "method":        "v4_pkl_modal",
    }


@app.function(
    image=image,
    secrets=[secrets],
    timeout=60,
    keep_warm=1,
    allow_concurrent_inputs=10,
)
@modal.asgi_app()
def serve():
    return web


@app.local_entrypoint()
def main():
    import math
    x = [
        math.log1p(164134.35), math.log1p(72100),  math.log1p(125014),
        math.log1p(75100),     3, 2, 1400, 30,
        72100/83000,           164134.35/83000,
        1, 0, 0.74,
    ]
    print("Local test vector ready — deploy first, then call /score endpoint")
