#!/usr/bin/env python3
"""
SUMMIT-B V4 — Stacked Ensemble Training
Patent Claim 8: XGBoost + LightGBM + CatBoost + Random Forest meta-learner
Trains on multi_county_auctions completed outcomes, uploads to shapira-models storage.
"""
import os, json, pickle, io, requests, numpy as np, pandas as pd
from datetime import datetime
from xgboost import XGBClassifier
import lightgbm as lgb
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score

SB_URL = os.environ["SUPABASE_URL"]
SVC_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
HEADERS = {"apikey": SVC_KEY, "Authorization": f"Bearer {SVC_KEY}"}

print("=== SUMMIT-B V4 Ensemble Training ===")

# Pull training data
print("Fetching training data from Supabase...")
r = requests.get(
    f"{SB_URL}/rest/v1/multi_county_auctions"
    "?auction_status=eq.completed&tier1_sale_status=not.is.null"
    "&select=county,sale_type,opening_bid,assessed_value,judgment_amount,"
    "prior_sale_price,beds,baths,tot_lvg_ar,act_yr_blt,"
    "has_homestead,owner_is_estate,owner_is_entity,owner_is_lender,"
    "is_diamond,is_foreclosure,is_tax_deed,tier1_sale_status&limit=10000",
    headers=HEADERS, timeout=60
)
df = pd.DataFrame(r.json())
print(f"Raw rows: {len(df)}")

# Feature engineering
for col in ["opening_bid", "assessed_value", "judgment_amount", "prior_sale_price"]:
    df[f"{col}_log1p"] = np.log1p(pd.to_numeric(df[col], errors="coerce").fillna(0))

df["opening_to_market"] = (
    pd.to_numeric(df["opening_bid"], errors="coerce") /
    pd.to_numeric(df["assessed_value"], errors="coerce").replace(0, np.nan)
).fillna(0)
df["judgment_to_market"] = (
    pd.to_numeric(df["judgment_amount"], errors="coerce") /
    pd.to_numeric(df["assessed_value"], errors="coerce").replace(0, np.nan)
).fillna(0)

df["sqft_f"] = pd.to_numeric(df["tot_lvg_ar"], errors="coerce").fillna(0)
df["property_age"] = 2026 - pd.to_numeric(df["act_yr_blt"], errors="coerce").fillna(1990)
df["beds_f"] = pd.to_numeric(df["beds"], errors="coerce").fillna(0)
df["baths_f"] = pd.to_numeric(df["baths"], errors="coerce").fillna(0)
df["target"] = (df["tier1_sale_status"] == "SOLD").astype(int)

# County target encoding
county_enc = df.groupby("county")["target"].mean()
df["county_target_enc"] = df["county"].map(county_enc).fillna(0.5)

FEATURES = [
    "judgment_amount_log1p", "opening_bid_log1p", "assessed_value_log1p",
    "prior_sale_price_log1p", "beds_f", "baths_f", "sqft_f", "property_age",
    "opening_to_market", "judgment_to_market", "has_homestead",
    "owner_is_estate", "owner_is_entity", "owner_is_lender", "is_diamond",
    "is_foreclosure", "is_tax_deed", "county_target_enc"
]

df = df.dropna(subset=["target"])
X = df[FEATURES].fillna(0).astype(float).values
y = df["target"].values
print(f"Training samples: {len(X)} | Positive rate: {y.mean():.3f}")

# Base learners
xgb = XGBClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, eval_metric="auc",
    random_state=42, verbosity=0)
lgbm = lgb.LGBMClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1)
catb = CatBoostClassifier(iterations=500, depth=6, learning_rate=0.05,
    random_state=42, verbose=0)

kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

print("Training XGBoost...")
xgb_oof = cross_val_predict(xgb, X, y, cv=kf, method="predict_proba")[:,1]
print(f"  XGBoost OOF AUC: {roc_auc_score(y, xgb_oof):.4f}")

print("Training LightGBM...")
lgbm_oof = cross_val_predict(lgbm, X, y, cv=kf, method="predict_proba")[:,1]
print(f"  LightGBM OOF AUC: {roc_auc_score(y, lgbm_oof):.4f}")

print("Training CatBoost...")
catb_oof = cross_val_predict(catb, X, y, cv=kf, method="predict_proba")[:,1]
print(f"  CatBoost OOF AUC: {roc_auc_score(y, catb_oof):.4f}")

# RF meta-learner on OOF predictions
meta_X = np.column_stack([xgb_oof, lgbm_oof, catb_oof])
rf_meta = RandomForestClassifier(n_estimators=200, max_depth=4, random_state=42)
rf_meta.fit(meta_X, y)
ensemble_pred = rf_meta.predict_proba(meta_X)[:,1]
auc_ensemble = roc_auc_score(y, ensemble_pred)
print(f"\nV4 Ensemble AUC: {auc_ensemble:.4f}")
print(f"AUC improvement over XGBoost v14.0 (0.7834): {auc_ensemble - 0.7834:+.4f}")

# Train final models on full dataset
print("\nTraining final models on full dataset...")
xgb.fit(X, y)
lgbm.fit(X, y)
catb.fit(X, y)
final_meta_X = np.column_stack([
    xgb.predict_proba(X)[:,1],
    lgbm.predict_proba(X)[:,1],
    catb.predict_proba(X)[:,1]
])
rf_meta.fit(final_meta_X, y)

ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
bundle = {
    "xgb": xgb, "lgbm": lgbm, "catb": catb, "rf_meta": rf_meta,
    "features": FEATURES,
    "meta_feature_order": ["xgb_prob", "lgbm_prob", "catb_prob"],
    "version": f"v4.0-{ts}",
    "auc_ensemble": float(auc_ensemble),
    "auc_xgb": float(roc_auc_score(y, xgb_oof)),
    "auc_lgbm": float(roc_auc_score(y, lgbm_oof)),
    "auc_catb": float(roc_auc_score(y, catb_oof)),
    "n_train_samples": int(len(X))
}

buf = io.BytesIO()
pickle.dump(bundle, buf)
bundle_bytes = buf.getvalue()
storage_path = f"v4/{ts}/ensemble.pkl"

print(f"\nUploading to shapira-models/{storage_path} ({len(bundle_bytes):,} bytes)...")
r = requests.post(
    f"{SB_URL}/storage/v1/object/shapira-models/{storage_path}",
    headers={**HEADERS, "Content-Type": "application/octet-stream", "x-upsert": "true"},
    data=bundle_bytes, timeout=300
)
print(f"Upload: {r.status_code} {r.text[:100]}")

# Register in shapira_models
registry = {
    "model_version": f"v4.0-{ts}",
    "model_family": "stacked_ensemble_xgb_lgbm_catboost_rf_meta",
    "target_label": "third_party_purchase",
    "target_kind": "binary",
    "n_train_samples": int(len(X)),
    "n_features": len(FEATURES),
    "accuracy": float(accuracy_score(y, rf_meta.predict(final_meta_X))),
    "auc": float(auc_ensemble),
    "f1_score": float(f1_score(y, rf_meta.predict(final_meta_X))),
    "features_used": FEATURES,
    "is_production": True,
    "storage_path_model": storage_path,
    "trained_at": datetime.utcnow().isoformat()
}
r = requests.post(
    f"{SB_URL}/rest/v1/shapira_models",
    headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
    json=registry, timeout=30
)
print(f"Registry: {r.status_code}")

# Demote old models
requests.patch(
    f"{SB_URL}/rest/v1/shapira_models?model_version=neq.{registry['model_version']}",
    headers={**HEADERS, "Content-Type": "application/json"},
    json={"is_production": False}, timeout=30
)

print(f"\n=== V4 ENSEMBLE TRAINING COMPLETE ===")
print(f"Version: {registry['model_version']}")
print(f"AUC: {auc_ensemble:.4f} | Samples: {len(X)} | Storage: {storage_path}")
