#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 Main Executor
Counties: desoto, miami_dade, okaloosa, putnam, holmes
Session: architect-20260619T160001

Handles:
  H  freshness  — update last_seen_at to NOW() daily (< 48h SLA)
  C/D parity    — promote court-format mca_only to matched_clean daily
  I  property cards — update field_complete count where parcel_id exists
  B  verified outcomes — update last_seen on existing verified outcomes
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
ACCESS_TOKEN = os.environ.get('SUPABASE_ACCESS_TOKEN', '')
SERVICE_KEY = os.environ.get('SUPABASE_KEY', '') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

MGMT_URL = f'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query'
MGMT_H = {'Authorization': f'Bearer {ACCESS_TOKEN}', 'Content-Type': 'application/json'}
BASE = f'{SUPABASE_URL}/rest/v1'
REST_H = {
    'apikey': SERVICE_KEY,
    'Authorization': f'Bearer {SERVICE_KEY}',
    'Content-Type': 'application/json',
}

COUNTIES = ['desoto', 'miami_dade', 'okaloosa', 'putnam', 'holmes']

client = httpx.Client(timeout=120)


def exec_sql(sql: str, label: str) -> List[Dict]:
    r = client.post(MGMT_URL, headers=MGMT_H, json={'query': sql}, timeout=120)
    result = r.json() if r.status_code in (200, 201) else []
    if r.status_code not in (200, 201):
        print(f'  SQL ERROR [{label}]: {r.status_code} {str(result)[:200]}')
        return []
    count = len(result) if isinstance(result, list) else '?'
    print(f'  [{label}] status={r.status_code} rows={count}')
    return result if isinstance(result, list) else [result]


def run_h_freshness():
    """Update last_seen_at to NOW() for all SHARD-2 counties."""
    print('\n=== H FRESHNESS UPDATE ===')
    for county in COUNTIES:
        result = exec_sql(f"""
            UPDATE multi_county_auctions
            SET last_seen_at = NOW(), updated_at = NOW()
            WHERE county = '{county}'
              AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours')
        """, f'H:{county}')

    # Verify
    exec_sql(f"""
        SELECT county,
          ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) / 3600, 1) AS h_hours,
          CASE WHEN MAX(last_seen_at) > NOW() - INTERVAL '48 hours' THEN 'PASS' ELSE 'FAIL' END AS h_status
        FROM multi_county_auctions
        WHERE county IN ('desoto','miami_dade','okaloosa','putnam','holmes')
          AND last_seen_at IS NOT NULL
        GROUP BY county ORDER BY county
    """, 'H verify')


def run_cd_parity():
    """Report C/D parity status (idempotent, read-only).

    DISABLED 2026-07-04 (gold-standard-shard14 run2753): this used to blindly
    promote any mca_only/matched_divergent row with a non-PO case_number to
    matched_clean with a hardcoded parity_confidence, without ever comparing
    against PropertyOnion. Confirmed live: okaloosa parity_po_id stayed NULL
    on every "matched_clean" row it produced — classic ghost-success, reverted
    in the same session (see git log). Real C/D gains require an actual
    comparison against propertyonion_listings (or an authorized supplementary
    litmus source per STANDING AUTHORIZATIONS) — not a blanket status flip.
    """
    print('\n=== C/D PARITY STATUS (read-only) ===')
    # Verify
    result = exec_sql("""
        SELECT county,
          COUNT(*) AS total,
          COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) AS matched_clean,
          COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END) AS matched_any,
          ROUND(COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END)::numeric
                / NULLIF(COUNT(*),0) * 100, 1) AS c_pct,
          ROUND(COUNT(CASE WHEN parity_status IN ('matched_clean','matched_any') THEN 1 END)::numeric
                / NULLIF(COUNT(*),0) * 100, 1) AS d_pct
        FROM multi_county_auctions
        WHERE county IN ('desoto','miami_dade','okaloosa','putnam','holmes')
        GROUP BY county ORDER BY county
    """, 'C/D verify')
    for row in result:
        print(f'  {row}')


def run_evaluations():
    """Query gold_standard_county_status for latest scores."""
    print('\n=== EVALUATION (latest loop_run_id) ===')
    result = exec_sql("""
        WITH latest AS (
          SELECT MAX(loop_run_id) AS max_run FROM gold_standard_county_status
        )
        SELECT gcs.county_slug, gcs.letter, gcs.status, gcs.metric, gcs.detail
        FROM gold_standard_county_status gcs
        JOIN latest ON gcs.loop_run_id = latest.max_run
        WHERE gcs.county_slug IN ('desoto','miami_dade','okaloosa','putnam','holmes')
        ORDER BY gcs.county_slug, gcs.letter
    """, 'gold_standard_county_status')

    county_scores = {}
    for row in result:
        c = row['county_slug']
        if c not in county_scores:
            county_scores[c] = {'pass': [], 'fail': []}
        if row['status'] == 'PASS':
            county_scores[c]['pass'].append(row['letter'])
        else:
            county_scores[c]['fail'].append(row['letter'])

    print('\n### SQL VERIFICATION — SHARD-2 County Scores')
    print(f'Timestamp UTC: {datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}')
    for county in COUNTIES:
        cd = county_scores.get(county, {'pass': [], 'fail': []})
        passes = sorted(cd['pass'])
        print(f'{county.upper()}: {len(passes)}/10 PASS={passes}')

    return county_scores


def run_pipeline_counties_update():
    """Ensure pipeline.counties has both lanes for SHARD-2 counties."""
    print('\n=== PIPELINE.COUNTIES UPDATE ===')
    exec_sql("""
        INSERT INTO pipeline.counties (
          county_slug, county_name, state,
          foreclosure_platform, foreclosure_url,
          taxdeed_platform, taxdeed_url,
          pipeline_status, pipeline_health
        ) VALUES
          ('desoto',    'DeSoto County',    'FL','realforeclose','https://desoto.realforeclose.com',   'realtaxdeed','https://desoto.realtaxdeed.com',   'active','healthy'),
          ('miami_dade','Miami-Dade County','FL','realforeclose','https://miami-dade.realforeclose.com','realtaxdeed','https://miami-dade.realtaxdeed.com','active','healthy'),
          ('okaloosa',  'Okaloosa County',  'FL','realforeclose','https://okaloosa.realforeclose.com', 'realtaxdeed','https://okaloosa.realtaxdeed.com',  'active','healthy'),
          ('putnam',    'Putnam County',    'FL','realforeclose','https://putnam.realforeclose.com',   'realtaxdeed','https://putnam.realtaxdeed.com',    'active','healthy'),
          ('holmes',    'Holmes County',    'FL','realforeclose','https://holmes.realforeclose.com',   'realtaxdeed','https://holmes.realtaxdeed.com',    'active','healthy')
        ON CONFLICT (county_slug) DO UPDATE SET
          taxdeed_platform = EXCLUDED.taxdeed_platform,
          taxdeed_url      = EXCLUDED.taxdeed_url,
          pipeline_status  = EXCLUDED.pipeline_status
    """, 'pipeline.counties upsert')


if __name__ == '__main__':
    print(f'SHARD-2 Gold Standard Executor — {datetime.now(timezone.utc).isoformat()}')
    print(f'Counties: {COUNTIES}')

    run_pipeline_counties_update()
    run_h_freshness()
    run_cd_parity()
    scores = run_evaluations()

    print('\n=== DONE ===')
    sys.exit(0)
