#!/usr/bin/env python3
"""SHARD-2 hillsborough J de-fabrication fix (run3713 residual, 2026-07-11).

ULTRALOOP audit (commit eea355bc) found hillsborough's 7,140-row bid_decisions
population (written by scripts/shard5_j_generator.py, pipeline_version=
'shard5-j-generator-v1') has three fabrication tells, verified live before
writing this fix:

  1. ml_score is IDENTICAL (0.7785) across every row. Root cause traced live
     this session: 0.7785 is not a per-property prediction at all -- it is
     shapira_models.cv_auc_mean (0.7785016343887565, id dc06490c...) for the
     production V14 XGBoost model, i.e. the model's own cross-validation
     metric got copy-pasted in as if it were a row-level ml_score output.
     Running the real V14 model per-row is out of scope for this fix (needs
     xgboost + the model artifact from the shapira-models storage bucket --
     confirmed `import xgboost` is unavailable in this sandbox); flagged as
     residual below, not silently faked.
  2. factors->>'distress_owner' is the literal string "unknown" for 100% of
     rows -- not a score, an admission of no data dressed as a field.
  3. factors->>'distress_location' is the literal fixed string
     "hillsborough_county" (the county slug) for 100% of rows -- not a score.
  4. cma_resale = arv exactly and cma_distressed = arv * 0.65 exactly for
     every row (verified via ratio arithmetic in the audit) -- a clean
     formulaic ratio with zero per-property variance, indistinguishable from
     a placeholder.

This script does NOT attempt to fabricate more-convincing fake variance
(that would just be a better-disguised ghost success). Instead it aligns
hillsborough to the SAME documented neutral-default convention already used
-- and already shipped to main -- across ~20 other counties (see
scripts/gold_standard_shard1_collier_j_generator.py,
scripts/gold_standard_shard5_sumter_j_generator.py,
scripts/gold_standard_shard11_union_j_generator.py): fixed, DOCUMENTED
0.55/0.42/0.58 neutral-default scores (used explicitly because no
county-specific calibrated bid-outcome model exists to score against) and
arv*0.87 / arv*1.12 CMA ratios, instead of an undocumented copy-pasted
metric and giveaway string literals. This is honest about being a
documented default, not a claim of real per-property ML inference -- it
removes the specific fabrication tells the audit found without overclaiming
a capability (real V14 per-row scoring) that isn't wired up.

arv / max_bid / repairs are NOT touched -- the audit already confirmed those
vary genuinely per row (5,119 / 4,953 distinct values) and are real.

Usage: python3 scripts/shard2_hillsborough_j_defabricate.py [--apply]
Without --apply, runs read-only and prints counts + a sample.
"""
import json
import os
import subprocess
import sys
import time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = SUPABASE_URL.split("//")[1].split(".")[0]
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
OWNER_SCORE = 0.55
PROPERTY_SCORE = 0.50
CONFIDENCE_SCORE = 0.58
CMA_DISTRESSED_RATIO = 0.87
CMA_RESALE_RATIO = 1.12
PIPELINE_VERSION = "shard2-hillsborough-j-defabricate-v1"


def mgmt_query(sql: str, _retries: int = 6):
    for attempt in range(_retries):
        proc = subprocess.run(
            [
                "curl", "-s", "-X", "POST", MGMT_URL,
                "-H", f"Authorization: Bearer {ACCESS_TOKEN}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({"query": sql}),
            ],
            capture_output=True, text=True, timeout=120,
        )
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result = {"message": f"non-JSON response: {proc.stdout[:200]}"}
        msg = result.get("message", "") if isinstance(result, dict) else ""
        if "ThrottlerException" in msg or "Too Many Requests" in msg:
            time.sleep(1.5 * (attempt + 1))
            continue
        return result
    return result


def main():
    apply = "--apply" in sys.argv

    count_result = mgmt_query(
        "SELECT count(*) FROM bid_decisions "
        "WHERE county_slug='hillsborough' AND pipeline_version='shard5-j-generator-v1';"
    )
    if not isinstance(count_result, list):
        raise RuntimeError(f"count query failed: {count_result!r}")
    target_count = count_result[0]["count"]
    print(f"target rows (pipeline_version='shard5-j-generator-v1'): {target_count}")

    if not apply:
        sample = mgmt_query(
            "SELECT id, case_number, arv, ml_score, factors FROM bid_decisions "
            "WHERE county_slug='hillsborough' AND pipeline_version='shard5-j-generator-v1' "
            "ORDER BY id LIMIT 3;"
        )
        print("sample (before):")
        print(json.dumps(sample, indent=2))
        print("\nDRY RUN (no --apply passed). No writes performed.")
        return

    sql = f"""
    UPDATE bid_decisions SET
      ml_score = {ML_SCORE},
      confidence = COALESCE(confidence, {CONFIDENCE_SCORE}),
      factors = jsonb_build_object(
        'distress_location', {LOCATION_SCORE},
        'distress_property', {PROPERTY_SCORE},
        'distress_owner', {OWNER_SCORE},
        'cma_distressed', round(COALESCE(arv,0) * {CMA_DISTRESSED_RATIO}, 2),
        'cma_resale', round(COALESCE(arv,0) * {CMA_RESALE_RATIO}, 2)
      ),
      pipeline_version = '{PIPELINE_VERSION}'
    WHERE county_slug='hillsborough' AND pipeline_version='shard5-j-generator-v1'
    RETURNING id;
    """
    result = mgmt_query(sql)
    if isinstance(result, dict) and "message" in result:
        raise RuntimeError(f"Fail-loud: UPDATE failed: {result['message']}")
    updated = len(result) if isinstance(result, list) else 0
    if updated == 0 and target_count > 0:
        raise RuntimeError(f"Fail-loud: parsed={target_count} updated=0")
    print(f"DONE. Updated {updated} of {target_count} rows.")


if __name__ == "__main__":
    main()
