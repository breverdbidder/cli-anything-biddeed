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
import re
import subprocess
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clerk_ssot.parsers import (  # noqa: E402
    brevard, gadsden, wakulla, highlands, lake, okeechobee, st_johns, suwannee, union,
    bay, calhoun, desoto, dixie, franklin, gulf, hamilton, hardee, holmes, jefferson,
    lafayette, levy, liberty, madison, manatee, nassau, sumter, taylor, st_lucie, walton,
    volusia,
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
#
# Re-verified 2026-08-13 for the P1 parity-coverage-gap issue (GH #19052) --
# hillsborough, palm_beach, marion, pasco, polk, lee, seminole all still have
# no independently-parseable calendar (403/Cloudflare/timeout/RealAuction-only,
# same as above). ONE new county cleared this session: volusia. Its main
# clerk.org pages are RealAuction-only like the rest, but a separate
# clerk-owned app (app02.clerk.org/cm_sales/) is a real, live, disclaimer-gated
# ASP.NET calendar -- not RealAuction, not login-gated, just JS-postback-gated
# -- see clerk_ssot/parsers/volusia.py. escambia and citrus each have a
# clerk-owned tax_deed search app (public.escambiaclerk.com/taxsale/,
# search.citrusclerk.org/TaxSmartWeb) that also cleared Cloudflare/rendered
# real sale dates under Playwright, but both require per-date-click
# navigation (no "view all") -- left unparsed pending a follow-up session,
# NOT added to PARSERS since an untested per-date loop would risk PARSE_FAIL
# noise or wrong data more than it's worth today.
#
# highlands tax_deed added 2026-08-24: highlands.realtdm.com/public/cases/list
# is a plain, unauthenticated public case-search form (isPublic=1, no login) --
# distinct from the gated RealForeclose/RealAuction bidding platforms this
# pipeline avoids driving. Live-verified against 10 known gap rows (case
# numbers 25000900-25000910) before registering; see
# scripts/clerk_ssot/parsers/highlands.py module docstring for the full
# gate-vs-public distinction and status-id derivation.
PARSERS = {
    "brevard": {"foreclosure": brevard.parse_foreclosure},
    "gadsden": {"foreclosure": gadsden.parse_foreclosure, "tax_deed": gadsden.parse_tax_deed},
    "highlands": {"foreclosure": highlands.parse_foreclosure, "tax_deed": highlands.parse_tax_deed},
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
    "volusia": {"foreclosure": volusia.parse_foreclosure},
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
        SELECT case_number, auction_status, parity_status, parcel_id
        FROM public.multi_county_auctions
        WHERE lower(county) = {sql_str(county_slug)}
          AND sale_type = {sql_str(sale_type)}
          AND auction_date BETWEEN {sql_str(window_start.isoformat())} AND {sql_str(window_end.isoformat())}
    """)
    ours_by_case = {r["case_number"]: r for r in ours}

    # Holmes's clerk site never publishes a real docket number for
    # foreclosures (see scripts/clerk_ssot/parsers/holmes.py docstring), so
    # the live scrape synthesizes case_number as "PARCEL-{parcel_id}". A
    # separate, earlier ingest path already stores some of these same
    # auctions under unrelated UUID-based case numbers
    # ("HOLMES-LEGACY-{uuid}") with parcel_id populated in its own column.
    # Since the two case-number schemes share no substring in common, none
    # of the fallbacks above (or the case_number-only "ours" lookup) can ever
    # match them -- every daily run re-inserted a duplicate blank stub AND
    # phantom-flagged the enriched legacy row, undoing manual reconciliation
    # every 24h (confirmed live 2026-08-14 and again 2026-08-15, same row,
    # same parcel_id 0936.01-004-00C-008.000, two occurrences one cron cycle
    # apart). Match "PARCEL-{parcel_id}" SSOT rows against any existing row
    # for this county+sale_type whose parcel_id column equals that parcel_id,
    # regardless of case_number scheme. Gated on county_slug=='holmes' to
    # stay a no-op elsewhere, matching the manatee-gating convention above.
    ours_by_parcel_id = {}
    if county_slug == "holmes":
        for case_number, row in ours_by_case.items():
            pid = row.get("parcel_id")
            if pid:
                ours_by_parcel_id.setdefault(pid, case_number)

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

    # Some counties' clerk calendar publishes case numbers WITHOUT
    # zero-padding on the trailing numeric suffix ("2025CA1608") while a
    # pre-existing multi_county_auctions row stores the zero-padded canonical
    # clerk form ("2025CA001608"). An exact-string miss here re-inserts a
    # duplicate empty stub under the unpadded number (marked PARITY_OK) while
    # flagging the real, data-rich row PHANTOM_NOT_ON_CLERK -- confirmed live
    # for lake, 2026-08-12. Fall back to stripping leading zeros off the
    # numeric suffix only when both the exact key AND the "/"-split fallback
    # above miss -- a no-op for every county whose case numbers already match
    # exactly or via the "/" fallback.
    _CASE_SUFFIX_RE = re.compile(r"^(\d{4}(?:CA|CC))0*(\d+)$")

    # Manatee's clerk calendar (records.manateeclerk.com) publishes the bare
    # short form ("2025CA000550AX"), while a separate ingest pipeline
    # (realtaxdeed / calendar_sweep_mca_v3) already stores the SAME
    # real-world case as the 12th Judicial Circuit's long clerk form
    # ("412025CA000550CAAXMA" = "41" circuit prefix + short form's
    # YYYY/TYPE/NNNNNN core + a repeated TYPE + "AXMA" suffix). Neither form
    # matches the other exactly nor via the "/"-split or zero-pad fallbacks
    # above, so every clerk_ssot run re-inserted a fresh empty stub under the
    # short form each time a case got continued to a new sale date, instead
    # of updating the existing enriched row -- confirmed live 2026-08-15:
    # 16 manatee cases had exactly this duplicate-pair shape, all 16 stub
    # rows carrying zero content beyond case_number/auction_date/status.
    # Strip both wrapper shapes down to the same YYYY+TYPE+NNNNNN core (zero
    # padding included, matching _CASE_SUFFIX_RE's own convention) so the
    # canonical-key fallback below finds the enriched sibling instead of
    # creating a duplicate. Gated on county_slug=='manatee' rather than
    # relying on the regex shape alone to stay a no-op: an ULTRALOOP
    # adversarial verify pass (2026-08-15) found that levy's and liberty's
    # foreclosure CASE_RE (^\d{2,4}-?\d*-?(CA|CC|TD)[A-Z0-9-]*$, both parsers
    # currently observe zero live cards so their real format is unverified)
    # is loose enough to also match these two Manatee-specific patterns, and
    # calhoun/lafayette-tax_deed apply no case-number regex at all -- an
    # unscoped version of this fallback would be a latent collision risk for
    # those counties the moment they start returning real rows.
    _MANATEE_SHORT_RE = re.compile(r"^(\d{4})(CA|CC)0*(\d+)AX$")
    _MANATEE_LONG_RE = re.compile(r"^41(\d{4})(CA|CC)0*(\d+)(?:CA|CC)AXMA$")

    # okeechobeeclerk.com's live foreclosure calendar publishes the
    # hyphenated short form ("2025-CA-130"), while calendar_sweep_mca_v3
    # already stores the 19th Judicial Circuit's long clerk form
    # ("472025CA000130CAAXMX" = "47" circuit prefix + YYYY + CA + zero-padded
    # sequence + "CAAXMX" division/case-type suffix). Neither the exact-match,
    # "/"-split, nor _CASE_SUFFIX_RE (which requires the year to be
    # immediately followed by CA/CC with no separator, and no leading circuit
    # prefix or trailing suffix) matches either shape, so every clerk_ssot run
    # re-inserted a blank stub under the short form and flagged the enriched
    # long-form row PHANTOM_NOT_ON_CLERK -- confirmed live 2026-08-16: cases
    # 130/143/205 regressed this way, revoking okeechobee's certification
    # (consecutive_non_gold=3). Same failure shape as the manatee fix above;
    # gated on county_slug=='okeechobee' for the same collision-risk reason.
    _OKEECHOBEE_SHORT_RE = re.compile(r"^(\d{4})-(CA|CC|TD)-0*(\d+)$")
    _OKEECHOBEE_LONG_RE = re.compile(r"^\d{2}(\d{4})(CA|CC)0*(\d+)(?:CA|CC)AX[A-Z]{2}$")

    def _canonical_case(case_number):
        if county_slug == "manatee":
            m = _MANATEE_SHORT_RE.match(case_number) or _MANATEE_LONG_RE.match(case_number)
            if m:
                return f"{m.group(1)}{m.group(2)}{m.group(3)}"
        if county_slug == "okeechobee":
            m = _OKEECHOBEE_SHORT_RE.match(case_number) or _OKEECHOBEE_LONG_RE.match(case_number)
            if m:
                return f"{m.group(1)}{m.group(2)}{m.group(3)}"
        m = _CASE_SUFFIX_RE.match(case_number)
        return f"{m.group(1)}{m.group(2)}" if m else case_number

    # Build once, outside the per-row loop below.
    ours_by_canonical = {}
    for case_number in ours_by_case:
        canon = _canonical_case(case_number)
        if canon != case_number:
            ours_by_canonical.setdefault(canon, case_number)

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
            canon = _canonical_case(case_number)
            real_case_number = ours_by_canonical.get(canon)
            if real_case_number is not None:
                our_row = ours_by_case.get(real_case_number)
                matched_case_number = real_case_number
        if our_row is None and county_slug == "holmes" and case_number.startswith("PARCEL-"):
            real_case_number = ours_by_parcel_id.get(case_number[len("PARCEL-"):])
            if real_case_number is not None:
                our_row = ours_by_case.get(real_case_number)
                matched_case_number = real_case_number
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
        # Sync auction_date too, not just parity fields: a clean match found
        # only via the canonical-key fallback (case continued/rescheduled,
        # matched_case_number != ssot's case_number) means the surviving row's
        # stored date is the PRE-continuance date -- leaving it unsynced would
        # silently keep showing the wrong sale date even though the duplicate
        # stub that carried the correct date is gone (see manatee 2026-08-15).
        #
        # clean_matches mixes two cases that need different handling: rows
        # where the SSOT now says NOT cancelled (reactivate/reschedule) vs.
        # rows where the SSOT still says cancelled and we already agree
        # (already_cancelled). The old single UPDATE guarded on
        # "m.parity_status IS DISTINCT FROM 'CLERK_SSOT_CANCELLED'" to avoid
        # re-marking an agreeing-cancelled row PARITY_OK, but that guard also
        # permanently locked out the reactivate case: once a row's stored
        # parity_status was CLERK_SSOT_CANCELLED, this UPDATE could never
        # touch it again even after the SSOT rescheduled it, and the SET
        # clause never assigned auction_status, so a reactivated row would
        # anyway stay stuck at auction_status='CANCELLED' (lake case
        # 2024CA000186, first diagnosed 2026-08-13, re-broken 2026-08-17).
        reactivate = [r for r in clean_matches if not r["cancelled"]]
        already_cancelled = [r for r in clean_matches if r["cancelled"]]
        if reactivate:
            values = ",".join(
                f"({sql_str(r['case_number'])},{sql_str(r['sale_date'])})" for r in reactivate
            )
            run_sql(f"""
                UPDATE public.multi_county_auctions m
                SET parity_status='PARITY_OK', parity_source={sql_str(f'{county_slug}_clerk_{sale_type}')},
                    auction_date=v.sale_date::date, auction_status='scheduled'
                FROM (VALUES {values}) AS v(case_number, sale_date)
                WHERE lower(m.county)={sql_str(county_slug)} AND m.sale_type={sql_str(sale_type)}
                  AND m.case_number = v.case_number;
            """)
        if already_cancelled:
            values = ",".join(
                f"({sql_str(r['case_number'])},{sql_str(r['sale_date'])})" for r in already_cancelled
            )
            run_sql(f"""
                UPDATE public.multi_county_auctions m
                SET parity_source={sql_str(f'{county_slug}_clerk_{sale_type}')},
                    auction_date=v.sale_date::date
                FROM (VALUES {values}) AS v(case_number, sale_date)
                WHERE lower(m.county)={sql_str(county_slug)} AND m.sale_type={sql_str(sale_type)}
                  AND m.case_number = v.case_number;
            """)

    if phantom_in_ours:
        in_list = ",".join(sql_str(c) for c in phantom_in_ours)
        run_sql(f"""
            UPDATE public.multi_county_auctions
            SET parity_status='PHANTOM_NOT_ON_CLERK'
            WHERE lower(county)={sql_str(county_slug)} AND sale_type={sql_str(sale_type)}
              AND auction_date BETWEEN {sql_str(window_start.isoformat())} AND {sql_str(window_end.isoformat())}
              AND case_number IN ({in_list})
              AND parity_status IS DISTINCT FROM 'CLERK_SSOT_CANCELLED';
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
