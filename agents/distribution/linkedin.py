"""LinkedIn COMPANY PAGE adapter (Community Management API / Posts API),
CMO Factory CP3g.

This is the org-page publish path for content drafted by the LinkedIn B2B
agent (.claude/skills/linkedin-b2b-agent/, agents/distribution/linkedin.py
is the publisher; the agent is the writer/validator). It is a SEPARATE
code path from supabase/functions/social-publish-worker/index.ts, which
posts to Ariel's PERSONAL profile (target_platform='linkedin_personal',
legacy, pre-CP3g) -- do not merge the two; see
docs/gtm/DISTRIBUTION_LANE.md for the reclassification note.

VERIFIED Sep 2026 against learn.microsoft.com/en-us/linkedin/marketing/
community-management/ (see docs/gtm/DISTRIBUTION_LANE.md for citations):
  - scope: w_organization_social, restricted to page roles ADMINISTRATOR /
    DIRECT_SPONSORED_CONTENT_POSTER / CONTENT_ADMIN
  - API product: Community Management API, a VETTED PRODUCT -- requires an
    access-request form (Development Tier: verified business email +
    verified org + verified domain; Standard Tier: a second form PLUS a
    screencast video of the OAuth flow). NOT self-serve. Say so plainly
    per the issue -- do not attempt a workaround.
  - IMPORTANT: lifecycleState only accepts PUBLISHED on create -- there is
    no draft/scheduled state at all (DRAFT/PUBLISH_REQUESTED/
    PUBLISH_FAILED are response-only). Like Instagram, M8 compliance here
    is enforced ENTIRELY by our own approved_at gate in
    base.PlatformAdapter.run() -- calling upload() IS Ariel's per-item
    LMS approval taking effect, there is no lower-risk intermediate state
    the platform offers.
  - rate limit: Dev Tier defaults 500 req/app, 100 req/member (no
    Standard Tier number published) -- daily_cap_default set conservatively
    below pending a real Standard Tier grant.
"""

from __future__ import annotations

try:
    from .base import PlatformAdapter, run_adapter_cli
except ImportError:  # allows `python agents/distribution/<platform>.py` direct invocation too
    from base import PlatformAdapter, run_adapter_cli

API = "https://api.linkedin.com/rest"


class LinkedInOrgAdapter(PlatformAdapter):
    platform = "linkedin_company"
    required_secrets = ["linkedin_company_access_token", "linkedin_organization_urn"]
    daily_cap_default = 3  # conservative pending a real Standard Tier grant, see docstring

    def validate(self, row: dict) -> None:
        text = row.get("content_text") or ""
        if not (900 <= len(text) <= 1300):
            raise ValueError(f"linkedin_company: post is {len(text)} chars, spec requires 900-1300")

    def build_payload(self, row: dict) -> dict:
        return {
            "author": None,  # filled in from creds in upload() -- author URN is a credential, not queue data
            "commentary": (row.get("content_text") or "").strip(),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED"},
            "lifecycleState": "PUBLISHED",  # only value the API accepts on create -- see docstring
        }

    def upload(self, payload: dict, creds: dict) -> dict:
        import json
        import urllib.request

        token = creds["linkedin_company_access_token"]
        payload["author"] = creds["linkedin_organization_urn"]

        req = urllib.request.Request(
            f"{API}/posts",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": "202609",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            post_urn = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id")
        return {"external_id": post_urn}

    def verify(self, result: dict) -> bool:
        return bool(result.get("external_id"))


if __name__ == "__main__":
    run_adapter_cli(LinkedInOrgAdapter())
