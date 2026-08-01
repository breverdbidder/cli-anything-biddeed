#!/usr/bin/env python3
"""SHARD-4 c40bb245: suwannee J (deal_complete) — run the proven real generator
(scripts/shard8_run6080_suwannee_j_generator_real.py) against the current live
DB, after downloading the production Shapira V14 model artifacts from Supabase
Storage (bucket shapira-models, path from shapira_models WHERE model_version=
'v14.0' AND is_production=true) into MODEL_DIR — the prior script assumes the
model is already staged locally and does not fetch it itself.

Investigated per task instructions before running:
  1. Queried multi_county_auctions vs bid_decisions live: 26/35 suwannee case_
     numbers already have a complete bid_decisions row (arv, max_bid, ml_score,
     all 5 factors keys) written by a prior real (non-fabricated) session.
     9 case_numbers have NO bid_decisions row at all: 4677, 4678, 4679, 4680,
     4681, 4741, 4752, 4758, 4760 -- all sale_type=tax_deed, auction_date=
     2026-09-03, data_source=calendar_sweep_mca_v3.
  2. Checked gen_valuations_comps_batch's target table: no valuations_comps /
     valuation_comps / comps_batch / gen_valuations_comps / cma_comps /
     property_comps table exists in PostgREST's schema cache under any name
     tried -- there is no separate CMA-comps table to draw a real ARV from for
     these 9 rows.
  3. Checked the 9 rows directly: property_address, assessed_value,
     market_value, latitude, longitude, owner_name are ALL NULL. Only
     opening_bid (delinquent-tax amount, not property value) is present.
     Using opening_bid as an ARV proxy would be fabrication -- no other J
     generator script in this repo does that, and real_arv() in the shard8
     script correctly restricts to assessed_value/market_value only.
  4. Re-ran the realtaxdeed.com AJAX harvester (shard2_run2450_ajax_
     realforeclose_harvest.harvest_date) live against suwannee.realtaxdeed.com
     for auction_date 09032026 (mmddyyyy) -- 0 items returned. The auction
     platform has not posted parcel records for that (>1-month-out) sale date
     yet. This matches the prior stage's finding for letter I on these exact
     9 case numbers -- same genuine upstream gap, not a pipeline bug.
  5. Tried Suwannee Property Appraiser GSA-corp direct parcel_id lookup
     (https://suwannee-search.gsacorp.io/parcel/<parcel_id>) as a bypass for
     the missing address -- returns a generic WordPress "not found" page (no
     Market Value / Assessed Value fields) for our short numeric parcel_ids;
     the site's real search only works by address-fragment livesearch, which
     needs an address we don't have for these 9 rows.

Conclusion: the 9 missing case_numbers are correctly and idempotently skipped
by the existing generator's skipped_no_real_value branch. No fabrication, no
opening_bid substitution. Re-running this script later (once realtaxdeed.com
posts the 2026-09-03 auction's parcel list, or the county GIS/appraiser
publishes these parcels) will pick them up automatically -- no code change
needed, only fresh upstream data.
"""
import os
import subprocess
import sys
import urllib.request
import json

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
MODEL_DIR = "/tmp/shapira"


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def stage_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    rows = rest_get("shapira_models?select=storage_bucket,storage_path_model,storage_path_features&model_version=eq.v14.0&is_production=eq.true")
    if not rows:
        print("FATAL: no production v14.0 shapira_models row found")
        sys.exit(1)
    bucket = rows[0]["storage_bucket"]
    for local_name, remote_path in (("model.json", rows[0]["storage_path_model"]),
                                     ("features.json", rows[0]["storage_path_features"])):
        dest = os.path.join(MODEL_DIR, local_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{remote_path}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"staged {dest} ({len(data)} bytes)")


def main():
    stage_model()
    here = os.path.dirname(os.path.abspath(__file__))
    real_gen = os.path.join(here, "shard8_run6080_suwannee_j_generator_real.py")
    print(f"running {real_gen} ...")
    subprocess.run([sys.executable, real_gen], check=True)


if __name__ == "__main__":
    main()
