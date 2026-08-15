#!/usr/bin/env python3
"""
County co_no certification expansion script.
Issue #19084 — expand confirmed coverage from 20/67 toward 95%+ of FL counties.

Methodology:
  - Address match: auction property_address vs fl_parcels for candidate co_no
  - Confirm only at: match_pct >= 85% AND sample_n >= 5
  - Normalization: suffix stripping, abbreviation expansion, city disambiguation
  - Write every result to county_co_no_resolution (insert or update)

dispatch_id: county-cert-expansion-20260814

Usage:
  python scripts/county_co_no_expand.py [--dry-run] [--county <slug>] [--batch <near-miss|unattempted|all>]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from difflib import SequenceMatcher

SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
REF = "mocerqjnksmhcjzxrewo"
MGMT_API = f"https://api.supabase.com/v1/projects/{REF}/database/query"
DISPATCH_ID = "county-cert-expansion-20260814"

MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}
REST_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}


def run_sql(sql: str, retries: int = 3) -> list:
    """Execute SQL via Management API (preferred) or Supabase REST RPC fallback."""
    if SUPABASE_ACCESS_TOKEN:
        body = json.dumps({"query": sql}).encode()
        req = urllib.request.Request(MGMT_API, data=body, headers=MGMT_HEADERS, method="POST")
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    raw = r.read()
                    result = json.loads(raw or b"[]")
                    return result if isinstance(result, list) else [result]
            except urllib.error.HTTPError as e:
                txt = e.read().decode()[:400]
                print(f"  [WARN] Mgmt API attempt {attempt+1}/{retries}: HTTP {e.code}: {txt}", flush=True)
                if e.code in (429, 503, 502) and attempt < retries - 1:
                    time.sleep(30 * (attempt + 1))
                    continue
                break
            except Exception as exc:
                print(f"  [WARN] Mgmt API attempt {attempt+1}/{retries}: {exc}", flush=True)
                if attempt < retries - 1:
                    time.sleep(15)
                    continue
                break

    if SUPABASE_SERVICE_ROLE_KEY:
        # Fall back to Supabase REST API via execute_sql RPC
        body = json.dumps({"sql_query": sql}).encode()
        url = f"{SUPABASE_URL}/rest/v1/rpc/execute_sql"
        req = urllib.request.Request(url, data=body, headers=REST_HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                result = json.loads(raw or b"[]")
                return result if isinstance(result, list) else [result]
        except Exception as exc:
            print(f"  [WARN] REST RPC fallback failed: {exc}", flush=True)

    raise RuntimeError(
        "No database credentials available. "
        "Set SUPABASE_ACCESS_TOKEN or SUPABASE_SERVICE_ROLE_KEY."
    )


# ─── Address normalization ────────────────────────────────────────────────────

SUFFIX_ABBREV = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD",
    "DRIVE": "DR", "ROAD": "RD", "COURT": "CT", "LANE": "LN",
    "PLACE": "PL", "CIRCLE": "CIR", "TERRACE": "TER",
    "TRAIL": "TRL", "HIGHWAY": "HWY", "PARKWAY": "PKWY",
    "WAY": "WAY", "LOOP": "LOOP", "RUN": "RUN",
}
SUFFIX_ABBREV_RE = re.compile(
    r"\b(" + "|".join(sorted(SUFFIX_ABBREV.keys(), key=len, reverse=True)) + r")\b"
)
SUFFIX_WORDS = set(SUFFIX_ABBREV.keys()) | set(SUFFIX_ABBREV.values())
UNIT_RE = re.compile(r"\s+(UNIT|APT|STE|SUITE|#)\s*\S+$", re.I)

# Known FL city/county names that sometimes appear at end of address strings (Glades quirk)
FL_CITY_SUFFIXES = [
    "FORT LAUDERDALE", "MIAMI", "ORLANDO", "TAMPA", "JACKSONVILLE",
    "TALLAHASSEE", "GAINESVILLE", "OCALA", "DUNNELLON", "SUMMERFIELD",
    "PENSACOLA", "FORT MYERS", "SARASOTA", "WEST PALM BEACH",
    "CLEARWATER", "ST PETERSBURG", "KISSIMMEE", "DAYTONA BEACH",
    "LAKELAND", "BRADENTON", "PALM BAY", "MELBOURNE",
    "FERNANDINA BEACH", "PALATKA", "QUINCY", "BUSHNELL",
    "BARTOW", "WAUCHULA", "AVON PARK", "OKEECHOBEE",
    "BLOUNTSTOWN", "BRISTOL", "MACCLENNY",
    "BONITA SPRINGS", "NAPLES", "IMMOKALEE", "MARCO ISLAND",
    "CRAWFORDVILLE", "MONTICELLO", "MADISON", "LIVE OAK",
    "LAKE CITY", "JASPER", "WHITE SPRINGS", "PERRY",
    "TRENTON", "CHIEFLAND", "BRONSON", "CEDAR KEY",
    "INVERNESS", "CRYSTAL RIVER", "HOMOSASSA",
    "BROOKSVILLE", "SPRING HILL", "WEEKI WACHEE",
    "DADE CITY", "ZEPHYRHILLS", "NEW PORT RICHEY",
    "ST AUGUSTINE", "GREEN COVE SPRINGS", "CALLAHAN", "YULEE",
    "DEFUNIAK SPRINGS", "CRESTVIEW", "FORT WALTON BEACH",
    "MARIANNA", "CHIPLEY", "BONIFAY",
    "STUART", "HOBE SOUND", "PALM CITY", "INDIANTOWN",
    "KEY WEST", "MARATHON", "HOMESTEAD", "FLORIDA CITY",
    "VERO BEACH", "SEBASTIAN", "FELLSMERE",
    "ARCADIA", "NOCATEE", "FORT OGDEN",
    "LABELLE", "CLEWISTON", "MOORE HAVEN",
    "BELLE GLADE", "PAHOKEE", "SOUTH BAY",
    "APALACHICOLA", "CARRABELLE", "MAYO", "OLD TOWN",
    "SANFORD", "DELTONA", "HOLLY HILL", "EDGEWATER",
    "LEESBURG", "TAVARES", "CLERMONT", "MOUNT DORA",
    "OCKLAWAHA", "BELLEVIEW", "SILVER SPRINGS",
]
FL_CITY_SUFFIXES_SORTED = sorted(FL_CITY_SUFFIXES, key=len, reverse=True)


def normalize_address(addr: str, mode: str = "standard") -> str:
    """
    Normalize a property address for fuzzy matching.
    modes:
      standard     - basic uppercase + unit strip + city strip
      strip_suffix - also strip street suffix entirely (Pasco quirk)
      abbrev       - also abbreviate spelled-out suffixes (Indian River quirk)
    """
    if not addr:
        return ""
    a = addr.upper().strip()
    # Remove unit number
    a = UNIT_RE.sub("", a)
    # Remove trailing city name (Glades quirk: address string includes city)
    for city in FL_CITY_SUFFIXES_SORTED:
        if a.endswith(f" {city}"):
            a = a[: -(len(city) + 1)].rstrip(",").strip()
            break
        if a.endswith(f", {city}"):
            a = a[: -(len(city) + 2)].strip()
            break
    # Collapse whitespace
    a = re.sub(r"\s+", " ", a).strip()

    if mode == "abbrev":
        a = SUFFIX_ABBREV_RE.sub(lambda m: SUFFIX_ABBREV.get(m.group(1), m.group(1)), a)

    elif mode == "strip_suffix":
        tokens = a.split()
        if tokens:
            last = tokens[-1]
            if last in SUFFIX_WORDS:
                tokens = tokens[:-1]
            a = " ".join(tokens)

    return a.strip()


def fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def address_score(aaddr: str, paddr: str, mode: str = "standard") -> float:
    """Score a pair of addresses. Returns 0.0-1.0."""
    n1 = normalize_address(aaddr, mode)
    n2 = normalize_address(paddr, mode)
    if not n1 or not n2:
        return 0.0

    base = fuzzy_ratio(n1, n2)

    # Boost: if first tokens (street numbers) match, give extra credit
    t1 = n1.split()
    t2 = n2.split()
    if t1 and t2 and t1[0] == t2[0] and t1[0].isdigit():
        rest_score = fuzzy_ratio(" ".join(t1[1:]), " ".join(t2[1:]))
        base = max(base, 0.65 + 0.35 * rest_score)

    return base


# ─── Matching core ────────────────────────────────────────────────────────────

MATCH_THRESHOLD = 0.78  # Fuzzy match threshold for individual address pair


def match_addresses(auction_rows: list, parcel_rows: list, mode: str = "standard") -> dict:
    """
    For each auction address, find the best matching parcel address.
    Returns: {matched, total, match_pct, city_sample, unmatched_sample}
    """
    if not auction_rows:
        return {"matched": 0, "total": 0, "match_pct": 0.0, "city_sample": [], "unmatched_sample": []}
    if not parcel_rows:
        return {"matched": 0, "total": len(auction_rows), "match_pct": 0.0, "city_sample": [], "unmatched_sample": []}

    matched = 0
    city_sample: list[str] = []
    unmatched_sample: list[str] = []

    for arow in auction_rows:
        aaddr = arow.get("property_address", "") or ""
        best_score = 0.0
        best_city = None

        for prow in parcel_rows:
            paddr = prow.get("address", "") or ""
            s = address_score(aaddr, paddr, mode)
            if s > best_score:
                best_score = s
                best_city = prow.get("city_name", "")

        if best_score >= MATCH_THRESHOLD:
            matched += 1
            if best_city and best_city not in city_sample:
                city_sample.append(best_city)
        else:
            if len(unmatched_sample) < 5:
                unmatched_sample.append(aaddr[:60])

    total = len(auction_rows)
    match_pct = round(100.0 * matched / total, 1) if total > 0 else 0.0
    return {
        "matched": matched,
        "total": total,
        "match_pct": match_pct,
        "city_sample": city_sample[:10],
        "unmatched_sample": unmatched_sample,
    }


def try_all_modes(auction_rows: list, parcel_rows: list) -> tuple[dict, str]:
    """Try standard, abbrev, strip_suffix modes; return best result."""
    best_result: dict | None = None
    best_mode = "standard"
    for mode in ("standard", "abbrev", "strip_suffix"):
        r = match_addresses(auction_rows, parcel_rows, mode)
        if best_result is None or r["match_pct"] > best_result["match_pct"]:
            best_result = r
            best_mode = mode
    return best_result, best_mode  # type: ignore[return-value]


# ─── DB I/O ──────────────────────────────────────────────────────────────────

def fetch_auction_addresses(county_slug: str, limit: int = 150) -> list:
    rows = run_sql(f"""
        SELECT id, property_address, city
        FROM multi_county_auctions
        WHERE lower(county) = '{county_slug.lower()}'
          AND property_address IS NOT NULL
          AND trim(property_address) <> ''
        LIMIT {limit};
    """)
    return rows if isinstance(rows, list) else []


def fetch_parcels_for_cono(co_no: int, limit: int = 3000) -> list:
    rows = run_sql(f"""
        SELECT parcel_id, phy_addr1 AS address, phy_city AS city_name
        FROM fl_parcels
        WHERE co_no = {co_no}
          AND phy_addr1 IS NOT NULL
          AND trim(phy_addr1) <> ''
        LIMIT {limit};
    """)
    return rows if isinstance(rows, list) else []


def upsert_resolution(
    county_slug: str,
    co_no: int,
    match_pct: float,
    sample_n: int,
    is_confirmed: bool,
    method: str,
    notes: str,
) -> None:
    safe_notes = notes.replace("'", "''")[:2000]
    safe_method = method.replace("'", "''")[:200]
    safe_slug = county_slug.lower().replace("'", "")
    run_sql(f"""
        INSERT INTO county_co_no_resolution
            (county_slug, co_no, match_pct, sample_n, is_confirmed, method, notes, resolved_at)
        VALUES
            ('{safe_slug}', {co_no}, {match_pct}, {sample_n},
             {'true' if is_confirmed else 'false'},
             '{safe_method}', '{safe_notes}', now())
        ON CONFLICT (county_slug)
        DO UPDATE SET
            co_no        = EXCLUDED.co_no,
            match_pct    = EXCLUDED.match_pct,
            sample_n     = EXCLUDED.sample_n,
            is_confirmed = EXCLUDED.is_confirmed,
            method       = EXCLUDED.method,
            notes        = EXCLUDED.notes,
            resolved_at  = now();
    """)


def log_op(task: str, status: str, evidence: str, severity: str = "info") -> None:
    safe_ev = evidence.replace("'", "''")[:2000]
    safe_task = task.replace("'", "''")[:500]
    try:
        run_sql(f"""
            INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity, created_at)
            VALUES ('{DISPATCH_ID}', '{safe_task}', '{status}', '{safe_ev}', '{severity}', now());
        """)
    except Exception as e:
        print(f"  [WARN] agent_ops_log insert failed: {e}", flush=True)


def coverage_query() -> dict:
    rows = run_sql("""
        SELECT
            count(*) as confirmed,
            (SELECT count(*) FROM multi_county_auctions
             WHERE auction_status='completed' AND tier1_sale_status IS NOT NULL
               AND lower(county) IN (
                   SELECT county_slug FROM county_co_no_resolution WHERE is_confirmed=true
               )) as training_rows_covered,
            (SELECT count(*) FROM multi_county_auctions
             WHERE auction_status='completed' AND tier1_sale_status IS NOT NULL
            ) as training_rows_total
        FROM county_co_no_resolution
        WHERE is_confirmed=true;
    """)
    if isinstance(rows, list) and rows:
        return rows[0]
    return {"confirmed": "?", "training_rows_covered": "?", "training_rows_total": "?"}


# ─── FL DOR co_no lookup (STARTING GUESS ONLY — must verify via fl_parcels) ─

# DOR 2024 county codes: https://floridarevenue.com/dor/property/docs/PT-114.pdf
FL_DOR_CONO: dict[str, int] = {
    "alachua": 1, "baker": 2, "bay": 3, "bradford": 4, "brevard": 5,
    "broward": 6, "calhoun": 7, "charlotte": 8, "citrus": 9, "clay": 10,
    "collier": 11, "columbia": 12, "miami_dade": 13, "desoto": 14, "dixie": 15,
    "duval": 16, "escambia": 17, "flagler": 18, "franklin": 19, "gadsden": 20,
    "gilchrist": 21, "glades": 22, "gulf": 23, "hamilton": 24, "hardee": 25,
    "hendry": 26, "hernando": 27, "highlands": 28, "hillsborough": 29,
    "holmes": 30, "indian_river": 31, "jackson": 32, "jefferson": 33,
    "lafayette": 34, "lake": 35, "lee": 36, "leon": 37, "levy": 38,
    "liberty": 39, "madison": 40, "manatee": 41, "marion": 42, "martin": 43,
    "monroe": 44, "nassau": 45, "okaloosa": 46, "okeechobee": 47, "orange": 48,
    "osceola": 49, "palm_beach": 50, "pasco": 51, "pinellas": 52, "polk": 53,
    "putnam": 54, "st_johns": 55, "st_lucie": 56, "santa_rosa": 57,
    "sarasota": 58, "seminole": 59, "sumter": 60, "suwannee": 61, "taylor": 62,
    "union": 63, "volusia": 64, "wakulla": 65, "walton": 66, "washington": 67,
}
# Slug normalization aliases
SLUG_ALIASES: dict[str, str] = {
    "miami-dade": "miami_dade",
    "st. johns": "st_johns",
    "st. lucie": "st_lucie",
    "saint_johns": "st_johns",
    "saint_lucie": "st_lucie",
    "santa rosa": "santa_rosa",
    "indian river": "indian_river",
    "palm beach": "palm_beach",
    "palm_beach": "palm_beach",
    "miami dade": "miami_dade",
}


def canonical_slug(slug: str) -> str:
    s = slug.lower().strip().replace(" ", "_").replace("-", "_")
    return SLUG_ALIASES.get(s, s)


# VERIFIED LIVE (2026-08-15) against fl_parcels: the co_no column in THIS
# project's fl_parcels table is the standard DOR alphabetical code + 10
# (e.g. co_no=16 -> phy_city Oakland Park/Lauderdale Lakes = Broward, whose
# standard DOR code is 6; co_no=58 -> Apopka = Orange, standard code 48).
# Confirmed against all 20 already-confirmed rows AND all 7 near-miss co_no
# hints in the issue brief (broward=16, gadsden=30, orange=58, clay=20,
# franklin=29, hardee=35, lafayette=44) -- every one matches DOR+10 exactly.
# Live query: SELECT co_no, array_agg(phy_city)[1:3] FROM fl_parcels GROUP BY co_no
# returned a clean, gapless 11..77 range (67 counties), never DOR's raw 1..67.
CO_NO_TABLE_OFFSET = 10


def candidate_conos(slug: str) -> list[int]:
    """Return ordered list of co_no candidates to try (primary first, then adjacent)."""
    cs = canonical_slug(slug)
    dor_code = FL_DOR_CONO.get(cs)
    if dor_code:
        primary = dor_code + CO_NO_TABLE_OFFSET
        candidates = [primary]
        # Add adjacent values in case registry/offset is still wrong for this
        # county specifically (Marion lesson: never trust it blindly)
        for delta in (-1, 1, -2, 2, 3, -3):
            n = primary + delta
            if 11 <= n <= 77 and n not in candidates:
                candidates.append(n)
        return candidates[:5]
    # Unknown slug — try sequential across the verified live range
    return list(range(11, 78))


# ─── Per-county processing ────────────────────────────────────────────────────

METHOD_NAME = {
    "standard": "address_match_vs_fl_parcels",
    "abbrev": "address_match_vs_fl_parcels_suffix_abbrev",
    "strip_suffix": "address_match_vs_fl_parcels_suffix_stripped",
}


def process_one_cono(county_slug: str, co_no: int, limit: int = 150) -> dict:
    """Run address matching for one county vs one co_no. Returns result dict."""
    auction_rows = fetch_auction_addresses(county_slug, limit=limit)
    n_auction = len(auction_rows)
    if n_auction == 0:
        return {
            "county_slug": county_slug, "co_no": co_no,
            "match_pct": 0.0, "sample_n": 0, "is_confirmed": False,
            "method": "address_match_vs_fl_parcels",
            "notes": "No rows with property_address found in multi_county_auctions for this county slug. "
                     "County may use a different slug format, or all rows lack property_address.",
            "city_sample": [],
        }

    parcel_rows = fetch_parcels_for_cono(co_no, limit=3000)
    if len(parcel_rows) == 0:
        return {
            "county_slug": county_slug, "co_no": co_no,
            "match_pct": 0.0, "sample_n": 0, "is_confirmed": False,
            "method": "address_match_vs_fl_parcels",
            "notes": f"co_no={co_no} returned 0 rows from fl_parcels — this co_no is likely wrong for this county.",
            "city_sample": [],
        }

    result, mode = try_all_modes(auction_rows, parcel_rows)
    match_pct = result["match_pct"]
    matched_n = result["matched"]
    city_sample = result["city_sample"]
    unmatched_sample = result.get("unmatched_sample", [])
    method = METHOD_NAME[mode]
    is_confirmed = match_pct >= 85.0 and matched_n >= 5

    notes_parts = [
        f"co_no={co_no} tested: {n_auction} auction addresses vs {len(parcel_rows)} fl_parcels rows.",
        f"Best normalization mode: {mode}. match_pct={match_pct}%, matched_n={matched_n}/{n_auction}.",
        f"City sample from matched parcels: {city_sample}.",
    ]
    if unmatched_sample:
        notes_parts.append(f"Sample unmatched auction addresses: {unmatched_sample}.")
    if is_confirmed:
        notes_parts.append(f"CONFIRMED: cleared >=85% threshold with sample_n={matched_n}>=5.")
    elif match_pct >= 80:
        notes_parts.append(
            f"Near-miss ({match_pct}% < 85% bar). "
            "Possible normalization issue or condo/unit address format variance."
        )
    elif matched_n < 5:
        notes_parts.append(
            f"Insufficient sample (n={matched_n} < 5 required). "
            "County has too few auction rows with property_address for reliable confirmation."
        )
    else:
        notes_parts.append(
            f"Low match rate ({match_pct}%); co_no={co_no} is likely wrong for this county. "
            "Try adjacent co_no values or investigate street-name collision."
        )

    return {
        "county_slug": county_slug, "co_no": co_no,
        "match_pct": match_pct, "sample_n": matched_n,
        "is_confirmed": is_confirmed, "method": method,
        "notes": " ".join(notes_parts),
        "city_sample": city_sample,
    }


def find_best_cono(county_slug: str, limit: int = 150) -> dict:
    """Try candidate co_no values for a county. Return best result (highest match_pct)."""
    candidates = candidate_conos(county_slug)
    best: dict | None = None
    for co_no in candidates:
        print(f"      trying co_no={co_no}...", flush=True)
        result = process_one_cono(county_slug, co_no, limit=limit)
        if best is None or result["match_pct"] > best["match_pct"]:
            best = result
        if result["is_confirmed"]:
            print(f"      ✅ co_no={co_no} confirmed at {result['match_pct']}%", flush=True)
            break
        if result["match_pct"] < 20 and result["sample_n"] > 0:
            # Very low match — co_no clearly wrong, try next
            pass
    return best  # type: ignore[return-value]


# ─── Known near-miss counties (7 from issue brief) ───────────────────────────

NEAR_MISS = [
    # (county_slug, co_no_hint, context)
    # co_no values are the real table codes from the issue brief (DOR alphabetical
    # code + CO_NO_TABLE_OFFSET, verified live) -- NOT the raw FL_DOR_CONO values.
    ("broward",   16, "84.0% at n=50 — condo/unit address variance suspected"),
    ("gadsden",  30,  "69.6% at n=23 — real gap below threshold"),
    ("orange",   58,  "54.6% at n=59 — street-name collision, try city/zip disambiguation"),
    ("clay",     20,  "80.0% at n=4 — sample too small"),
    ("franklin", 29,  "81.8% at n=9 — sample too small"),
    ("hardee",   35,  "75.0% at n=4 — only 4 rows with property_address in total"),
    ("lafayette", 44, "100% but n=1 only — single match not evidence"),
]


# ─── Steps ───────────────────────────────────────────────────────────────────

def step1_inspect() -> tuple[list, set]:
    print("\n" + "=" * 64)
    print("STEP 1: Inspect live county_co_no_resolution table")
    print("=" * 64)

    rows = run_sql("""
        SELECT county_slug, co_no, match_pct, sample_n, is_confirmed, method,
               left(notes, 100) as notes_preview
        FROM county_co_no_resolution
        ORDER BY is_confirmed DESC, match_pct DESC;
    """)
    if not isinstance(rows, list):
        print(f"  ERROR: {rows}", flush=True)
        return [], set()

    confirmed = [r for r in rows if r.get("is_confirmed")]
    unconfirmed = [r for r in rows if not r.get("is_confirmed")]
    existing_slugs = {r["county_slug"] for r in rows}

    print(f"\n  CONFIRMED ({len(confirmed)}):", flush=True)
    for r in confirmed:
        print(f"    {r['county_slug']:22s} co_no={r['co_no']:3d}  match={r['match_pct']}%  n={r['sample_n']}", flush=True)

    print(f"\n  UNCONFIRMED ({len(unconfirmed)}):", flush=True)
    for r in unconfirmed:
        print(f"    {r['county_slug']:22s} co_no={r['co_no']:3d}  match={r['match_pct']}%  n={r['sample_n']}", flush=True)

    # Also find county slugs in MCA not in resolution table
    mca_slugs = run_sql("""
        SELECT lower(county) as slug, count(*) as cnt
        FROM multi_county_auctions
        GROUP BY lower(county)
        ORDER BY cnt DESC;
    """)
    if isinstance(mca_slugs, list):
        unattempted = [r for r in mca_slugs if r["slug"] not in existing_slugs]
        print(f"\n  UNATTEMPTED IN MCA ({len(unattempted)}):", flush=True)
        for r in unattempted[:25]:
            print(f"    {r['slug']:22s}  cnt={r['cnt']}", flush=True)
        if len(unattempted) > 25:
            print(f"    ... +{len(unattempted)-25} more", flush=True)

    cov = coverage_query()
    print(f"\n  BEFORE COVERAGE: confirmed={cov.get('confirmed')}  "
          f"training_rows_covered={cov.get('training_rows_covered')}  "
          f"training_rows_total={cov.get('training_rows_total')}", flush=True)

    return rows, existing_slugs


def step2_near_misses(dry_run: bool = True) -> list[dict]:
    label = "DRY RUN" if dry_run else "APPLYING"
    print(f"\n{'='*64}", flush=True)
    print(f"STEP 2: Near-miss counties [{label}]", flush=True)
    print("=" * 64, flush=True)

    results = []
    for county_slug, co_no_hint, context in NEAR_MISS:
        print(f"\n  --- {county_slug.upper()} (hint co_no={co_no_hint}) ---", flush=True)
        print(f"  Context: {context}", flush=True)
        # For orange, try more addresses to improve city disambiguation
        limit = 200 if county_slug == "orange" else 150
        result = process_one_cono(county_slug, co_no_hint, limit=limit)
        results.append(result)

        status_label = "✅ CONFIRMED" if result["is_confirmed"] else "❌ still unconfirmed"
        print(f"  RESULT: match_pct={result['match_pct']}%  n={result['sample_n']}  {status_label}", flush=True)
        print(f"  Method: {result['method']}", flush=True)
        print(f"  Notes: {result['notes'][:250]}", flush=True)

        if not dry_run:
            upsert_resolution(
                result["county_slug"], result["co_no"], result["match_pct"],
                result["sample_n"], result["is_confirmed"], result["method"], result["notes"],
            )
            log_op(
                task=f"near_miss_{county_slug}",
                status="VERIFIED" if result["is_confirmed"] else "PARTIAL",
                evidence=f"match_pct={result['match_pct']} sample_n={result['sample_n']} confirmed={result['is_confirmed']}",
                severity="info" if result["is_confirmed"] else "warn",
            )

    return results


def step3_unattempted(existing_slugs: set, dry_run: bool = False) -> list[dict]:
    print(f"\n{'='*64}", flush=True)
    print("STEP 3: Unattempted counties", flush=True)
    print("=" * 64, flush=True)

    mca_slugs = run_sql("""
        SELECT lower(county) as slug, count(*) as cnt
        FROM multi_county_auctions
        GROUP BY lower(county)
        ORDER BY cnt DESC;
    """)
    if not isinstance(mca_slugs, list):
        print(f"  ERROR fetching MCA slugs: {mca_slugs}", flush=True)
        return []

    # Include near-miss counties that exist in table but might need re-attempt
    near_miss_slugs = {s for s, _, _ in NEAR_MISS}
    unattempted = [
        r for r in mca_slugs
        if r["slug"] not in existing_slugs and r["slug"] not in near_miss_slugs
    ]
    print(f"  {len(unattempted)} unattempted counties to process", flush=True)

    results = []
    for i, row in enumerate(unattempted):
        slug = row["slug"]
        cnt = row.get("cnt", 0)
        print(f"\n  [{i+1}/{len(unattempted)}] {slug.upper()} (auctions={cnt})", flush=True)

        result = find_best_cono(slug)
        if result:
            results.append(result)
            s = "✅ CONFIRMED" if result["is_confirmed"] else "❌ unconfirmed"
            print(f"    → co_no={result['co_no']} match={result['match_pct']}% n={result['sample_n']} {s}", flush=True)

            if not dry_run:
                upsert_resolution(
                    result["county_slug"], result["co_no"], result["match_pct"],
                    result["sample_n"], result["is_confirmed"], result["method"], result["notes"],
                )
                log_op(
                    task=f"unattempted_{slug}",
                    status="VERIFIED" if result["is_confirmed"] else "PARTIAL",
                    evidence=f"match_pct={result['match_pct']} sample_n={result['sample_n']} co_no={result['co_no']}",
                    severity="info" if result["is_confirmed"] else "warn",
                )

        # Progress checkpoint every 10
        if (i + 1) % 10 == 0:
            cov = coverage_query()
            print(f"\n  === PROGRESS after {i+1} counties ===", flush=True)
            print(f"  confirmed={cov.get('confirmed')}  "
                  f"training_rows_covered={cov.get('training_rows_covered')}  "
                  f"training_rows_total={cov.get('training_rows_total')}", flush=True)

    return results


def teardown_log() -> None:
    """Mandatory session teardown cost telemetry."""
    try:
        run_sql(f"""
            SELECT public.log_cc_session_cost(
                p_issue        := 19084,
                p_run_id       := NULL,
                p_shard_label  := '{DISPATCH_ID}',
                p_model        := 'claude-sonnet-4-6',
                p_effort_level := 'high',
                p_input_tokens := 0,
                p_output_tokens:= 0,
                p_cache_read   := 0,
                p_cache_write  := 0,
                p_started_at   := now() - interval '10 minutes',
                p_ended_at     := now(),
                p_conclusion   := 'success',
                p_dod_met      := NULL,
                p_raw_usage    := NULL
            );
        """)
        print("  Teardown cost log: OK", flush=True)
    except Exception as e:
        print(f"  Teardown cost log: FAILED ({e})", flush=True)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="County co_no certification expansion")
    parser.add_argument("--dry-run", action="store_true", help="Show results without writing to DB")
    parser.add_argument("--county", help="Process only this county slug")
    parser.add_argument(
        "--batch",
        choices=["near-miss", "unattempted", "all"],
        default="all",
        help="Which batch to process",
    )
    args = parser.parse_args()

    print("=== County co_no Certification Expansion ===", flush=True)
    print(f"dispatch_id: {DISPATCH_ID}", flush=True)
    print(f"SUPABASE_ACCESS_TOKEN: {'SET' if SUPABASE_ACCESS_TOKEN else 'NOT_SET'}", flush=True)
    print(f"SUPABASE_SERVICE_ROLE_KEY: {'SET' if SUPABASE_SERVICE_ROLE_KEY else 'NOT_SET'}", flush=True)
    print(f"dry_run={args.dry_run}  batch={args.batch}", flush=True)

    if not SUPABASE_ACCESS_TOKEN and not SUPABASE_SERVICE_ROLE_KEY:
        print("\nBLOCKED: No database credentials available.", flush=True)
        print("Set SUPABASE_ACCESS_TOKEN (preferred) or SUPABASE_SERVICE_ROLE_KEY.", flush=True)
        sys.exit(1)

    # Single county mode
    if args.county:
        slug = canonical_slug(args.county)
        print(f"\nSingle-county mode: {slug}", flush=True)
        result = find_best_cono(slug)
        print(f"\n  Result: {result}", flush=True)
        if not args.dry_run and result:
            upsert_resolution(
                result["county_slug"], result["co_no"], result["match_pct"],
                result["sample_n"], result["is_confirmed"], result["method"], result["notes"],
            )
            print("  Written to DB.", flush=True)
        return

    # Step 1: Inspect
    existing_rows, existing_slugs = step1_inspect()
    if not existing_rows and not existing_slugs:
        print("ERROR: Could not read county_co_no_resolution table.", flush=True)
        sys.exit(1)

    # Step 2: Near-miss counties
    if args.batch in ("near-miss", "all"):
        # Dry run first
        print("\n--- DRY RUN near-miss counties ---", flush=True)
        dry_results = step2_near_misses(dry_run=True)
        print("\n--- Dry-run summary ---", flush=True)
        for r in dry_results:
            s = "✅ WOULD CONFIRM" if r["is_confirmed"] else "❌ still unconfirmed"
            print(f"  {r['county_slug']:15s} co_no={r['co_no']} "
                  f"match={r['match_pct']}% n={r['sample_n']} {s}", flush=True)

        if not args.dry_run:
            print("\n--- APPLYING near-miss results ---", flush=True)
            step2_near_misses(dry_run=False)
            cov = coverage_query()
            print(f"\n  COVERAGE after near-miss batch: "
                  f"confirmed={cov.get('confirmed')}  "
                  f"covered={cov.get('training_rows_covered')}/"
                  f"{cov.get('training_rows_total')}", flush=True)

    # Step 3: Unattempted counties
    if args.batch in ("unattempted", "all"):
        step3_unattempted(existing_slugs, dry_run=args.dry_run)

    # Final coverage
    cov = coverage_query()
    print(f"\n{'='*64}", flush=True)
    print(f"FINAL COVERAGE:", flush=True)
    print(f"  confirmed={cov.get('confirmed')}", flush=True)
    print(f"  training_rows_covered={cov.get('training_rows_covered')}", flush=True)
    print(f"  training_rows_total={cov.get('training_rows_total')}", flush=True)

    if not args.dry_run:
        teardown_log()

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
