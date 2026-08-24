#!/usr/bin/env python3
"""SummitLeads Sprint 2 — Tracerfy skip-trace client.

STATUS: VERIFIED live 2026-08-24. Endpoint paths and response schema below
are confirmed against https://www.tracerfy.com/skip-tracing-api-documentation/
and a live 200 response (see decision log). Two bugs found and fixed in this
same session, both blocking every prior call attempt:
  1. Cloudflare (error code 1010) silently blocks the default urllib
     User-Agent on tracerfy.com — fixed by setting a real UA on every request.
  2. The endpoint paths guessed from issue comments ("enhanced", "dnc",
     "queues/") were wrong (404/405) — real paths are
     /v1/api/trace/enhanced/lookup/, /v2/api/dnc/scrub/, /v1/api/queue/{id}.

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
TRACERFY_BASE_V2 = "https://tracerfy.com/v2/api/"
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


def _request(path: str, payload: dict | None, limiter: RateLimiter, base: str = TRACERFY_BASE, method: str = "POST") -> dict | None:
    if not TRACERFY_KEY:
        log("TRACERFY_API_KEY absent -- cannot call Tracerfy.", "ERROR")
        return None
    limiter.wait()
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {TRACERFY_KEY}",
            "Content-Type": "application/json",
            # Cloudflare (error 1010) blocks the default urllib UA on tracerfy.com —
            # confirmed live 2026-08-24: identical requests succeed once a
            # non-default User-Agent is set. Same root cause class as the
            # Supabase Management API UA requirement in summitleads_pipeline.py.
            "User-Agent": "summitleads-pipeline/1.0",
        },
        method=method,
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


_NAME_SUFFIXES = {"SR", "JR", "II", "III", "IV", "V", "ESQ"}


def _split_owner_name(name: str) -> tuple[str, str]:
    """FL property-appraiser own_name / auction-winner name convention is
    SURNAME-FIRST -- "DAVIS, RONALD L." or "Sanchez Juan" (last name is
    always the first token, comma or not). Verified live 2026-08-24: naive
    "first token = first name" splitting sent a garbled/reversed name on
    every call against fl_parcels-sourced input (e.g. "DAVIS, RONALD L."
    -> first_name="DAVIS,", last_name="RONALD L.") and silently produced
    hit=false on a request that hits=true once reordered correctly. Do not
    revert to a plain str.split(" ", 1) -- that bug already cost a full
    session's worth of false NO_MATCH results.

    Some rows use the comma as a SUFFIX separator instead of a name
    separator -- "Labelle James,SR" is "Labelle James" (Last First) +
    suffix "SR", not "Labelle James" (last) + "SR" (first). Detect that
    case by checking whether the token after the comma is a known suffix.
    """
    cleaned = name.strip()
    if "," in cleaned:
        before, _, after = cleaned.partition(",")
        before = before.strip()
        after = after.strip()
        after_first_tok = after.split(" ", 1)[0].upper().rstrip(".") if after else ""
        if not after or after_first_tok in _NAME_SUFFIXES:
            parts = before.split(" ", 1)
            return (parts[1], parts[0]) if len(parts) > 1 else ("", before)
        first = after.split(" ", 1)[0]
        return first, before
    parts = cleaned.split(" ", 1)
    if len(parts) > 1:
        return parts[1], parts[0]
    return "", cleaned


def enhanced_trace(name: str, address: str, city: str, state: str, zipcode: str) -> dict | None:
    """Name + known mailing address -> phone/email. The PROVEN method
    (per issue comment: trace the buyer at THEIR OWN prior address, not the
    address they just bought). Endpoint + payload verified live 2026-08-24
    against /v1/api/trace/enhanced/lookup/.
    """
    first, last = _split_owner_name(name)
    payload = {
        "first_name": first, "last_name": last,
        "address": address, "city": city, "state": state, "zip": zipcode,
    }
    return _request("trace/enhanced/lookup/", payload, _enhanced_limiter)


def dnc_scrub(phones: list[str]) -> dict | None:
    return _request("dnc/scrub/", {"phones": phones}, _dnc_limiter, base=TRACERFY_BASE_V2)


def get_queue_status(queue_id: int) -> dict | None:
    """Poll a DNC scrub queue. Verified live 2026-08-24: the plain
    `queue/{id}` path 403s ("You do not have permission to access this
    queue") -- the real, version-independent path is `dnc/queue/{id}`
    (confirmed against tracerfy.com's published docs and a live 200)."""
    return _request(f"dnc/queue/{queue_id}", None, _queue_limiter, method="GET")


def _parse_trace_response(resp: dict) -> dict:
    """Extract best contact from the verified /trace/enhanced/lookup/ schema:
    {hit, persons_count, persons: [{full_name, phones: [{number, rank, dnc}],
    emails: [{email, rank}]}]}. Picks the first person (Tracerfy's own best
    match) and their rank-1 phone/email. If the shape doesn't match what was
    verified live 2026-08-24, returns all-null tagged SKIP_TRACE_PARSE_MISMATCH
    rather than guessing (BLANK > WRONG) -- Tracerfy may still change its API."""
    if not isinstance(resp, dict):
        return {"phone": None, "email": None, "full_name": None, "parse_status": "UNEXPECTED_RESPONSE_SHAPE"}
    if not resp.get("hit"):
        return {"phone": None, "email": None, "full_name": None, "parse_status": "NO_MATCH"}
    persons = resp.get("persons") or []
    if not persons:
        return {"phone": None, "email": None, "full_name": None, "parse_status": "HIT_BUT_NO_PERSONS_SHAPE_MISMATCH"}
    person = persons[0]
    phones = sorted(person.get("phones") or [], key=lambda p: p.get("rank", 999))
    emails = sorted(person.get("emails") or [], key=lambda e: e.get("rank", 999))
    phone = phones[0].get("number") if phones else None
    email = emails[0].get("email") if emails else None
    if phone is None and email is None:
        return {"phone": None, "email": None, "full_name": person.get("full_name"), "parse_status": "HIT_NO_CONTACT_FIELDS"}
    return {"phone": phone, "email": email, "full_name": person.get("full_name"), "parse_status": "OK"}


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
