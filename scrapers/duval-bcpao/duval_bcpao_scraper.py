"""
duval_bcpao_scraper.py — Duval County Property Appraiser harvester

Source:        https://paopropertysearch.coj.net/Basic/Detail.aspx?RE={parcel_id_no_dash}
Legal basis:   F.S. 119 (Florida public records — assessed values are public)
Output table:  public.duval_bcpao_assessments
Queue table:   public.duval_bcpao_harvest_queue

Run as a GitHub Actions workflow or directly on Hetzner. Idempotent: ON CONFLICT.
Rate limit: 1.5 req/sec default (gentle on the COJ site).

Usage:
    python duval_bcpao_scraper.py --batch 50 --workers 1 --rate 1.5
    python duval_bcpao_scraper.py --batch 500 --rate 2.0 --priority-max 10  # top-20 only

Environment:
    SUPABASE_URL          (required)
    SUPABASE_SERVICE_ROLE (required — service role, never echoed)
    USER_AGENT_EMAIL      (optional, identifies you to the host)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import socket
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup


# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

BCPAO_DETAIL = "https://paopropertysearch.coj.net/Basic/Detail.aspx?RE={re}"
SEARCH_RESULTS_PATH = "/Basic/Results.aspx"  # redirect target = parcel not found

# ASP.NET WebForms label IDs from paopropertysearch.coj.net (verified 2026-05-26)
# Strategy: prefer Certified (last tax roll, Oct 2025) for VERIFIED honesty;
#           fall back to InProgress (current year) if Certified is missing.
LABEL_IDS_CERTIFIED = {
    "assessed_value":       "ctl00_cphBody_lblAssessedValueA10Certified",
    "just_market_value":    "ctl00_cphBody_lblJustMarketValueCertified",
    "land_value_market":    "ctl00_cphBody_lblLandValueMarketCertified",
    "total_building_value": "ctl00_cphBody_lblBuildingValueCertified",
    "taxable_value":        "ctl00_cphBody_lblTaxableValueCertified",
}
LABEL_IDS_INPROGRESS = {
    "assessed_value":       "ctl00_cphBody_lblAssessedValueA10InProgress",
    "just_market_value":    "ctl00_cphBody_lblJustMarketValueInProgress",
    "land_value_market":    "ctl00_cphBody_lblLandValueMarketInProgress",
    "total_building_value": "ctl00_cphBody_lblBuildingValueInProgress",
    "taxable_value":        "ctl00_cphBody_lblTaxableValueInProgress",
}
LABEL_IDS_STATIC = {
    "property_use":      "ctl00_cphBody_lblPropertyUse",      # "0100 Single Family"
    "total_area":        "ctl00_cphBody_lblTotalArea1",        # GIS sqft
    "num_buildings":     "ctl00_cphBody_lblNumberOfBuildings",
    # Owner / address (label IDs may vary; left in fallback regex)
    "year_built":        "ctl00_cphBody_repeaterBuilding_ctl00_lblYearBuilt",
    "building_sqft":     "ctl00_cphBody_repeaterBuilding_ctl00_lblHeatedArea",
}

# Final-resort regex fallbacks if BCPAO changes IDs
FALLBACK_PATTERNS = [
    ("assessed_value",      r"lblAssessedValueA10Certified\">\s*\$([\d,\.]+)"),
    ("just_market_value",   r"lblJustMarketValueCertified\">\s*\$([\d,\.]+)"),
    ("land_value_market",   r"lblLandValueMarketCertified\">\s*\$([\d,\.]+)"),
    ("total_building_value",r"lblBuildingValueCertified\">\s*\$([\d,\.]+)"),
    ("taxable_value",       r"lblTaxableValueCertified\">\s*\$([\d,\.]+)"),
]


# ──────────────────────────────────────────────────────────────────────────────
# PARSING
# ───────────────────────────────────────────────────────────────────────────────

@dataclass
class BcpaoRecord:
    parcel_id_raw: str
    parcel_id_re: str
    assessed_value: Optional[float] = None
    just_market_value: Optional[float] = None
    total_building_value: Optional[float] = None
    land_value_market: Optional[float] = None
    taxable_value: Optional[float] = None
    property_use_code: Optional[str] = None
    property_use_desc: Optional[str] = None
    year_built: Optional[int] = None
    total_area_sqft: Optional[float] = None
    building_sqft: Optional[float] = None
    current_owner_name: Optional[str] = None
    current_owner_address: Optional[str] = None
    property_address: Optional[str] = None
    source_url: Optional[str] = None
    http_status: Optional[int] = None
    parse_status: str = "pending"
    parse_error: Optional[str] = None
    raw_html_hash: Optional[str] = None
    honesty_marker: str = "VERIFIED"


def _num(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    s = re.sub(r"[^\d.\-]", "", text)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _int(text: Optional[str]) -> Optional[int]:
    n = _num(text)
    return int(n) if n is not None else None


def _split_use_code(text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """'0800 Multi-Family Units 2-9' → ('0800', 'Multi-Family Units 2-9')"""
    if not text:
        return None, None
    m = re.match(r"\s*(\d{3,4})\s+(.+?)\s*$", text)
    if m:
        return m.group(1), m.group(2).strip()
    return None, text.strip()


def parse_bcpao_html(html: str, parcel_id_raw: str, parcel_id_re: str) -> BcpaoRecord:
    rec = BcpaoRecord(
        parcel_id_raw=parcel_id_raw,
        parcel_id_re=parcel_id_re,
        raw_html_hash=hashlib.sha256(html.encode("utf-8", "ignore")).hexdigest()[:16],
    )

    soup = BeautifulSoup(html, "html.parser")

    # Helper: extract label by ID
    def by_id(lid: str) -> Optional[str]:
        el = soup.find(id=lid)
        return el.get_text(strip=True) if el else None

    # ── VALUES: try Certified first, then InProgress as fallback ───────────
    def value_field(field: str) -> Optional[float]:
        v = _num(by_id(LABEL_IDS_CERTIFIED[field]))
        if v is None or v == 0:
            v_ip = _num(by_id(LABEL_IDS_INPROGRESS[field]))
            if v_ip is not None and v_ip > 0:
                return v_ip
        return v

    rec.assessed_value       = value_field("assessed_value")
    rec.just_market_value    = value_field("just_market_value")
    rec.land_value_market    = value_field("land_value_market")
    rec.total_building_value = value_field("total_building_value")
    rec.taxable_value        = value_field("taxable_value")

    # ── STATIC fields ──────────────────────────────────────────────────────
    rec.property_use_code, rec.property_use_desc = _split_use_code(by_id(LABEL_IDS_STATIC["property_use"]))
    rec.total_area_sqft   = _num(by_id(LABEL_IDS_STATIC["total_area"]))
    rec.year_built        = _int(by_id(LABEL_IDS_STATIC["year_built"]))
    rec.building_sqft     = _num(by_id(LABEL_IDS_STATIC["building_sqft"]))

    # ── Owner & address: regex sweep (label IDs vary across page versions) ─
    m = re.search(r'lblPrimaryOwner[^>]*>\s*([^<]+)', html)
    if m: rec.current_owner_name = m.group(1).strip()
    m = re.search(r'lblSiteAddress[^>]*>\s*([^<]+)', html)
    if m: rec.property_address = m.group(1).strip()
    m = re.search(r'lblMailingAddress[^>]*>\s*([^<]+)', html)
    if m: rec.current_owner_address = m.group(1).strip()

    # Final-resort regex if both by-ID and field-fallback failed
    for field, pattern in FALLBACK_PATTERNS:
        if getattr(rec, field) is None:
            m = re.search(pattern, html)
            if m:
                setattr(rec, field, _num(m.group(1)))

    # Diagnose parse quality — 4 core fields must be populated for VERIFIED
    populated = sum(1 for v in [rec.assessed_value, rec.just_market_value,
                                 rec.land_value_market, rec.property_use_code] if v is not None)
    if populated == 4:
        rec.parse_status = "parsed"
    elif populated >= 2:
        rec.parse_status = "partial"
        rec.honesty_marker = "INFERRED"
    else:
        rec.parse_status = "failed"
        rec.parse_error = f"only {populated}/4 core fields extracted"
        rec.honesty_marker = "UNKNOWN"

    return rec


# ──────────────────────────────────────────────────────────────────────────────
# HTTP CLIENT
# ──────────────────────────────────────────────────────────────────────────────

def make_client(timeout: int = 30) -> httpx.Client:
    ua_email = os.environ.get("USER_AGENT_EMAIL", "research@everestcapital.us")
    return httpx.Client(
        headers={
            "User-Agent": f"BidDeed.AI Research Scraper (contact: {ua_email})",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=timeout,
        follow_redirects=True,
    )


def fetch_one(client: httpx.Client, parcel_id_re: str) -> tuple[Optional[str], int, str]:
    url = BCPAO_DETAIL.format(re=parcel_id_re)
    try:
        r = client.get(url)
        final_url = str(r.url)
        # If the site redirected us to Results.aspx?Results=None, parcel doesn't exist
        if SEARCH_RESULTS_PATH in final_url:
            return None, r.status_code, final_url
        return r.text, r.status_code, final_url
    except httpx.HTTPError as e:
        return None, 0, f"http_error: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# SUPABASE REST
# ──────────────────────────────────────────────────────────────────────────────

class Supabase:
    def __init__(self, url: str, service_role: str):
        self._base = url.rstrip("/")
        self._headers = {
            "apikey": service_role,
            "Authorization": f"Bearer {service_role}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._client = httpx.Client(timeout=30)

    def claim_batch(self, batch: int, priority_max: int, claimed_by: str) -> list[dict]:
        """Atomic UPDATE...RETURNING to claim up to `batch` pending rows."""
        sql = f"""
        WITH next AS (
          SELECT parcel_id_raw FROM public.duval_bcpao_harvest_queue
          WHERE status='pending' AND attempts < 3 AND priority <= {priority_max}
          ORDER BY priority, queued_at
          LIMIT {batch}
          FOR UPDATE SKIP LOCKED
        )
        UPDATE public.duval_bcpao_harvest_queue q
        SET status='in_progress',
            claimed_by=%(by)s,
            claimed_at=now(),
            attempts=q.attempts+1,
            last_attempt=now()
        FROM next
        WHERE q.parcel_id_raw=next.parcel_id_raw
        RETURNING q.parcel_id_raw, q.parcel_id_re;
        """
        # Use a simple SELECT through PostgREST RPC fallback if execute_sql unavailable
        # For workflow simplicity, we use the rpc/exec_sql endpoint OR direct PostgREST.
        # Here we use Supabase REST direct upsert pattern instead.
        # NOTE: In production GitHub Actions we use a Postgres connection; this script
        # is designed to be invoked with both options.
        raise NotImplementedError("Use direct psycopg2 path; see main()")

    def upsert_assessment(self, rec: BcpaoRecord) -> int:
        payload = {k: v for k, v in asdict(rec).items() if v is not None}
        payload["scraped_at"] = datetime.now(timezone.utc).isoformat()
        url = f"{self._base}/rest/v1/duval_bcpao_assessments?on_conflict=parcel_id_raw"
        r = self._client.post(url, json=payload, headers={
            **self._headers,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        })
        return r.status_code


# ──────────────────────────────────────────────────────────────────────────────
# DIRECT POSTGRES PATH (preferred — uses pg pool, supports SKIP LOCKED)
# ──────────────────────────────────────────────────────────────────────────────

def run_with_postgres(db_url: str, batch: int, priority_max: int, rate: float, max_iters: int):
    import psycopg
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{int(time.time())}"
    delay = 1.0 / max(rate, 0.1)
    iters = 0

    with psycopg.connect(db_url, autocommit=False) as conn:
        client = make_client()
        while iters < max_iters:
            iters += 1
            # Claim a batch atomically
            with conn.cursor() as cur:
                cur.execute("""
                    WITH next AS (
                      SELECT parcel_id_raw FROM public.duval_bcpao_harvest_queue
                      WHERE status='pending' AND attempts < 3 AND priority <= %s
                      ORDER BY priority, queued_at
                      LIMIT %s
                      FOR UPDATE SKIP LOCKED
                    )
                    UPDATE public.duval_bcpao_harvest_queue q
                    SET status='in_progress',
                        claimed_by=%s,
                        claimed_at=now(),
                        attempts=q.attempts+1,
                        last_attempt=now()
                    FROM next
                    WHERE q.parcel_id_raw=next.parcel_id_raw
                    RETURNING q.parcel_id_raw, q.parcel_id_re;
                """, (priority_max, batch, worker_id))
                claimed = cur.fetchall()
            conn.commit()

            if not claimed:
                print(f"[{worker_id}] no pending rows, exiting.")
                return

            print(f"[{worker_id}] claimed {len(claimed)} parcels")

            for parcel_id_raw, parcel_id_re in claimed:
                html, status, final_url = fetch_one(client, parcel_id_re)
                if html is None and SEARCH_RESULTS_PATH in (final_url or ""):
                    # No record at BCPAO
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE public.duval_bcpao_harvest_queue SET status='no_record', last_error=%s WHERE parcel_id_raw=%s",
                            ("no_record_at_bcpao", parcel_id_raw),
                        )
                        cur.execute(
                            """INSERT INTO public.duval_bcpao_assessments
                               (parcel_id_raw, parcel_id_re, http_status, source_url, parse_status, parse_error, honesty_marker)
                               VALUES (%s, %s, %s, %s, 'no_record', 'no_record_at_bcpao', 'VERIFIED')
                               ON CONFLICT (parcel_id_raw) DO NOTHING""",
                            (parcel_id_raw, parcel_id_re, status, final_url),
                        )
                    conn.commit()
                    time.sleep(delay)
                    continue
                if html is None:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE public.duval_bcpao_harvest_queue SET status='pending', last_error=%s WHERE parcel_id_raw=%s",
                            (f"fetch_failed: status={status} url={final_url[:200]}", parcel_id_raw),
                        )
                    conn.commit()
                    time.sleep(delay)
                    continue

                rec = parse_bcpao_html(html, parcel_id_raw, parcel_id_re)
                rec.http_status = status
                rec.source_url = final_url

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.duval_bcpao_assessments (
                          parcel_id_raw, parcel_id_re,
                          assessed_value, just_market_value, total_building_value,
                          land_value_market, taxable_value,
                          property_use_code, property_use_desc, year_built,
                          total_area_sqft, building_sqft,
                          current_owner_name, current_owner_address, property_address,
                          source_url, http_status, parse_status, parse_error,
                          raw_html_hash, honesty_marker, scraped_at
                        ) VALUES (
                          %(parcel_id_raw)s, %(parcel_id_re)s,
                          %(assessed_value)s, %(just_market_value)s, %(total_building_value)s,
                          %(land_value_market)s, %(taxable_value)s,
                          %(property_use_code)s, %(property_use_desc)s, %(year_built)s,
                          %(total_area_sqft)s, %(building_sqft)s,
                          %(current_owner_name)s, %(current_owner_address)s, %(property_address)s,
                          %(source_url)s, %(http_status)s, %(parse_status)s, %(parse_error)s,
                          %(raw_html_hash)s, %(honesty_marker)s, now()
                        )
                        ON CONFLICT (parcel_id_raw) DO UPDATE SET
                          assessed_value=EXCLUDED.assessed_value,
                          just_market_value=EXCLUDED.just_market_value,
                          total_building_value=EXCLUDED.total_building_value,
                          land_value_market=EXCLUDED.land_value_market,
                          property_use_code=EXCLUDED.property_use_code,
                          property_use_desc=EXCLUDED.property_use_desc,
                          year_built=EXCLUDED.year_built,
                          total_area_sqft=EXCLUDED.total_area_sqft,
                          building_sqft=EXCLUDED.building_sqft,
                          current_owner_name=EXCLUDED.current_owner_name,
                          current_owner_address=EXCLUDED.current_owner_address,
                          property_address=EXCLUDED.property_address,
                          source_url=EXCLUDED.source_url,
                          http_status=EXCLUDED.http_status,
                          parse_status=EXCLUDED.parse_status,
                          parse_error=EXCLUDED.parse_error,
                          raw_html_hash=EXCLUDED.raw_html_hash,
                          honesty_marker=EXCLUDED.honesty_marker,
                          scraped_at=now();
                    """, asdict(rec))
                    cur.execute(
                        "UPDATE public.duval_bcpao_harvest_queue SET status='done' WHERE parcel_id_raw=%s",
                        (parcel_id_raw,),
                    )
                conn.commit()
                print(f"  {parcel_id_raw} → {rec.parse_status} assessed=${rec.assessed_value or 0:.0f} use={rec.property_use_code}")
                time.sleep(delay)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=int, default=50)
    p.add_argument("--priority-max", type=int, default=200, help="Only claim rows with priority <= this")
    p.add_argument("--rate", type=float, default=1.5, help="Requests per second")
    p.add_argument("--max-iters", type=int, default=200, help="Max claim/process cycles before exit")
    args = p.parse_args()

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL env var required (postgres connection string)", file=sys.stderr)
        sys.exit(2)

    print(f"Starting BCPAO scraper | batch={args.batch} priority<={args.priority_max} rate={args.rate}r/s")
    run_with_postgres(db_url, args.batch, args.priority_max, args.rate, args.max_iters)
    print("Done.")


if __name__ == "__main__":
    main()
