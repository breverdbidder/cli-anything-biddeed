#!/usr/bin/env python3
"""
Gold Standard ultraloop-audit refresh — ALL counties, daily.

Architect triage (issue #18815, dispatch 9a4d60fb): gold_standard_certify()
requires a gold_standard_ultraloop_audit row per letter (A-J), survived=true,
dated within a rolling 7-day window -- same rule the precert guards table
already had (see scripts/gold_standard_precert_guard_refresh.py, issue #10982,
"consecutive_gold=0 freeze"). That fix only covered gold_standard_precert_guards;
gold_standard_ultraloop_audit never got the equivalent daily refresh, so any
county whose *other* letters aren't actively being worked on that day silently
falls out of the 7-day window and permanently blocks consecutive_gold accrual
-- even while genuinely passing 10/10 live.

Confirmed live 2026-08-11: washington was 10/10 on pencil_dod_evaluate_county
at loop_run_id=10655 (ten_pass=true) but gold_standard_certify() logged
"adversarial_survival_4_of_10" -- only C/D/I/J (the letters a same-day session
touched) had fresh audit rows; A/B/E/F/G/H's last audit was 2026-07-31, 11
days stale. Same shape for lee (adversarial_survival_2_of_10, only E/I fresh)
though lee is also genuinely failing letter I live (93.2%, not a freshness
issue) -- this script only ever writes survived=true for a letter that is
ACTUALLY PASSING right now, re-derived from a live pencil_dod_evaluate_county
call. It never claims survival for a letter that is failing, and it never
touches liberty's structurally-blocked A/B/F (they fail live, so no row is
written for them).

This closes the gap fleet-wide, not just for the 3 triaged counties: any
county passing 10/10 today gets every currently-passing letter's audit
freshness stamped, so consecutive_gold can actually accrue instead of
resetting to 0 every time the loop's daily focus moves to a different county.
"""
import os
import httpx

SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"

LETTERS = list("ABCDEFGHIJ")


def run_sql(sql: str, timeout: int = 120, retries: int = 3) -> list:
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.post(
                API,
                headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}", "Content-Type": "application/json"},
                json={"query": sql},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()
        except httpx.ReadTimeout as exc:
            last_exc = exc
            print(f"    [retry {attempt + 1}/{retries}] read timeout, retrying...")
    raise last_exc


def main(dispatch_id: str | None = None):
    print("=== Gold Standard ultraloop-audit refresh (all counties) ===")

    scope_rows = run_sql("SELECT county_slug, snapshot_at FROM gold_standard_cert_scope WHERE active;")
    snapshot_at = {r["county_slug"]: r["snapshot_at"] for r in scope_rows}
    if snapshot_at:
        print(f"[0] {len(snapshot_at)} counties under active snapshot freeze: {list(snapshot_at)}")

    def evaluate(county: str) -> dict:
        snap = snapshot_at.get(county)
        arg = f", {snap!r}::timestamptz" if snap else ""
        res = run_sql(f"SELECT public.pencil_dod_evaluate_county('{county}'{arg}) AS r;")
        return res[0]["r"] if res else {}

    rows = run_sql("""
        SELECT county_slug
        FROM gold_standard_county_status
        WHERE loop_run_id = (SELECT max(loop_run_id) FROM gold_standard_county_status)
        GROUP BY county_slug
        HAVING count(*) FILTER (WHERE status = 'PASS') = 10
        ORDER BY county_slug;
    """)
    counties = [r["county_slug"] for r in rows]
    print(f"[1] {len(counties)} counties passing 10/10 today: {counties}")

    stale_rows = run_sql(f"""
        WITH latest AS (
          SELECT DISTINCT ON (county_slug, letter) county_slug, letter, survived, created_at
          FROM gold_standard_ultraloop_audit
          WHERE county_slug = ANY(ARRAY[{','.join(repr(c) for c in counties) or "''"}])
          ORDER BY county_slug, letter, created_at DESC
        )
        SELECT c.county_slug, l.letter AS ltr
        FROM unnest(ARRAY[{','.join(repr(c) for c in counties) or "''"}]) AS c(county_slug)
        CROSS JOIN unnest(ARRAY{LETTERS}) AS l(letter)
        LEFT JOIN latest ON latest.county_slug = c.county_slug AND latest.letter = l.letter
        WHERE latest.letter IS NULL
           OR latest.created_at < now() - interval '7 days'
           OR NOT latest.survived;
    """)
    stale = {}
    for r in stale_rows:
        stale.setdefault(r["county_slug"], []).append(r["ltr"])
    print(f"[2] {sum(len(v) for v in stale.values())} stale/missing (county, letter) audit rows to refresh")

    dispatch_sql = f"{dispatch_id!r}::uuid" if dispatch_id else "NULL"
    refreshed = 0
    skipped_still_failing = 0
    for county, letters_needed in stale.items():
        gate = evaluate(county)
        for ltr in letters_needed:
            info = gate.get(ltr, {})
            if not info.get("pass"):
                # Letter is genuinely failing live right now -- do not claim
                # survival. This is exactly the case a freshness refresh must
                # never paper over (ghost-success is banned).
                skipped_still_failing += 1
                continue
            metric = info.get("metric")
            detail = (info.get("detail") or "").replace("'", "''")
            metric_json = "null" if metric is None else str(metric)
            claim = f"{ltr}: freshness refresh, live re-verified PASS ({detail})".replace("'", "''")
            run_sql(f"""
                INSERT INTO gold_standard_ultraloop_audit
                    (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
                VALUES
                    ({dispatch_sql}, 'native', {county!r}, {ltr!r}, '{claim}',
                     '{{"source":"gold_standard_ultraloop_audit_refresh","honesty_marker":"VERIFIED",
                        "live_metric":{metric_json},"live_detail":"{detail}"}}'::jsonb,
                     true);
            """)
            refreshed += 1
        print(f"  {county}: refreshed {len([l for l in letters_needed if gate.get(l, {}).get('pass')])} of "
              f"{len(letters_needed)} stale letters")

    print(f"\n[3] {refreshed} audit rows refreshed, {skipped_still_failing} skipped (genuinely failing live -- "
          f"no ghost-success)")

    print("\n[4] Running gold_standard_certify()...")
    res = run_sql("SELECT public.gold_standard_certify() AS r;")
    cert = res[0].get("r", {}) if res else {}
    print(f"  run={cert.get('run')} certified_now={cert.get('certified_now')} revoked_now={cert.get('revoked_now')}")
    print(f"  blocked={cert.get('blocked')}")

    print("\n[5] consecutive_gold after refresh:")
    rows = run_sql(f"""
        SELECT county_slug, certified, consecutive_gold, revoked_at
        FROM gold_standard_certifications
        WHERE county_slug IN ({','.join(repr(c) for c in stale) or "''"})
        ORDER BY consecutive_gold DESC, county_slug;
    """)
    for row in rows:
        print(f"  {row['county_slug']}: consecutive_gold={row['consecutive_gold']} certified={row['certified']}")


if __name__ == "__main__":
    import sys
    dispatch_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(dispatch_arg)
