"""Daily token-health probe for the CMO Factory distribution lane
(issue #19789). For each platform: if its vault credential(s) are absent,
record NOT_CONFIGURED (expected, dormant, no gate opened -- this is the
normal state until Ariel completes that platform's account setup per
docs/gtm/DISTRIBUTION_LANE.md). If credentials exist but a live check
against the platform fails, record the failure AND open an spi_gates row
naming the platform + the plain-English cause, so it surfaces in /spi.

Run via .github/workflows/cmo-factory-distribution-scheduler.yml.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])
from agents.distribution.base import SUPABASE_URL, SUPABASE_KEY, _rest, vault_secret, log  # noqa: E402

PLATFORMS = {
    "instagram": ["instagram_access_token", "instagram_business_account_id"],
    "facebook": ["facebook_page_access_token", "facebook_page_id"],
    "tiktok": ["tiktok_access_token"],
    "x": ["x_access_token"],
    "linkedin_company": ["linkedin_company_access_token", "linkedin_organization_urn"],
}


def probe_platform(platform: str, creds: dict) -> tuple[bool, str]:
    """Cheap live reachability check. Best-effort: any transport error is a
    failure, not an exception the caller has to handle specially."""
    try:
        if platform in ("instagram", "facebook"):
            token = creds[next(k for k in creds if k.endswith("access_token"))]
            req = urllib.request.Request(f"https://graph.facebook.com/v21.0/me?access_token={token}")
        elif platform == "tiktok":
            req = urllib.request.Request(
                "https://open.tiktokapis.com/v2/user/info/",
                headers={"Authorization": f"Bearer {creds['tiktok_access_token']}"},
            )
        elif platform == "x":
            req = urllib.request.Request(
                "https://api.x.com/2/users/me",
                headers={"Authorization": f"Bearer {creds['x_access_token']}"},
            )
        elif platform == "linkedin_company":
            req = urllib.request.Request(
                "https://api.linkedin.com/v2/organizationAcls?q=roleAssignee",
                headers={"Authorization": f"Bearer {creds['linkedin_company_access_token']}"},
            )
        else:
            return False, f"no probe implemented for {platform}"
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return True, "live probe ok"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} on live probe: {e.read().decode()[:300]}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def upsert_health(platform: str, healthy: bool, detail: str, consecutive_failures: int):
    _rest(
        "social_token_health",
        method="POST",
        params="on_conflict=platform",
        body={
            "platform": platform,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "healthy": healthy,
            "detail": detail,
            "consecutive_failures": consecutive_failures,
        },
        extra_headers={"Prefer": "resolution=merge-duplicates"},
    )


def open_gate(platform: str, cause: str):
    _rest(
        "spi_gates",
        method="POST",
        params="on_conflict=gate_key",
        body={
            "gate_key": f"social_token_{platform}_unhealthy",
            "title": f"{platform} distribution token unhealthy",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "verified_at": None,
            "proof": cause,
        },
        extra_headers={"Prefer": "resolution=merge-duplicates"},
    )


def main():
    results = {}
    for platform, secret_names in PLATFORMS.items():
        creds = {name: vault_secret(name) for name in secret_names}
        missing = [n for n, v in creds.items() if not v]
        if missing:
            upsert_health(platform, False, f"NOT_CONFIGURED -- missing vault secret(s) {missing}", 0)
            results[platform] = "NOT_CONFIGURED"
            continue

        ok, detail = probe_platform(platform, creds)
        if ok:
            upsert_health(platform, True, detail, 0)
            results[platform] = "HEALTHY"
        else:
            prior = _rest("social_token_health", params=f"platform=eq.{platform}&select=consecutive_failures")
            failures = (prior[0]["consecutive_failures"] if prior else 0) + 1
            upsert_health(platform, False, detail, failures)
            open_gate(platform, f"consecutive_failures={failures}: {detail}")
            results[platform] = f"UNHEALTHY ({failures} consecutive)"
            log(platform, "WARN", f"token unhealthy, spi_gates opened: {detail}")

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
