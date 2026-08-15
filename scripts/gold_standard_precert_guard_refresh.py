#!/usr/bin/env python3
"""
Gold Standard precert guard refresh — ALL counties, daily.

Root cause (insights row, VERIFIED, 2026-07-06): gold_standard_certify() requires
calendar_parity + denominator_integrity rows in gold_standard_precert_guards dated
within a rolling 7-day window. Only scripts/shard3_certify_all.py (5 counties:
leon/desoto/baker/hendry/liberty) refreshes these daily. Every other county's guard
rows were inserted exactly once by past one-off remediation scripts/migrations and
silently expire 7 days later, permanently blocking consecutive_gold accrual and
causing revocation the next time gold_standard_certify() runs after expiry
(e.g. brevard: guard inserted 2026-06-22 23:52, expired 2026-06-29 23:52, revoked
2026-06-30 01:30 — the very next certify tick after expiry).

This script closes that gap for every county, not just shard3's five: it re-derives
calendar_parity (C+D letters pass) and denominator_integrity (G letter pass) from a
live pencil_dod_evaluate_county() call and stamps a fresh guard row when the county
is currently passing 10/10. Counties still blocked on adversarial evidence
(gold_standard_ultraloop_audit letters C/D — see issue #10978, "C/D LITMUS V2") are
unaffected by this fix; that gap is out of scope here and tracked separately.

GTM-22 Phase 1.3 follow-up (2026-07-18, issue #12745 Session 4): pencil_dod_evaluate_county
gained p_snapshot_at (gold_standard_cert_scope frozen-calendar scoping) and
gold_standard_loop() was rewired to pass it through per county. This script must
do the same — it was calling the RPC unscoped, so a county under an active freeze
(brevard/duval/hillsborough/orange/palm_beach/sarasota/volusia as of this writing)
got guard rows derived from live data instead of the frozen snapshot, diverging
from what loop()/certify() actually computed for that county. Confirmed live: with
the RPC still unscoped, brevard C, orange I, and sarasota C/D/I all disagreed
between scoped and unscoped evaluation. Fix: look up each county's active
snapshot_at once and pass it through on every pencil_dod_evaluate_county call.

C/D LITMUS V2 wiring (issue #10981, Ariel directive 2026-07-06): in addition to the
10/10 refresh above, this script now also runs pencil_dod_evaluate_county_v2() (the
RealAuction-primary / FloridaBidder-fallback hierarchy evaluator added in
migrations/20260706_cd_litmus_v2_evaluator_surface.sql) for the issue's named
priority counties and persists a 'calendar_parity_v2_realauction' guard row for
each. This is deliberately observational, not a C+D pass/fail override: blending a
count/coverage recount into the same threshold used for every other county's
row-level cert history would be a NEVER-LIE risk (see the migration's own comment).
It DOES make the V2 hierarchy load-bearing in the sense that used to be missing:
executed automatically by the daily production precert pipeline (not just callable
ad hoc), with results persisted for the next follow-up (row-level
tier1_realauction_v2 matching) to consume.
"""
import os
import httpx

SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"

# Issue #10981 priority counties (C/D-blocked near-golds under the legacy PO-era
# litmus). Kept in sync with scripts/cd_litmus_v2_realauction_parity.py.
V2_PRIORITY_COUNTIES = [
    "duval", "okeechobee", "bay", "desoto", "dixie", "escambia", "hendry",
    "highlands", "hillsborough", "levy", "palm_beach", "pasco", "polk",
    "sarasota", "broward", "hamilton",
]


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


def main():
    print("=== Gold Standard precert guard refresh (all counties) ===")

    scope_rows = run_sql("""
        SELECT county_slug, snapshot_at FROM gold_standard_cert_scope WHERE active;
    """)
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

    refreshed = []
    for county in counties:
        gate = evaluate(county)
        letters = {k: v for k, v in gate.items() if k in "ABCDEFGHIJ"}
        c_pass = bool(letters.get("C", {}).get("pass"))
        d_pass = bool(letters.get("D", {}).get("pass"))
        g_pass = bool(letters.get("G", {}).get("pass"))
        auctions_total = gate.get("auctions_total")

        calendar_parity_ok = c_pass and d_pass
        denom_ok = g_pass and bool(auctions_total)

        c_detail = letters.get("C", {})
        d_detail = letters.get("D", {})
        g_detail = letters.get("G", {})

        run_sql(f"""
            INSERT INTO gold_standard_precert_guards (county_slug, guard_type, passed, detail)
            VALUES
              ({county!r}, 'calendar_parity', {str(calendar_parity_ok).lower()},
               '{{"source":"gold_standard_precert_guard_refresh","honesty_marker":"VERIFIED",
                  "c_metric":{c_detail.get('metric')},"c_detail":"{c_detail.get('detail')}",
                  "d_metric":{d_detail.get('metric')},"d_detail":"{d_detail.get('detail')}"}}'::jsonb),
              ({county!r}, 'denominator_integrity', {str(denom_ok).lower()},
               '{{"source":"gold_standard_precert_guard_refresh","honesty_marker":"VERIFIED",
                  "g_metric":{g_detail.get('metric')},"g_detail":"{g_detail.get('detail')}",
                  "auctions_total":{auctions_total}}}'::jsonb);
        """)
        refreshed.append((county, calendar_parity_ok, denom_ok))
        print(f"  {county}: calendar_parity={calendar_parity_ok} denominator_integrity={denom_ok}")

    print(f"\n[1b] C/D LITMUS V2 (issue #10981): {len(V2_PRIORITY_COUNTIES)} priority counties, "
          f"observational guard only")
    v2_flips = []
    for county in V2_PRIORITY_COUNTIES:
        res = run_sql(f"SELECT public.pencil_dod_evaluate_county_v2('{county}') AS r;")
        v2 = res[0]["r"] if res else {}
        v2_source = v2.get("v2_hierarchy_source")
        if v2_source in (None, "propertyonion_tertiary_fallback"):
            print(f"  {county}: no fresh V2 evidence (<=48h) — skipping guard row")
            continue

        v2_c_pass = bool(v2.get("C", {}).get("pass"))
        v2_d_pass = bool(v2.get("D", {}).get("pass"))
        v2_metric = v2.get("C", {}).get("metric")
        v2_metric_json = "null" if v2_metric is None else str(v2_metric)

        # Legacy (row-level tier1) C/D for the same county, to log whether V2 would
        # have flipped a currently-blocked county — evidence only, never applied.
        legacy = evaluate(county)
        legacy_c_pass = bool(legacy.get("C", {}).get("pass"))
        legacy_d_pass = bool(legacy.get("D", {}).get("pass"))
        would_flip = (v2_c_pass or v2_d_pass) and not (legacy_c_pass and legacy_d_pass)

        run_sql(f"""
            INSERT INTO gold_standard_precert_guards (county_slug, guard_type, passed, detail)
            VALUES
              ({county!r}, 'calendar_parity_v2_realauction', {str(v2_c_pass and v2_d_pass).lower()},
               '{{"source":"gold_standard_precert_guard_refresh","honesty_marker":"VERIFIED",
                  "v2_hierarchy_source":"{v2_source}","v2_metric":{v2_metric_json},
                  "v2_c_pass":{str(v2_c_pass).lower()},"v2_d_pass":{str(v2_d_pass).lower()},
                  "legacy_c_pass":{str(legacy_c_pass).lower()},"legacy_d_pass":{str(legacy_d_pass).lower()},
                  "would_flip_blocked_county":{str(would_flip).lower()},
                  "note":"observational only -- does not affect calendar_parity guard or certify()"}}'::jsonb);
        """)
        if would_flip:
            v2_flips.append(county)
        print(f"  {county}: v2_source={v2_source} v2_metric={v2_metric} "
              f"v2_c={v2_c_pass} v2_d={v2_d_pass} legacy_c={legacy_c_pass} legacy_d={legacy_d_pass} "
              f"would_flip={would_flip}")

    print(f"  -> {len(v2_flips)} priority counties would flip C/D under V2 hierarchy: {v2_flips}")

    print("\n[2] Running gold_standard_certify()...")
    res = run_sql("SELECT public.gold_standard_certify() AS r;")
    cert = res[0].get("r", {}) if res else {}
    print(f"  run={cert.get('run')} certified_now={cert.get('certified_now')} revoked_now={cert.get('revoked_now')}")
    print(f"  blocked={cert.get('blocked')}")
    print(f"  guard_blocked={cert.get('guard_blocked')}")

    print("\n[3] consecutive_gold after refresh:")
    rows = run_sql(f"""
        SELECT county_slug, certified, consecutive_gold, revoked_at
        FROM gold_standard_certifications
        WHERE county_slug IN ({','.join(repr(c) for c, _, _ in refreshed) or "''"})
        ORDER BY consecutive_gold DESC, county_slug;
    """)
    for row in rows:
        print(f"  {row['county_slug']}: consecutive_gold={row['consecutive_gold']} certified={row['certified']}")


if __name__ == "__main__":
    main()
