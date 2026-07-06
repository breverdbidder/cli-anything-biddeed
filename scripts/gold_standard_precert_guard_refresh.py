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
"""
import os
import httpx

SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"


def run_sql(sql: str, timeout: int = 60) -> list:
    r = httpx.post(
        API,
        headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def main():
    print("=== Gold Standard precert guard refresh (all counties) ===")

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
        res = run_sql(f"SELECT public.pencil_dod_evaluate_county('{county}') AS r;")
        gate = res[0]["r"] if res else {}
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
