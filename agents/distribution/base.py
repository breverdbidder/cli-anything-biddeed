"""Shared thin-adapter contract for the CMO Factory CP3g distribution lane
(issue #19789). One bolt32 32s master asset is fanned out across platforms;
each platform gets its own adapter module implementing the same four-step
interface (adopted orchestration shape: langchain-ai/social-media-agent MIT,
curate -> draft -> human gate -> schedule -> verify -- see
docs/gtm/DISTRIBUTION_LANE.md):

    validate(row)          -- does this queue row have what this platform needs?
    build_payload(row)     -- shape the platform-specific request body
    upload(payload, creds) -- call the platform API, private/draft only
    verify(result)         -- confirm the platform accepted it
    record(row_id, result) -- write to social_content_queue + campaign_agent_log

run_adapter_cli() drives the pipeline and enforces the safety rails that are
shared across every platform, so no single adapter can accidentally violate
them:

  - NOT_CONFIGURED: missing vault credential -> log the literal word
    "NOT_CONFIGURED" and exit 0. Checked BEFORE anything else, so
    `python agents/distribution/<platform>.py` is always a safe, zero-cost,
    zero-side-effect smoke test in an environment with no platform tokens.
  - M8 gate: a row is only ever handed to upload() if
    social_content_queue.approved_at IS NOT NULL (Ariel's LMS click). No
    adapter method ever sets a public/live status itself.
  - Attribution gate: a row without its own short_code + utm_source is
    refused, never published unattributed (negative test (e)).
  - Quota gate: social_quota_ledger is checked before upload; exceeding the
    platform's daily_cap SKIPS the row with a reason instead of attempting
    it (negative test (f)).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

NOT_CONFIGURED = "NOT_CONFIGURED"

# Statuses an adapter is legally allowed to write. Enforced in record() so a
# bug in a platform module can't accidentally set anything public/live --
# this is the code-level backstop for negative test (a).
_ALLOWED_WRITE_STATUSES = {"published", "failed", "skipped_duplicate", "not_configured"}
_FORBIDDEN_STATUS_FRAGMENTS = ("live", "public")


def _headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _rest(path: str, method: str = "GET", body=None, params: str = "", extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(extra_headers), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"PostgREST {method} {path} -> {e.code}: {e.read().decode()[:500]}") from e


def rpc(name: str, args: dict):
    return _rest(f"rpc/{name}", method="POST", body=args)


def vault_secret(name: str):
    """Fetch a vault secret INSIDE this process only -- never printed, never
    passed to a shell command, per CLAUDE.md CREDENTIAL HANDLING (GTM-22D).
    Returns None if absent (never raises), same contract as vault_secret.sql."""
    try:
        return rpc("vault_secret", {"p_name": name})
    except RuntimeError:
        return None


class NotConfiguredError(Exception):
    pass


class PlatformAdapter:
    platform: str = ""
    required_secrets: list[str] = []
    daily_cap_default: int = 1

    # ---- hooks every adapter implements ------------------------------
    def validate(self, row: dict) -> None:
        raise NotImplementedError

    def build_payload(self, row: dict) -> dict:
        raise NotImplementedError

    def upload(self, payload: dict, creds: dict) -> dict:
        raise NotImplementedError

    def verify(self, result: dict) -> bool:
        raise NotImplementedError

    # ---- shared machinery ----------------------------------------------
    def credentials(self) -> dict:
        creds = {}
        missing = []
        for name in self.required_secrets:
            val = vault_secret(name)
            if not val:
                missing.append(name)
            else:
                creds[name] = val
        if missing:
            raise NotConfiguredError(f"{self.platform}: missing vault secret(s) {missing}")
        return creds

    def check_and_reserve_quota(self) -> tuple[bool, str]:
        today = datetime.now(timezone.utc).date().isoformat()
        rows = _rest(
            "social_quota_ledger",
            params=f"platform=eq.{self.platform}&ledger_date=eq.{today}&select=*",
        )
        if not rows:
            _rest(
                "social_quota_ledger",
                method="POST",
                body={"platform": self.platform, "ledger_date": today, "posts_used": 0, "daily_cap": self.daily_cap_default},
                extra_headers={"Prefer": "resolution=ignore-duplicates"},
            )
            rows = _rest(
                "social_quota_ledger",
                params=f"platform=eq.{self.platform}&ledger_date=eq.{today}&select=*",
            )
        row = rows[0] if rows else {"posts_used": 0, "daily_cap": self.daily_cap_default}
        if row["posts_used"] >= row["daily_cap"]:
            return False, f"{self.platform} daily cap {row['daily_cap']} reached for {today}"
        return True, ""

    def _reserve_slot(self):
        today = datetime.now(timezone.utc).date().isoformat()
        rows = _rest("social_quota_ledger", params=f"platform=eq.{self.platform}&ledger_date=eq.{today}&select=posts_used")
        used = rows[0]["posts_used"] if rows else 0
        _rest(
            "social_quota_ledger",
            method="PATCH",
            params=f"platform=eq.{self.platform}&ledger_date=eq.{today}",
            body={"posts_used": used + 1, "updated_at": datetime.now(timezone.utc).isoformat()},
        )

    def record(self, row_id: str | None, status: str, detail: str, external_id: str | None = None):
        if status not in _ALLOWED_WRITE_STATUSES:
            raise ValueError(f"refusing to write disallowed status {status!r}")
        for frag in _FORBIDDEN_STATUS_FRAGMENTS:
            if frag in status.lower() and status not in _ALLOWED_WRITE_STATUSES:
                raise ValueError(f"status {status!r} looks public/live -- refused (M8)")

        now = datetime.now(timezone.utc).isoformat()
        try:
            _rest(
                "campaign_agent_log",
                method="POST",
                body={
                    "agent_id": f"cmo_factory_distribution_{self.platform}",
                    "action": f"gtm_publish_{self.platform}",
                    "success": status == "published",
                    "details": {
                        "journey": "cmo_factory_distribution_v1",
                        "platform": self.platform,
                        "status": status,
                        "detail": detail,
                        "external_id": external_id,
                        "row_id": row_id,
                    },
                },
            )
        except RuntimeError as e:
            log(self.platform, "WARN", f"campaign_agent_log write failed (non-fatal): {e}")

        if row_id:
            update = {"status": status, "last_attempt_at": now, "error_message": detail if status == "failed" else None}
            if status == "published":
                update.update({"published_at": now, "external_post_id": external_id})
            _rest("social_content_queue", method="PATCH", params=f"id=eq.{row_id}", body=update)

    # ---- pipeline driver ----------------------------------------------
    def run(self, row: dict | None) -> dict:
        try:
            creds = self.credentials()
        except NotConfiguredError as e:
            log(self.platform, "INFO", f"{NOT_CONFIGURED}: {e}")
            return {"status": NOT_CONFIGURED, "detail": str(e)}

        if row is None:
            return {"status": "NO_ROW", "detail": "credentials present but no row supplied"}

        if not row.get("approved_at"):
            log(self.platform, "INFO", f"row {row.get('id')} held: approved_at is null (M1/M8 gate)")
            return {"status": "pending_approval", "detail": "not yet approved in LMS"}

        if not row.get("short_code") or not row.get("utm_source"):
            self.record(row.get("id"), "failed", "missing short_code/utm_source -- refusing unattributed publish")
            return {"status": "failed", "detail": "missing short_code/utm_source"}

        ok, reason = self.check_and_reserve_quota()
        if not ok:
            log(self.platform, "INFO", f"SKIPPED: {reason}")
            return {"status": "skipped_duplicate", "detail": reason}

        try:
            self.validate(row)
            payload = self.build_payload(row)
            result = self.upload(payload, creds)
            ok = self.verify(result)
        except Exception as e:  # noqa: BLE001 -- adapter boundary, must never crash the scheduler
            self.record(row.get("id"), "failed", f"{type(e).__name__}: {e}")
            return {"status": "failed", "detail": str(e)}

        if ok:
            self._reserve_slot()
            self.record(row.get("id"), "published", "verified", external_id=result.get("external_id"))
            return {"status": "published", "detail": "verified", "result": result}

        self.record(row.get("id"), "failed", "verify() returned false")
        return {"status": "failed", "detail": "verify() returned false"}


def log(platform: str, level: str, message: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] [{platform}] [{level}] {message}", file=sys.stderr)


def fetch_approved_rows(platform: str, limit: int = 10) -> list[dict]:
    """Rows this adapter is allowed to attempt: approved by Ariel in the
    LMS (approved_at set), status='approved' (never 'pending_approval' --
    that status means still awaiting the click), targeted at this platform.
    Scheduler is poll-only (no pushes), per the issue's architecture note."""
    return _rest(
        "social_content_queue",
        params=(
            f"target_platform=eq.{platform}&status=eq.approved"
            f"&approved_at=not.is.null&order=created_at.asc&limit={limit}&select=*"
        ),
    ) or []


def run_adapter_cli(adapter: PlatformAdapter):
    """Entry point for `python -m agents.distribution.<platform>` (or the
    direct-script fallback). Credentials are checked FIRST and always --
    NOT_CONFIGURED short-circuits before the queue is ever touched, so this
    is always a safe smoke test in an environment with no platform tokens
    (negative test (b): missing credentials -> NOT_CONFIGURED, exit 0).
    When credentials ARE present, it polls for this platform's approved
    rows and runs the pipeline on each -- this is the scheduler's per-
    platform dispatch step (.github/workflows/cmo-factory-distribution-
    scheduler.yml calls this once per platform per tick)."""
    probe = adapter.run(row=None)
    if probe["status"] == NOT_CONFIGURED:
        print(json.dumps(probe))
        sys.exit(0)

    rows = fetch_approved_rows(adapter.platform)
    if not rows:
        log(adapter.platform, "INFO", "no approved rows -- no-op")
        print(json.dumps({"status": "NO_ROWS", "processed": 0}))
        sys.exit(0)

    results = [adapter.run(row) for row in rows]
    print(json.dumps({"status": "PROCESSED", "processed": len(results), "results": results}, default=str))
    sys.exit(0)
