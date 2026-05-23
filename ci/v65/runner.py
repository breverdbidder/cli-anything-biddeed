#!/usr/bin/env python3
"""
CI V6.5 Artillery Runner
========================

Canary-mode scaffold for the ci-v65-artillery.yml workflow.
Implements three subcommands:

  checkpoint        Write phase state to ci_v65_phases and event_log
  execute           Run the actual artillery for a given phase (P1..P5)
  annotate-dispatch Mark the originating summit_chat_dispatch row as observed

Environment requirements:
  SUPABASE_URL                 e.g. https://mocerqjnksmhcjzxrewo.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    JWT, NEVER inline (read from GH Actions secrets)
  DOSSIER_ID                   uuid of ci_v65_dossiers row
  PHASE                        ci_v65_phase enum literal (P1_RECON, etc.)

Honesty Protocol V3 markers (V/U/I/A/UNK) are emitted on every artillery finding.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

import httpx


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


# ---------- supabase helpers ------------------------------------------------
def _post(path: str, payload: Dict[str, Any]) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=HEADERS, json=payload)
    return resp


def _patch(path: str, payload: Dict[str, Any]) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.patch(url, headers=HEADERS, json=payload)
    return resp


def _rpc(fn: str, args: Dict[str, Any]) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=HEADERS, json=args)
    return resp


# ---------- subcommands -----------------------------------------------------
def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Append a checkpoint row to ci_v65_phases for the active dossier+phase."""
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
    update_payload = {
        "notes": note,
    }
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

    # Otherwise insert a new row (typically on initial checkpoint)
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


def cmd_execute(args: argparse.Namespace) -> int:
    """
    Execute the requested phase.

    CANARY MODE (default for first runs): logs a synthetic finding and exits 0.
    Proves the round-trip from SUMMIT → workflow_dispatch → Hetzner → Supabase write-back.

    FULL MODE: TODO — wires in playwright capture per the SUMMIT package phase brief.
    """
    mode = (args.mode or os.environ.get("MODE", "canary")).lower()
    phase = (args.phase or PHASE).upper()

    if mode == "canary":
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

    # FULL mode dispatch table (stubs to be expanded per CI V6.5 spec)
    handlers = {
        "P1_RECON": _run_p1_recon,
        "P2_TECH_FOOTPRINT": _run_p2_tech_footprint,
        "P5_API_CAPTURE": _run_p5_api_capture,
    }
    fn = handlers.get(phase)
    if not fn:
        print(f"phase {phase} not yet implemented in runner; falling back to canary log", file=sys.stderr)
        return cmd_execute(argparse.Namespace(phase=phase, mode="canary"))

    return fn(args)


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


# ---------- phase stubs (to be expanded) ------------------------------------
def _run_p1_recon(args: argparse.Namespace) -> int:
    """Surface intelligence harvest. Stub — full impl pulls SUMMIT URLs from dossier meta."""
    print("P1_RECON full-mode stub — implementation pending next sprint")
    return 0


def _run_p2_tech_footprint(args: argparse.Namespace) -> int:
    """Playwright + BuiltWith fingerprint sweep. Stub."""
    print("P2_TECH_FOOTPRINT full-mode stub — implementation pending next sprint")
    return 0


def _run_p5_api_capture(args: argparse.Namespace) -> int:
    """Chromium DevTools HAR capture. Stub."""
    print("P5_API_CAPTURE full-mode stub — implementation pending next sprint")
    return 0


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
