"""Instagram Reels adapter (Content Publishing API), CMO Factory CP3g.

VERIFIED Sep 2026 against developers.facebook.com/docs/instagram-platform/
(see docs/gtm/DISTRIBUTION_LANE.md for full citations):
  - scopes: instagram_business_basic, instagram_business_content_publish
  - prerequisite: IG Business/Creator account linked to a Facebook Page,
    Page Publishing Authorization complete, Meta app with Advanced Access
    (requires App Review + Business Verification)
  - media: 3s-15min, <=300MB, aspect 0.01:1-10:1 (9:16 recommended),
    caption <=2200 chars, <=30 hashtags, <=20 @-mentions
  - rate limit: Meta's own docs disagree (50 vs 100 posts/24h on two
    different pages) -- daily_cap_default below is set to the LOWER,
    more conservative figure until Ariel/CC can get a definitive answer.
  - IMPORTANT: the Content Publishing API has NO documented draft/private
    state for media_publish -- unlike Facebook Reels and TikTok, there is
    no platform-level safety net. M8 compliance here is enforced ENTIRELY
    by base.PlatformAdapter.run()'s approved_at gate: upload() is simply
    never invoked until Ariel has approved the row in the LMS.
"""

from __future__ import annotations

import time

try:
    from .base import PlatformAdapter, run_adapter_cli
except ImportError:  # allows `python agents/distribution/<platform>.py` direct invocation too
    from base import PlatformAdapter, run_adapter_cli

GRAPH_API = "https://graph.facebook.com/v21.0"


class InstagramAdapter(PlatformAdapter):
    platform = "instagram"
    required_secrets = ["instagram_access_token", "instagram_business_account_id"]
    daily_cap_default = 25  # conservative floor of the 50 vs 100/24h conflict, see module docstring

    def validate(self, row: dict) -> None:
        if not row.get("media_url"):
            raise ValueError("instagram: row has no media_url (Reels require a video)")
        caption = row.get("content_text") or ""
        if len(caption) > 2200:
            raise ValueError(f"instagram: caption {len(caption)} chars exceeds 2200 limit")

    def build_payload(self, row: dict) -> dict:
        caption = (row.get("content_text") or "").strip()
        return {
            "media_type": "REELS",
            "video_url": row["media_url"],
            "caption": caption,
            "share_to_feed": True,
        }

    def upload(self, payload: dict, creds: dict) -> dict:
        import json
        import urllib.request

        ig_user_id = creds["instagram_business_account_id"]
        token = creds["instagram_access_token"]

        create_req = urllib.request.Request(
            f"{GRAPH_API}/{ig_user_id}/media",
            data=json.dumps({**payload, "access_token": token}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(create_req, timeout=30) as resp:
            container_id = json.loads(resp.read())["id"]

        for _ in range(10):
            status_req = urllib.request.Request(
                f"{GRAPH_API}/{container_id}?fields=status_code&access_token={token}"
            )
            with urllib.request.urlopen(status_req, timeout=30) as resp:
                status = json.loads(resp.read()).get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError(f"instagram: container {container_id} failed processing")
            time.sleep(5)

        publish_req = urllib.request.Request(
            f"{GRAPH_API}/{ig_user_id}/media_publish",
            data=json.dumps({"creation_id": container_id, "access_token": token}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(publish_req, timeout=30) as resp:
            media_id = json.loads(resp.read())["id"]
        return {"external_id": media_id, "container_id": container_id}

    def verify(self, result: dict) -> bool:
        return bool(result.get("external_id"))


if __name__ == "__main__":
    run_adapter_cli(InstagramAdapter())
