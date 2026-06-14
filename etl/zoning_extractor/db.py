"""
Supabase access layer. Reads the source map and the real assigned zone codes,
writes ONLY to zoning_codes_staging (never to zoning_codes — the human gate sits
between staging and the cert table).
"""
from typing import Optional
from supabase import create_client, Client
import config


def client() -> Client:
    if not (config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY):
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def load_jurisdictions(db: Client, county: str, only: Optional[str] = None) -> list[dict]:
    """
    Returns source-map rows joined to their codes_jurisdiction (the naming used in
    zoning_codes / staging), ordered by priority. County-agnostic: filters by county.
    """
    smap = db.table("zoning_source_map").select("*").order("priority").execute().data
    xwalk = db.table("zoning_jurisdiction_xwalk").select("*").execute().data
    codes_name = {x["assignment_jurisdiction"]: x["codes_jurisdiction"] for x in xwalk}
    counties = {x["assignment_jurisdiction"]: x.get("county", "Brevard") for x in xwalk}

    rows = []
    for r in smap:
        aj = r["assignment_jurisdiction"]
        if counties.get(aj, "Brevard").lower() != county.lower():
            continue
        if only and aj != only:
            continue
        r["codes_jurisdiction"] = codes_name.get(aj, aj)
        rows.append(r)
    return rows


def target_codes(db: Client, county: str, assignment_jurisdiction: str) -> list[str]:
    """
    Distinct zone codes ACTUALLY assigned to parcels in this jurisdiction
    (so we only extract codes that have inventory), placeholders removed.
    """
    res = (
        db.table("zoning_assignments")
        .select("zone_code")
        .ilike("county", f"{county}%")
        .eq("jurisdiction", assignment_jurisdiction)
        .execute()
    )
    seen, out = set(), []
    for row in res.data:
        c = (row.get("zone_code") or "").strip()
        if not c or config.PLACEHOLDER_CODE_RE.match(c):
            continue
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def stage(db: Client, rows: list[dict]) -> int:
    if not rows:
        return 0
    db.table("zoning_codes_staging").upsert(
        rows, on_conflict="jurisdiction,zoning_code"
    ).execute()
    return len(rows)
