#!/usr/bin/env python3
# CONFIDENTIAL — Trade Secret of Everest Capital USA
# Protected under DTSA (18 U.S.C. § 1836) and FUTSA (Fla. Stat. § 688)
"""Modal: SUMMIT-B V4 Stacked Ensemble Inference endpoint.

Exposes POST /score for BidDeed.AI predict_auction_outcome (S5 report).
Primary inference runtime — called by ensemble-model.js in the MCP server.

Architecture: XGBoost + LightGBM + CatBoost base learners
              → Random Forest meta-learner (stacked ensemble)
AUC: 0.9468 (vs v14.0 XGBoost baseline 0.7834)
Trained: 2026-08-02 on 5,118 FL auction outcomes
Source: ensemble.pkl in model_artifacts table (Supabase)

Deploy:  modal deploy modal/ensemble_scorer.py
Secrets: everest-secrets (SUPABASE_URL, SUPABASE_SERVICE_KEY, ENSEMBLE_WORKER_SECRET)
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
    "fastapi[standard]==0.115.0",
)

secrets = modal.Secret.from_name("everest-secrets")

MODEL_VERSION = "v4.0-20260802-015242"


# ── Model cache (warm across requests) ────────────────────────────────────────
_ensemble = None


def _load_ensemble():
    global _ensemble
    if _ensemble is not None:
        return _ensemble

    import os, pickle, base64, requests as req

    sb_url = os.environ["SUPABASE_URL"]
    sb_key = os.environ["SUPABASE_SERVICE_KEY"]

    headers = {
        "Authorization": f"Bearer {sb_key}",
        "apikey": sb_key,
    }

    r = req.get(
        f"{sb_url}/rest/v1/model_artifacts",
        headers=headers,
        params={
            "select": "artifact_b64",
            "artifact_name": "eq.ensemble.pkl",
            "model_version": f"eq.{MODEL_VERSION}",
            "limit": "1",
        },
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f"ensemble.pkl not found in model_artifacts for {MODEL_VERSION}")

    pkl_bytes = base64.b64decode(rows[0]["artifact_b64"])
    _ensemble = pickle.loads(pkl_bytes)
    return _ensemble


# ── Web endpoint ──────────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[secrets],
    timeout=60,
    # Keep 1 warm container — eliminates cold starts for active sessions
    keep_warm=1,
    # Allow up to 10 concurrent requests per container before spawning new one
    allow_concurrent_inputs=10,
)
@modal.web_endpoint(method="POST", docs=False)
def score(request: dict) -> dict:
    """Score a single auction feature vector through the V4 stacked ensemble."""
    import os
    import numpy as np
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    # Auth
    auth_secret = os.environ.get("ENSEMBLE_WORKER_SECRET", "")
    provided    = request.get("auth_secret", "")
    if not auth_secret or provided != auth_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    feature_vector = request.get("feature_vector")
    if not isinstance(feature_vector, list) or len(feature_vector) != 13:
        raise HTTPException(status_code=400, detail="feature_vector must be 13 floats")

    ensemble = _load_ensemble()
    X = np.array([feature_vector], dtype=np.float32)

    # Stacked ensemble: base learners → meta-learner
    # ensemble.pkl is a dict: {xgb, lgbm, catb, rf_meta} OR a Pipeline
    if isinstance(ensemble, dict):
        xgb_prob  = float(ensemble["xgb"].predict_proba(X)[0][1])
        lgbm_prob = float(ensemble["lgbm"].predict_proba(X)[0][1])
        catb_prob = float(ensemble["catb"].predict_proba(X)[0][1])
        meta_X    = np.array([[xgb_prob, lgbm_prob, catb_prob]], dtype=np.float32)
        ensemble_prob = float(ensemble["rf_meta"].predict_proba(meta_X)[0][1])
    else:
        # Pipeline or VotingClassifier — single predict_proba call
        ensemble_prob = float(ensemble.predict_proba(X)[0][1])
        xgb_prob = lgbm_prob = catb_prob = None

    return {
        "probability":   ensemble_prob,
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


@app.function(image=image, secrets=[secrets], timeout=10)
@modal.web_endpoint(method="GET", docs=False)
def health(request: dict) -> dict:
    """Health check — no auth required."""
    return {
        "status":        "ok",
        "model_version": MODEL_VERSION,
        "model_loaded":  _ensemble is not None,
    }


@app.local_entrypoint()
def main():
    """Test locally: modal run modal/ensemble_scorer.py"""
    import math
    test_vector = [
        math.log1p(164134.35), math.log1p(72100),  math.log1p(125014),
        math.log1p(75100),     3, 2, 1400, 30,
        72100 / 83000,         164134.35 / 83000,
        1, 0, 0.74,
    ]
    result = score.remote({"feature_vector": test_vector, "auth_secret": "local-test"})
    print(f"Result: {result}")
