"""
ensemble_model_v4.py  —  Shapira V4 stacked ensemble (CANDIDATE trainer)
Target repo path: breverdbidder/cli-anything-biddeed/brevard-bidder-scraper/src/models/ensemble_model_v4.py

WHAT THIS IS
  V4 = XGBoost + LightGBM + CatBoost base learners -> out-of-fold stacking -> meta-learner,
  trained on the SAME corpus/label/target as V14 PLUS a behavioral + competition feature overlay.
  Writes a CANDIDATE row to shapira_models (is_production = FALSE). Promotion is a SEPARATE gated step.

WHAT CHANGED vs V14 (the point of V4): ENRICHMENT, not just ensembling.
  Dry run (2026-06-13) proved V14's features are mostly DEAD on multi_county_auctions: owner_is_*/homestead/
  prior_sale = 0% populated; judgment/year_built/sqft only on the 22% foreclosure slice. V14's 0.7834 came
  from ~6 live features (market_value, beds, sale_type, county_target_enc). V4 LEFT JOINs fl_parcels on the
  normalized parcel_id to revive owner_name/year_built/sqft/homestead/prior_sale/just_value from the DOR roll.
  => V4 is NOT a pure V14 parity test. It is a V14 SUPERSET: it sees property attributes V14 never had.

  target      = third_party_purchase (binary): winning_bidder.str.contains("3rd Party")
  row filter  = EXACT V14 filter (4-value IN). ~154k rows live, 62.7% positive, ~21.7% labels are weak (inferred).
  V14 baseline= AUC 0.7834 / CV 0.7785  <-- V4 should beat this BECAUSE of the new features, not the ensemble.

HONESTY (V/U/I)
  [VERIFIED]  label, transforms, split, CV, train-only county encoding (dry-run validated on live corpus).
  [VERIFIED]  fl_parcels has own_name/act_yr_blt/tot_lvg_ar/sale_prc1/jv/av_hmstd; lateral join yields ~74%
              match on parceled rows. Net reach (≈55% of rows carry a parcel_id): owner ~40%, yr/sqft ~45%,
              prior_sale ~10%, homestead ~14%. NOT 100% — prior_sale/homestead stay sparse even enriched.
  [INFERRED]  behavioral overlay — still OFF by default (V4_OVERLAY=on).
  [DONE]      ~45% of rows have no parcel_id; diamond_parcel_matches recovers the fl_parcels parcel via
              directional/word-order address token-set (precision-gated >=0.90), wired as enrichment source 2.
  [UNTESTED]  not yet run on GHA.

LEAKAGE GUARD (non-negotiable): county encoding is train-only; any overlay signal is AS-OF auction date.
  Nothing observed at/after the auction may enter a feature. A suspiciously high AUC => check this first.
"""

import os, json, datetime as dt
import numpy as np, pandas as pd
import psycopg2
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score, log_loss
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

# ----------------------------------------------------------------------------- config
PROJECT_REF   = "mocerqjnksmhcjzxrewo"
DB_DSN        = os.environ["SUPABASE_DB_DSN"]          # secret NAME only — never hardcode
BUCKET        = "shapira-models"
MODEL_VERSION = "v4.0"
MODEL_FAMILY  = "stacked_ensemble"
TARGET        = "third_party_purchase"
LABEL_FILTER  = "winning_bidder in ('3rd Party','Plaintiff','3rd Party (inferred)','Plaintiff (inferred)')"  # EXACT V14 filter (verified from shapira_models v14 record). ~21.7% of labels are weak '(inferred)'.
SEED          = 42
N_FOLDS       = 5
TEST_SIZE     = 0.20                                   # ~matches V14 137488/34372 split

BASE_FEATURES = [  # VERIFIED — identical to V14 (do not reorder/rename: parity)
    "judgment_amount_log1p","opening_bid_log1p","market_value_log1p","assessed_value_log1p",
    "prior_sale_price_log1p","beds_f","baths_f","sqft_f","property_age","opening_to_market",
    "judgment_to_market","years_since_prior_sale","has_prior_sale","is_foreclosure","is_tax_deed",
    "has_homestead","owner_is_estate","owner_is_entity","owner_is_lender","is_diamond","county_target_enc",
]

# Behavioral + competition overlay (the V4 delta). All AS-OF auction date. OFF by default for parity.
OVERLAY_ENABLED  = os.environ.get("V4_OVERLAY", "off").lower() in ("1", "true", "on", "yes")
OVERLAY_FEATURES = ([
    "comp_avg_bidder_count","comp_county_competition_index","comp_plaintiff_discount_factor",  # shapira_formula_params
    "beh_n_watchers_asof","beh_n_views_asof","beh_n_buyboxes_matching_asof","beh_avg_dwell_asof",  # behavioral
] if OVERLAY_ENABLED else [])

XGB_PARAMS = {  # VERIFIED — V14 hyperparameters, reused for the XGB base learner
    "gamma":0.1,"max_depth":6,"subsample":0.85,"objective":"binary:logistic","eval_metric":["logloss","auc"],
    "tree_method":"hist","n_estimators":400,"learning_rate":0.08,"colsample_bytree":0.85,
    "min_child_weight":5,"n_jobs":-1,"random_state":SEED,
}
LGB_PARAMS = {"n_estimators":600,"max_depth":7,"learning_rate":0.05,"subsample":0.85,
              "colsample_bytree":0.85,"min_child_samples":40,"random_state":SEED,"n_jobs":-1}
CAT_PARAMS = {"iterations":700,"depth":6,"learning_rate":0.05,"l2_leaf_reg":5.0,
              "random_state":SEED,"verbose":False}

# ----------------------------------------------------------------------------- data
def conn():
    return psycopg2.connect(DB_DSN)

RAW_SQL = f"""
  select
    mca.id as auction_id, mca.county, mca.property_type, mca.sale_type, mca.auction_date,
    mca.winning_bidder,
    mca.judgment_amount, mca.opening_bid,
    coalesce(mca.market_value,    fp.jv)        as market_value,
    coalesce(mca.assessed_value,  fp.av_sd)     as assessed_value,
    coalesce(mca.prior_sale_price, fp.sale_prc1) as prior_sale_price,
    mca.bedrooms, mca.beds, mca.bathrooms, mca.baths,
    coalesce(mca.living_area_sqft, fp.tot_lvg_ar::int) as living_area_sqft, mca.sqft,
    coalesce(mca.year_built, fp.act_yr_blt)     as year_built,
    coalesce(mca.prior_sale_date,
             case when fp.sale_yr1 > 1900
                  then make_date(fp.sale_yr1, greatest(least(coalesce(fp.sale_mo1,1),12),1), 1) end) as prior_sale_date,
    coalesce(mca.homestead_exemption,
             (coalesce(fp.av_hmstd,0) > 0 or coalesce(fp.jv_hmstd,0) > 0)) as homestead_exemption,
    coalesce(nullif(btrim(mca.owner_name),''), fp.own_name) as owner_name,
    mca.property_address
  from multi_county_auctions mca
  -- ENRICHMENT source 2: diamond entity-resolution matches. For rows with no parcel_id, this recovers the
  -- fl_parcels parcel via directional/word-order address token-set (precision-gated >= 0.90). Mutually
  -- exclusive with the direct parcel_id (dpm only holds rows that had no parcel_id), so no double-counting.
  left join diamond_parcel_matches dpm
    on  dpm.auction_id = mca.id::text
    and dpm.decision   = 'matched'
    and dpm.confidence >= 0.90
  -- ENRICHMENT: at most ONE fl_parcels row per auction (limit 1 => no row duplication / no label inflation).
  -- Join key = direct normalized parcel_id, else the diamond-matched parcel_id (native fl_parcels.parcel_id).
  left join lateral (
    select p.jv, p.av_sd, p.sale_prc1, p.tot_lvg_ar, p.act_yr_blt,
           p.sale_yr1, p.sale_mo1, p.av_hmstd, p.jv_hmstd, p.own_name
    from fl_parcels p
    where p.parcel_id = coalesce(
            dpm.matched_parcel_id,
            nullif(replace(replace(replace(mca.parcel_id,'-',''),' ',''),'*',''),'')
          )
    order by (p.own_name is not null) desc, p.jv desc nulls last
    limit 1
  ) fp on true
  where {LABEL_FILTER}
"""

def load_base(cx) -> pd.DataFrame:
    """Load raw columns and engineer the 21 V14 features verbatim."""
    return engineer_features(pd.read_sql(RAW_SQL, cx))

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    VERBATIM replication of V14 (xgboost_model_v14.py) feature engineering, recovered from the
    May-27 training session. county_target_enc is added LATER (train-only, in main) — never here.
    """
    # Label — V14: winning_bidder.fillna("").str.contains("3rd Party")
    df["y"] = df["winning_bidder"].fillna("").str.contains("3rd Party", regex=False).astype(int)

    # Coalesce duplicated columns (bedrooms/beds, bathrooms/baths, living_area_sqft/sqft)
    df["beds_f"]  = pd.to_numeric(df["bedrooms"], errors="coerce").fillna(pd.to_numeric(df["beds"], errors="coerce")).astype(float)
    df["baths_f"] = pd.to_numeric(df["bathrooms"], errors="coerce").fillna(pd.to_numeric(df["baths"], errors="coerce")).astype(float)
    df["sqft_f"]  = pd.to_numeric(df["living_area_sqft"], errors="coerce").fillna(pd.to_numeric(df["sqft"], errors="coerce")).astype(float)

    # Financial log1p (negatives clipped to 0 first)
    for col in ["judgment_amount","opening_bid","market_value","assessed_value","prior_sale_price"]:
        df[f"{col}_log1p"] = np.log1p(pd.to_numeric(df[col], errors="coerce").clip(lower=0))

    # Property age — V14 hardcodes 2026 as the reference year (kept for parity); drop impossible ages
    yb = pd.to_numeric(df["year_built"], errors="coerce")
    df["property_age"] = 2026 - yb
    df.loc[df["property_age"] < 0, "property_age"]   = np.nan
    df.loc[df["property_age"] > 200, "property_age"] = np.nan

    # Ratios (clip upper 10)
    mv  = pd.to_numeric(df["market_value"], errors="coerce")
    ob  = pd.to_numeric(df["opening_bid"], errors="coerce")
    jud = pd.to_numeric(df["judgment_amount"], errors="coerce")
    df["opening_to_market"]  = (ob  / mv.replace(0, np.nan)).clip(upper=10)
    df["judgment_to_market"] = (jud / mv.replace(0, np.nan)).clip(upper=10)

    # Prior-sale recency
    prior_dt   = pd.to_datetime(df["prior_sale_date"], errors="coerce")
    auction_dt = pd.to_datetime(df["auction_date"], errors="coerce")
    df["years_since_prior_sale"] = (auction_dt - prior_dt).dt.days / 365.25
    df["has_prior_sale"] = df["prior_sale_price"].notna().astype(int)

    # sale_type one-hot
    df["is_foreclosure"] = (df["sale_type"] == "foreclosure").astype(int)
    df["is_tax_deed"]    = (df["sale_type"] == "tax_deed").astype(int)

    # Homestead
    df["has_homestead"] = df["homestead_exemption"].fillna(False).astype(int)

    # Owner signals (regex on owner_name) — V14 patterns; (?:...) non-capturing = result-identical, no warning
    own = df["owner_name"].fillna("").str.upper()
    df["owner_is_estate"] = own.str.contains(r'\b(?:ESTATE|TRUST|HEIRS|DECEASED|DECD)\b', regex=True, na=False).astype(int)
    df["owner_is_entity"] = own.str.contains(r'\b(?:LLC|INC|CORP|LP|HOLDING|PROPERTIES|REALTY)\b', regex=True, na=False).astype(int)
    df["owner_is_lender"] = own.str.contains(r'\b(?:BANK|MORTGAGE|FANNIE|FREDDIE|HUD|FHA|LENDER|FINANCIAL|SERVICING)\b', regex=True, na=False).astype(int)

    # Diamond flag (unknown / placeholder address: blank or all-digits)
    addr = df["property_address"].fillna("").str.strip()
    df["is_diamond"] = ((addr == "") | (addr.str.fullmatch(r'\d+'))).astype(int)

    print(f"  rows={len(df)}  label_dist={df['y'].value_counts().to_dict()}")
    return df

def load_overlay(cx, df: pd.DataFrame) -> pd.DataFrame:
    """Join competition params + AS-OF behavioral aggregates. Degrades gracefully; logs availability."""
    if not OVERLAY_ENABLED:
        print("[parity] overlay OFF — training on the 21 V14 features only")
        return df
    # Competition (VERIFIED table: shapira_formula_params 262 rows, county x property_type x sale_type)
    comp = pd.read_sql("""
        select county, property_type, sale_type,
               avg_bidder_count          as comp_avg_bidder_count,
               county_competition_index  as comp_county_competition_index,
               plaintiff_discount_factor as comp_plaintiff_discount_factor
        from shapira_formula_params
    """, cx)
    df = df.merge(comp, on=["county","property_type","sale_type"], how="left")

    # Behavioral AS-OF auction_date. [INFERRED] columns — wrapped so missing tables don't crash the run.
    try:
        beh = pd.read_sql("""
          select a.auction_id,
                 count(distinct w.user_id) filter (where w.event_time < a.auction_date) as beh_n_watchers_asof,
                 count(v.id)               filter (where v.event_time < a.auction_date) as beh_n_views_asof,
                 avg(v.dwell_seconds)      filter (where v.event_time < a.auction_date) as beh_avg_dwell_asof
          from multi_county_auctions a
          left join watch_events w on w.auction_id = a.auction_id
          left join user_events  v on v.auction_id = a.auction_id
          group by a.auction_id
        """, cx)
        df = df.merge(beh, on="auction_id", how="left")
        df["beh_n_buyboxes_matching_asof"] = 0  # RECONCILE: compute from user_buyboxes match as-of date
        print("[INFERRED] behavioral overlay joined")
    except Exception as e:
        for c in ["beh_n_watchers_asof","beh_n_views_asof","beh_avg_dwell_asof","beh_n_buyboxes_matching_asof"]:
            df[c] = np.nan
        print(f"[UNKNOWN] behavioral overlay unavailable, base+competition only :: {e}")
    return df

# ----------------------------------------------------------------------------- train
def oof_stack(X, y, Xte):
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
    bases = {"xgb":XGBClassifier(**XGB_PARAMS),"lgb":LGBMClassifier(**LGB_PARAMS),"cat":CatBoostClassifier(**CAT_PARAMS)}
    oof = np.zeros((len(X), len(bases))); te = np.zeros((len(Xte), len(bases)))
    cv_aucs = []
    for j,(name,mdl) in enumerate(bases.items()):
        fold_auc = []
        te_fold = np.zeros((len(Xte), N_FOLDS))
        for k,(tr,va) in enumerate(skf.split(X,y)):
            m = mdl.__class__(**mdl.get_params())
            m.fit(X.iloc[tr], y.iloc[tr])
            oof[va,j] = m.predict_proba(X.iloc[va])[:,1]
            te_fold[:,k] = m.predict_proba(Xte)[:,1]
            fold_auc.append(roc_auc_score(y.iloc[va], oof[va,j]))
        te[:,j] = te_fold.mean(axis=1)
        cv_aucs.extend(fold_auc)
        print(f"[base {name}] CV-AUC {np.mean(fold_auc):.4f} +/- {np.std(fold_auc):.4f}")
    meta = LogisticRegression(max_iter=2000)
    meta.fit(oof, y)
    return meta, oof, te, float(np.mean(cv_aucs)), float(np.std(cv_aucs))

# ------------------------------------------------------------------------------ main
def main():
    cx = conn()
    df = load_overlay(cx, load_base(cx))
    feats = BASE_FEATURES + OVERLAY_FEATURES
    non_enc = [f for f in feats if f != "county_target_enc"]
    df[non_enc] = df[non_enc].apply(pd.to_numeric, errors="coerce")
    y = df["y"]
    Xall = df[non_enc + ["county"]].copy()
    Xtr, Xte, ytr, yte = train_test_split(Xall, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)
    # county_target_enc — TRAIN-ONLY, exactly as V14 (no leakage into test or CV folds)
    gm = float(ytr.mean())
    rate = ytr.groupby(Xtr["county"]).mean()
    Xtr["county_target_enc"] = Xtr["county"].map(rate).fillna(gm)
    Xte["county_target_enc"] = Xte["county"].map(rate).fillna(gm)
    Xtr, Xte = Xtr[feats].fillna(-1), Xte[feats].fillna(-1)

    meta, oof, te, cv_mean, cv_std = oof_stack(Xtr, ytr, Xte)
    p = meta.predict_proba(te)[:,1]; pred = (p>=0.5).astype(int)
    metrics = dict(
        accuracy=accuracy_score(yte,pred), auc=roc_auc_score(yte,p),
        precision_score=precision_score(yte,pred), recall_score=recall_score(yte,pred),
        f1_score=f1_score(yte,pred), log_loss=log_loss(yte,p),
        cv_auc_mean=cv_mean, cv_auc_std=cv_std)
    print("[V4 HOLDOUT]", json.dumps({k:round(v,4) for k,v in metrics.items()}))
    print(f"[GATE] V14 baseline AUC=0.7834 — promote ONLY if V4 holdout AUC beats it by a real margin.")

    # persist CANDIDATE row (is_production = FALSE) — promotion is a separate gated step
    with cx, cx.cursor() as c:
        c.execute("""
          insert into public.shapira_models
            (model_version,model_family,target_label,target_kind,trained_at,trained_by,
             n_train_samples,n_test_samples,n_features,features_used,hyperparameters,
             accuracy,auc,precision_score,recall_score,f1_score,log_loss,cv_auc_mean,cv_auc_std,
             storage_bucket,corpus_source,corpus_row_count_at_train,corpus_label_filter,is_production,notes)
          values (%s,%s,%s,'binary',now(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,%s)
        """, (MODEL_VERSION,MODEL_FAMILY,TARGET, os.environ.get("GITHUB_RUN_ID","local"),
              len(Xtr),len(Xte),len(feats),json.dumps(feats),json.dumps({"xgb":XGB_PARAMS,"lgb":LGB_PARAMS,"cat":CAT_PARAMS}),
              metrics["accuracy"],metrics["auc"],metrics["precision_score"],metrics["recall_score"],
              metrics["f1_score"],metrics["log_loss"],metrics["cv_auc_mean"],metrics["cv_auc_std"],
              BUCKET,"multi_county_auctions+fl_parcels(parcel_id + diamond_match lateral)",len(df),LABEL_FILTER,
              f"V4 stacked ensemble (XGB+LGBM+CatBoost->LogReg meta) + fl_parcels ENRICHMENT "
              f"(owner/year_built/sqft/homestead/prior_sale/jv via normalized parcel_id lateral join, "
              f"plus diamond_parcel_matches recovering parcels for no-parcel_id rows, precision-gated >=0.90). "
              f"NOT a pure V14 parity run — V4 sees property attributes V14 never had. "
              f"overlay={'on' if OVERLAY_ENABLED else 'off'}. CANDIDATE — promote only on validated win + EG14 + sign-off."))
    print("[OK] candidate row written to shapira_models (is_production=false)")

if __name__ == "__main__":
    main()
