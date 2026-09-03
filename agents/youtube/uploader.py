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
        lib.rest_update("youtube_uploads", f"id=eq.{row_id}", {
            "upload_status": "uploaded",
            "youtube_video_id": video_id,
            "uploaded_at": "now()",
        })
        return {"status": "uploaded", "youtube_video_id": video_id, "row_id": row_id}
    except Exception as e:  # noqa: BLE001 -- must always land a status, never crash silently
        lib.rest_update("youtube_uploads", f"id=eq.{row_id}", {
            "upload_status": "failed",
            "error_text": str(e)[:2000],
        })
        return {"status": "failed", "error": str(e), "row_id": row_id}


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

    queue = get_publish_queue()[:remaining]
    if not queue:
        print("youtube_publish_queue is empty (no qa_pass=true + HTTP-200 + Ariel-approved candidates). Nothing to do.")
        return 0

    results = []
    for row in queue:
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
    # filter (defends against a future edit silently dropping it).
    migration_sql = open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "supabase", "migrations", "20260903f_youtube_publish_lane.sql",
    )).read()
    if "vs.ariel_decision = 'approved'" in migration_sql:
        print("(c) PASS: youtube_publish_queue view hard-filters ariel_decision = 'approved'")
    else:
        print("(c) FAIL: ariel_decision = 'approved' filter not found in the view definition")
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
    args = parser.parse_args()
    if args.self_test:
        sys.exit(self_test())
    sys.exit(run())
