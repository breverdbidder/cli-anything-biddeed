#!/usr/bin/env python3
"""Shared helpers for the YouTube publish lane (issue #19788).

DORMANT BY DESIGN: no youtube_client_id / youtube_client_secret /
youtube_oauth_refresh_token secret exists in the vault yet (checked live via
get_vault_secret_mcp, 2026-09-03 -- all three resolve null). Every caller of
this module MUST check secrets_configured() first and degrade to
NOT_CONFIGURED, never fabricate a token or an upload response.

M8 (issue body): every video this module ever builds a request for carries
PRIVACY_STATUS = 'private', a module-level constant, never a parameter. There
is no function in this file that accepts a privacy status argument.

DB access pattern (matches scripts/biddeed_reels_lib.py's module docstring):
public.* tables/RPCs (youtube_quota_ledger, youtube_token_health,
youtube_uploads) go through PostgREST (SUPABASE_URL + SERVICE_ROLE_KEY).
winnerdata.* (youtube_publish_queue view, reel_variant_metrics writes) is NOT
exposed via PostgREST on this project (live-confirmed: "permission denied for
schema winnerdata", 42501) -- those go through the Supabase Management API
(SUPABASE_ACCESS_TOKEN), same as every other winnerdata access in this repo.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - py<3.9 not used in this repo
    ZoneInfo = None

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

MGMT_API_RETRIES = 3
MGMT_API_BACKOFF_SECONDS = 3
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# M8 -- hard-coded, never a function parameter anywhere in this lane.
PRIVACY_STATUS = "private"

# Hard constraints from the issue body, verified 2026-09-03 -- design
# constants, not guesses.
DAILY_QUOTA_CAP = 10000
QUOTA_RESERVE = 400          # reserved for Analytics + channel reads
UPLOAD_BUDGET = DAILY_QUOTA_CAP - QUOTA_RESERVE  # 9600
MAX_UPLOADS_PER_DAY = 6      # 9600 / 1600 == 6, not an independent number

QUOTA_COSTS = {
    "videos.insert": 1600,
    "videos.list": 1,
    "channels.list": 1,
    "playlistItems.insert": 50,
    "playlistItems.list": 1,
    # YouTube Analytics reports run against a separate Google-documented
    # quota pool in general, but the issue's own verified hard constraint
    # ("Every other call shares that same 10,000 pool") says to budget it
    # against this project's shared pool too -- conservative, costs nothing
    # to over-budget, and this is what the issue explicitly asked for.
    "youtubeAnalytics.query": 1,
}

REQUIRED_SECRET_NAMES = (
    "youtube_client_id",
    "youtube_client_secret",
    "youtube_oauth_refresh_token",
)

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_INIT_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB, multiple of the required 256 KiB


class NotConfigured(Exception):
    """Raised when one or more youtube_* vault secrets are absent."""


class TokenExpired(Exception):
    """Raised on invalid_grant -- the 7-day Testing-mode trap."""

    def __init__(self, raw_error: str):
        super().__init__(raw_error)
        self.raw_error = raw_error


# ---------------------------------------------------------------------------
# Vault / secrets
# ---------------------------------------------------------------------------

def get_vault_secret(name: str) -> str | None:
    """Matches scripts/biddeed_reels_lib.py's get_vault_secret() -- RPC only,
    never echoed, never written to a shell command (CREDENTIAL HANDLING
    mandate). Returns None (not an exception) on a genuine miss so callers
    can build a clean NOT_CONFIGURED decision instead of a stack trace."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp",
        data=json.dumps({"p_name": name}).encode(),
        headers={
            "apikey": SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "youtube-publish-lane/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode().strip()
    if raw in ("null", '""', ""):
        return None
    return raw.strip('"')


def load_credentials() -> dict[str, str] | None:
    """Returns {client_id, client_secret, refresh_token} or None if ANY of
    the three is absent -- never a partial credential set."""
    creds = {name: get_vault_secret(name) for name in REQUIRED_SECRET_NAMES}
    if any(v is None for v in creds.values()):
        return None
    return {
        "client_id": creds["youtube_client_id"],
        "client_secret": creds["youtube_client_secret"],
        "refresh_token": creds["youtube_oauth_refresh_token"],
    }


def secrets_configured() -> bool:
    return load_credentials() is not None


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def refresh_access_token(creds: dict[str, str]) -> str:
    """POST to Google's token endpoint. Raises TokenExpired on invalid_grant
    (the 7-day Testing-mode trap) so callers can react distinctly from a
    generic network failure."""
    body = urllib.parse.urlencode({
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        OAUTH_TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "youtube-publish-lane/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            err = json.loads(raw).get("error", "")
        except json.JSONDecodeError:
            err = ""
        if err == "invalid_grant":
            raise TokenExpired(raw) from e
        raise


# ---------------------------------------------------------------------------
# public schema access (PostgREST)
# ---------------------------------------------------------------------------

def _rest_request(method: str, path: str, params: str = "", body=None, extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    last_err = None
    for attempt in range(1, MGMT_API_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < MGMT_API_RETRIES:
                time.sleep(MGMT_API_BACKOFF_SECONDS * attempt)
    raise last_err


def rpc(name: str, params: dict):
    return _rest_request("POST", f"rpc/{name}", body=params)


def rest_get(table: str, params: str):
    return _rest_request("GET", table, params=params)


def rest_insert(table: str, row: dict, extra_headers=None):
    headers = {"Prefer": "return=representation"}
    if extra_headers:
        headers.update(extra_headers)
    return _rest_request("POST", table, body=row, extra_headers=headers)


def rest_update(table: str, params: str, patch: dict):
    return _rest_request("PATCH", table, params=params, body=patch,
                          extra_headers={"Prefer": "return=representation"})


# ---------------------------------------------------------------------------
# winnerdata schema access (Management API) -- youtube_publish_queue,
# reel_variant_metrics writes.
# ---------------------------------------------------------------------------

def run_sql(query: str):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
        },
        method="POST",
    )
    last_err = None
    for attempt in range(1, MGMT_API_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "message" in body:
                raise RuntimeError(body["message"])
            return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < MGMT_API_RETRIES:
                time.sleep(MGMT_API_BACKOFF_SECONDS * attempt)
    raise last_err


def sql_str(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def sql_num(v):
    return "null" if v is None else str(v)


# ---------------------------------------------------------------------------
# Quota
# ---------------------------------------------------------------------------

def quota_preflight_reserve(units: int, call_name: str) -> dict:
    """Atomic pre-flight + reserve via public.youtube_quota_preflight_reserve
    (SECURITY DEFINER, SELECT ... FOR UPDATE inside one transaction). Never
    fires an upload/API call before this returns allow=true."""
    result = rpc("youtube_quota_preflight_reserve", {
        "p_units": units, "p_call_name": call_name,
    })
    return result


def pacific_today() -> str:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()  # pragma: no cover


def pacific_is_weekday() -> bool:
    """issue #19793 PART 4 -- the 2/day cadence is Mon-Fri only."""
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("America/Los_Angeles")).weekday() < 5
    return datetime.now(timezone.utc).weekday() < 5  # pragma: no cover


# ---------------------------------------------------------------------------
# spi_gates (deliverable 3 -- token expiry alarm)
# ---------------------------------------------------------------------------

def open_token_expired_gate(proof: str):
    """Upserts spi_gates row 'youtube_token_expired'. Matches the existing
    watchdog pattern (supabase/migrations/20260903a_cmo_factory_watchdog.sql):
    only reopen if the prior trip was already closed (verified_at not null),
    so a still-open gate isn't churned every run."""
    run_sql(f"""
        insert into public.spi_gates (gate_key, title, opened_at, proof)
        values (
          'youtube_token_expired',
          'YouTube OAuth refresh token invalid_grant -- OAuth app is in '
          'Testing mode; it must be Published/In production for the '
          'refresh token to persist beyond 7 days.',
          now(),
          {sql_str(proof)}
        )
        on conflict (gate_key) do update
          set opened_at = excluded.opened_at,
              proof = excluded.proof,
              verified_at = null
          where public.spi_gates.verified_at is not null;
    """)
