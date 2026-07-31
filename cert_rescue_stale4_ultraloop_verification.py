#!/usr/bin/env python3
"""
CERT-RESCUE: ULTRALOOP VERIFICATION for 4 stale counties
Dispatch: 00d0b7bf-6c8a-448f-83fc-e6f7f259925d
Purpose: Refresh gold_standard_ultraloop_audit for hillsborough, lafayette, orange, st_johns
         (all >7 days stale, blocking recertification).
Protocol: Fresh pencil_dod_evaluate_county() per county -> adversarial refuter per letter (A-J)
          -> survival vote -> log to gold_standard_ultraloop_audit via Management API.
Honesty: survived=false is written honestly when a letter genuinely fails. No forced PASS.
"""
import os
import json
import httpx
from datetime import datetime, timezone

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
DISPATCH_ID = "00d0b7bf-6c8a-448f-83fc-e6f7f259925d"
TARGET_COUNTIES = ["hillsborough", "lafayette", "orange", "st_johns"]
LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

# Letters whose "metric" is a genuine percentage (0-100 scale) suitable for the
# >105 / ==0 anomaly checks. A (raw fc/td counts) and H (hours-since-seen, lower
# is better) use different semantics and get letter-specific checks instead.
PERCENT_LETTERS = {"B", "C", "D", "E", "F", "G", "I", "J"}


def mgmt_query(query: str):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                    headers=h, json={"query": query}, timeout=120)
    r.raise_for_status()
    return r.json()


def get_fresh_county_evaluation(county_slug):
    result = mgmt_query(f"SELECT public.pencil_dod_evaluate_county('{county_slug}');")
    return result[0]["pencil_dod_evaluate_county"]


def audit_letter(county_slug, letter, letter_data):
    metric = letter_data.get("metric")
    passes = letter_data.get("pass", False)
    detail = letter_data.get("detail", "")

    findings = []

    if letter in PERCENT_LETTERS:
        if metric is None:
            findings.append("NULL METRIC: structural measurement issue - missing infrastructure")
        elif metric > 105:
            findings.append(f"ANOMALOUS: {metric}% exceeds 105% - likely denominator mismatch")
        elif metric == 0:
            findings.append("ZERO METRIC: indicates missing implementation or data")

        if letter == "J" and metric is not None and metric < 10:
            findings.append(f"J METRIC TOO LOW: {metric}% suggests bid_decisions pipeline not operational")
        if letter in ("C", "D") and metric is not None and metric < 50:
            findings.append(f"PARITY TOO LOW: {metric}% suggests litmus coverage gap not resolved")
        if letter == "G" and metric is not None and metric < 80:
            findings.append(f"G METRIC LOW: {metric}% suggests zone_standards backfill incomplete")
        if letter == "B" and metric is not None and (metric < 90 or metric > 110):
            findings.append(f"B METRIC SUSPICIOUS: {metric}% outside 90-110% range")
        if letter == "I" and not passes:
            findings.append(f"CARD COMPLETENESS BELOW THRESHOLD: {detail} ({metric}%, needs >=95%)")
    elif letter == "A":
        # metric is td count; pass requires both fc and td present (dual-product coverage)
        if metric == 0:
            findings.append("ZERO TD: tax_deed pipeline appears absent despite pass flag")
        if "fc=0" in detail:
            findings.append("ZERO FC: foreclosure pipeline appears absent despite pass flag")
    elif letter == "H":
        if metric is None:
            findings.append("NULL FRESHNESS: no last_seen timestamp found")
        elif metric > 48:
            findings.append(f"STALE: {metric}h since last activity exceeds 48h SLA despite pass flag")

    survived = bool(passes) and len(findings) == 0
    claim = f"{county_slug} letter {letter}: {detail} (metric={metric}, pass={passes})"

    return {
        "county_slug": county_slug,
        "letter": letter,
        "claim": claim,
        "metric": metric,
        "passes": passes,
        "findings": findings,
        "survived": survived,
    }


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def build_insert_sql(audit_rows, audit_ts):
    values = []
    for r in audit_rows:
        evidence = {
            "findings": r["findings"],
            "metric_value": r["metric"],
            "audit_timestamp": audit_ts,
        }
        evidence_json = sql_escape(json.dumps(evidence))
        claim_esc = sql_escape(r["claim"])
        survived_sql = "true" if r["survived"] else "false"
        values.append(
            f"('{DISPATCH_ID}', 'native', '{r['county_slug']}', '{r['letter']}', "
            f"'{claim_esc}', '{evidence_json}'::jsonb, {survived_sql})"
        )
    values_sql = ",\n".join(values)
    return (
        "INSERT INTO public.gold_standard_ultraloop_audit "
        "(dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived) "
        f"VALUES\n{values_sql};"
    )


def main():
    audit_ts = datetime.now(timezone.utc).isoformat()
    all_results = []

    for county in TARGET_COUNTIES:
        metrics = get_fresh_county_evaluation(county)
        for letter in LETTERS:
            letter_data = metrics.get(letter, {})
            result = audit_letter(county, letter, letter_data)
            all_results.append(result)

    insert_sql = build_insert_sql(all_results, audit_ts)
    insert_result = mgmt_query(insert_sql)

    print(json.dumps({
        "audit_timestamp": audit_ts,
        "rows_written": len(all_results),
        "insert_result": insert_result,
        "summary": {
            county: {
                "survived": sum(1 for r in all_results if r["county_slug"] == county and r["survived"]),
                "failed": [r["letter"] for r in all_results if r["county_slug"] == county and not r["survived"]],
            }
            for county in TARGET_COUNTIES
        },
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
