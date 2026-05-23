#!/usr/bin/env python3
"""
CI V6.5 Artillery Runner
========================

Subcommands:
  checkpoint        Write phase state to ci_v65_phases
  execute           Run the artillery for a given phase (P1_RECON full impl, others stub)
  annotate-dispatch Mark the originating summit_chat_dispatch row as observed

Environment (all required):
  SUPABASE_URL                 e.g. https://mocerqjnksmhcjzxrewo.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    JWT (from GH Actions secrets — never inline)
  DOSSIER_ID                   uuid of ci_v65_dossiers row
  PHASE                        ci_v65_phase enum literal (P1_RECON, etc.)

Honesty Protocol V3 markers (V/U/I/A/UNK) emitted on every artillery finding.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


# ---------- env -------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DOSSIER_ID = os.environ.get("DOSSIER_ID", "")
PHASE = os.environ.get("PHASE", "P1_RECON")

if not SUPABASE_URL or not SERVICE_KEY:
    print("FATAL: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing from env", file=sys.stderr)
    sys.exit(2)

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; BidDeedCI/6.5; +https://biddeed.ai/about)"
)

PER_REQUEST_TIMEOUT_S = 25.0
MAX_LINKS_PER_SIDE = 50


# ---------- supabase helpers ------------------------------------------------
def _post(path: str, payload: Any) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=30.0) as client:
        return client.post(url, headers=HEADERS, json=payload)


def _patch(path: str, payload: Dict[str, Any]) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=30.0) as client:
        return client.patch(url, headers=HEADERS, json=payload)


def _get(path: str) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=30.0) as client:
        return client.get(url, headers=HEADERS)


def _upsert(table: str, payload: Dict[str, Any], on_conflict: str) -> httpx.Response:
    """Upsert via PostgREST: merge-duplicates conflict resolution."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    with httpx.Client(timeout=30.0) as client:
        return client.post(url, headers=headers, json=payload)


# ---------- checkpoint ------------------------------------------------------
def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Append/update a checkpoint row in ci_v65_phases for the active dossier+phase."""
    note = {
        "checkpoint_ts": int(time.time()),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
        "github_workflow": os.environ.get("GITHUB_WORKFLOW", "ci-v65-artillery"),
        "note": args.note or "",
        "mode": os.environ.get("MODE", "canary"),
    }

    # Try update existing running row first
    update_path = (
        f"ci_v65_phases?dossier_id=eq.{DOSSIER_ID}"
        f"&phase=eq.{PHASE}&status=eq.running"
    )
    update_payload: Dict[str, Any] = {"notes": note}
    if args.status in ("success", "passed"):
        update_payload["status"] = "passed"
        update_payload["completed_at"] = "now()"
    elif args.status in ("failure", "failed"):
        update_payload["status"] = "failed"
        update_payload["completed_at"] = "now()"
        update_payload["fail_reason"] = args.note or "workflow failed"

    r = _patch(update_path, update_payload)
    if r.status_code in (200, 204) and r.text and r.text != "[]":
        print(f"checkpoint patched existing phase row: status={args.status}")
        return 0

    # Otherwise insert a new row (initial checkpoint)
    insert_payload = {
        "dossier_id": DOSSIER_ID,
        "phase": PHASE,
        "attempt_number": 1,
        "status": "running" if args.status == "running" else args.status,
        "notes": note,
    }
    r = _post("ci_v65_phases", insert_payload)
    if r.status_code not in (200, 201):
        print(f"FATAL: phase insert failed http={r.status_code} body={r.text[:300]}", file=sys.stderr)
        return 1
    print(f"checkpoint inserted phase row: status={args.status}")
    return 0


# ---------- annotate dispatch ----------------------------------------------
def cmd_annotate_dispatch(args: argparse.Namespace) -> int:
    """Mark the originating summit_chat_dispatch row with the workflow_run_id."""
    if not args.dispatch_id:
        print("dispatch_id empty — skipping annotation", file=sys.stderr)
        return 0
    path = f"summit_chat_dispatch?id=eq.{args.dispatch_id}"
    payload = {
        "workflow_run_id": int(args.workflow_run_id) if args.workflow_run_id else None,
        "workflow_run_url": (
            f"https://github.com/breverdbidder/cli-anything-biddeed/actions/runs/{args.workflow_run_id}"
            if args.workflow_run_id else None
        ),
        "delivery_proof": {
            "runner_note": f"ci-v65-artillery completed with status={args.status}",
            "annotated_by": "ci_v65_runner",
        },
    }
    r = _patch(path, payload)
    if r.status_code not in (200, 204):
        print(f"WARN: dispatch annotation failed http={r.status_code} body={r.text[:300]}", file=sys.stderr)
        return 0  # non-fatal
    print(f"dispatch row {args.dispatch_id} annotated")
    return 0


# ---------- execute ---------------------------------------------------------
def cmd_execute(args: argparse.Namespace) -> int:
    """Dispatch to phase handler based on mode + phase."""
    mode = (args.mode or os.environ.get("MODE", "canary")).lower()
    phase = (args.phase or PHASE).upper()

    if mode == "canary":
        return _run_canary(phase)

    handlers = {
        "P1_RECON": _run_p1_recon,
        "P2_TECH_FOOTPRINT": _run_p2_tech_footprint_stub,
        "P5_API_CAPTURE": _run_p5_api_capture_stub,
    }
    fn = handlers.get(phase)
    if not fn:
        print(f"phase {phase} not yet implemented; falling back to canary", file=sys.stderr)
        return _run_canary(phase)

    return fn(args)


def _run_canary(phase: str) -> int:
    """Synthetic V-event proving round-trip dispatch path."""
    event_payload = {
        "dossier_id": DOSSIER_ID,
        "signal_kind": "other",
        "source": "ci_v65_runner_canary",
        "source_url": "https://github.com/breverdbidder/cli-anything-biddeed/actions",
        "payload": {
            "honesty_marker": "V",
            "phase": phase,
            "mode": "canary",
            "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
            "finding": "ci-v65-artillery.yml round-trip proven — dispatch path is alive",
        },
        "triggers_phases": [phase],
    }
    r = _post("ci_v65_event_log", event_payload)
    if r.status_code not in (200, 201):
        print(f"FATAL: event_log insert failed http={r.status_code} body={r.text[:300]}", file=sys.stderr)
        return 1
    print(f"canary execute complete for phase={phase} dossier={DOSSIER_ID}")
    return 0


# ---------- P1_RECON full implementation -----------------------------------
def _fetch_dossier(dossier_id: str) -> Optional[Dict[str, Any]]:
    r = _get(f"ci_v65_dossiers?id=eq.{dossier_id}&select=*")
    if r.status_code != 200:
        print(f"dossier fetch http={r.status_code} body={r.text[:200]}", file=sys.stderr)
        return None
    data = r.json()
    return data[0] if data else None


def _classify_link(link_url: str, dossier_domain: str) -> str:
    """Internal if link host matches dossier domain (or is a subdomain of it)."""
    try:
        host = urlparse(link_url).netloc.lower()
        if not host:
            return "internal"  # relative link
        dossier_domain = (dossier_domain or "").lower().lstrip("www.")
        if not dossier_domain:
            return "external"
        return "internal" if (host == dossier_domain or host.endswith("." + dossier_domain)) else "external"
    except Exception:
        return "external"


def _fetch_and_parse(url: str, dossier_domain: str) -> Dict[str, Any]:
    """Fetch URL via httpx, parse with BeautifulSoup. Returns ci_v65_pages row payload."""
    started = time.time()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    try:
        with httpx.Client(
            timeout=PER_REQUEST_TIMEOUT_S,
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = client.get(url)
        load_ms = int((time.time() - started) * 1000)

        page: Dict[str, Any] = {
            "url": url,
            "http_status": resp.status_code,
            "load_time_ms": load_ms,
            "is_authenticated": False,
            "honesty_marker": "V" if 200 <= resp.status_code < 300 else "A",
            "console_errors": [],
        }

        if resp.status_code < 200 or resp.status_code >= 300:
            page["page_title"] = f"HTTP {resp.status_code}"
            page["word_count"] = 0
            page["internal_links"] = []
            page["external_links"] = []
            return page

        # Parse only if HTML-ish; otherwise mark UNKNOWN content
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower():
            page["page_title"] = f"non-HTML content-type: {content_type}"
            page["word_count"] = 0
            page["internal_links"] = []
            page["external_links"] = []
            page["honesty_marker"] = "U"
            return page

        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("title")
        page["page_title"] = (title_tag.get_text(strip=True)[:500] if title_tag else None)

        text = soup.get_text(separator=" ", strip=True)
        page["word_count"] = len(text.split())

        internal: List[Dict[str, str]] = []
        external: List[Dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
                continue
            try:
                abs_url = urljoin(url, href)
            except Exception:
                continue
            link_text = a.get_text(strip=True)[:200]
            entry = {"url": abs_url, "text": link_text}
            if _classify_link(abs_url, dossier_domain) == "internal":
                internal.append(entry)
            else:
                external.append(entry)

        page["internal_links"] = internal[:MAX_LINKS_PER_SIDE]
        page["external_links"] = external[:MAX_LINKS_PER_SIDE]
        return page

    except httpx.TimeoutException:
        return {
            "url": url, "http_status": 0, "load_time_ms": int((time.time() - started) * 1000),
            "is_authenticated": False, "honesty_marker": "A",
            "page_title": "FETCH_ERROR: timeout", "word_count": 0,
            "internal_links": [], "external_links": [], "console_errors": ["httpx_timeout"],
        }
    except Exception as exc:
        return {
            "url": url, "http_status": 0, "load_time_ms": int((time.time() - started) * 1000),
            "is_authenticated": False, "honesty_marker": "A",
            "page_title": f"FETCH_ERROR: {type(exc).__name__}", "word_count": 0,
            "internal_links": [], "external_links": [],
            "console_errors": [f"{type(exc).__name__}: {str(exc)[:200]}"],
        }


def _run_p1_recon(args: argparse.Namespace) -> int:
    """
    P1_RECON: surface intelligence harvest.

    For each (role, url) in dossier.meta.targets:
      - Skip placeholder URLs (TBD, empty)
      - Fetch via httpx with browser-like UA, follow redirects
      - Parse title / word_count / links via BeautifulSoup
      - Classify links internal vs external against dossier.primary_domain
      - UPSERT into ci_v65_pages on (dossier_id, url)
    Then log a summary V-event into ci_v65_event_log.

    Honesty markers:
      V — fetched + parsed HTML successfully (2xx HTML)
      A — fetch failed or non-2xx
      U — fetched non-HTML content (PDF, JSON, etc.)
    """
    dossier = _fetch_dossier(DOSSIER_ID)
    if not dossier:
        print(f"FATAL: dossier {DOSSIER_ID} not found", file=sys.stderr)
        return 1

    slug = dossier.get("slug") or "unknown"
    primary_domain = (dossier.get("primary_domain") or "").lstrip("www.")
    meta = dossier.get("meta") or {}
    targets = meta.get("targets") or {}

    if not isinstance(targets, dict) or not targets:
        print(f"P1_RECON: no meta.targets for dossier {slug}; nothing to recon")
        return 0

    print(f"P1_RECON start: dossier={slug} domain={primary_domain} targets={len(targets)}")

    succeeded = 0
    failed = 0
    skipped = 0
    findings: List[Dict[str, Any]] = []

    for role, url in targets.items():
        url = (url or "").strip()
        if not url or url.upper().startswith("TBD"):
            print(f"  SKIP role={role} url={url!r} (placeholder)")
            skipped += 1
            continue

        print(f"  FETCH role={role} url={url}")
        page = _fetch_and_parse(url, primary_domain)
        page["dossier_id"] = DOSSIER_ID
        page["page_kind"] = "marketing_page"
        page["page_slug"] = role
        page["crawled_at"] = "now()"

        r = _upsert("ci_v65_pages", page, "dossier_id,url")
        if r.status_code in (200, 201):
            succeeded += 1
            findings.append({
                "role": role,
                "url": url,
                "http_status": page["http_status"],
                "word_count": page["word_count"],
                "internal_links": len(page["internal_links"]),
                "external_links": len(page["external_links"]),
                "title": page.get("page_title"),
                "honesty_marker": page["honesty_marker"],
            })
            print(
                f"    OK status={page['http_status']} words={page['word_count']} "
                f"int_links={len(page['internal_links'])} ext_links={len(page['external_links'])} "
                f"marker={page['honesty_marker']}"
            )
        else:
            failed += 1
            print(f"    UPSERT_ERR http={r.status_code} body={r.text[:200]}", file=sys.stderr)

    # Summary event
    event = {
        "dossier_id": DOSSIER_ID,
        "signal_kind": "other",
        "source": "ci_v65_runner_p1_recon",
        "source_url": "https://github.com/breverdbidder/cli-anything-biddeed/actions",
        "payload": {
            "honesty_marker": "V" if succeeded > 0 else "A",
            "phase": "P1_RECON",
            "mode": "full",
            "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
            "dossier_slug": slug,
            "primary_domain": primary_domain,
            "targets_total": len(targets),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "findings": findings,
            "finding": f"P1_RECON {slug}: {succeeded}/{len(targets) - skipped} fetched ok, {failed} fetch/upsert errors, {skipped} skipped",
        },
        "triggers_phases": ["P1_RECON", "P2_TECH_FOOTPRINT"],
    }
    r = _post("ci_v65_event_log", event)
    if r.status_code not in (200, 201):
        print(f"WARN: event_log insert failed http={r.status_code} body={r.text[:200]}", file=sys.stderr)

    print(f"P1_RECON complete: {succeeded} ok / {failed} failed / {skipped} skipped")

    # Fail the phase only if every non-skipped target failed
    real_targets = len(targets) - skipped
    if real_targets > 0 and succeeded == 0:
        return 1
    return 0


# ---------- stubs (P2+) -----------------------------------------------------
def _run_p2_tech_footprint_stub(args: argparse.Namespace) -> int:
    print("P2_TECH_FOOTPRINT full-mode stub — implementation pending next sprint")
    return _run_canary("P2_TECH_FOOTPRINT")


def _run_p5_api_capture_stub(args: argparse.Namespace) -> int:
    print("P5_API_CAPTURE full-mode stub — implementation pending next sprint")
    return _run_canary("P5_API_CAPTURE")


# ---------- entrypoint ------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(prog="ci_v65_runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ck = sub.add_parser("checkpoint")
    p_ck.add_argument("--status", default="running")
    p_ck.add_argument("--note", default="")
    p_ck.set_defaults(func=cmd_checkpoint)

    p_ex = sub.add_parser("execute")
    p_ex.add_argument("--phase", default=None)
    p_ex.add_argument("--mode", default=None)
    p_ex.set_defaults(func=cmd_execute)

    p_an = sub.add_parser("annotate-dispatch")
    p_an.add_argument("--dispatch-id", default="")
    p_an.add_argument("--workflow-run-id", default="")
    p_an.add_argument("--status", default="")
    p_an.set_defaults(func=cmd_annotate_dispatch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
