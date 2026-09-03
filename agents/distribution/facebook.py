"""Facebook Page Reels adapter (Video API /video_reels), CMO Factory CP3g.

VERIFIED Sep 2026 against developers.facebook.com/docs/video-api/guides/reels-publishing/
(see docs/gtm/DISTRIBUTION_LANE.md for full citations):
  - scopes: pages_show_list, pages_read_engagement, pages_manage_posts
    (+ Page access token with CREATE_CONTENT task capability)
  - prerequisite: Facebook Page, Meta app, 3-phase resumable upload
    (POST /{page_id}/video_reels start -> rupload.facebook.com upload ->
    finish)
  - media: aspect 9:16 (range 16:9-9:16), 1080x1920 recommended (540x960
    min), duration 3-90s, H.264/H.265, audio >=128kbps
  - rate limit: 30 API-published Reels / 24h moving window on
    POST /{page_id}/video_reels -- VERIFIED, used as daily_cap_default.
  - IMPORTANT (differs from Instagram): video_state is a real enum
    {DRAFT, SCHEDULED, PUBLISHED} on this endpoint. This adapter ALWAYS
    finishes the upload with video_state=DRAFT -- flipping a Reel from
    DRAFT to live PUBLISHED is a distinct, separate action this ticket's
    DoD does not require and this module does not implement, so there is
    no code path here that can ever set a public/live status (M8), with a
    platform-level safety net on top of our own approved_at gate.
"""

from __future__ import annotations

try:
    from .base import PlatformAdapter, run_adapter_cli
except ImportError:  # allows `python agents/distribution/<platform>.py` direct invocation too
    from base import PlatformAdapter, run_adapter_cli

GRAPH_API = "https://graph.facebook.com/v21.0"


class FacebookAdapter(PlatformAdapter):
    platform = "facebook"
    required_secrets = ["facebook_page_access_token", "facebook_page_id"]
    daily_cap_default = 30  # VERIFIED: Meta's documented 30/24h cap on /video_reels

    def validate(self, row: dict) -> None:
        if not row.get("media_url"):
            raise ValueError("facebook: row has no media_url")

    def build_payload(self, row: dict) -> dict:
        return {
            "upload_phase": "start",
            "media_url": row["media_url"],
            "description": (row.get("content_text") or "").strip(),
            "video_state": "DRAFT",  # never PUBLISHED -- see module docstring
        }

    def upload(self, payload: dict, creds: dict) -> dict:
        import json
        import urllib.request

        page_id = creds["facebook_page_id"]
        token = creds["facebook_page_access_token"]

        start_req = urllib.request.Request(
            f"{GRAPH_API}/{page_id}/video_reels",
            data=json.dumps({"upload_phase": "start", "access_token": token}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(start_req, timeout=30) as resp:
            start = json.loads(resp.read())
        video_id = start["video_id"]
        upload_url = start["upload_url"]

        # rupload.facebook.com fetch-from-URL upload (avoids downloading the
        # asset into this process): pass file_url header per Meta's docs.
        upload_req = urllib.request.Request(
            upload_url,
            headers={
                "Authorization": f"OAuth {token}",
                "file_url": payload["media_url"],
            },
            method="POST",
        )
        urllib.request.urlopen(upload_req, timeout=120)

        finish_req = urllib.request.Request(
            f"{GRAPH_API}/{page_id}/video_reels",
            data=json.dumps(
                {
                    "upload_phase": "finish",
                    "video_id": video_id,
                    "video_state": "DRAFT",
                    "description": payload["description"],
                    "access_token": token,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(finish_req, timeout=30) as resp:
            json.loads(resp.read())
        return {"external_id": video_id, "video_state": "DRAFT"}

    def verify(self, result: dict) -> bool:
        return result.get("video_state") == "DRAFT" and bool(result.get("external_id"))


if __name__ == "__main__":
    run_adapter_cli(FacebookAdapter())
