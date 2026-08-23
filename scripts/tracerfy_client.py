#!/usr/bin/env python3
"""SummitLeads Sprint 2 — Tracerfy skip-trace client.

STATUS: UNTESTED this session. TRACERFY_API_KEY was not present in this
session's environment (confirmed: `env | grep -i tracer` returned nothing,
despite the secret existing in the repo since 2026-08-23 ~13:15 UTC — same
cc-runner-ghonly.yml wiring gap as Bright Data, fixed in the same commit
as this file). No prior session has ever called tracerfy.com from this
repo; the endpoint/auth contract below is transcribed from the issue
comments (Ariel's own account-dashboard verification), not independently
confirmed by a live call from this codebase. Treat the first real
invocation as a validation call: run it against ONE known buyer first,
print the raw response shape, and confirm it matches the field names
assumed in _parse_trace_response() before trusting it in a batch.

Auth: Bearer TRACERFY_API_KEY. Base: https://tracerfy.com/v1/api/
Rate limits (per issue comments, pace under all of these):
  - batch trace:      10 requests / 5 min
  - instant lookups:  500 requests / min (shared across lookup types)
  - DNC scrub:        10 requests / 5 min
  - queue fetch:      1 request / 20 sec

CRITICAL lesson already learned in chat this session (do not re-discover):
property-owner lookup (find_owner=true) returns the FORECLOSED FORMER
OWNER on a fresh sale, not the auction buyer -- deed records lag. NEVER
attach a find_owner result as a buyer's contact. Use enhanced trace
(name + address) against the BUYER's own prior-deed mailing address
(fl_parcels.own_addr1 from an earlier deed where this buyer is the owner
of record) -- documented 88% hit rate (23/26) using this method, vs a
23% hit rate (3/9) guessing at the just-purchased property's address.

This module never re-purchases: main() takes leads that do NOT already
have contact_phone set (SSOT-first is the caller's job, e.g. only call
this for leads lacking a phone).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone

TRACERFY_BASE = "https://tracerfy.com/v1/api/"
TRACERFY_KEY = os.environ.get("TRACERFY_API_KEY", "")

ENHANCED_COST_CENTS = 1500  # 15 credits, credit=~1 cent per issue comment; verify against real invoice
DNC_COST_CENTS = 0  # cost model for DNC scrub not documented in issue comments -- leave 0 + note, never guess


class RateLimiter:
    """Sliding-window limiter: max `count` calls per `window` seconds."""

    def __init__(self, count: int, window: float):
        self.count = count
        self.window = window
        self._calls: deque[float] = deque()

    def wait(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] > self.window:
            self._calls.popleft()
        if len(self._calls) >= self.count:
            sleep_for = self.window - (now - self._calls[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._calls.append(time.monotonic())


_enhanced_limiter = RateLimiter(10, 300)   # 10 / 5min
_instant_limiter = RateLimiter(400, 60)    # under the 500/min shared ceiling
_dnc_limiter = RateLimiter(10, 300)        # 10 / 5min
_queue_limiter = RateLimiter(1, 20)        # 1 / 20s


def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {tag}: {msg}", flush=True)


def _request(path: str, payload: dict, limiter: RateLimiter) -> dict | None:
    if not TRACERFY_KEY:
        log("TRACERFY_API_KEY absent -- cannot call Tracerfy.", "ERROR")
        return None
    limiter.wait()
    req = urllib.request.Request(
        TRACERFY_BASE + path,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {TRACERFY_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        log(f"Tracerfy {path} HTTP {e.code}: {body}", "ERROR")
        return None
    except Exception as e:
        log(f"Tracerfy {path} failed: {e}", "ERROR")
        return None


def enhanced_trace(name: str, address: str, city: str, state: str, zipcode: str) -> dict | None:
    """Name + known mailing address -> phone/email. The PROVEN method
    (per issue comment: trace the buyer at THEIR OWN prior address, not the
    address they just bought). Field names below (`first_name`/`last_name`
    split, `address1`) are the shape documented in the issue comment set;
    UNVERIFIED against a live response this session -- confirm on first
    real call before trusting downstream.
    """
    parts = name.strip().split(" ", 1)
    first, last = (parts[0], parts[1]) if len(parts) > 1 else (name, "")
    payload = {
        "first_name": first, "last_name": last,
        "address1": address, "city": city, "state": state, "zip": zipcode,
    }
    return _request("enhanced", payload, _enhanced_limiter)


def dnc_scrub(phone: str) -> dict | None:
    return _request("dnc", {"phone": phone}, _dnc_limiter)


def get_queue_status() -> dict | None:
    return _request("queues/", {}, _queue_limiter)


def _parse_trace_response(resp: dict) -> dict:
    """Best-effort extraction -- UNVERIFIED field names. If Tracerfy's real
    response shape differs, this returns all-null rather than raising, and
    the caller must treat a fully-null result as SKIP_TRACE_PARSE_MISMATCH,
    not as "person has no phone" (BLANK > WRONG)."""
    if not isinstance(resp, dict):
        return {"phone": None, "email": None, "parse_status": "UNEXPECTED_RESPONSE_SHAPE"}
    data = resp.get("data", resp)
    phone = data.get("phone") or data.get("phone_number")
    email = data.get("email") or data.get("email_address")
    if phone is None and email is None:
        return {"phone": None, "email": None, "parse_status": "NO_MATCH_OR_UNPARSED"}
    return {"phone": phone, "email": email, "parse_status": "OK"}


def trace_lead(entity_name: str, mailing_address: str, city: str, state: str, zipcode: str) -> dict:
    """Trace one lead via the enhanced (name+address) method only.
    Never calls find_owner -- see module docstring for why."""
    if not mailing_address:
        return {"phone": None, "email": None, "parse_status": "NO_MAILING_ADDRESS_AVAILABLE", "cost_cents": 0}
    resp = enhanced_trace(entity_name, mailing_address, city, state, zipcode)
    if resp is None:
        return {"phone": None, "email": None, "parse_status": "REQUEST_FAILED", "cost_cents": 0}
    parsed = _parse_trace_response(resp)
    parsed["cost_cents"] = ENHANCED_COST_CENTS
    return parsed


def main() -> int:
    """Manual smoke-test entrypoint: python3 tracerfy_client.py "NAME" "ADDR" "CITY" "ST" "ZIP"
    Prints the raw response so a human/agent can confirm field-name
    assumptions in _parse_trace_response() before any batch run."""
    if len(sys.argv) != 6:
        log("Usage: tracerfy_client.py NAME ADDRESS CITY STATE ZIP (single-lead smoke test only)", "ERROR")
        return 2
    if not TRACERFY_KEY:
        log("TRACERFY_API_KEY absent from environment -- cannot run smoke test.", "ERROR")
        return 2
    name, address, city, state, zipcode = sys.argv[1:6]
    resp = enhanced_trace(name, address, city, state, zipcode)
    log(f"RAW RESPONSE: {json.dumps(resp)}")
    log(f"PARSED: {json.dumps(_parse_trace_response(resp) if resp else {})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
