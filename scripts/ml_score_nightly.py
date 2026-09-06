#!/usr/bin/env python3
"""Issue #20044 item 2a — nightly batch scoring: real 3-learner V4 ensemble.

The Node report path (packages/biddeed-mcp/src/report/ensemble-model.js)
cannot execute the trained sklearn/xgboost/lightgbm/catboost pickles that
live in model_artifacts.artifact_b64 (artifact_name='ensemble.pkl',
model_version='v4.0-20260802-015242') — Node has no Python runtime. This
script does, and is meant to run nightly in GitHub Actions
(.github/workflows/ml-score-nightly.yml), scoring every upcoming auction and
upserting one row per (mca_id, model_version) into ml_scores. composer.js's
scoreModel() reads that row and prefers it over a live Modal/pure-JS call.

Feature vector: ported FAITHFULLY from the 13-name V4_FEATURE_NAMES list in
packages/biddeed-mcp/src/report/feature-vector.js (the list actually used by
the deployed V4 model per issue #19079 — NOT the 21-name list at the top of
that file, which was reconstructed for the retired v14.0 model and is not
what v4.0-20260802-015242 was trained on). Any feature that could not be
reconstructed 1:1 from a Node expression is called out below (there are
none — every one of the 13 V4 features maps to a plain column read + a pure
arithmetic transform, no JS-runtime-only behavior).

county_target_enc is the one genuinely-live-computed feature (mirrors
computeCountyTargetEncoding in feature-vector.js exactly): the county's own
historical third-party-purchase rate, queried once per distinct county in
this batch rather than per-row, both for the JS parity (same formula) and
so this batch job doesn't fire one query per auction.

Reboot resilience: every Supabase HTTP call goes through supabase_request(),
which retries 3x with backoff on connection errors / 5xx / non-JSON bodies
(the same failure signature the whole repo has documented as "the DB is
mid-restart" — a Cloudflare error page instead of a JSON response). After 3
failed attempts the run logs a line and exits 0 — a mid-restart DB is not a
scoring bug and must never fail the nightly job.
"""
import base64
import json
import math
import os
import pickle
import sys
import time
from datetime import datetime, timezone

import numpy as np
import requests

MODEL_VERSION = "v4.0-20260802-015242"  # must match ensemble-model.js's MODEL_VERSION exactly
BATCH_SIZE = 500
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [5, 15, 30]
REQUEST_TIMEOUT = 30

# The exact 13-name, exact-order feature list the deployed V4 model was
# trained on — copied from feature-vector.js's V4_FEATURE_NAMES, not the
# 21-name reconstruction above it in that same file.
V4_FEATURE_NAMES = [
    "judgment_amount_log1p", "opening_bid_log1p", "assessed_value_log1p",
    "prior_sale_price_log1p", "beds_f", "baths_f", "sqft_f", "property_age",
    "opening_to_market", "judgment_to_market", "is_foreclosure", "is_tax_deed",
    "county_target_enc",
]

THIRD_PARTY_LABELS = {"3rd Party", "Plaintiff", "3rd Party (inferred)", "Plaintiff (inferred)"}
THIRD_PARTY_ONLY = {"3rd Party", "3rd Party (inferred)"}
COUNTY_ENC_FALLBACK = 0.42


def log(msg):
    print(f"[ml-score-nightly] {msg}", flush=True)


class SupabaseUnavailable(Exception):
    """The DB looks mid-restart (Cloudflare 5xx / non-JSON body) after retries."""


def supabase_request(method, resource, *, session, base_url, headers, **kwargs):
    """`resource` is the table/rpc path with NO query string — pass filters via
    kwargs['params'] (a dict) so `requests` percent-encodes them correctly.
    PostgREST's `in.("a b","c")` filter syntax contains spaces/parens that
    must be encoded — passing them raw in an f-string URL is not reliable.

    Only 5xx / connection errors / an HTML body (Cloudflare's actual error-
    page content-type when the origin is mid-restart) count as "looks like a
    restart" and get the retry-then-exit-0 treatment. A successful write
    with `Prefer: return=minimal` legitimately comes back with an empty body
    and no content-type — that must NOT be misread as an outage. A genuine
    4xx (bad request, RLS, schema mismatch) is a real bug, not a restart —
    it's raised immediately via raise_for_status() so the run fails loudly
    instead of being silently swallowed as reboot-tolerance."""
    url = f"{base_url}/rest/v1/{resource}"
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            res = session.request(method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
        except requests.RequestException as err:
            last_err = err
            if attempt < RETRY_ATTEMPTS - 1:
                wait = RETRY_BACKOFF_SECONDS[attempt]
                log(f"retry {attempt + 1}/{RETRY_ATTEMPTS} for {method} {resource} after connection error: {err} (sleeping {wait}s)")
                time.sleep(wait)
            continue

        content_type = res.headers.get("content-type", "")
        if res.status_code >= 500 or "text/html" in content_type:
            last_err = SupabaseUnavailable(
                f"{method} {resource} -> HTTP {res.status_code}, content-type={content_type!r} "
                f"(looks like a Cloudflare/DB error page, not a REST response)"
            )
            if attempt < RETRY_ATTEMPTS - 1:
                wait = RETRY_BACKOFF_SECONDS[attempt]
                log(f"retry {attempt + 1}/{RETRY_ATTEMPTS} for {method} {resource} after error: {last_err} (sleeping {wait}s)")
                time.sleep(wait)
            continue

        res.raise_for_status()
        return res
    raise SupabaseUnavailable(f"{method} {resource} failed after {RETRY_ATTEMPTS} attempts: {last_err}")


def log1p_safe(v):
    n = float(v) if v is not None else 0.0
    if math.isnan(n):
        n = 0.0
    return math.log1p(max(0.0, n))


def safe_ratio(numer, denom):
    d = float(denom) if denom else 0.0
    if d <= 0:
        return 0.0
    n = float(numer) if numer is not None else 0.0
    return n / d


def year_of(date_str):
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except ValueError:
        return None


def build_feature_vector(auction, county_target_enc):
    auction_year = year_of(auction.get("auction_date")) or datetime.now(timezone.utc).year
    market_value = auction.get("market_value") or auction.get("assessed_value") or 0
    prior_sale_year = year_of(auction.get("prior_sale_date"))
    beds = auction.get("bedrooms")
    beds = beds if beds is not None else auction.get("beds")
    baths = auction.get("bathrooms")
    baths = baths if baths is not None else auction.get("baths")
    sqft = auction.get("living_area_sqft")
    sqft = sqft if sqft is not None else auction.get("sqft")
    year_built = auction.get("year_built")
    sale_type = (auction.get("sale_type") or "").lower()

    by_name = {
        "judgment_amount_log1p": log1p_safe(auction.get("judgment_amount")),
        "opening_bid_log1p": log1p_safe(auction.get("opening_bid")),
        "assessed_value_log1p": log1p_safe(auction.get("assessed_value")),
        "prior_sale_price_log1p": log1p_safe(auction.get("prior_sale_price")),
        "beds_f": float(beds) if beds is not None else 0.0,
        "baths_f": float(baths) if baths is not None else 0.0,
        "sqft_f": float(sqft) if sqft is not None else 0.0,
        "property_age": float(max(0, auction_year - int(year_built))) if year_built else 0.0,
        "opening_to_market": safe_ratio(auction.get("opening_bid"), market_value),
        "judgment_to_market": safe_ratio(auction.get("judgment_amount"), market_value),
        "is_foreclosure": 1.0 if sale_type == "foreclosure" else 0.0,
        "is_tax_deed": 1.0 if sale_type == "tax_deed" else 0.0,
        "county_target_enc": county_target_enc,
    }
    return by_name


def compute_county_target_encodings(counties, *, session, base_url, headers):
    """Mirrors computeCountyTargetEncoding in feature-vector.js: one query per
    distinct county in this batch (not per row), same formula, same fallback."""
    encodings = {}
    labels = ",".join(f'"{label}"' for label in THIRD_PARTY_LABELS)
    for county in counties:
        if not county:
            continue
        params = {
            "county": f"eq.{county.lower()}",
            "winning_bidder": f"in.({labels})",
            "select": "winning_bidder",
            "limit": "5000",
        }
        try:
            res = supabase_request("GET", "multi_county_auctions", session=session, base_url=base_url, headers=headers, params=params)
            rows = res.json()
        except SupabaseUnavailable:
            raise
        except Exception:
            rows = []
        if not rows:
            encodings[county] = COUNTY_ENC_FALLBACK
            continue
        third_party = sum(1 for r in rows if r.get("winning_bidder") in THIRD_PARTY_ONLY)
        encodings[county] = third_party / len(rows)
    return encodings


def load_ensemble(*, session, base_url, headers):
    params = {
        "select": "artifact_b64",
        "artifact_name": "eq.ensemble.pkl",
        "model_version": f"eq.{MODEL_VERSION}",
        "limit": "1",
    }
    res = supabase_request("GET", "model_artifacts", session=session, base_url=base_url, headers=headers, params=params)
    rows = res.json()
    if not rows:
        raise RuntimeError(f"ensemble.pkl not found in model_artifacts for model_version={MODEL_VERSION}")
    model = pickle.loads(base64.b64decode(rows[0]["artifact_b64"]))
    # The pickle itself carries the exact feature list/order it was trained
    # on (model['features']) — confirmed live (2026-09-06) to match
    # V4_FEATURE_NAMES exactly. Assert it rather than trust it silently, so a
    # future retrain with a different feature set fails loudly here instead
    # of mis-scoring every row.
    trained_features = model.get("features")
    if trained_features is not None and list(trained_features) != V4_FEATURE_NAMES:
        raise RuntimeError(
            f"ensemble.pkl['features'] {trained_features} does not match this script's "
            f"V4_FEATURE_NAMES {V4_FEATURE_NAMES} — feature vector would be built in the wrong order"
        )
    return model


def score_row(model, feature_by_name):
    x = np.array([[feature_by_name[name] for name in V4_FEATURE_NAMES]], dtype=np.float32)
    xgb_prob = float(model["xgb"].predict_proba(x)[0][1])
    lgbm_prob = float(model["lgbm"].predict_proba(x)[0][1])
    catb_prob = float(model["catb"].predict_proba(x)[0][1])
    meta_x = np.array([[xgb_prob, lgbm_prob, catb_prob]], dtype=np.float32)
    p_third_party = float(model["rf_meta"].predict_proba(meta_x)[0][1])
    return p_third_party, xgb_prob, lgbm_prob, catb_prob


def fetch_upcoming_auctions(*, session, base_url, headers):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    select = (
        "id,county,auction_date,judgment_amount,opening_bid,market_value,assessed_value,"
        "prior_sale_price,prior_sale_date,bedrooms,beds,bathrooms,baths,living_area_sqft,sqft,"
        "year_built,sale_type"
    )
    rows = []
    offset = 0
    page_size = 1000
    while True:
        params = {
            "select": select,
            "auction_date": f"gte.{today}",
            "order": "id",
            "limit": str(page_size),
            "offset": str(offset),
        }
        res = supabase_request("GET", "multi_county_auctions", session=session, base_url=base_url, headers=headers, params=params)
        page = res.json()
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def upsert_scores(scores, *, session, base_url, headers):
    upserted = 0
    for i in range(0, len(scores), BATCH_SIZE):
        batch = scores[i:i + BATCH_SIZE]
        upsert_headers = {**headers, "Prefer": "resolution=merge-duplicates"}
        supabase_request(
            "POST", "ml_scores",
            session=session, base_url=base_url, headers=upsert_headers,
            params={"on_conflict": "mca_id,model_version"},
            data=json.dumps(batch),
        )
        upserted += len(batch)
        log(f"upserted {upserted}/{len(scores)}")
    return upserted


def main():
    base_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not service_key:
        log("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — cannot run, exiting 1 (not a DB-restart condition)")
        sys.exit(1)

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    session = requests.Session()

    try:
        log(f"loading ensemble.pkl for model_version={MODEL_VERSION}")
        model = load_ensemble(session=session, base_url=base_url, headers=headers)

        log("fetching auctions with auction_date >= today")
        auctions = fetch_upcoming_auctions(session=session, base_url=base_url, headers=headers)
        log(f"{len(auctions)} upcoming auctions to score")
        if not auctions:
            log("nothing to score — exiting 0")
            return

        counties = {a.get("county") for a in auctions if a.get("county")}
        county_encodings = compute_county_target_encodings(counties, session=session, base_url=base_url, headers=headers)

        scored_at = datetime.now(timezone.utc).isoformat()
        scores = []
        for auction in auctions:
            county_enc = county_encodings.get((auction.get("county") or "").lower(), COUNTY_ENC_FALLBACK)
            feature_by_name = build_feature_vector(auction, county_enc)
            p_third_party, xgb_prob, lgbm_prob, catb_prob = score_row(model, feature_by_name)
            scores.append({
                "mca_id": auction["id"],
                "model_version": MODEL_VERSION,
                "p_third_party": p_third_party,
                "xgb_prob": xgb_prob,
                "lgbm_prob": lgbm_prob,
                "catb_prob": catb_prob,
                "feature_vector": feature_by_name,
                "scored_at": scored_at,
            })

        log(f"scored {len(scores)} rows — upserting into ml_scores")
        upserted = upsert_scores(scores, session=session, base_url=base_url, headers=headers)
        log(f"done — {upserted} rows upserted for model_version={MODEL_VERSION}")

    except SupabaseUnavailable as err:
        # Reboot resilience (item 2a): a mid-restart DB is not a scoring bug.
        log(f"Supabase unavailable after retries, likely mid-restart — skipping run cleanly: {err}")
        sys.exit(0)


if __name__ == "__main__":
    main()
