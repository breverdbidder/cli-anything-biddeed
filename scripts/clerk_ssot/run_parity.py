"""CLERK-SSOT daily parity runner (Task 3).

For each registered county/sale_type parser: fetch clerk rows, stage them,
diff against multi_county_auctions for the today->+90d window, write a
clerk_parity_results row, and apply the corrective reconciliation actions
from the spec (insert missing, flag clerk-cancelled, suppress phantom,
mark clean matches PARITY_OK -- never delete). The PARITY_OK mark is what
lets the render gate (Task 4.2, v_property_card_verified) show anything
beyond newly-reconciled rows -- without it every already-matching row stays
parity_status=NULL and gets suppressed.

Hard rule (spec Task 2): a parser that returns 0 rows is a FAILURE, not an
empty calendar, if it previously returned >0. This script never silently
swallows a parser exception into a clean 0-row parity result -- it writes
status='PARSE_FAIL' instead.
"""
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clerk_ssot.parsers import (  # noqa: E402
    brevard, gadsden, wakulla, highlands, lake, okeechobee, st_johns, suwannee, union,
    bay, calhoun, desoto, dixie, franklin, gulf, hamilton, hardee, holmes, jefferson,
    lafayette, levy, liberty, madison, manatee, nassau, sumter, taylor, st_lucie, walton,
)

MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

# county_slug -> {sale_type: parser_fn}
#
# Counties confirmed to have NO independently-parseable public calendar for
# EITHER sale type (as of 2026-08-10, live-verified this session unless
# noted) -- every source is exclusively hosted on a gated third-party
# platform (RealForeclose/RealAuction/RealTaxDeed/RealTDM/bid4assets, which
# this pipeline is not allowed to log into or drive) or is fully JS/
# Cloudflare-Turnstile-gated with no static fallback. Their
# clerk_sale_calendar_sources.honesty_marker rows were downgraded to
# NO_PUBLIC_CALENDAR to match (see scripts/clerk_ssot/downgrade_uncoverable.py):
#   hendry (Cloudflare + municode doc-viewer, re-verified this session --
#     Playwright clears the Cloudflare challenge but the actual docket lives
#     on a gated municode SPA with no extractable calendar)
#   baker, bradford, clay, collier, columbia, flagler, gilchrist, glades,
#   hernando, indian_river, jackson, martin, okaloosa, osceola, pinellas,
#   putnam, broward, charlotte, citrus, duval, leon, polk,
#   santa_rosa, sarasota, seminole, washington
PARSERS = {
    "brevard": {"foreclosure": brevard.parse_foreclosure},
    "gadsden": {"foreclosure": gadsden.parse_foreclosure, "tax_deed": gadsden.parse_tax_deed},
    "highlands": {"foreclosure": highlands.parse_foreclosure},
    "lake": {"foreclosure": lake.parse_foreclosure},
    "okeechobee": {"foreclosure": okeechobee.parse_foreclosure},
    "st_johns": {"tax_deed": st_johns.parse_tax_deed},
    "suwannee": {"tax_deed": suwannee.parse_tax_deed},
    "union": {"foreclosure": union.parse_foreclosure},
    "wakulla": {"foreclosure": wakulla.parse_foreclosure, "tax_deed": wakulla.parse_tax_deed},
    "bay": {"foreclosure": bay.parse_foreclosure},
    "calhoun": {"foreclosure": calhoun.parse_foreclosure, "tax_deed": calhoun.parse_tax_deed},
    "desoto": {"foreclosure": desoto.parse_foreclosure, "tax_deed": desoto.parse_tax_deed},
    "dixie": {"foreclosure": dixie.parse_foreclosure, "tax_deed": dixie.parse_tax_deed},
    "franklin": {"foreclosure": franklin.parse_foreclosure, "tax_deed": franklin.parse_tax_deed},
    "gulf": {"tax_deed": gulf.parse_tax_deed},
    "hamilton": {"foreclosure": hamilton.parse_foreclosure, "tax_deed": hamilton.parse_tax_deed},
    "hardee": {"tax_deed": hardee.parse_tax_deed},
    "holmes": {"foreclosure": holmes.parse_foreclosure},
    "jefferson": {"foreclosure": jefferson.parse_foreclosure, "tax_deed": jefferson.parse_tax_deed},
    "lafayette": {"foreclosure": lafayette.parse_foreclosure, "tax_deed": lafayette.parse_tax_deed},
    "levy": {"foreclosure": levy.parse_foreclosure, "tax_deed": levy.parse_tax_deed},
    "liberty": {"foreclosure": liberty.parse_foreclosure, "tax_deed": liberty.parse_tax_deed},
    "madison": {"foreclosure": madison.parse_foreclosure, "tax_deed": madison.parse_tax_deed},
    "manatee": {"foreclosure": manatee.parse_foreclosure},
    "nassau": {"tax_deed": nassau.parse_tax_deed},
    "sumter": {"foreclosure": sumter.parse_foreclosure, "tax_deed": sumter.parse_tax_deed},
    "taylor": {"foreclosure": taylor.parse_foreclosure, "tax_deed": taylor.parse_tax_deed},
    "st_lucie": {"tax_deed": st_lucie.parse_tax_deed},
    "walton": {"tax_deed": walton.parse_tax_deed},
}

WINDOW_DAYS = 90


def run_sql(sql: str, _retries: int = 3):
    payload = json.dumps({"query": sql})
    for attempt in range(_retries):
        result = subprocess.run(
            ["curl", "-sS", "-X", "POST", MGMT_API,
             "-H", f"Authorization: Bearer {os.environ['SUPABASE_ACCESS_TOKEN']}",
             "-H", "Content-Type: application/json",
             "-H", "User-Agent: cli-anything-biddeed-cc/1.0",
             "-d", "@-"],
            input=payload, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            # transient Supabase Management API 502/503 under burst load -- retry
            if attempt < _retries - 1 and ("502" in result.stdout or "503" in result.stdout or not result.stdout.strip()):
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"non-JSON response: {result.stdout[:500]}")


def sql_str(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def stage_rows(rows: list[dict]):
    if not rows:
        return
    values = []
    for r in rows:
        values.append("(%s,%s,%s,%s,%s,%s,%s,%s,now())" % (
            sql_str(r["county_slug"]), sql_str(r["sale_type"]), sql_str(r["case_number"]),
            sql_str(r["sale_date"]), "true" if r["cancelled"] else "false",
            sql_str(r["raw_comment"]), sql_str(r["case_title"]), sql_str(r["source_url"]),
        ))
    sql = f"""
    INSERT INTO public.clerk_ssot_sale_rows
      (county_slug, sale_type, case_number, sale_date, cancelled, raw_comment, case_title, source_url, parsed_at)
    VALUES {','.join(values)}
    ON CONFLICT (county_slug, sale_type, case_number, sale_date) DO UPDATE SET
      cancelled = EXCLUDED.cancelled,
      raw_comment = EXCLUDED.raw_comment,
      case_title = EXCLUDED.case_title,
      parsed_at = now();
    """
    run_sql(sql)


def diff_and_reconcile(county_slug: str, sale_type: str, rows: list[dict]) -> dict:
    window_start = date.today()
    window_end = window_start + timedelta(days=WINDOW_DAYS)

    def _in_window(sale_date_str):
        if not sale_date_str:
            return False
        d = date.fromisoformat(sale_date_str)
        return window_start <= d <= window_end

    ssot_by_case = {r["case_number"]: r for r in rows if _in_window(r["sale_date"])}
    ours = run_sql(f"""
        SELECT case_number, auction_status, parity_status
        FROM public.multi_county_auctions
        WHERE lower(county) = {sql_str(county_slug)}
          AND sale_type = {sql_str(sale_type)}
          AND auction_date BETWEEN {sql_str(window_start.isoformat())} AND {sql_str(window_end.isoformat())}
    """)
    ours_by_case = {r["case_number"]: r for r in ours}

    # Some counties' clerk PDF case numbers ("4680/2019-2108") don't match
    # the short numeric case_number an earlier ingest sweep already stored
    # for the same real-world auction ("4680"). An exact-string miss here
    # re-inserts a duplicate bare stub every run and flags the enriched row
    # PHANTOM_NOT_ON_CLERK, undoing any manual reconciliation daily
    # (confirmed live for suwannee, 2026-08-11: 21/21 rows regressed to
    # match_pct=0.0 on the run immediately after a manual fix). Fall back to
    # the clerk case number's prefix before "/" only when the exact key
    # misses -- a no-op for every other clerk_ssot county, none of which use
    # "/"-format case numbers (verified live across all 27 counties).
    def _normalize_case(case_number):
        return case_number.split("/")[0] if "/" in case_number else case_number

    matched = 0
    missing_from_ours = []
    cancelled_mismatch = []
    clean_matches = []
    matched_our_cases = set()
    for case_number, ssot_row in ssot_by_case.items():
        our_row = ours_by_case.get(case_number)
        matched_case_number = case_number
        if our_row is None:
            normalized = _normalize_case(case_number)
            if normalized != case_number:
                our_row = ours_by_case.get(normalized)
                matched_case_number = normalized
        if our_row is None:
            missing_from_ours.append(ssot_row)
            continue
        matched += 1
        matched_our_cases.add(matched_case_number)
        matched_row = ssot_row if matched_case_number == case_number else {**ssot_row, "case_number": matched_case_number}
        if ssot_row["cancelled"] and our_row["auction_status"] != "CANCELLED":
            cancelled_mismatch.append(matched_row)
        else:
            clean_matches.append(matched_row)

    phantom_in_ours = [c for c in ours_by_case if c not in ssot_by_case and c not in matched_our_cases]

    # --- reconciliation actions (additive/corrective only, never delete) ---
    for ssot_row in missing_from_ours:
        status_val = "CANCELLED" if ssot_row["cancelled"] else "scheduled"
        parity_val = "CLERK_SSOT_CANCELLED" if ssot_row["cancelled"] else "CLERK_VERIFIED"
        run_sql(f"""
            INSERT INTO public.multi_county_auctions (county, sale_type, case_number, auction_date, auction_status, parity_status, parity_source)
            VALUES ({sql_str(county_slug)}, {sql_str(sale_type)}, {sql_str(ssot_row['case_number'])}, {sql_str(ssot_row['sale_date'])}, {sql_str(status_val)}, {sql_str(parity_val)}, {sql_str(f'{county_slug}_clerk_{sale_type}')})
            ON CONFLICT (county, case_number, sale_type) DO UPDATE SET
              auction_date = EXCLUDED.auction_date,
              auction_status = EXCLUDED.auction_status,
              parity_status = EXCLUDED.parity_status,
              parity_source = EXCLUDED.parity_source;
        """)

    for ssot_row in cancelled_mismatch:
        run_sql(f"""
            UPDATE public.multi_county_auctions
            SET auction_status='CANCELLED', parity_status='CLERK_SSOT_CANCELLED', parity_source={sql_str(f'{county_slug}_clerk_{sale_type}')}
            WHERE lower(county)={sql_str(county_slug)} AND sale_type={sql_str(sale_type)} AND case_number={sql_str(ssot_row['case_number'])};
        """)

    if clean_matches:
        in_list = ",".join(sql_str(r["case_number"]) for r in clean_matches)
        run_sql(f"""
            UPDATE public.multi_county_auctions
            SET parity_status='PARITY_OK', parity_source={sql_str(f'{county_slug}_clerk_{sale_type}')}
            WHERE lower(county)={sql_str(county_slug)} AND sale_type={sql_str(sale_type)}
              AND case_number IN ({in_list})
              AND parity_status IS DISTINCT FROM 'CLERK_SSOT_CANCELLED';
        """)

    if phantom_in_ours:
        in_list = ",".join(sql_str(c) for c in phantom_in_ours)
        run_sql(f"""
            UPDATE public.multi_county_auctions
            SET parity_status='PHANTOM_NOT_ON_CLERK'
            WHERE lower(county)={sql_str(county_slug)} AND sale_type={sql_str(sale_type)}
              AND auction_date BETWEEN {sql_str(window_start.isoformat())} AND {sql_str(window_end.isoformat())}
              AND case_number IN ({in_list});
        """)

    ssot_count = len(ssot_by_case)
    our_count = len(ours)
    match_pct = round(100.0 * matched / ssot_count, 1) if ssot_count else None
    if ssot_count == 0:
        status = "PARSE_FAIL"  # caller only reaches here with rows>0; guarded upstream
    elif missing_from_ours or cancelled_mismatch:
        status = "BEHIND" if missing_from_ours else "STALE_CANCEL"
    elif phantom_in_ours:
        status = "PHANTOM"
    else:
        status = "PARITY"

    detail = {
        "missing_case_numbers": [r["case_number"] for r in missing_from_ours][:20],
        "cancelled_mismatch_case_numbers": [r["case_number"] for r in cancelled_mismatch][:20],
        "phantom_case_numbers": phantom_in_ours[:20],
    }
    run_sql(f"""
        INSERT INTO public.clerk_parity_results
          (county_slug, sale_type, window_start, window_end, ssot_count, our_count, matched,
           missing_from_ours, phantom_in_ours, cancelled_mismatch, match_pct, status, detail)
        VALUES ({sql_str(county_slug)}, {sql_str(sale_type)}, {sql_str(window_start.isoformat())}, {sql_str(window_end.isoformat())},
                {ssot_count}, {our_count}, {matched}, {len(missing_from_ours)}, {len(phantom_in_ours)}, {len(cancelled_mismatch)},
                {match_pct if match_pct is not None else 'NULL'}, {sql_str(status)}, {sql_str(json.dumps(detail))}::jsonb);
    """)

    return {
        "county_slug": county_slug, "sale_type": sale_type, "ssot_count": ssot_count,
        "our_count": our_count, "matched": matched, "missing_from_ours": len(missing_from_ours),
        "phantom_in_ours": len(phantom_in_ours), "cancelled_mismatch": len(cancelled_mismatch),
        "match_pct": match_pct, "status": status,
    }


def main():
    results = []
    failures = []
    for county_slug, sale_types in PARSERS.items():
        for sale_type, parser_fn in sale_types.items():
            try:
                rows = parser_fn()
            except Exception as e:
                failures.append({"county_slug": county_slug, "sale_type": sale_type, "error": str(e)})
                run_sql(f"""
                    INSERT INTO public.clerk_parity_results (county_slug, sale_type, status, detail)
                    VALUES ({sql_str(county_slug)}, {sql_str(sale_type)}, 'PARSE_FAIL', {sql_str(json.dumps({'error': str(e)}))}::jsonb);
                """)
                continue
            if not rows:
                failures.append({"county_slug": county_slug, "sale_type": sale_type, "error": "0 rows from a successful parse — treated as FAILURE"})
                continue
            try:
                stage_rows(rows)
                results.append(diff_and_reconcile(county_slug, sale_type, rows))
            except Exception as e:
                failures.append({"county_slug": county_slug, "sale_type": sale_type, "error": f"SQL/reconcile error: {e}"})

    print(json.dumps({"results": results, "failures": failures}, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
