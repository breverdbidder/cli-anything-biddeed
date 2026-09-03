"""X (Twitter) API v2 adapter, CMO Factory CP3g.

VERIFIED Sep 2026 against docs.x.com (see docs/gtm/DISTRIBUTION_LANE.md for
full citations) -- and this is the platform where research overturned the
issue's own starting hypothesis, so record it plainly rather than building
around it:

  - X retired the tiered Free/Basic model on 2026-02-06. New API access is
    PAY-PER-USAGE: $0.015/post ($0.20 if it contains a URL), no free
    write quota at all. developer.x.com/en/portal/products now 402s.
  - POST /2/tweets has NO scheduled_at/draft field -- every successful
    call publishes immediately and publicly. There is no platform-level
    safety net here at all (worse than Instagram/LinkedIn, which are at
    least free to attempt).
  - This directly conflicts with this issue's own non-goal ("no paid
    vendors") and with M8 (immediate-live, zero platform-side hold).

POLICY DECISION (this build, pending Ariel): daily_cap_default is 0 --
X posting stays structurally disabled (quota gate always skips) even if a
token is ever added to the vault, until Ariel explicitly raises the cap in
social_quota_ledger after accepting the per-post cost and the
immediate-publish risk. NOT_CONFIGURED fires first regardless, since no
vault secret exists in this environment.
"""

from __future__ import annotations

try:
    from .base import PlatformAdapter, run_adapter_cli
except ImportError:  # allows `python agents/distribution/<platform>.py` direct invocation too
    from base import PlatformAdapter, run_adapter_cli

API = "https://api.x.com/2"


class XAdapter(PlatformAdapter):
    platform = "x"
    required_secrets = ["x_access_token"]
    daily_cap_default = 0  # policy hold -- see module docstring, not a technical limit

    def validate(self, row: dict) -> None:
        caption = row.get("content_text") or ""
        if len(caption) > 280:
            raise ValueError(f"x: post {len(caption)} chars exceeds 280 limit")

    def build_payload(self, row: dict) -> dict:
        return {"text": (row.get("content_text") or "").strip()}

    def upload(self, payload: dict, creds: dict) -> dict:
        import json
        import urllib.request

        token = creds["x_access_token"]
        req = urllib.request.Request(
            f"{API}/tweets",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
        return {"external_id": body.get("data", {}).get("id")}

    def verify(self, result: dict) -> bool:
        return bool(result.get("external_id"))


if __name__ == "__main__":
    run_adapter_cli(XAdapter())
