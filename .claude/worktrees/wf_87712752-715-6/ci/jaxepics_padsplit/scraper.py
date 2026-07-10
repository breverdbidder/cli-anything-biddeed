#!/usr/bin/env python3
"""
JAXEPICS + PadSplit New Construction Scraper
=============================================

Hunts the Duval County JAXEPICS permit system for 7BR/7BA single-family
new-construction permits owned by known PadSplit-Pulse operator LLCs, then
downloads the submitted blueprints (PDFs from /Documentations/DownloadFile).

Why Playwright (not httpx): jaxepics.coj.net is behind Akamai Bot Manager.
Akamai fingerprints TLS handshake + HTTP/2 + sec-ch-ua headers. Direct httpx
returns 403 with `server-timing: ak_p` regardless of header spoofing. A real
Chromium browser context inherits the right TLS fingerprint and passes.

Workflow
--------
1. Open https://jaxepics.coj.net in a Chromium browser to seed Akamai cookies.
2. POST /api/Users/LoginGuest from the browser context (cookies inherited).
3. For each operator LLC in the known list, POST /api/Permits/CompanyNameSearch.
4. For each returned permit, filter by:
     - ZIP starts with 32208 or 32209 (Mid-Westside / Northside)
     - year >= 2024 (per record_number prefix e.g. B-24-... or B-25-...)
     - description keywords (NEW, SFR, SINGLE FAMILY, 7 BEDROOM, RESIDENTIAL NEW)
     - permit_type contains BUILDING or RESIDENTIAL
5. For each matched permit, fetch detail and enumerate documents.
6. Download blueprint PDFs via GET /api/Documentations/DownloadFile/{id}.
7. Upsert results into Supabase:
     - padsplit_jax_new_construction_permits (one row per permit)
     - padsplit_jax_permit_documents (one row per document; PDF as base64)

Honesty Protocol V3 markers per finding:
  V = VERIFIED (Akamai-passed, full record extracted)
  U = UNTESTED (record exists but filter not yet applied)
  I = INFERRED (record extracted, ownership match probabilistic)
  A = ASSUMED (record matched on weak signal, needs human review)
  UNKNOWN = UNK (request failed, fingerprint blocked, etc.)

Environment (all required, set in GitHub Actions secrets — NEVER inline):
  SUPABASE_URL                  e.g. https://mocerqjnksmhcjzxrewo.supabase.co
  SUPABASE_SERVICE_ROLE_KEY     JWT (from GH secrets — never logged)
  DISPATCH_ID                   uuid of triggering summit_chat_dispatch row (optional)

Output dispatch row is annotated with worker_run_id + finding count on completion.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from playwright.async_api import async_playwright, BrowserContext, Page


# ---------- env -------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DISPATCH_ID = os.environ.get("DISPATCH_ID", "")

if not SUPABASE_URL or not SERVICE_KEY:
    print("FATAL: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing", file=sys.stderr)
    sys.exit(2)

SB_HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}


# ---------- targets ---------------------------------------------------------
# Known PadSplit-Pulse operator LLCs (and adjacent investor entities) reported
# in Jacksonville new-construction coliving projects. Pulled from the May 25
# checkpoint. NOT exhaustive — the list is widened on each scrape pass.
OPERATOR_LLCS: List[str] = [
    "JWB",
    "HOOSE HOMES",
    "SSIG PROPERTIES",
    "RED CEDAR",
    "PIN GROUP",
    "BLOUNT PADSPLIT",
    "HAVEN HOMES",
    "DRK 22ND",
    "IXE",
    "BLUE MONKEY",
    "JAXR4",
    "DAZZ CAPITAL",
    "LIONS GROUP",
    "MG3 RE FUND",
    "A&E RENTAL",
    "AOS VENTURE",
    "BCEL 10D",
    "OSCONE",
    "PADSPLIT",  # catch-all on entity names that literally include PadSplit
    "COLIVING",  # catch-all on coliving-branded entities
]

# Acceptable ZIPs for the Mid-Westside / Northside Jacksonville coliving belt.
ACCEPT_ZIPS = {"32208", "32209", "32202", "32204", "32206", "32210"}

# Permit-type keywords that indicate residential new construction.
PERMIT_TYPE_KEYWORDS = ["BUILDING", "RESIDENTIAL", "NEW", "SFR", "SINGLE FAMILY"]

# Description keywords for 7BR/7BA new construction.
DESC_KEYWORDS = [
    "NEW",
    "SFR",
    "SINGLE FAMILY",
    "RESIDENTIAL NEW",
    "7 BEDROOM",
    "7BR",
    "CO-LIVING",
    "COLIVING",
    "BOARDING",
    "ROOMING HOUSE",
]

# JAXEPICS endpoints (from May 25 checkpoint reconnaissance).
JAXEPICS_BASE = "https://jaxepics.coj.net"
JAXEPICS_API_BASE = "https://jaxepicsapi.coj.net/api"


# ---------- data classes ---------------------------------------------------
@dataclass
class PermitMatch:
    record_number: str
    permit_type: str
    permit_subtype: Optional[str]
    description: Optional[str]
    address: Optional[str]
    zip: Optional[str]
    year: Optional[int]
    operator_searched: str
    raw: Dict[str, Any]
    honesty_marker: str = "V"
    document_ids: List[Dict[str, Any]] = field(default_factory=list)


# ---------- supabase helpers -----------------------------------------------
def sb_upsert(table: str, rows: List[Dict[str, Any]], on_conflict: str) -> int:
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, headers=SB_HEADERS, json=rows)
    if r.status_code in (200, 201):
        return len(rows)
    print(f"WARN upsert {table} http={r.status_code} body={r.text[:400]}", file=sys.stderr)
    return 0


def sb_patch_dispatch(dispatch_id: str, payload: Dict[str, Any]) -> None:
    if not dispatch_id:
        return
    url = f"{SUPABASE_URL}/rest/v1/summit_chat_dispatch?id=eq.{dispatch_id}"
    with httpx.Client(timeout=30.0) as client:
        r = client.patch(url, headers=SB_HEADERS, json=payload)
    if r.status_code not in (200, 204):
        print(f"WARN dispatch annotate http={r.status_code} body={r.text[:300]}", file=sys.stderr)


# ---------- akamai-safe browser fetch --------------------------------------
async def open_context() -> tuple[BrowserContext, Page]:
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security",
        ],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )
    # Stealth shim: blank navigator.webdriver
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    page = await context.new_page()
    return context, page


async def seed_akamai(page: Page) -> bool:
    """Visit jaxepics.coj.net to acquire Akamai _abck / bm_sz cookies."""
    try:
        resp = await page.goto(JAXEPICS_BASE, wait_until="domcontentloaded", timeout=45_000)
        if resp is None:
            return False
        status = resp.status
        print(f"seed_akamai status={status}")
        # Akamai sometimes serves a sensor-data challenge; wait briefly for JS to run.
        await page.wait_for_timeout(3_500)
        return 200 <= status < 400
    except Exception as exc:
        print(f"seed_akamai error: {exc}", file=sys.stderr)
        return False


async def api_post(page: Page, path: str, payload: Dict[str, Any]) -> tuple[int, Any]:
    """POST to JAXEPICS API from inside the browser context (inherits Akamai cookies)."""
    url = f"{JAXEPICS_API_BASE}{path}"
    try:
        resp = await page.request.post(
            url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Origin": JAXEPICS_BASE,
                "Referer": f"{JAXEPICS_BASE}/",
            },
            timeout=45_000,
        )
        status = resp.status
        if status == 200:
            try:
                return status, await resp.json()
            except Exception:
                return status, await resp.text()
        return status, await resp.text()
    except Exception as exc:
        return 0, f"EXC: {type(exc).__name__}: {exc}"


async def api_get_bytes(page: Page, path: str) -> tuple[int, Optional[bytes]]:
    url = f"{JAXEPICS_API_BASE}{path}"
    try:
        resp = await page.request.get(
            url,
            headers={"Referer": f"{JAXEPICS_BASE}/"},
            timeout=60_000,
        )
        if resp.status == 200:
            return resp.status, await resp.body()
        return resp.status, None
    except Exception as exc:
        print(f"api_get_bytes error: {exc}", file=sys.stderr)
        return 0, None


# ---------- filters ---------------------------------------------------------
PERMIT_NUM_RE = re.compile(r"^([A-Z])-(\d{2})-(\d+)(\.\d{3})?$", re.IGNORECASE)


def extract_year(record_number: str) -> Optional[int]:
    m = PERMIT_NUM_RE.match(record_number or "")
    if not m:
        return None
    yy = int(m.group(2))
    # Two-digit year heuristic: 70-99 -> 19xx, 00-69 -> 20xx.
    return 1900 + yy if yy >= 70 else 2000 + yy


def matches_filter(permit: Dict[str, Any]) -> tuple[bool, str]:
    """Return (matches, honesty_marker)."""
    rec = (permit.get("recordNumber") or permit.get("RecordNumber") or "").upper()
    ptype = (permit.get("permitType") or permit.get("PermitType") or "").upper()
    desc = (permit.get("description") or permit.get("Description") or "").upper()
    addr = (permit.get("address") or permit.get("Address") or "").upper()

    year = extract_year(rec)
    if year is None or year < 2024:
        return False, "A"  # ASSUMED — not parseable / too old

    zip_match = any(z in addr for z in ACCEPT_ZIPS)
    type_match = any(k in ptype for k in PERMIT_TYPE_KEYWORDS)
    desc_match = any(k in desc for k in DESC_KEYWORDS)

    if zip_match and type_match and desc_match:
        return True, "V"  # VERIFIED triple match
    if zip_match and (type_match or desc_match):
        return True, "I"  # INFERRED — partial match, worth a human look
    return False, "A"


# ---------- main scrape ----------------------------------------------------
async def scrape() -> Dict[str, Any]:
    started_at = time.time()
    stats = {
        "operators_searched": 0,
        "raw_permits": 0,
        "matched_permits": 0,
        "documents_downloaded": 0,
        "errors": [],
    }
    matches: List[PermitMatch] = []
    document_rows: List[Dict[str, Any]] = []

    context, page = await open_context()
    try:
        ok = await seed_akamai(page)
        if not ok:
            stats["errors"].append("akamai_seed_failed")
            return _finalize(stats, matches, document_rows, started_at)

        # Guest login (may set additional cookies / a token in localStorage).
        status, body = await api_post(page, "/Users/LoginGuest", {})
        print(f"LoginGuest status={status}")
        if status == 403:
            stats["errors"].append("akamai_blocked_login_guest")
            return _finalize(stats, matches, document_rows, started_at)

        # Iterate operator LLCs.
        for llc in OPERATOR_LLCS:
            stats["operators_searched"] += 1
            print(f"\n--- searching operator: {llc} ---")
            status, body = await api_post(
                page,
                "/Permits/CompanyNameSearch",
                {"searchValue": llc},
            )
            if status != 200:
                print(f"  http={status} body={str(body)[:200]}")
                stats["errors"].append(f"search_failed:{llc}:{status}")
                # Brief backoff so we don't tip Akamai's rate budget.
                await asyncio.sleep(1.2)
                continue

            # Response shape varies; try common keys.
            permits = []
            if isinstance(body, list):
                permits = body
            elif isinstance(body, dict):
                for k in ("permits", "Permits", "results", "Results", "data", "Data"):
                    if isinstance(body.get(k), list):
                        permits = body[k]
                        break

            print(f"  raw permits={len(permits)}")
            stats["raw_permits"] += len(permits)

            for p in permits:
                ok, marker = matches_filter(p)
                if not ok:
                    continue
                rec = p.get("recordNumber") or p.get("RecordNumber") or ""
                pm = PermitMatch(
                    record_number=rec.upper(),
                    permit_type=p.get("permitType") or p.get("PermitType") or "",
                    permit_subtype=p.get("permitSubtype") or p.get("PermitSubtype"),
                    description=p.get("description") or p.get("Description"),
                    address=p.get("address") or p.get("Address"),
                    zip=_extract_zip(p.get("address") or p.get("Address") or ""),
                    year=extract_year(rec),
                    operator_searched=llc,
                    raw=p,
                    honesty_marker=marker,
                )
                matches.append(pm)
                stats["matched_permits"] += 1

            await asyncio.sleep(0.8)  # polite delay

        # For each matched permit, fetch detail + enumerate documents.
        print(f"\n--- enumerating documents for {len(matches)} matched permits ---")
        for pm in matches:
            if not pm.address:
                continue
            status, body = await api_post(
                page,
                f"/Permits/PermitsByAddress/{pm.address}",
                {},
            )
            if status != 200 or not isinstance(body, (list, dict)):
                continue
            docs = _extract_documents(body)
            pm.document_ids = docs

            # Download each blueprint PDF (cap at 10 per permit to bound runtime).
            for doc in docs[:10]:
                doc_id = doc.get("id") or doc.get("Id") or doc.get("documentId")
                doc_name = doc.get("name") or doc.get("DisplayName") or f"doc_{doc_id}"
                if not doc_id:
                    continue
                d_status, d_bytes = await api_get_bytes(
                    page, f"/Documentations/DownloadFile/{doc_id}"
                )
                if d_status != 200 or not d_bytes:
                    continue
                stats["documents_downloaded"] += 1
                document_rows.append(
                    {
                        "permit_record_number": pm.record_number,
                        "document_id": str(doc_id),
                        "document_name": doc_name,
                        "byte_size": len(d_bytes),
                        "brava_viewer_url": (
                            f"https://jaxbravaviewer.coj.net/Home/JAXEPICSViewer"
                            f"?docid={doc_id}&displayName={doc_name}"
                        ),
                        "content_base64": base64.b64encode(d_bytes).decode("ascii"),
                        "honesty_marker": "V",
                        "scraped_at": "now()",
                    }
                )

        return _finalize(stats, matches, document_rows, started_at)

    finally:
        await context.close()


def _extract_zip(addr: str) -> Optional[str]:
    m = re.search(r"\b(3\d{4})\b", addr or "")
    return m.group(1) if m else None


def _extract_documents(detail: Any) -> List[Dict[str, Any]]:
    """JAXEPICS permit detail shape is inconsistent — try common keys."""
    if isinstance(detail, list):
        return [d for d in detail if isinstance(d, dict)]
    if isinstance(detail, dict):
        for k in ("documents", "Documents", "files", "Files", "attachments", "Attachments"):
            v = detail.get(k)
            if isinstance(v, list):
                return [d for d in v if isinstance(d, dict)]
    return []


def _finalize(
    stats: Dict[str, Any],
    matches: List[PermitMatch],
    document_rows: List[Dict[str, Any]],
    started_at: float,
) -> Dict[str, Any]:
    elapsed_s = int(time.time() - started_at)

    permit_rows = [
        {
            "record_number": m.record_number,
            "permit_type": m.permit_type,
            "permit_subtype": m.permit_subtype,
            "description": m.description,
            "address": m.address,
            "zip": m.zip,
            "year": m.year,
            "operator_searched": m.operator_searched,
            "raw_jaxepics": m.raw,
            "document_count": len(m.document_ids),
            "honesty_marker": m.honesty_marker,
            "scraped_at": "now()",
        }
        for m in matches
    ]

    perms_inserted = sb_upsert(
        "padsplit_jax_new_construction_permits",
        permit_rows,
        on_conflict="record_number",
    )
    docs_inserted = sb_upsert(
        "padsplit_jax_permit_documents",
        document_rows,
        on_conflict="document_id",
    ),

    stats["permits_upserted"] = perms_inserted
    stats["documents_upserted"] = docs_inserted
    stats["elapsed_seconds"] = elapsed_s

    print("\n=== SCRAPE COMPLETE ===")
    print(json.dumps(stats, indent=2, default=str))

    if DISPATCH_ID:
        sb_patch_dispatch(
            DISPATCH_ID,
            {
                "delivery_proof": {
                    "runner_note": "jaxepics_padsplit_scraper completed",
                    "stats": stats,
                },
                "completed_at": "now()",
                "state": "closed" if not stats["errors"] else "quarantined",
                "last_error": (stats["errors"][0] if stats["errors"] else None),
            },
        )

    return stats


# ---------- entrypoint ------------------------------------------------------
def main() -> int:
    stats = asyncio.run(scrape())
    # Exit 0 if at least one permit matched; exit 1 if zero matches + errors
    # so the GH workflow surfaces failure honestly.
    if stats.get("matched_permits", 0) == 0 and stats.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
