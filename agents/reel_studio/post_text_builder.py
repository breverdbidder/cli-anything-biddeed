#!/usr/bin/env python3
"""agents/reel_studio/post_text_builder.py -- issue #20057 (GTM-8 / M9).

Builds the per-platform post text (YouTube description/title/pinned comment,
Instagram/Facebook/TikTok caption) that carries the clickable
biddeed.ai/r/<code> link IN THE POST ITSELF -- the end-card link burned into
the video frame is not clickable on any platform, which is the whole bug
this issue fixes. Pure functions; the only network/DB call in this module is
the CLI's `backfill` subcommand, which persists the result to
winnerdata.reel_variants.post_text (see supabase/migrations/
20260906j_post_text_publish_gate_20057.sql).

M9: every platform's text uses the variant's OWN short_url
(https://biddeed.ai/r/<code>, minted per-variant by agents/reel_studio/
analyst.py::mint_variant_short_link -- never the reel's shared /reels/<code>
interstitial) so the redirect lands signed-out viewers on that property's
deal page (per docs/spec/20052.md, resolve_reel_link() already resolves a
variant-minted code straight to /deal/<county>/<case>).

Never-list #7 / M7: no unverified numbers are invented here -- title and
hashtags are read verbatim from the already-QA'd reel_variants row (Director/
QA, issue #19782, already validated title_chosen before qa_pass was set).
This module's own defensive banned-terms check is reused from
agents/youtube/metadata_builder.py rather than duplicated.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "youtube"))
import metadata_builder as ymb  # noqa: E402 -- reuse _assert_no_banned_terms + DISCLOSURE_LINE

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

SEE_DEAL_LABEL = "See this deal →"  # "See this deal →"
MAX_YOUTUBE_TITLE_CHARS = 100
MAX_HASHTAGS = 5
MIN_HASHTAGS = 3


class PostTextValidationError(Exception):
    pass


def _clean_hashtags(hashtags: list[str] | None, max_n: int = MAX_HASHTAGS) -> list[str]:
    out: list[str] = []
    seen = set()
    for h in hashtags or []:
        tag = (h or "").strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        if tag.lower() in seen:
            continue
        seen.add(tag.lower())
        out.append(tag)
        if len(out) >= max_n:
            break
    return out


def _truncate_title(title: str, max_chars: int = MAX_YOUTUBE_TITLE_CHARS) -> str:
    title = (title or "").strip()
    if len(title) <= max_chars:
        return title
    return title[: max_chars - 1].rstrip() + "…"


def build_youtube_post_text(row: dict) -> dict:
    """row: a winnerdata.reel_variants row (+ hashtags, short_url, title).
    First line of `description` is the bare https short link so YouTube
    auto-links it -- this is the fix; the prior long UTM-tagged landing_url
    (agents/youtube/metadata_builder.build_utm_link, issue #19788) is not
    used here because it is not what a viewer taps in the post text. The
    short link's own redirect (docs/spec/20052.md resolve_reel_link()) is
    what stamps utm_source=reel_variant&utm_medium=short_link server-side --
    tagging is not lost, just moved to the resolver, matching how every
    other reel distribution surface already links out."""
    short_url = row.get("short_url")
    if not short_url:
        raise PostTextValidationError("row has no short_url -- cannot build a clickable link")
    title = _truncate_title(row.get("title") or "")
    if not title:
        raise PostTextValidationError("row has no title")
    ymb._assert_no_banned_terms("title", title)

    hashtags = _clean_hashtags(row.get("hashtags"))
    link_line = f"{SEE_DEAL_LABEL} {short_url}"
    description_lines = [link_line, title]
    if hashtags:
        description_lines.append(" ".join(hashtags))
    description_lines.append("")
    description_lines.append(ymb.DISCLOSURE_LINE)
    description = "\n".join(description_lines)
    ymb._assert_no_banned_terms("description", description)

    pinned_comment = link_line
    ymb._assert_no_banned_terms("pinned_comment", pinned_comment)

    return {
        "title": title,
        "description": description,
        "pinned_comment": pinned_comment,
        "pinned_comment_id": None,
        "link": short_url,
    }


def build_social_caption(row: dict, platform: str) -> dict:
    """Shared builder for Instagram Reels / Facebook / TikTok -- none of
    these render a clickable link in the caption itself (issue body: "IG
    captions are not clickable"; TikTok/Facebook captions treated the same
    here, conservatively, since the issue does not carve out an exception
    for either). The caption still leads with the link so a viewer who
    copies/screenshots it, or the platform's own link-detection, has the
    best chance of surfacing it -- the actual one-tap path on these
    platforms is the account's link-in-bio target (see
    record_link_in_bio_targets() below), not the caption text."""
    short_url = row.get("short_url")
    if not short_url:
        raise PostTextValidationError("row has no short_url -- cannot build a caption link")
    bare_link = short_url.split("://", 1)[-1]  # "biddeed.ai/r/<code>", no scheme, per issue text
    title = (row.get("title") or "").strip()
    if not title:
        raise PostTextValidationError("row has no title")
    ymb._assert_no_banned_terms("title", title)

    hashtags = _clean_hashtags(row.get("hashtags"))
    link_line = f"{SEE_DEAL_LABEL} {bare_link}"
    caption_lines = [link_line, title]
    if hashtags:
        caption_lines.append(" ".join(hashtags))
    caption = "\n".join(caption_lines)
    ymb._assert_no_banned_terms("caption", caption)

    return {
        "caption": caption,
        "link_in_bio_target": row.get("landing_url") or short_url,
        "note": (
            f"{platform} does not render a clickable link in the caption -- "
            "the viewer must type or scan the URL above, or tap the account's "
            "link-in-bio target (kept pointed at this deal via "
            "winnerdata.link_in_bio_targets)."
        ),
    }


def build_post_text(row: dict) -> dict:
    """row: winnerdata.reel_variants joined with biddeed_reels (title,
    hashtags, short_url, landing_url). Returns the full post_text jsonb
    value keyed by platform (see migration for the exact jsonb path the
    youtube_publish_queue gate checks: post_text->'youtube'->>'description').
    Keyed by platform only, not platform+lang -- each reel_variants row is
    already single-language (translations get their own row, own short_code,
    own hashtags -- issue #20032/#19793), so nesting by lang inside the jsonb
    would duplicate a dimension the row already carries. INFERRED reading of
    the issue's "per variant, per platform, per lang" phrasing -- documented
    in docs/spec/20057.md."""
    return {
        "youtube": build_youtube_post_text(row),
        "instagram": build_social_caption(row, "Instagram"),
        "facebook": build_social_caption(row, "Facebook"),
        "tiktok": build_social_caption(row, "TikTok"),
    }


# ---------------------------------------------------------------------------
# CLI -- backfill (issue deliverable 5: "Backfill post_text for all 20 EN
# finals now").
# ---------------------------------------------------------------------------

def _fetch_target_rows(lang: str, tts_model: str | None) -> list[dict]:
    where = [f"rv.lang = {lib.sql_str(lang)}"]
    if tts_model:
        where.append(f"rv.tts_model = {lib.sql_str(tts_model)}")
    where_sql = " and ".join(where)
    return lib.run_sql(f"""
        select rv.id, rv.reel_id, rv.variant_key, rv.title, rv.hashtags,
               rv.short_code, rv.short_url, rv.lang, rv.is_draft, rv.qa_pass,
               br.county, br.sale_type, br.case_number, br.landing_url,
               br.page_http_status
        from winnerdata.reel_variants rv
        join winnerdata.biddeed_reels br on br.id = rv.reel_id
        where {where_sql} and rv.is_draft = false
        order by br.county, rv.variant_key;
    """)


def record_link_in_bio_targets(rows: list[dict], post_texts: dict[str, dict]):
    """Inserts one pending link-in-bio candidate row per (variant, platform)
    for instagram/facebook/tiktok -- 'pending' because no IG/TikTok/Facebook
    publish lane exists anywhere in this repo yet (only the dormant YouTube
    lane, #19788, does), so there is no live "newest published deal" to point
    the bio at today. A future publish step flips a row to status='live' when
    it actually posts -- see docs/spec/20057.md for why this session does not
    fabricate a live state. ON CONFLICT is a no-op re-run guard."""
    for row in rows:
        pt = post_texts[row["id"]]
        for platform in ("instagram", "facebook", "tiktok"):
            target_url = pt[platform]["link_in_bio_target"]
            lib.run_sql(f"""
                insert into winnerdata.link_in_bio_targets
                    (platform, variant_id, target_url, status)
                values ({lib.sql_str(platform)}, {lib.sql_str(row["id"])},
                        {lib.sql_str(target_url)}, 'pending')
                on conflict (platform, variant_id) do update
                    set target_url = excluded.target_url;
            """)


def backfill(lang: str, tts_model: str | None, dry_run: bool) -> int:
    rows = _fetch_target_rows(lang, tts_model)
    if not rows:
        print(f"no rows found for lang={lang!r} tts_model={tts_model!r}")
        return 0

    post_texts: dict[str, dict] = {}
    errors = []
    for row in rows:
        try:
            post_texts[row["id"]] = build_post_text(row)
        except PostTextValidationError as e:
            errors.append((row["id"], str(e)))

    if errors:
        for vid, err in errors:
            print(f"SKIPPED variant_id={vid}: {err}")

    ok_rows = [r for r in rows if r["id"] in post_texts]
    print(f"built post_text for {len(ok_rows)}/{len(rows)} rows (lang={lang}, tts_model={tts_model})")

    if dry_run:
        sample = ok_rows[0] if ok_rows else None
        if sample:
            print("--- dry-run sample post_text (no DB write) ---")
            print(json.dumps(post_texts[sample["id"]], indent=2, ensure_ascii=False))
        return 0

    for row in ok_rows:
        lib.run_sql(f"""
            update winnerdata.reel_variants
            set post_text = {lib.sql_jsonb(post_texts[row["id"]])},
                updated_at = now()
            where id = {lib.sql_str(row["id"])};
        """)
    record_link_in_bio_targets(ok_rows, post_texts)
    print(f"wrote post_text to {len(ok_rows)} reel_variants rows + "
          f"{len(ok_rows) * 3} link_in_bio_targets candidate rows (instagram/facebook/tiktok)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    bf = sub.add_parser("backfill")
    bf.add_argument("--lang", default="en")
    bf.add_argument("--tts-model", default=None)
    bf.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.cmd == "backfill":
        sys.exit(backfill(args.lang, args.tts_model, args.dry_run))


if __name__ == "__main__":
    main()
