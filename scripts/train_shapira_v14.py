#!/usr/bin/env python3
"""
Shapira V14 XGBoost Training Pipeline
=====================================
Reads labeled rows from multi_county_auctions, trains XGBoost binary classifier
predicting 3rd-party purchase probability, persists model artifact to Supabase
Storage bucket `shapira-models`, registers metadata in `shapira_models` table.

References:
  - ci_v65_event_log id: 13be7baa-c50c-4fd1-8223-091788cb9bda
  - summit_chat_dispatch id: 2572cb98-5c24-4606-800d-0b106e83de7f

Honesty: this is V14 (single XGBoost). NOT the V4 patent's stacked ensemble.
V4 stacked is queued as SUMMIT-C (Q3 2026).
"""

import os, sys, json, time, io
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (
    accuracy_score, roc_auc_score, precision_score, recall_score,
    f1_score, log_loss, confusion_matrix, classification_report
)

# ── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET       = "shapira-models"
MODEL_VERSION = "v14.0"
TARGET_LABEL = "third_party_purchase"
WORKFLOW_RUN_ID = os.environ.get("GITHUB_RUN_ID", "local")
SUMMIT_DISPATCH_ID = "2572cb98-5c24-4606-800d-0b106e83de7f"
CI_EVENT_ID = "13be7baa-c50c-4fd1-8223-091788cb9bda"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Filter applied at corpus-fetch time. Rows where winning_bidder is the 4-value
# enum (3rd Party / Plaintiff / either-inferred). Confirmed clean labels.
CORPUS_LABEL_FILTER = (
    "winning_bidder=in.(\"3rd Party\",\"Plaintiff\","
    "\"3rd Party (inferred)\",\"Plaintiff (inferred)\")"
)

# ── Phase 1: fetch labeled corpus ─────────────────────────────────────────────
def fetch_corpus():
    """Page through multi_county_auctions and return DataFrame of labeled rows."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Fetching corpus...")
    select = (
        "id,sale_type,county,property_type,winning_bidder,"
        "judgment_amount,opening_bid,market_value,assessed_value,"
        "beds,baths,sqft,year_built,bedrooms,bathrooms,living_area_sqft,"
        "homestead_exemption,prior_sale_date,prior_sale_price,"
        "auction_status,property_address,owner_name,plaintiff,auction_date"
    )
    page_size = 1000
    all_rows = []
    offset = 0
    while True:
        url = (f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
               f"?select={select}&{CORPUS_LABEL_FILTER}"
               f"&order=id.asc&limit={page_size}&offset={offset}")
        r = requests.get(url, headers=HEADERS, timeout=120)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        all_rows.extend(batch)
        offset += page_size
        if offset % 10000 == 0:
            print(f"  fetched {offset} rows so far...")
        if len(batch) < page_size:
            break
    df = pd.DataFrame(all_rows)
    print(f"  total rows fetched: {len(df)}")
    return df

# ── Phase 2: feature engineering ──────────────────────────────────────────────
def engineer_features(df):
    """Build feature matrix X and label vector y. XGBoost handles NaN natively
    so we keep missing values as-is rather than imputing."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Engineering features...")

    # Coalesce duplicated columns (some rows use beds, others use bedrooms etc)
    df["beds_f"] = df["bedrooms"].fillna(df["beds"]).astype(float)
    df["baths_f"] = df["bathrooms"].fillna(df["baths"]).astype(float)
    df["sqft_f"] = df["living_area_sqft"].fillna(df["sqft"]).astype(float)

    # Numeric financial features (raw and log1p — XGBoost can use either)
    for col in ["judgment_amount", "opening_bid", "market_value", "assessed_value", "prior_sale_price"]:
        df[f"{col}_log1p"] = np.log1p(pd.to_numeric(df[col], errors="coerce").clip(lower=0))

    # Property age
    df["year_built_f"] = pd.to_numeric(df["year_built"], errors="coerce")
    df["property_age"] = 2026 - df["year_built_f"]
    df.loc[df["property_age"] < 0, "property_age"] = np.nan
    df.loc[df["property_age"] > 200, "property_age"] = np.nan

    # Ratios
    mv = pd.to_numeric(df["market_value"], errors="coerce")
    ob = pd.to_numeric(df["opening_bid"], errors="coerce")
    jud = pd.to_numeric(df["judgment_amount"], errors="coerce")
    df["opening_to_market"] = ob / mv.replace(0, np.nan)
    df["judgment_to_market"] = jud / mv.replace(0, np.nan)
    # Clip extreme ratios
    for c in ["opening_to_market", "judgment_to_market"]:
        df[c] = df[c].clip(upper=10)

    # Prior sale recency
    df["prior_sale_dt"] = pd.to_datetime(df["prior_sale_date"], errors="coerce")
    auction_dt = pd.to_datetime(df["auction_date"], errors="coerce")
    df["years_since_prior_sale"] = ((auction_dt - df["prior_sale_dt"]).dt.days / 365.25)
    df["has_prior_sale"] = df["prior_sale_price"].notna().astype(int)

    # Categorical: sale_type one-hot
    df["is_foreclosure"] = (df["sale_type"] == "foreclosure").astype(int)
    df["is_tax_deed"]    = (df["sale_type"] == "tax_deed").astype(int)

    # Homestead
    df["has_homestead"] = df["homestead_exemption"].fillna(False).astype(int)

    # Owner signals (Triangle subset — recompute here to avoid joining triangle.*)
    own = df["owner_name"].fillna("").str.upper()
    df["owner_is_estate"] = own.str.contains(r"\b(ESTATE|TRUST|HEIRS?|DECEASED|DECD)\b", regex=True, na=False).astype(int)
    df["owner_is_entity"] = own.str.contains(r"\b(LLC|INC|CORP|LP|HOLDING|PROPERTIES|REALTY)\b", regex=True, na=False).astype(int)
    df["owner_is_lender"] = own.str.contains(r"\b(BANK|MORTGAGE|FANNIE|FREDDIE|HUD|FHA|LENDER|FINANCIAL|SERVICING)\b", regex=True, na=False).astype(int)

    # Diamond flag (unknown address)
    addr = df["property_address"].fillna("").str.strip()
    df["is_diamond"] = ((addr == "") | (addr.str.fullmatch(r"\d+"))).astype(int)

    # County target encoding — done AFTER train/test split to avoid leakage.
    # We'll compute it in the train function.

    # Label
    bidder = df["winning_bidder"].fillna("")
    df["y"] = bidder.str.contains("3rd Party", regex=False).astype(int)

    feature_cols = [
        "judgment_amount_log1p", "opening_bid_log1p", "market_value_log1p",
        "assessed_value_log1p", "prior_sale_price_log1p",
        "beds_f", "baths_f", "sqft_f", "property_age",
        "opening_to_market", "judgment_to_market",
        "years_since_prior_sale", "has_prior_sale",
        "is_foreclosure", "is_tax_deed", "has_homestead",
        "owner_is_estate", "owner_is_entity", "owner_is_lender", "is_diamond",
    ]

    print(f"  feature columns: {len(feature_cols)}")
    print(f"  label distribution: {df['y'].value_counts().to_dict()}")
    return df[feature_cols + ["y", "county"]].copy(), feature_cols

# ── Phase 3: train ────────────────────────────────────────────────────────────
def train_model(df_feat, feature_cols):
    print(f"[{datetime.now(timezone.utc).isoformat()}] Training XGBoost V14...")

    X = df_feat[feature_cols].copy()
    y = df_feat["y"].values
    county = df_feat["county"].values

    X_train, X_test, y_train, y_test, cty_tr, cty_te = train_test_split(
        X, y, county, test_size=0.20, stratify=y, random_state=42
    )

    # Target-encode county using TRAIN ONLY (no leakage)
    cty_target_rate = pd.Series(y_train, index=cty_tr).groupby(level=0).mean()
    global_rate = float(y_train.mean())
    X_train["county_target_enc"] = pd.Series(cty_tr).map(cty_target_rate).fillna(global_rate).values
    X_test["county_target_enc"] = pd.Series(cty_te).map(cty_target_rate).fillna(global_rate).values
    feature_cols = feature_cols + ["county_target_enc"]

    hyperparameters = {
        "max_depth": 6, "learning_rate": 0.08, "n_estimators": 400,
        "min_child_weight": 5, "gamma": 0.1, "subsample": 0.85,
        "colsample_bytree": 0.85, "objective": "binary:logistic",
        "eval_metric": ["logloss", "auc"], "random_state": 42,
        "tree_method": "hist", "n_jobs": -1
    }
    model = XGBClassifier(**hyperparameters)

    # 5-fold CV on training fold for AUC stability estimate
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    print("  running 5-fold CV...")
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=-1)
    print(f"  CV AUC mean={cv_scores.mean():.4f}  std={cv_scores.std():.4f}  folds={cv_scores.tolist()}")

    # Final fit on full train
    print("  fitting final model on full training set...")
    t0 = time.time()
    model.fit(X_train, y_train, verbose=False)
    fit_seconds = time.time() - t0
    print(f"  fit time: {fit_seconds:.1f}s")

    # Test set evaluation
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "auc": float(roc_auc_score(y_test, y_proba)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "log_loss": float(log_loss(y_test, y_proba)),
        "cv_auc_mean": float(cv_scores.mean()),
        "cv_auc_std": float(cv_scores.std()),
        "cv_folds": cv_scores.tolist(),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "fit_seconds": float(fit_seconds),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(y_test, y_pred, output_dict=True),
        "feature_importance": dict(zip(feature_cols, model.feature_importances_.tolist())),
        "county_target_encoding_map": {k: float(v) for k, v in cty_target_rate.items()},
    }

    print("\n  === METRICS ===")
    print(f"  Accuracy: {metrics['accuracy']*100:.2f}%")
    print(f"  AUC:      {metrics['auc']:.4f}  (CV: {cv_scores.mean():.4f} ± {cv_scores.std():.4f})")
    print(f"  Precision: {metrics['precision']:.4f}")
    print(f"  Recall:    {metrics['recall']:.4f}")
    print(f"  F1:        {metrics['f1']:.4f}")
    print(f"  Log loss:  {metrics['log_loss']:.4f}")

    return model, metrics, feature_cols, hyperparameters

# ── Phase 4: persist artifacts ────────────────────────────────────────────────
def upload_artifact(path, body_bytes, content_type):
    """PUT object to Supabase Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    r = requests.post(url, headers=headers, data=body_bytes, timeout=60)
    if r.status_code not in (200, 201):
        # Some Supabase Storage versions return PUT semantics
        r = requests.put(url, headers=headers, data=body_bytes, timeout=60)
    r.raise_for_status()
    return r.json() if r.text else {}

def persist(model, metrics, feature_cols, hyperparameters):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    prefix = f"v14/{ts}"
    print(f"[{datetime.now(timezone.utc).isoformat()}] Persisting to {BUCKET}/{prefix}/...")

    # Serialize XGBoost native JSON format (5-10x smaller than pickle, version-stable)
    model_json = model.get_booster().save_raw(raw_format="json").decode()
    upload_artifact(f"{prefix}/model.json", model_json.encode(), "application/json")

    features_blob = json.dumps({
        "version": MODEL_VERSION, "features": feature_cols,
        "hyperparameters": hyperparameters, "target_label": TARGET_LABEL,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "workflow_run_id": WORKFLOW_RUN_ID,
    }, indent=2)
    upload_artifact(f"{prefix}/features.json", features_blob.encode(), "application/json")

    metrics_blob = json.dumps(metrics, indent=2, default=str)
    upload_artifact(f"{prefix}/metrics.json", metrics_blob.encode(), "application/json")

    # Register in shapira_models — use REST endpoint with service key
    registry_row = {
        "model_version": MODEL_VERSION,
        "model_family": "xgboost",
        "target_label": TARGET_LABEL,
        "target_kind": "binary",
        "trained_by": f"gha:{WORKFLOW_RUN_ID}",
        "n_train_samples": metrics["n_train"],
        "n_test_samples": metrics["n_test"],
        "n_features": len(feature_cols),
        "features_used": feature_cols,
        "hyperparameters": hyperparameters,
        "accuracy": metrics["accuracy"],
        "auc": metrics["auc"],
        "precision_score": metrics["precision"],
        "recall_score": metrics["recall"],
        "f1_score": metrics["f1"],
        "log_loss": metrics["log_loss"],
        "cv_auc_mean": metrics["cv_auc_mean"],
        "cv_auc_std": metrics["cv_auc_std"],
        "storage_bucket": BUCKET,
        "storage_path_model": f"{prefix}/model.json",
        "storage_path_features": f"{prefix}/features.json",
        "storage_path_metrics": f"{prefix}/metrics.json",
        "corpus_source": "multi_county_auctions",
        "corpus_row_count_at_train": metrics["n_train"] + metrics["n_test"],
        "corpus_label_filter": CORPUS_LABEL_FILTER,
        "is_production": True,  # first real V14 model = production
        "notes": "First real V14 training run. Single XGBoost (NOT V4 stacked).",
        "ci_event_id": CI_EVENT_ID,
        "summit_dispatch_id": SUMMIT_DISPATCH_ID,
    }

    # Demote any prior is_production=true for v14 family (unique index would block otherwise)
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/shapira_models?model_version=like.v14*&is_production=eq.true",
        headers={**HEADERS, "Prefer": "return=minimal"},
        json={"is_production": False}, timeout=30
    )
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/shapira_models",
        headers={**HEADERS, "Prefer": "return=representation"},
        json=registry_row, timeout=30
    )
    r.raise_for_status()
    row = r.json()[0]
    print(f"  registered model: {row['id']}  is_production=true")
    return row, prefix

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    df = fetch_corpus()
    df_feat, feature_cols = engineer_features(df)
    model, metrics, feature_cols, hyperparameters = train_model(df_feat, feature_cols)
    row, prefix = persist(model, metrics, feature_cols, hyperparameters)

    print("\n" + "=" * 70)
    print("SHAPIRA V14 TRAINING COMPLETE")
    print("=" * 70)
    print(f"Model UUID:    {row['id']}")
    print(f"Storage path:  {BUCKET}/{prefix}/")
    print(f"AUC:           {metrics['auc']:.4f}  (CV: {metrics['cv_auc_mean']:.4f} ± {metrics['cv_auc_std']:.4f})")
    print(f"Accuracy:      {metrics['accuracy']*100:.2f}%")
    print(f"Precision/Recall/F1: {metrics['precision']:.3f} / {metrics['recall']:.3f} / {metrics['f1']:.3f}")
    print("=" * 70)

    # Write summary to GHA step output if running in CI
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"# Shapira V14 Training Results\n\n")
            f.write(f"- **Model UUID:** `{row['id']}`\n")
            f.write(f"- **AUC:** {metrics['auc']:.4f} (CV {metrics['cv_auc_mean']:.4f} ± {metrics['cv_auc_std']:.4f})\n")
            f.write(f"- **Accuracy:** {metrics['accuracy']*100:.2f}%\n")
            f.write(f"- **Precision / Recall / F1:** {metrics['precision']:.3f} / {metrics['recall']:.3f} / {metrics['f1']:.3f}\n")
            f.write(f"- **n_train / n_test:** {metrics['n_train']} / {metrics['n_test']}\n")
            f.write(f"- **Storage:** `{BUCKET}/{prefix}/`\n")
            f.write(f"- **SUMMIT:** [{SUMMIT_DISPATCH_ID}](https://supabase.com/dashboard)\n")

if __name__ == "__main__":
    main()
