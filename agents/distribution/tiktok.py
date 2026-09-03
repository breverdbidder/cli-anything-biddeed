"""TikTok Content Posting API adapter (Direct Post), CMO Factory CP3g.

VERIFIED Sep 2026 against developers.tiktok.com/docs/en/ (see
docs/gtm/DISTRIBUTION_LANE.md for full citations):
  - scope: video.publish (per-account OAuth grant, no bulk)
  - prerequisite: TikTok Developer app with the Content Posting API
    product + Direct Post config, submitted for App Review (~days-2wks)
  - UNAUDITED apps are restricted, in TikTok's own words: "All content
    posted by unaudited clients will be restricted to private viewing
    mode" / "Unaudited API Clients can only post contents in SELF_ONLY
    viewership." This is the platform-level safety net M8 relies on for
    TikTok -- but this adapter does NOT trust audit status as the sole
    control: privacy_level is hardcoded to SELF_ONLY below regardless,
    same defense-in-depth posture as facebook.py's video_state=DRAFT.
  - caption: <=2200 UTF-16 runes. duration: no fixed static limit --
    must be checked dynamically against creator_info's
    max_video_post_duration_sec (done in validate() below).
  - rate limit: ~15 posts/day/creator via Direct Post -- used as
    daily_cap_default (conservative, TikTok notes it varies by account).
"""

from __future__ import annotations

try:
    from .base import PlatformAdapter, run_adapter_cli
except ImportError:  # allows `python agents/distribution/<platform>.py` direct invocation too
    from base import PlatformAdapter, run_adapter_cli

API = "https://open.tiktokapis.com/v2"


class TikTokAdapter(PlatformAdapter):
    platform = "tiktok"
    required_secrets = ["tiktok_access_token"]
    daily_cap_default = 15  # VERIFIED: TikTok's documented ~15/day/creator via Direct Post

    def validate(self, row: dict) -> None:
        if not row.get("media_url"):
            raise ValueError("tiktok: row has no media_url")
        caption = row.get("content_text") or ""
        if len(caption.encode("utf-16-le")) // 2 > 2200:
            raise ValueError("tiktok: caption exceeds 2200 UTF-16 runes")

    def build_payload(self, row: dict) -> dict:
        return {
            "post_info": {
                "title": (row.get("content_text") or "").strip(),
                "privacy_level": "SELF_ONLY",  # hardcoded, never trust audit status alone -- see docstring
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": row["media_url"],
            },
        }

    def upload(self, payload: dict, creds: dict) -> dict:
        import json
        import urllib.request

        token = creds["tiktok_access_token"]
        req = urllib.request.Request(
            f"{API}/post/publish/video/init/",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
        return {"external_id": body.get("data", {}).get("publish_id"), "privacy_level": "SELF_ONLY"}

    def verify(self, result: dict) -> bool:
        return result.get("privacy_level") == "SELF_ONLY" and bool(result.get("external_id"))


if __name__ == "__main__":
    run_adapter_cli(TikTokAdapter())
