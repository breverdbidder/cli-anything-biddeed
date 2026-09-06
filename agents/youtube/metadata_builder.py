#!/usr/bin/env python3
"""Builds YouTube upload metadata from a winnerdata.youtube_publish_queue row
(issue #19788, deliverable 4). Pure functions, no network/DB calls -- every
value that reaches the YouTube API is assembled here from row fields, never
free-written at upload time.

M3/M7: title/description/tags/pinned-comment are all re-checked here against
a banned-terms list (vendor/tool names + generic person-name markers) as a
final defensive layer, even though the upstream Hook Writer/Director QA
(issue #19782) already validated title_chosen before qa_pass was set to true
-- cheap, and this is the last code that touches the text before it would
ever reach a real API call.
"""
from __future__ import annotations

import re
import urllib.parse

# Same house disclaimer already live on biddeed.ai (src/worker.js, used on
# both the sample S5 report and the reel deal-page footer) -- reused
# verbatim rather than inventing new legal language.
DISCLOSURE_LINE = (
    "Not legal advice. BidDeed.AI is an information and analytics platform, "
    "not a law firm or title company. Auction data is informational and "
    "must be independently verified."
)

CATEGORY_ID = "22"  # People & Blogs -- no clearer fit justified (see docs/spec/19788.md)

# M3 vendor/tool names + generic internal-process words that must never
# appear in a client-facing surface. Not exhaustive -- a defensive net, not
# the primary control (that's upstream in #19782's Director/QA).
_BANNED_TERMS = (
    "google", "elevenlabs", "eleven labs", "anthropic", "claude", "openai",
    "gpt", "deepseek", "openrouter", "gemini", "github", "issue #", "run id",
    "skip-trace", "skip trace", "firecrawl", "supabase", "biddeed reels",
    "summitleads",
)


class MetadataValidationError(Exception):
    pass


def _assert_no_banned_terms(label: str, text: str):
    if not text:
        return
    lowered = text.lower()
    for term in _BANNED_TERMS:
        if term in lowered:
            raise MetadataValidationError(f"{label} contains banned term: {term!r}")


def detect_video_type(duration_sec: float | None) -> str:
    """Shorts are 1080x1920 (this pipeline's only video product -- documented
    in docs/gtm/REEL_SPEC_BOLT32.md, no width/height column exists on either
    biddeed_reels or reel_variants because every render is vertical) and
    <=60s. Anything else -- there is no long-form renderer in this repo yet
    -- falls to 'longform' so the caller can apply the 5-Shorts+1-longform
    split IF a long-form asset ever exists; today every candidate is 'shorts'
    (a real, documented data ceiling, not a bug)."""
    if duration_sec is not None and duration_sec <= 60:
        return "shorts"
    return "longform"


def build_utm_link(landing_url: str, county: str, variant_key: str, video_type: str) -> str:
    if not landing_url:
        raise MetadataValidationError("landing_url is required to build a UTM link")
    medium = "shorts" if video_type == "shorts" else "longform"
    params = {
        "utm_source": "youtube",
        "utm_medium": medium,
        "utm_campaign": county or "unknown",
        "utm_content": variant_key or "unknown",
    }
    parts = urllib.parse.urlsplit(landing_url)
    existing = dict(urllib.parse.parse_qsl(parts.query))
    existing.update(params)
    new_query = urllib.parse.urlencode(existing)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


# issue #19804 -- sale-type-slotted cadence means a row can be either
# sale_type now; the description must say which, and must never claim a
# sale happened "today" if it didn't (see the starvation ladder's real-
# sale-date labelling requirement in agents/youtube/uploader.py).
_SALE_TYPE_LABEL = {
    "tax_deed": "public tax deed sale",
    "foreclosure": "public foreclosure auction",
}


def build_description(utm_link: str, county: str, video_type: str,
                       sale_type: str | None = None, auction_date: str | None = None) -> str:
    county_label = (county or "this county").replace("_", " ").title()
    sale_label = _SALE_TYPE_LABEL.get(sale_type, "public auction")
    context_line_1 = f"A {county_label} County property just changed hands at a {sale_label}."
    if auction_date:
        context_line_1 += f" Sale date: {auction_date}."
    context_line_2 = "Full public record, photos, and sale details are at the link above."
    return "\n".join([utm_link, context_line_1, context_line_2, DISCLOSURE_LINE])


def build_pinned_comment(utm_link: str) -> str:
    return f"Full details and public record: {utm_link}"


def build_tags(hashtags: list[str] | None) -> list[str]:
    tags: list[str] = []
    seen = set()
    for h in hashtags or []:
        clean = re.sub(r"^#", "", (h or "").strip())
        if not clean or clean.lower() in seen:
            continue
        seen.add(clean.lower())
        tags.append(clean)
    # YouTube caps total tags length at 500 chars (comma-joined) -- trim
    # defensively rather than let an API call fail on a limit this module
    # can check for free.
    out: list[str] = []
    total = 0
    for t in tags:
        total += len(t) + 1
        if total > 500:
            break
        out.append(t)
    return out


def build_metadata(row: dict) -> dict:
    """row is one winnerdata.youtube_publish_queue record (variant_id,
    reel_id, variant_key, title, short_code, short_url, hashtags, county,
    landing_url, page_http_status, duration_sec, video_type, post_text, ...).

    issue #20057 -- when the row carries a `post_text.youtube` object (the
    queue view now REQUIRES this to exist, see the migration), that is the
    SSOT: title/description/pinned_comment are read verbatim from it rather
    than rebuilt here, because #20057's description format (short r/<code>
    link as line 1) differs from this function's own legacy build_description
    (long UTM-tagged landing_url) and the whole point of #20057 is that the
    clickable link a viewer sees IN THE POST must be the one Ariel/QA already
    reviewed on the LMS review screen (deliverable 6) -- never silently
    rebuilt into different text at upload time. Falls back to the legacy
    build below only if post_text is absent (defensive; the queue gate means
    this should not happen for any row this function is ever handed)."""
    video_type = row.get("video_type") or detect_video_type(row.get("duration_sec"))
    county = row.get("county") or ""
    variant_key = row.get("variant_key") or ""

    yt_post_text = (row.get("post_text") or {}).get("youtube")
    if yt_post_text and yt_post_text.get("description"):
        title = (yt_post_text.get("title") or row.get("title") or "").strip()
        if not title:
            raise MetadataValidationError("row has no title (title_chosen equivalent) -- refusing to upload")
        _assert_no_banned_terms("title", title)

        description = yt_post_text["description"]
        _assert_no_banned_terms("description", description)

        pinned_comment_text = yt_post_text.get("pinned_comment") or build_pinned_comment(
            yt_post_text.get("link") or row.get("short_url") or ""
        )
        _assert_no_banned_terms("pinned_comment", pinned_comment_text)

        utm_link = yt_post_text.get("link") or row.get("short_url") or ""
        tags = build_tags(row.get("hashtags"))
        for t in tags:
            _assert_no_banned_terms("tag", t)

        return {
            "variant_id": row["variant_id"],
            "reel_id": row.get("reel_id"),
            "county": county,
            "variant_key": variant_key,
            "video_type": video_type,
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": CATEGORY_ID,
            "pinned_comment_text": pinned_comment_text,
            "utm_link": utm_link,
        }

    title = (row.get("title") or "").strip()
    if not title:
        raise MetadataValidationError("row has no title (title_chosen equivalent) -- refusing to upload")
    _assert_no_banned_terms("title", title)

    utm_link = build_utm_link(row.get("landing_url"), county, variant_key, video_type)

    description = build_description(utm_link, county, video_type,
                                     sale_type=row.get("sale_type"), auction_date=row.get("auction_date"))
    _assert_no_banned_terms("description", description)

    pinned_comment_text = build_pinned_comment(utm_link)
    tags = build_tags(row.get("hashtags"))
    for t in tags:
        _assert_no_banned_terms("tag", t)

    return {
        "variant_id": row["variant_id"],
        "reel_id": row.get("reel_id"),
        "county": county,
        "variant_key": variant_key,
        "video_type": video_type,
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": CATEGORY_ID,
        "pinned_comment_text": pinned_comment_text,
        "utm_link": utm_link,
    }
