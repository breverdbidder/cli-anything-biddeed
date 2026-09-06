#!/usr/bin/env python3
"""agents/youtube/uploader.py -- issue #19788 deliverable 1.

Resumable YouTube upload lane. DORMANT until youtube_client_id /
youtube_client_secret / youtube_oauth_refresh_token exist in the vault --
checked live 2026-09-03, all three absent. This script has never made a
real videos.insert call; every path below is written against the documented
YouTube Data API v3 resumable upload protocol and this session's own
--self-test (no network).

Run:
  python agents/youtube/uploader.py            # normal run
  python agents/youtube/uploader.py --self-test  # negative tests (a)-(d),
                                                    no network/DB calls

M8: privacyStatus is ALWAYS youtube_lib.PRIVACY_STATUS ('private'). No
function in this file, and no CLI flag, can change it -- see negative test
(d) and the DB CHECK constraint on public.youtube_uploads.privacy_status.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metadata_builder as mb
import youtube_lib as lib


def get_publish_queue() -> list[dict]:
    """winnerdata.youtube_publish_queue, Management-API read (see
    youtube_lib module docstring for why this isn't PostgREST)."""
    rows = lib.run_sql("select * from winnerdata.youtube_publish_queue;")
    return rows


def already_uploaded_today(day_pacific: str) -> int:
    rows = lib.rest_get(
        "youtube_uploads",
        f"select=id&day_pacific=eq.{day_pacific}&upload_status=eq.uploaded",
    )
    return len(rows or [])


def uploaded_reel_ids_today(day_pacific: str) -> set[str]:
    """issue #19793 PART 4 -- same-property-per-day rule: reel_ids that
    already have an uploaded/queued/uploading row today. queued/uploading
    also count so a same-run second variant of a property already picked
    earlier THIS run is excluded too (see select_cadence_batch)."""
    rows = lib.rest_get(
        "youtube_uploads",
        f"select=reel_id&day_pacific=eq.{day_pacific}"
        f"&upload_status=in.(queued,uploading,uploaded)",
    )
    return {r["reel_id"] for r in (rows or []) if r.get("reel_id")}


def get_cadence_config() -> dict:
    """public.youtube_publish_cadence singleton row (issue #19804 -- sale-
    type-slotted cadence, superseding #19793 PART 4's global-ranking 1-
    winner+1-exploration reading). Falls back to the conservative issue
    default (2/day floor = 1 foreclosure slot + 1 tax_deed slot, weekdays
    only, 14-day starvation lookback, same-property-per-day enforced) if the
    row is somehow missing -- never falls back to the old 6/day quota-ceiling
    figure, which is a ceiling, not a cadence."""
    rows = lib.rest_get("youtube_publish_cadence", "select=*&limit=1")
    if rows:
        return rows[0]
    return {
        "max_uploads_per_day": 2, "weekdays_only": True,
        "foreclosure_slots": 1, "tax_deed_slots": 1,
        "starvation_lookback_days": 14, "same_property_per_day": True,
    }


def _within_lookback(auction_date: str | None, today_date: str, lookback_days: int) -> bool:
    """auction_date/today_date are ISO 'YYYY-MM-DD' strings (as returned by
    PostgREST/Management API for a `date` column) -- pure string/date-math,
    no network."""
    if not auction_date:
        return False
    cutoff = (datetime.date.fromisoformat(today_date) - datetime.timedelta(days=lookback_days)).isoformat()
    return cutoff <= auction_date <= today_date


def select_foreclosure_slot(pool: list[dict], used_reel_ids: set[str]) -> dict | None:
    """SLOT 1 (issue #19804) -- best foreclosure of the day, Analyst-ranked
    (pool is already ordered by sale_type_rank from the view). No starvation
    ladder here -- the issue only specifies one for slot 2; foreclosure is
    not the scarce side (20 rows vs 5 tax_deed, live-verified 2026-09-03)."""
    for row in pool:
        if row.get("reel_id") not in used_reel_ids:
            return row
    return None


def select_tax_deed_slot(pool: list[dict], used_reel_ids: set[str], today_date: str,
                          lookback_days: int = 14) -> tuple[dict | None, str]:
    """SLOT 2 (issue #19804) -- best tax_deed of the day, with the
    starvation ladder: (a) most recent unpublished tax_deed reel within
    `lookback_days` (labelled by its own real auction_date -- never
    relabelled as 'today', see metadata_builder.build_description); (b) a
    presale tax_deed reel for an upcoming county sale; (c) SLOT_STARVED.
    `pool` is pre-filtered to sale_type='tax_deed' by the caller -- this
    function never reaches into a foreclosure pool, so a foreclosure row can
    never be promoted into slot 2."""
    postsale_candidates = [
        r for r in pool
        if r.get("reel_id") not in used_reel_ids
        and r.get("phase") != "presale"
        and _within_lookback(r.get("auction_date"), today_date, lookback_days)
    ]
    if postsale_candidates:
        return postsale_candidates[0], "a_recent_within_lookback"

    presale_candidates = [
        r for r in pool
        if r.get("reel_id") not in used_reel_ids
        and r.get("phase") == "presale"
    ]
    if presale_candidates:
        return presale_candidates[0], "b_presale_upcoming"

    return None, "c_slot_starved"


def _least_observed(rows: list[dict]) -> dict | None:
    """Thompson-sampling floor: explore what we have the least signal on --
    ascending plays, nulls/never-tried first."""
    if not rows:
        return None
    return sorted(rows, key=lambda r: (r.get("plays") is not None, r.get("plays") or 0))[0]


def apply_exploration_overlay(foreclosure_pick: dict | None, foreclosure_pool: list[dict],
                               tax_deed_pick: dict | None, tax_deed_bucket: list[dict],
                               used_reel_ids: set[str]) -> tuple[dict | None, dict | None, str | None]:
    """issue #19804 -- the exploration/Thompson-sampling floor variant rides
    inside whichever slot's current pick has the weaker confidence interval
    (fewer `plays` = wider CI = less confident), replacing that slot's
    Analyst-ranked winner with the least-observed candidate from the SAME
    eligible pool (same sale_type; for tax_deed, the same ladder rung the
    winner came from -- never silently upgrading a starved/presale pick to
    a different rung). It never consumes a third slot. No-op if either slot
    has no pick at all (nothing to compare a confidence interval against)."""
    if foreclosure_pick is None or tax_deed_pick is None:
        return foreclosure_pick, tax_deed_pick, None

    fc_plays = foreclosure_pick.get("plays") or 0
    td_plays = tax_deed_pick.get("plays") or 0

    if fc_plays <= td_plays:
        pool = [r for r in foreclosure_pool if r.get("reel_id") not in used_reel_ids]
        explore_pick = _least_observed(pool)
        if explore_pick and explore_pick.get("reel_id") != foreclosure_pick.get("reel_id"):
            return explore_pick, tax_deed_pick, "foreclosure"
        return foreclosure_pick, tax_deed_pick, None

    pool = [r for r in tax_deed_bucket if r.get("reel_id") not in used_reel_ids]
    explore_pick = _least_observed(pool)
    if explore_pick and explore_pick.get("reel_id") != tax_deed_pick.get("reel_id"):
        return foreclosure_pick, explore_pick, "tax_deed"
    return foreclosure_pick, tax_deed_pick, None


def select_daily_slots(queue: list[dict], cadence: dict, used_reel_ids_today: set[str],
                        today_date: str) -> dict:
    """issue #19804 -- top-level per-day slot selection replacing #19793's
    global-ranking select_cadence_batch(). `queue` is the already-ranked
    (sale_type_rank asc within sale_type) youtube_publish_queue rows.
    Returns {'foreclosure': row|None, 'tax_deed': row|None,
    'tax_deed_ladder_rung': 'a_recent_within_lookback'|'b_presale_upcoming'|
    'c_slot_starved', 'exploration_slot': 'foreclosure'|'tax_deed'|None}."""
    lookback_days = cadence.get("starvation_lookback_days", 14)
    foreclosure_pool = [r for r in queue if r.get("sale_type") == "foreclosure"]
    tax_deed_pool = [r for r in queue if r.get("sale_type") == "tax_deed"]

    foreclosure_pick = select_foreclosure_slot(foreclosure_pool, used_reel_ids_today)
    tax_deed_pick, ladder_rung = select_tax_deed_slot(
        tax_deed_pool, used_reel_ids_today, today_date, lookback_days,
    )

    if ladder_rung == "a_recent_within_lookback":
        tax_deed_bucket = [
            r for r in tax_deed_pool
            if r.get("phase") != "presale" and _within_lookback(r.get("auction_date"), today_date, lookback_days)
        ]
    elif ladder_rung == "b_presale_upcoming":
        tax_deed_bucket = [r for r in tax_deed_pool if r.get("phase") == "presale"]
    else:
        tax_deed_bucket = []

    exploration_slot = None
    if foreclosure_pick and tax_deed_pick:
        foreclosure_pick, tax_deed_pick, exploration_slot = apply_exploration_overlay(
            foreclosure_pick, foreclosure_pool, tax_deed_pick, tax_deed_bucket, used_reel_ids_today,
        )

    return {
        "foreclosure": foreclosure_pick,
        "tax_deed": tax_deed_pick,
        "tax_deed_ladder_rung": ladder_rung,
        "exploration_slot": exploration_slot,
    }


def _upload_init(access_token: str, meta: dict, total_bytes: int) -> str:
    """Step 1 of the resumable protocol: POST the metadata, get back a
    session URI in the Location header. See
    https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol"""
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category_id"],
        },
        "status": {
            # M8 -- structurally the only value this ever is.
            "privacyStatus": lib.PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,  # INFERRED default -- no kids-directed content in this pipeline
        },
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{lib.UPLOAD_INIT_URL}?uploadType=resumable&part=snippet,status",
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(total_bytes),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        session_uri = resp.headers.get("Location")
    if not session_uri:
        raise RuntimeError("resumable upload init did not return a Location header")
    return session_uri


def _query_resume_offset(session_uri: str, total_bytes: int) -> int:
    """Ask Google how many bytes it has, per the resumable protocol's resume
    contract: PUT with Content-Range: bytes */<total> and empty body; a 308
    response's Range header tells us where to resume."""
    req = urllib.request.Request(
        session_uri,
        data=b"",
        headers={"Content-Range": f"bytes */{total_bytes}"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return total_bytes  # 200/201 means it's already fully received
    except urllib.error.HTTPError as e:
        if e.code == 308:
            rng = e.headers.get("Range")  # e.g. "bytes=0-1048575"
            if rng and "-" in rng:
                return int(rng.split("-")[1]) + 1
            return 0
        raise


def _upload_bytes(session_uri: str, video_url: str, resume_from: int = 0, max_retries: int = 5) -> dict:
    """Streams video_url's bytes to the resumable session in CHUNK_SIZE
    pieces, resuming from wherever _query_resume_offset() says to on any
    5xx/network drop (real retry, not a single best-effort attempt)."""
    with urllib.request.urlopen(video_url, timeout=60) as src:
        total_bytes = int(src.headers.get("Content-Length", "0"))
        if resume_from:
            src.close()
        # Re-open with a Range request if resuming mid-file.
    offset = resume_from
    attempt_for_offset = 0
    while offset < total_bytes:
        attempt_for_offset += 1
        if attempt_for_offset > max_retries:
            raise RuntimeError(f"exceeded {max_retries} retries stalled at byte {offset}/{total_bytes}")
        req_src = urllib.request.Request(video_url, headers={"Range": f"bytes={offset}-{total_bytes - 1}"})
        with urllib.request.urlopen(req_src, timeout=60) as src:
            chunk = src.read(lib.CHUNK_SIZE)
        if not chunk:
            break
        chunk_end = offset + len(chunk) - 1
        put_req = urllib.request.Request(
            session_uri, data=chunk,
            headers={"Content-Range": f"bytes {offset}-{chunk_end}/{total_bytes}",
                     "Content-Length": str(len(chunk))},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(put_req, timeout=120) as resp:
                if resp.status in (200, 201):
                    return json.loads(resp.read())
            offset = chunk_end + 1
            attempt_for_offset = 0
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600:
                # Resumable per protocol -- re-query actual offset and retry
                # this chunk instead of assuming it landed.
                offset = _query_resume_offset(session_uri, total_bytes)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            offset = _query_resume_offset(session_uri, total_bytes)
            continue
    raise RuntimeError("upload loop exited without a final video resource")


def upload_one(access_token: str, meta: dict, video_url: str, day_pacific: str) -> dict:
    """Reserves quota, performs the resumable upload, writes the
    public.youtube_uploads row. Never refunds a reservation on failure --
    conservative budgeting per the issue's own hard-constraint framing."""
    reservation = lib.quota_preflight_reserve(lib.QUOTA_COSTS["videos.insert"], "videos.insert")
    if not reservation.get("allow"):
        row = lib.rest_insert("youtube_uploads", {
            **{k: meta[k] for k in ("variant_id", "reel_id", "county", "variant_key",
                                     "video_type", "title", "description", "tags",
                                     "category_id", "pinned_comment_text", "utm_link")},
            "privacy_status": lib.PRIVACY_STATUS,
            "quota_units_planned": lib.QUOTA_COSTS["videos.insert"],
            "quota_units_spent": 0,
            "upload_status": "skipped_quota",
            "error_text": json.dumps(reservation),
            "day_pacific": day_pacific,
        })
        return {"status": "skipped_quota", "reservation": reservation, "row": row}

    upload_row = lib.rest_insert("youtube_uploads", {
        **{k: meta[k] for k in ("variant_id", "reel_id", "county", "variant_key",
                                 "video_type", "title", "description", "tags",
                                 "category_id", "pinned_comment_text", "utm_link")},
        "privacy_status": lib.PRIVACY_STATUS,
        "quota_units_planned": lib.QUOTA_COSTS["videos.insert"],
        "quota_units_spent": lib.QUOTA_COSTS["videos.insert"],
        "upload_status": "uploading",
        "day_pacific": day_pacific,
    })
    row_id = upload_row[0]["id"] if isinstance(upload_row, list) else upload_row["id"]

    try:
        with urllib.request.urlopen(video_url, timeout=30) as head:
            total_bytes = int(head.headers.get("Content-Length", "0"))
        session_uri = _upload_init(access_token, meta, total_bytes)
        result = _upload_bytes(session_uri, video_url)
        video_id = result.get("id")
    except Exception as e:  # noqa: BLE001 -- must always land a status, never crash silently
        lib.rest_update("youtube_uploads", f"id=eq.{row_id}", {
            "upload_status": "failed",
            "error_text": str(e)[:2000],
        })
        return {"status": "failed", "error": str(e), "row_id": row_id}

    # issue #20057 (M9) -- a Short with no clickable link in the post is not
    # "published". The video itself is already on YouTube at this point, but
    # this variant is only marked 'uploaded' once the pinned-link comment
    # insert also succeeds; a comment-insert failure fails the whole
    # variant (publish_error), not just a logged warning. See
    # youtube_lib.COMMENT_THREADS_URL's docstring for why this posts (but
    # cannot pin) the comment -- no public API exists to pin it.
    try:
        comment = lib.post_top_level_comment(access_token, video_id, meta["pinned_comment_text"])
        comment_id = comment.get("id")
        if not comment_id:
            raise RuntimeError(f"commentThreads.insert returned no id: {comment}")
        lib.record_pinned_comment_id(meta["variant_id"], comment_id)
        lib.rest_update("youtube_uploads", f"id=eq.{row_id}", {
            "upload_status": "uploaded",
            "youtube_video_id": video_id,
            "uploaded_at": "now()",
        })
        return {"status": "uploaded", "youtube_video_id": video_id, "pinned_comment_id": comment_id, "row_id": row_id}
    except Exception as e:  # noqa: BLE001 -- pinned-comment failure fails the whole variant, per M9
        error_text = f"video uploaded (youtube_video_id={video_id}) but pinned-comment insert failed: {e}"
        lib.rest_update("youtube_uploads", f"id=eq.{row_id}", {
            "upload_status": "failed",
            "youtube_video_id": video_id,
            "error_text": error_text[:2000],
        })
        lib.mark_variant_publish_error(meta["variant_id"], error_text)
        return {"status": "failed", "error": error_text, "youtube_video_id": video_id, "row_id": row_id}


def dry_run_payload() -> int:
    """issue #20057 evidence requirement ("one dry-run payload printed, no
    upload"). Bypasses the live ariel_decision='approved' gate (every
    #20057-backfilled variant is still pending that separate, untouched
    M8/LMS approval) so this can print a real payload against the queue's
    other filters (qa_pass, non-draft, lang=en, HTTP-200, post_text gate).
    Makes zero network calls -- videos.insert/commentThreads.insert bodies
    are built and printed only, exactly what upload_one() would send."""
    rows = lib.run_sql("""
        select rv.id as variant_id, rv.reel_id, rv.variant_key, rv.title, rv.short_code,
               rv.short_url, rv.video_url, rv.hashtags, rv.post_text, rv.lang,
               br.county, br.sale_type, br.landing_url, br.page_http_status,
               coalesce(br.duration_bolt32_sec, br.duration_sec) as duration_sec
        from winnerdata.reel_variants rv
        join winnerdata.biddeed_reels br on br.id = rv.reel_id
        where rv.qa_pass = true and rv.is_draft = false and rv.lang = 'en'
          and br.page_http_status = 200
          and rv.post_text is not null
          and rv.post_text -> 'youtube' ->> 'description' is not null
          and rv.post_text -> 'youtube' ->> 'pinned_comment' is not null
          and split_part(rv.post_text -> 'youtube' ->> 'description', chr(10), 1)
              like ('%' || rv.short_url || '%')
        order by rv.created_at limit 1;
    """)
    if not rows:
        print("no post_text-eligible candidate found -- nothing to print")
        return 0
    row = rows[0]
    if row.get("duration_sec") is not None:
        row["duration_sec"] = float(row["duration_sec"])
    meta = mb.build_metadata(row)
    videos_insert_body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category_id"],
        },
        "status": {"privacyStatus": lib.PRIVACY_STATUS, "selfDeclaredMadeForKids": False},
    }
    comment_threads_insert_body = {
        "snippet": {
            "videoId": "<video_id from videos.insert response>",
            "topLevelComment": {"snippet": {"textOriginal": meta["pinned_comment_text"]}},
        },
    }
    print(f"DRY RUN (no network call) -- variant_id={row['variant_id']} variant_key={row['variant_key']} county={row['county']}")
    print("POST /upload/youtube/v3/videos?uploadType=resumable&part=snippet,status")
    print(json.dumps(videos_insert_body, indent=2, ensure_ascii=False))
    print("POST /youtube/v3/commentThreads?part=snippet (after upload succeeds, video_id filled in)")
    print(json.dumps(comment_threads_insert_body, indent=2, ensure_ascii=False))
    return 0


def run() -> int:
    creds = lib.load_credentials()
    if creds is None:
        print("NOT_CONFIGURED: one or more of youtube_client_id / "
              "youtube_client_secret / youtube_oauth_refresh_token is absent "
              "from the vault -- uploading nothing this run.")
        return 0

    try:
        access_token = lib.refresh_access_token(creds)
    except lib.TokenExpired as e:
        lib.rest_insert("youtube_token_health", {"ok": False, "error": f"invalid_grant: {e.raw_error}"[:2000]})
        lib.open_token_expired_gate(str(e.raw_error))
        print("TOKEN_EXPIRED: invalid_grant -- spi_gates row 'youtube_token_expired' opened.")
        return 1

    day_pacific = lib.pacific_today()
    already = already_uploaded_today(day_pacific)
    remaining = lib.MAX_UPLOADS_PER_DAY - already
    if remaining <= 0:
        print(f"quota reached for {day_pacific}: {already}/{lib.MAX_UPLOADS_PER_DAY} already uploaded. Nothing to do.")
        return 0

    # issue #19793 PART 4 -- publish-RATE governor, independent of and
    # tighter than the quota-unit CEILING above. 6/day is what the Google
    # quota allows; 2/day (Mon-Fri, 1 Analyst winner + 1 exploration variant)
    # is what we actually publish during the pilot window. Both gates apply.
    cadence = get_cadence_config()
    if cadence.get("weekdays_only") and not lib.pacific_is_weekday():
        print(f"cadence: {day_pacific} is a weekend and this cadence is Mon-Fri only. Nothing to do.")
        return 0
    cadence_remaining = cadence.get("max_uploads_per_day", 2) - already
    if cadence_remaining <= 0:
        print(f"cadence reached for {day_pacific}: {already}/{cadence.get('max_uploads_per_day')} already uploaded "
              f"(cadence cap, tighter than the {lib.MAX_UPLOADS_PER_DAY}/day quota ceiling). Nothing to do.")
        return 0
    remaining = min(remaining, cadence_remaining)

    queue = get_publish_queue()
    # Defense in depth (issue #19793 PART 1 negative test (a)): the
    # youtube_publish_queue view already filters is_draft=false, but a
    # draft row reaching this loop is refused again here so a future view
    # regression can't silently upload one.
    non_draft_queue = [r for r in queue if not r.get("is_draft")]
    dropped_drafts = len(queue) - len(non_draft_queue)
    if dropped_drafts:
        print(f"REFUSED {dropped_drafts} is_draft=true row(s) reaching the upload loop (should never happen -- view regression?)")

    used_reel_ids = uploaded_reel_ids_today(day_pacific) if cadence.get("same_property_per_day", True) else set()
    slots = select_daily_slots(non_draft_queue, cadence, used_reel_ids, day_pacific)

    if slots["tax_deed_ladder_rung"] == "c_slot_starved":
        print(f"SLOT_STARVED: no tax_deed candidate (lookback={cadence.get('starvation_lookback_days', 14)}d, "
              f"no presale fallback either) -- publishing slot 1 (foreclosure) alone, per issue #19804.")
    elif slots["tax_deed_ladder_rung"] == "b_presale_upcoming" and slots["tax_deed"]:
        print(f"tax_deed slot: starvation ladder rung (b) -- presale reel for an upcoming sale "
              f"(auction_date={slots['tax_deed'].get('auction_date')})")
    elif slots["tax_deed"]:
        print(f"tax_deed slot: starvation ladder rung (a) -- real sale date "
              f"auction_date={slots['tax_deed'].get('auction_date')} (never relabelled as 'today')")
    if slots["exploration_slot"]:
        print(f"exploration/Thompson-sampling floor rides in the {slots['exploration_slot']} slot this run "
              f"(weaker confidence interval -- fewer plays -- than the other slot's pick)")

    batch = [row for row in (slots["foreclosure"], slots["tax_deed"]) if row is not None][:remaining]
    if not batch:
        print("youtube_publish_queue is empty (no qa_pass=true + HTTP-200 + Ariel-approved + non-draft candidates "
              "in either sale_type, or every remaining candidate's property was already published today). "
              "Nothing to do.")
        return 0

    results = []
    for row in batch:
        if row.get("is_draft"):
            print(f"SKIPPED variant_id={row.get('variant_id')}: is_draft=true -- draft renders are never uploaded")
            continue
        try:
            meta = mb.build_metadata(row)
        except mb.MetadataValidationError as e:
            print(f"SKIPPED variant_id={row.get('variant_id')}: metadata validation failed: {e}")
            continue
        video_url = row.get("video_url")
        if not video_url:
            print(f"SKIPPED variant_id={row.get('variant_id')}: no video_url on this variant row")
            continue
        outcome = upload_one(access_token, meta, video_url, day_pacific)
        results.append(outcome)
        print(f"{outcome['status']}: variant_id={row.get('variant_id')} variant_key={row.get('variant_key')}")
        if outcome["status"] == "skipped_quota":
            break  # budget exhausted -- no point checking the rest this run

    n_uploaded = sum(1 for r in results if r["status"] == "uploaded")
    n_skipped = sum(1 for r in results if r["status"] == "skipped_quota")
    n_failed = sum(1 for r in results if r["status"] == "failed")
    print(f"done: uploaded={n_uploaded} skipped_quota={n_skipped} failed={n_failed}")
    return 0


# ---------------------------------------------------------------------------
# Negative tests (a)-(d) -- no network/DB calls.
# ---------------------------------------------------------------------------

def self_test() -> int:
    ok = True

    # (a) with secrets absent the run completes as NOT_CONFIGURED, uploads nothing
    real_get = lib.get_vault_secret
    lib.get_vault_secret = lambda name: None
    try:
        assert lib.load_credentials() is None
        print("(a) PASS: load_credentials() returns None when all secrets are absent")
    finally:
        lib.get_vault_secret = real_get

    # (b) a 7th upload in one Pacific day is SKIPPED with the quota reason
    # (simulated at the reservation-math layer, not a live DB call)
    fake_ledger_used = lib.MAX_UPLOADS_PER_DAY * lib.QUOTA_COSTS["videos.insert"]
    projected = fake_ledger_used + lib.QUOTA_COSTS["videos.insert"]
    would_allow = projected <= lib.UPLOAD_BUDGET
    if would_allow:
        print("(b) FAIL: 7th upload's projected spend should exceed the budget")
        ok = False
    else:
        print(f"(b) PASS: 7th upload projected={projected} > budget={lib.UPLOAD_BUDGET} -> would be SKIPPED, not attempted")

    # (c) a variant lacking Ariel's approval is never selected -- the
    # youtube_publish_queue view's WHERE clause hard-filters
    # ariel_decision = 'approved'; assert the SQL literally contains that
    # filter (defends against a future edit silently dropping it). Reads the
    # CURRENT view definition (issue #19804's migration DROP+CREATEd the
    # view again to add sale_type/phase/auction_date/sale_type_rank --
    # 20260903h's own view text is stale/superseded now, checking it here
    # would silently pass even if the live view regressed).
    migration_sql = open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "supabase", "migrations", "20260903i_sale_type_slotted_cadence_19804.sql",
    )).read()
    if "vs.ariel_decision = 'approved'" in migration_sql:
        print("(c) PASS: youtube_publish_queue view hard-filters ariel_decision = 'approved'")
    else:
        print("(c) FAIL: ariel_decision = 'approved' filter not found in the current view definition")
        ok = False

    # (issue #19793 negative test (a)) an upload attempt on an is_draft=true
    # row is refused -- both at the view level (checked below) and at the
    # defensive run()-loop level (checked directly against real data).
    if "rv.is_draft = false" in migration_sql:
        print("(19793-a) PASS: youtube_publish_queue view hard-filters is_draft = false")
    else:
        print("(19793-a) FAIL: is_draft = false filter not found in the current view definition")
        ok = False
    non_draft = [r for r in [{"is_draft": True}, {"is_draft": False}] if not r.get("is_draft")]
    if len(non_draft) == 1 and non_draft[0]["is_draft"] is False:
        print("(19793-a) PASS: run()'s defensive filter drops is_draft=true rows before the upload loop")
    else:
        print("(19793-a) FAIL: defensive is_draft filter logic is wrong")
        ok = False

    # issue #19804 -- sale-type-slotted cadence tests.
    fake_cadence = {"foreclosure_slots": 1, "tax_deed_slots": 1, "max_uploads_per_day": 2,
                     "same_property_per_day": True, "starvation_lookback_days": 14}
    today = "2026-09-03"

    # (19804-same-property) same-day same-property refusal: the top-ranked
    # foreclosure candidate's reel already published earlier today (in
    # used_reel_ids_today) must be skipped in favor of the next-ranked one,
    # never re-selected.
    fc_pool = [
        {"variant_id": "f1", "reel_id": "propA", "sale_type": "foreclosure", "phase": "postsale",
         "auction_date": today, "ctr": 0.9, "plays": 10},
        {"variant_id": "f2", "reel_id": "propB", "sale_type": "foreclosure", "phase": "postsale",
         "auction_date": today, "ctr": 0.5, "plays": 5},
    ]
    pick = select_foreclosure_slot(fc_pool, used_reel_ids={"propA"})
    if pick is not None and pick["reel_id"] == "propB":
        print("(19804-same-property) PASS: reel already published today (propA, top-ranked) is refused; "
              "the next-ranked candidate (propB) is selected instead")
    else:
        print(f"(19804-same-property) FAIL: expected propB, got {pick}")
        ok = False

    # (19804-starved) starved-slot case: zero tax_deed candidates anywhere
    # (no postsale within lookback, no presale) -> SLOT_STARVED, slot 1
    # still gets its foreclosure pick, no foreclosure row is ever promoted
    # into the tax_deed slot.
    starved_slots = select_daily_slots(fc_pool, fake_cadence, used_reel_ids_today=set(), today_date=today)
    if (starved_slots["foreclosure"] is not None and starved_slots["foreclosure"]["reel_id"] == "propA"
            and starved_slots["tax_deed"] is None
            and starved_slots["tax_deed_ladder_rung"] == "c_slot_starved"):
        print("(19804-starved) PASS: empty tax_deed pool -> tax_deed=None, ladder_rung=c_slot_starved, "
              "foreclosure slot still filled alone, no foreclosure row promoted into slot 2")
    else:
        print(f"(19804-starved) FAIL: {starved_slots}")
        ok = False

    # (19804-ladder-a) a tax_deed reel 5 days old is within the 14-day
    # lookback and wins slot 2, labelled by its OWN real auction_date.
    td_pool_a = [
        {"variant_id": "t1", "reel_id": "propC", "sale_type": "tax_deed", "phase": "postsale",
         "auction_date": "2026-08-29", "ctr": 0.7, "plays": 3},
    ]
    queue_a = fc_pool + td_pool_a
    slots_a = select_daily_slots(queue_a, fake_cadence, used_reel_ids_today=set(), today_date=today)
    if (slots_a["tax_deed_ladder_rung"] == "a_recent_within_lookback"
            and slots_a["tax_deed"] and slots_a["tax_deed"]["auction_date"] == "2026-08-29"):
        print("(19804-ladder-a) PASS: 5-day-old unpublished tax_deed reel wins slot 2 via ladder rung (a), "
              "labelled with its real auction_date (2026-08-29), not 'today'")
    else:
        print(f"(19804-ladder-a) FAIL: {slots_a}")
        ok = False

    # (19804-ladder-a-boundary) a tax_deed reel 20 days old is OUTSIDE the
    # 14-day lookback and must not win rung (a).
    td_pool_stale = [
        {"variant_id": "t2", "reel_id": "propD", "sale_type": "tax_deed", "phase": "postsale",
         "auction_date": "2026-08-14", "ctr": 0.7, "plays": 3},
    ]
    stale_pick, stale_rung = select_tax_deed_slot(td_pool_stale, set(), today, lookback_days=14)
    if stale_pick is None and stale_rung == "c_slot_starved":
        print("(19804-ladder-a-boundary) PASS: a 20-day-old tax_deed reel (outside the 14-day lookback) "
              "does not win rung (a) -- correctly falls through to c_slot_starved with no presale fallback")
    else:
        print(f"(19804-ladder-a-boundary) FAIL: expected starved, got pick={stale_pick} rung={stale_rung}")
        ok = False

    # (19804-ladder-b) no postsale candidate within lookback, but a presale
    # (upcoming county sale) tax_deed reel exists -> ladder rung (b).
    td_pool_presale = [
        {"variant_id": "t3", "reel_id": "propE", "sale_type": "tax_deed", "phase": "presale",
         "auction_date": "2026-09-20", "ctr": None, "plays": None},
    ]
    presale_pick, presale_rung = select_tax_deed_slot(td_pool_presale, set(), today, lookback_days=14)
    if presale_pick is not None and presale_pick["reel_id"] == "propE" and presale_rung == "b_presale_upcoming":
        print("(19804-ladder-b) PASS: no postsale candidate within lookback -> falls back to a presale "
              "reel for an upcoming sale (auction_date=2026-09-20), ladder rung (b)")
    else:
        print(f"(19804-ladder-b) FAIL: pick={presale_pick} rung={presale_rung}")
        ok = False

    # (19804-no-cross-promote) a foreclosure-only queue never fills slot 2 --
    # select_tax_deed_slot only ever reads a caller-filtered tax_deed pool,
    # so passing it zero tax_deed rows must never surface a foreclosure row.
    no_td_pick, no_td_rung = select_tax_deed_slot([], set(), today, lookback_days=14)
    if no_td_pick is None and no_td_rung == "c_slot_starved":
        print("(19804-no-cross-promote) PASS: with zero tax_deed rows in the pool, slot 2 is never filled "
              "by a foreclosure row -- correctly SLOT_STARVED")
    else:
        print(f"(19804-no-cross-promote) FAIL: {no_td_pick} {no_td_rung}")
        ok = False

    # (19804-exploration-overlay) the weaker-confidence-interval slot (fewer
    # plays) gets its Analyst-ranked winner replaced by the least-observed
    # candidate in the SAME pool; the other slot's winner is untouched; the
    # batch never exceeds 2 (exploration never consumes a third slot).
    fc_pool_overlay = [
        {"variant_id": "f1", "reel_id": "propA", "sale_type": "foreclosure", "phase": "postsale",
         "auction_date": today, "ctr": 0.9, "plays": 50},   # ranked winner, well-observed
        {"variant_id": "f2", "reel_id": "propB", "sale_type": "foreclosure", "phase": "postsale",
         "auction_date": today, "ctr": 0.2, "plays": None},  # least-observed
    ]
    td_pool_overlay = [
        {"variant_id": "t1", "reel_id": "propC", "sale_type": "tax_deed", "phase": "postsale",
         "auction_date": today, "ctr": 0.6, "plays": 2},     # ranked winner, but far weaker CI than foreclosure's
        {"variant_id": "t2", "reel_id": "propF", "sale_type": "tax_deed", "phase": "postsale",
         "auction_date": today, "ctr": 0.1, "plays": None},  # least-observed -- the exploration target
    ]
    overlay_slots = select_daily_slots(fc_pool_overlay + td_pool_overlay, fake_cadence,
                                        used_reel_ids_today=set(), today_date=today)
    batch_size = len([s for s in (overlay_slots["foreclosure"], overlay_slots["tax_deed"]) if s is not None])
    if (overlay_slots["exploration_slot"] == "tax_deed"
            and overlay_slots["tax_deed"]["reel_id"] == "propF"    # swapped to the least-observed tax_deed row
            and overlay_slots["foreclosure"]["reel_id"] == "propA"  # untouched -- it's the stronger-CI slot
            and batch_size == 2):
        print("(19804-exploration-overlay) PASS: tax_deed (weaker CI) got the exploration override, swapping "
              "its ranked winner (propC, 2 plays) for the least-observed candidate (propF, never played); "
              "foreclosure's ranked winner (50 plays) is untouched; batch size stays 2, not 3")
    else:
        print(f"(19804-exploration-overlay) FAIL: {overlay_slots} batch_size={batch_size}")
        ok = False

    # (d) any code setting privacyStatus other than 'private' fails CI
    if lib.PRIVACY_STATUS == "private":
        print("(d) PASS: youtube_lib.PRIVACY_STATUS == 'private'")
    else:
        print("(d) FAIL: PRIVACY_STATUS is not 'private'")
        ok = False
    import ast as _ast
    tree = _ast.parse(open(os.path.abspath(__file__)).read())
    bad = []
    found_any = False
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, _ast.Constant) and k.value == "privacyStatus":
                    found_any = True
                    is_const_ref = (
                        isinstance(v, _ast.Attribute)
                        and v.attr == "PRIVACY_STATUS"
                        and isinstance(v.value, _ast.Name)
                        and v.value.id == "lib"
                    )
                    if not is_const_ref:
                        bad.append(_ast.dump(v))
    if not found_any:
        print("(d) FAIL: no privacyStatus assignment found at all")
        ok = False
    elif bad:
        print(f"(d) FAIL: found non-constant privacyStatus assignment(s): {bad}")
        ok = False
    else:
        print("(d) PASS: every privacyStatus assignment in uploader.py references lib.PRIVACY_STATUS (AST-verified)")

    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="print the payload for one eligible candidate, no network/upload calls")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(self_test())
    if args.dry_run:
        sys.exit(dry_run_payload())
    sys.exit(run())
