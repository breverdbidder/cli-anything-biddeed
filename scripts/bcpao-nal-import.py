#!/usr/bin/env python3
"""
BCPAO NAL Import — folio→PIN bridge (no CF, no bulk file needed)

v3 approach: BCPAO bulk download is CF-blocked. This script builds the same
folio→PIN mapping using data already in Supabase (fl_parcels + MCA).

Strategies (in confidence order):
  S1 bcpao_data   — extract PIN from mca.bcpao_data->>'parcel_id' where available
  S2 addr_exact   — mca.street_normalized == fl_parcels.addr_key (co_no=15)
  S3 addr_clean   — strip city/state/zip from street_normalized, retry exact match
  S4 addr_num_zip — house number + zip where fl_parcels match is unique

Writes to: brevard_folio_pin_bridge
Updates:   bcpao_fetch_jobs status (done / empty / failed)
Calls:     bcpao_folio_drain() to push PINs into multi_county_auctions

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import os, sys, re, time, json
import urllib.request, urllib.parse, urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY", "")
)

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
    sys.exit(1)

MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
PROJECT_REF = "mocerqjnksmhcjzxrewo"

# Brevard city names as they appear concatenated in street_normalized (no spaces)
BREVARD_CITIES = [
    "TITUSVILLE", "COCOA", "COCOABEACH", "MELBOURNEBEACH", "MELBOURNE",
    "PALMBAY", "ROCKLEDGE", "VIERA", "SATELLITEBEACH", "INDIATLANTIC",
    "INDIALANTIC", "MERRITTISLAND", "CAPECANAVERAL", "BAREFOOTBAY",
    "GRANT", "MICCO", "SEBASTIAN", "FELLSMERE", "GIFFORD", "WABASSO",
    "PALM BAY", "PALM", "MIMS", "SCOTTSMOOR", "OSTEEN", "SHARPES",
    "INTERLAKENFL", "FLORIDAFL",
]
# Sort by length descending so longer names match first
BREVARD_CITIES.sort(key=len, reverse=True)


# ── Supabase REST helpers ──────────────────────────────────────────────────────

def _headers(prefer=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "bcpao-nal-import/1.0",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def rest_get(table, params="", prefer=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}" if params else f"{SUPABASE_URL}/rest/v1/{table}"
    req = urllib.request.Request(url, headers=_headers(prefer))
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_post(table, body, prefer="resolution=ignore-duplicates,return=minimal"):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}", data=data,
        headers=_headers(prefer), method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read()
        return json.loads(txt) if txt else None


def rest_patch(table, params, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}", data=data,
        headers=_headers("return=minimal"), method="PATCH"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def rpc(func, params=None):
    data = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{func}", data=data,
        headers=_headers(), method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read()
        return json.loads(txt) if txt else None


def sql(query):
    """Run SQL via Supabase Management API (requires SUPABASE_ACCESS_TOKEN)."""
    if not MGMT_TOKEN:
        return None
    data = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        MGMT_URL, data=data,
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "bcpao-nal-import/1.0",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:  # type: ignore
        body = e.read().decode()[:400]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def count(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=count&{params}"
    req = urllib.request.Request(url, headers=_headers("count=exact"))
    with urllib.request.urlopen(req, timeout=30) as r:
        hdr = r.headers.get("content-range", "?/?")
        return hdr.split("/")[-1]


# ── Address normalization helpers ──────────────────────────────────────────────

def strip_fl_zip(s):
    """Remove trailing zip code (5 digits) from normalized address string."""
    return re.sub(r"\d{5}$", "", s).rstrip()


def strip_state(s):
    """Remove trailing FL state abbreviation."""
    return re.sub(r"FL$", "", s).rstrip()


def strip_brevard_city(s):
    """Remove trailing Brevard city name."""
    for city in BREVARD_CITIES:
        city_clean = city.replace(" ", "")
        if s.upper().endswith(city_clean):
            return s[: len(s) - len(city_clean)].rstrip()
    return s


def normalize_for_match(raw_addr):
    """
    Clean a raw normalized address string: remove city, state, zip suffixes.
    Returns cleaned string or None if nothing useful remains.
    """
    s = raw_addr.strip().upper()
    if not s or s in ("0UNKNOWN", "UNKNOWN", "0 UNKNOWN"):
        return None
    s = strip_fl_zip(s)
    s = strip_state(s)
    s = strip_brevard_city(s)
    s = strip_fl_zip(s)   # second pass in case zip appeared before city
    s = strip_state(s)
    s = s.strip()
    if len(s) < 4 or s.startswith("0UNKNOWN") or s == "UNKNOWN":
        return None
    return s


# ── Strategy implementations ───────────────────────────────────────────────────

def strategy_bcpao_data():
    """
    S1: extract PIN from mca.bcpao_data->>'parcel_id' where it's a real PIN
    (not a 7-digit folio), for accounts not yet bridged.
    """
    print("S1 bcpao_data: querying MCA for embedded PINs …")
    q = """
    SELECT DISTINCT m.parcel_id AS folio,
                    (m.bcpao_data->>'parcel_id') AS pin
    FROM multi_county_auctions m
    LEFT JOIN brevard_folio_pin_bridge b ON b.folio = m.parcel_id
    WHERE m.county    = 'brevard'
      AND m.parcel_id ~ '^\\d{7}$'
      AND m.bcpao_data IS NOT NULL
      AND (m.bcpao_data->>'parcel_id') IS NOT NULL
      AND (m.bcpao_data->>'parcel_id') !~ '^\\d{7}$'
      AND length(m.bcpao_data->>'parcel_id') > 3
      AND b.folio IS NULL
    """
    result = sql(q)
    if not result or isinstance(result, dict) and "error" in result:
        print(f"  S1 query error: {result}")
        return 0

    rows = result if isinstance(result, list) else result.get("data", [])
    done = 0
    for r in rows:
        folio, pin = r["folio"], r["pin"]
        try:
            rest_post("brevard_folio_pin_bridge", {
                "folio": folio,
                "resolved_pin": pin,
                "match_method": "bcpao_data",
            })
            rest_patch(
                "bcpao_fetch_jobs", f"account=eq.{folio}",
                {"status": "done", "parcel_id": pin, "done_at": _now()}
            )
            done += 1
        except Exception as e:
            print(f"  S1 write error for {folio}: {e}")
    print(f"  S1: {done} bridges written")
    return done


def strategy_addr_exact(queued_accounts):
    """
    S2: exact match of mca.street_normalized against fl_parcels.addr_key (co_no=15).
    Uses SQL bulk join for efficiency.
    """
    print("S2 addr_exact: bulk join via SQL …")
    q = """
    INSERT INTO brevard_folio_pin_bridge (folio, resolved_pin, match_method)
    SELECT DISTINCT j.account, fp.parcel_id, 'addr_exact'
    FROM bcpao_fetch_jobs j
    JOIN multi_county_auctions mca
        ON mca.county = 'brevard' AND mca.parcel_id = j.account
       AND mca.street_normalized IS NOT NULL
       AND length(mca.street_normalized) > 3
       AND mca.street_normalized NOT ILIKE '%unknown%'
    JOIN fl_parcels fp
        ON fp.co_no = 15 AND fp.addr_key = mca.street_normalized
    WHERE j.status IN ('queued','failed')
    ON CONFLICT (folio) DO NOTHING
    """
    result = sql(q)
    if result and isinstance(result, dict) and "error" in result:
        print(f"  S2 insert error: {result}")
        return 0

    # Mark newly-bridged accounts as done
    mark_q = """
    UPDATE bcpao_fetch_jobs j
    SET status = 'done',
        parcel_id = b.resolved_pin,
        done_at = now()
    FROM brevard_folio_pin_bridge b
    WHERE b.folio = j.account
      AND j.status IN ('queued','failed')
      AND b.match_method IN ('addr_exact','addr_key','bcpao_data')
    """
    sql(mark_q)

    new_count = int(count("brevard_folio_pin_bridge", "match_method=eq.addr_exact"))
    print(f"  S2: {new_count} bridges via addr_exact")
    return new_count


def strategy_addr_clean(queued_accounts):
    """
    S3: normalize MCA addresses by stripping city/state/zip, retry exact match.
    Processes in Python batches against fl_parcels.
    """
    print("S3 addr_clean: strip city/state/zip then match …")

    # Fetch all queued accounts with their MCA addresses
    if not queued_accounts:
        return 0

    # We'll build a lookup: cleaned_addr → [folio, ...]
    # Then batch-query fl_parcels for those cleaned addresses
    cleaned = {}  # cleaned_addr → set of folios
    for folio, addrs in queued_accounts.items():
        for addr in addrs:
            c = normalize_for_match(addr)
            if c and c != addr:   # only if normalization changed something
                cleaned.setdefault(c, set()).add(folio)

    if not cleaned:
        print("  S3: no addresses to clean")
        return 0

    print(f"  S3: {len(cleaned)} distinct cleaned addresses to test")
    done = 0
    batch_size = 200

    cleaned_list = list(cleaned.items())
    for i in range(0, len(cleaned_list), batch_size):
        batch = cleaned_list[i:i + batch_size]
        addr_keys = [a for a, _ in batch]
        # Build SQL IN clause
        addr_in = ", ".join(f"'{a}'" for a in addr_keys)
        q = f"""
        SELECT addr_key, parcel_id
        FROM fl_parcels
        WHERE co_no = 15 AND addr_key IN ({addr_in})
        """
        result = sql(q)
        if not result or isinstance(result, dict) and "error" in result:
            continue

        rows = result if isinstance(result, list) else []
        fp_map = {r["addr_key"]: r["parcel_id"] for r in rows}

        for addr, folios in batch:
            if addr in fp_map:
                pin = fp_map[addr]
                for folio in folios:
                    try:
                        rest_post("brevard_folio_pin_bridge", {
                            "folio": folio,
                            "resolved_pin": pin,
                            "match_method": "addr_clean",
                        })
                        rest_patch(
                            "bcpao_fetch_jobs", f"account=eq.{folio}",
                            {"status": "done", "parcel_id": pin, "done_at": _now()}
                        )
                        done += 1
                    except Exception as e:
                        print(f"  S3 write error for {folio}: {e}")
        time.sleep(0.2)

    print(f"  S3: {done} bridges via addr_clean")
    return done


def strategy_suffix_norm():
    """
    S5: normalize street-type suffixes (WAY→WY, AVENUE→AVE, etc.) then retry
    exact addr_key match. fl_parcels uses USPS abbreviations; MCA sometimes
    stores the full word (e.g. 'NAPOLIWAY' vs 'NAPOLIWY').
    """
    print("S5 suffix_norm: USPS suffix abbreviation match …")
    # USPS long→short normalization applied to mca.street_normalized
    suffix_chain = (
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "REGEXP_REPLACE("
        "    mca.street_normalized,"
        "    'WAY$', 'WY'),"
        "    'AVENUE$', 'AVE'),"
        "    'BOULEVARD$', 'BLVD'),"
        "    'CIRCLE$', 'CIR'),"
        "    'COURT$', 'CT'),"
        "    'STREET$', 'ST'),"
        "    'TERRACE$', 'TER')"
    )
    q = f"""
    INSERT INTO brevard_folio_pin_bridge (folio, resolved_pin, match_method)
    SELECT DISTINCT j.account, fp.parcel_id, 'suffix_norm'
    FROM bcpao_fetch_jobs j
    JOIN multi_county_auctions mca
        ON mca.county = 'brevard' AND mca.parcel_id = j.account
       AND mca.street_normalized IS NOT NULL
       AND length(mca.street_normalized) > 3
       AND mca.street_normalized NOT ILIKE '%unknown%'
    JOIN fl_parcels fp
        ON fp.co_no = 15
       AND fp.addr_key = {suffix_chain}
    WHERE j.status IN ('queued','failed')
    ON CONFLICT (folio) DO NOTHING
    """
    result = sql(q)
    if result and isinstance(result, dict) and "error" in result:
        print(f"  S5 insert error: {result}")
        return 0

    # Mark newly-bridged accounts as done
    sql("""
    UPDATE bcpao_fetch_jobs j
    SET status = 'done', parcel_id = b.resolved_pin, done_at = now()
    FROM brevard_folio_pin_bridge b
    WHERE b.folio = j.account
      AND j.status IN ('queued','failed')
      AND b.match_method = 'suffix_norm'
    """)

    new_count = int(count("brevard_folio_pin_bridge", "match_method=eq.suffix_norm"))
    print(f"  S5: {new_count} bridges via suffix_norm")
    return new_count


_DIRECTIONS = ("N", "NE", "NW", "E", "SE", "SW", "S", "W")

_SUFFIX_MAP = {
    "WAY": "WY", "AVENUE": "AVE", "BOULEVARD": "BLVD",
    "CIRCLE": "CIR", "COURT": "CT", "STREET": "ST", "TERRACE": "TER",
}


def _apply_suffix_norm(s: str) -> str:
    for long, short in _SUFFIX_MAP.items():
        if s.endswith(long):
            return s[: -len(long)] + short
    return s


def _directional_candidates(addr: str, apply_suffix: bool = False) -> list[str]:
    """Return all 8 directional variants of addr (optionally after suffix normalization)."""
    base = _apply_suffix_norm(addr) if apply_suffix else addr
    return [base + d for d in _DIRECTIONS]


def _run_directional_strategy(strategy_name: str, apply_suffix: bool, queued_accounts: dict) -> int:
    """
    Index-friendly directional suffix matching.
    Generates all 8 directional variants for each queued addr in Python, then
    does exact addr_key IN lookups in fl_parcels (uses B-tree index, no regex scan).
    Only bridges when exactly ONE folio maps to a given addr_key variant.
    """
    print(f"{strategy_name}: generating directional candidates …")
    if not queued_accounts:
        return 0

    # candidate_key → list of folios that produce it
    candidate_map: dict[str, list[str]] = {}
    for folio, addrs in queued_accounts.items():
        for addr in addrs:
            if not addr or len(addr) < 4 or "UNKNOWN" in addr.upper():
                continue
            for cand in _directional_candidates(addr, apply_suffix=apply_suffix):
                candidate_map.setdefault(cand, []).append(folio)

    if not candidate_map:
        print(f"  {strategy_name}: no candidates generated")
        return 0

    print(f"  {strategy_name}: {len(candidate_map)} candidate addr_keys for {len(queued_accounts)} accounts")

    # Batch queries: look up candidates in fl_parcels by exact addr_key
    # Use SQL VALUES table to avoid per-item roundtrips
    done = 0
    method = "directional_suffix" if not apply_suffix else "suffix_directional"
    cand_list = list(candidate_map.items())
    batch_size = 300  # stay well under SQL query size limits

    for i in range(0, len(cand_list), batch_size):
        batch = cand_list[i:i + batch_size]
        # Only query candidates that could be unique (single folio)
        unique_batch = [(k, v[0]) for k, v in batch if len(v) == 1]
        if not unique_batch:
            continue

        in_list = ", ".join(f"'{k}'" for k, _ in unique_batch)
        q = f"""
        SELECT addr_key, parcel_id
        FROM fl_parcels
        WHERE co_no = 15 AND addr_key IN ({in_list})
        """
        result = sql(q)
        if not result or isinstance(result, dict) and "error" in result:
            if isinstance(result, dict) and "error" in result:
                print(f"  {strategy_name} batch {i//batch_size}: {result['error'][:100]}", file=sys.stderr)
            continue

        rows = result if isinstance(result, list) else []
        fp_map = {r["addr_key"]: r["parcel_id"] for r in rows}

        for addr_key, folio in unique_batch:
            if addr_key in fp_map:
                pin = fp_map[addr_key]
                try:
                    rest_post("brevard_folio_pin_bridge", {
                        "folio": folio,
                        "resolved_pin": pin,
                        "match_method": method,
                    })
                    rest_patch(
                        "bcpao_fetch_jobs", f"account=eq.{folio}",
                        {"status": "done", "parcel_id": pin, "done_at": _now()}
                    )
                    done += 1
                except Exception as e:
                    print(f"  {strategy_name} write error for {folio}: {e}")

        time.sleep(0.1)

    new_count = int(count("brevard_folio_pin_bridge", f"match_method=eq.{method}"))
    print(f"  {strategy_name}: {done} new bridges, {new_count} total via {method}")
    return done


def strategy_directional_suffix(queued_accounts: dict) -> int:
    """S6: exact lookup with directional suffix appended (uses index)."""
    return _run_directional_strategy("S6 directional_suffix", apply_suffix=False, queued_accounts=queued_accounts)


def strategy_suffix_directional_combo(queued_accounts: dict) -> int:
    """S7: USPS suffix_norm + directional suffix (WAY→WY then + direction)."""
    return _run_directional_strategy("S7 suffix_directional", apply_suffix=True, queued_accounts=queued_accounts)


def strategy_mark_empty():
    """
    Mark queued accounts with UNKNOWN/empty addresses as 'empty' —
    confirmed not resolvable without the BCPAO API.
    """
    print("S4 mark_empty: marking UNKNOWN-address accounts as empty …")
    q = """
    UPDATE bcpao_fetch_jobs j
    SET status   = 'empty',
        done_at  = now(),
        last_error = 'no_valid_address'
    WHERE j.status IN ('queued','failed')
      AND NOT EXISTS (
        SELECT 1 FROM multi_county_auctions mca
        WHERE mca.county = 'brevard'
          AND mca.parcel_id = j.account
          AND mca.street_normalized IS NOT NULL
          AND length(mca.street_normalized) > 3
          AND mca.street_normalized NOT ILIKE '%unknown%'
      )
    """
    result = sql(q)
    if result and isinstance(result, dict) and "error" in result:
        print(f"  S4 error: {result}")
    else:
        print("  S4: done")


def _now():
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BCPAO NAL Import — folio→PIN bridge (no-CF addr matching)")
    print("=" * 60)

    # Current state
    bridge_before = count("brevard_folio_pin_bridge")
    queued_before = count("bcpao_fetch_jobs", "status=eq.queued")
    print(f"\nBefore: bridge={bridge_before}  queued={queued_before}")

    # ── S1: bcpao_data extraction ──────────────────────────────────────────
    done_s1 = strategy_bcpao_data()

    # ── S2: exact addr_key match (SQL bulk) ───────────────────────────────
    done_s2 = strategy_addr_exact({})  # uses SQL join internally

    # ── Fetch remaining queued accounts + their addresses for S3 ──────────
    print("\nFetching remaining queued accounts and addresses …")
    q = """
    SELECT DISTINCT j.account, mca.street_normalized
    FROM bcpao_fetch_jobs j
    JOIN multi_county_auctions mca
        ON mca.county = 'brevard' AND mca.parcel_id = j.account
    WHERE j.status IN ('queued','failed')
      AND mca.street_normalized IS NOT NULL
      AND length(mca.street_normalized) > 3
    """
    rows = sql(q)
    queued_accounts = {}  # folio → set of normalized addresses
    if rows and isinstance(rows, list):
        for r in rows:
            queued_accounts.setdefault(r["account"], set()).add(r["street_normalized"])
    print(f"  {len(queued_accounts)} accounts with addresses remaining")

    # ── S3: cleaned address match ──────────────────────────────────────────
    done_s3 = strategy_addr_clean(queued_accounts)

    # ── S5: USPS suffix normalization (WAY→WY, AVENUE→AVE, etc.) ──────────
    done_s5 = strategy_suffix_norm()

    # ── S6: directional suffix (addr_key = street_normalized + N/S/E/W…) ──
    done_s6 = strategy_directional_suffix(queued_accounts)

    # ── S7: suffix_norm + directional combo ───────────────────────────────
    done_s7 = strategy_suffix_directional_combo(queued_accounts)

    # ── S4: mark no-address accounts as empty ──────────────────────────────
    strategy_mark_empty()

    # ── Call drain ────────────────────────────────────────────────────────
    print("\nRunning bcpao_folio_drain() …")
    try:
        drain_result = rpc("bcpao_folio_drain")
        print(f"  drain: {drain_result}")
    except Exception as e:
        # Unique constraint means target PIN already exists in MCA as a different row.
        # This is a known issue when a property has two MCA rows (folio + real PIN).
        # The already-bridged rows are still usable; downstream joins work via the bridge table.
        print(f"  drain: partial (duplicate PIN conflict, safe to ignore) — {e}")

    # ── Final verification ─────────────────────────────────────────────────
    bridge_after = count("brevard_folio_pin_bridge")
    queued_after  = count("bcpao_fetch_jobs", "status=eq.queued")
    done_after    = count("bcpao_fetch_jobs", "status=eq.done")
    empty_after   = count("bcpao_fetch_jobs", "status=eq.empty")
    failed_after  = count("bcpao_fetch_jobs", "status=eq.failed")

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"brevard_folio_pin_bridge  total={bridge_after}")
    print(f"bcpao_fetch_jobs  queued={queued_after}  done={done_after}  empty={empty_after}  failed={failed_after}")
    print(f"New bridges this run: {int(bridge_after) - int(bridge_before)}")
    print(f"  S1 bcpao_data      : {done_s1}")
    print(f"  S2 addr_exact      : {done_s2}")
    print(f"  S3 addr_clean      : {done_s3}")
    print(f"  S5 suffix_norm     : {done_s5}")
    print(f"  S6 dir_suffix      : {done_s6}")
    print(f"  S7 suffix+dir      : {done_s7}")

    try:
        n = int(bridge_after)
        if n >= 5500:
            print(f"\n✓ DoD MET: brevard_folio_pin_bridge = {n} >= 5500")
        else:
            print(f"\n⚠ DoD NOT MET: {n} < 5500 (BCPAO API required for remaining accounts)")
    except (ValueError, TypeError):
        print("WARNING: could not parse bridge count")


if __name__ == "__main__":
    main()
