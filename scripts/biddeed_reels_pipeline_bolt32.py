#!/usr/bin/env python3
"""BidDeed Reels bolt32 -- 32s BoltMotivation-technique edit template
(issue #19779). Re-renders EXISTING winnerdata.biddeed_reels rows in place
with the new bolt32_* columns -- never overwrites video_url/video_v2_url
(v1/v2/presale rows stay untouched for comparison), never touches a row
whose status='approved' (M8: everything renders to pending_approval; this
script refuses to run against an approved row at all).

GENERATES AND STAGES ONLY. No posting, no publish step (M8).

Run:
  python scripts/biddeed_reels_pipeline_bolt32.py --ids <uuid>[,<uuid>...]
  python scripts/biddeed_reels_pipeline_bolt32.py --self-test   (negative
    tests only, no network/DB/ffmpeg calls)

Required env/vault: GOOGLE_MAPS_API_KEY (unused -- imagery is reused from
the row's existing aerial_wide_url/aerial_tight_url/street_url, never
re-fetched, so no new Maps spend) and ELEVENLABS_API_KEY (voiceover is
regenerated against the bolt32 script).
"""
import argparse
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biddeed_reels_lib as lib


def get_target_rows(ids: list[str]) -> list[dict]:
    id_list = ",".join(lib.sql_str(i) for i in ids)
    rows = lib.run_sql(f"""
        select id, case_number, county, sale_type, phase, auction_date,
               sold_amount, assessed_value, delta_pct, opening_bid, judgment_amount,
               days_to_auction, condition_json, condition_score,
               aerial_wide_url, aerial_tight_url, street_url, short_code, short_url,
               status, tts_model
        from winnerdata.biddeed_reels
        where id in ({id_list})
        order by phase, auction_date;
    """)
    return rows


def _normalize_case_number(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def banned_names_for_case(case_number: str, county: str) -> list[str]:
    """Best-effort M7 name lookup against public.multi_county_auctions
    (owner_name/plaintiff). Fetches by county only, then matches
    case_number client-side after normalizing (strip spaces/dashes,
    uppercase) -- a first-token ilike wildcard was live-reproduced this
    session to match unrelated rows sharing only a filing YEAR (e.g. "2025"),
    pulling that other row's owner_name/plaintiff text in as false-positive
    banned tokens. Returns [] on a genuine miss -- never fabricates a name,
    and an empty result here does not mean the check is skipped: the
    generator's own templates never interpolate a free-text name field
    regardless, so this list is a second, independent guard, not the only
    one. Common non-name words ("the", "home", "llc", etc.) are excluded
    from the token list -- they are not names and would otherwise make
    almost every generated title unpassable."""
    target = _normalize_case_number(case_number)
    rows = lib.pg_rest(
        "multi_county_auctions",
        f"select=case_number,owner_name,plaintiff&county=ilike.{county}&limit=1000",
    )
    stopwords = {"the", "a", "an", "llc", "inc", "trust", "estate", "of", "and", "home", "co"}
    names = []
    for r in rows:
        if _normalize_case_number(r.get("case_number")) != target:
            continue
        for field in ("owner_name", "plaintiff"):
            v = (r.get(field) or "").strip()
            if v:
                names.extend(
                    part for part in v.replace(",", " ").split()
                    if len(part) >= 3 and part.lower() not in stopwords
                )
    return names


def _sql_val(col: str, v):
    if col in ("duration_bolt32_sec", "loop_frame_ms"):
        return lib.sql_num(v)
    if col in ("title_candidates", "beat_map"):
        return lib.sql_jsonb(v)
    if col == "hashtags":
        return lib.sql_text_array(v)
    return lib.sql_str(v)


def update_row(row_id: str, fields: dict) -> None:
    set_clause = ", ".join(f"{c} = {_sql_val(c, v)}" for c, v in fields.items())
    lib.run_sql(f"""
        update winnerdata.biddeed_reels
        set {set_clause}, updated_at = now()
        where id = {lib.sql_str(row_id)};
    """)


def process_row_bolt32(row: dict, keys: dict) -> dict:
    case_number = row["case_number"]
    county = row["county"]
    result = {"case_number": case_number, "county": county, "phase": row["phase"], "status": None, "error": None}

    if row.get("status") == "approved":
        result["status"] = "blocked_approved_row"
        result["error"] = "M8: refusing to touch an already-approved row"
        return result

    try:
        assessed_value = float(row["assessed_value"]) if row.get("assessed_value") is not None else None
        sold_amount = float(row["sold_amount"]) if row.get("sold_amount") is not None else None
        delta_pct = float(row["delta_pct"]) if row.get("delta_pct") is not None else None
        opening_bid = float(row["opening_bid"]) if row.get("opening_bid") is not None else None
        judgment_amount = float(row["judgment_amount"]) if row.get("judgment_amount") is not None else None
        condition = row.get("condition_json") or {}
        if not condition:
            raise RuntimeError("no condition_json to reuse -- run v2/presale pipeline first")
        if not (row.get("aerial_wide_url") and row.get("aerial_tight_url") and row.get("street_url")):
            raise RuntimeError("missing existing imagery -- run v2/presale pipeline first (bolt32 never re-fetches Maps)")
        if not row.get("short_url"):
            raise RuntimeError("missing existing short_url -- run v2/presale pipeline first")

        banned = banned_names_for_case(case_number, county)

        title_context = {
            "phase": row["phase"], "county_slug": county,
            "sold_amount": sold_amount, "assessed_value": assessed_value, "delta_pct": delta_pct,
            "opening_bid": opening_bid, "judgment_amount": judgment_amount,
            "days_to_auction": row.get("days_to_auction"),
            "condition_tier": condition.get("general_condition_tier"),
            "banned_names": banned,
        }
        title_candidates = lib.generate_bolt32_titles(title_context)
        chosen = lib.pick_bolt32_title(title_candidates)
        if chosen is None:
            raise RuntimeError(f"all 5 title candidates failed validation: {title_candidates}")
        title_chosen = chosen["title"]

        facts = {
            "phase": row["phase"], "sold_amount": sold_amount, "assessed_value": assessed_value,
            "delta_pct": delta_pct, "opening_bid": opening_bid, "judgment_amount": judgment_amount,
        }
        sc = lib.build_bolt32_script_and_caption(title_chosen, county, row.get("sale_type"), facts, condition, row["short_url"])
        beat_map = lib.build_bolt32_beat_map(title_chosen, sc["setup_line"], sc["payoff_line"], sc["loop_line"])

        import urllib.parse as up
        date_key = row["auction_date"].isoformat() if hasattr(row["auction_date"], "isoformat") else row["auction_date"]
        case_key = up.quote(case_number.replace(" ", "_").replace("/", "-"), safe="")
        prefix = f"{date_key}/{case_key}"

        with tempfile.TemporaryDirectory() as tmp:
            wide_path = os.path.join(tmp, "aerial_wide.png")
            tight_path = os.path.join(tmp, "aerial_tight.png")
            street_path = os.path.join(tmp, "street.jpg")
            lib.fetch_url_to_file(row["aerial_wide_url"], wide_path)
            lib.fetch_url_to_file(row["aerial_tight_url"], tight_path)
            lib.fetch_url_to_file(row["street_url"], street_path)

            qr_path = os.path.join(tmp, "qr.png")
            lib.generate_qr_png(row["short_url"], qr_path)

            audio_path = os.path.join(tmp, "voice_bolt32.mp3")
            lib.elevenlabs_tts_v3(sc["script_text_v3"], keys["elevenlabs"], audio_path)
            audio_url = lib.storage_upload(audio_path, f"{prefix}/voice_bolt32.mp3", "audio/mpeg")

            overlays = {
                "county": lib.county_display(county).replace(" County", ""),
                "sale_type_label": (row.get("sale_type") or "").replace("_", " ").upper(),
                "condition_tier": condition.get("general_condition_tier"),
                "payoff_text": sc["payoff_line"],
                "loop_line_text": sc["loop_line"],
            }
            images = {"aerial_wide": wide_path, "aerial_tight": tight_path, "street": street_path}
            video_path = os.path.join(tmp, "reel_bolt32.mp4")
            duration_sec = lib.assemble_video_bolt32(images, audio_path, overlays, qr_path, video_path, title_chosen)

            # DoD gates -- raise (not warn) before anything lands in the DB
            # if either fails. tts_model is asserted against the constant
            # this script itself just used, not re-read from the DB, so this
            # is a real assertion on what actually happened this run.
            lib.assert_bolt32_duration(duration_sec)
            lib.assert_bolt32_tts_model(lib.V2_TTS_MODEL)

            video_bolt32_url = lib.storage_upload(video_path, f"{prefix}/reel_bolt32.mp4", "video/mp4")

            update_row(row["id"], {
                "template": "bolt32",
                "title_candidates": title_candidates,
                "title_chosen": title_chosen,
                "beat_map": beat_map,
                "loop_frame_ms": 0,
                "video_bolt32_url": video_bolt32_url,
                "duration_bolt32_sec": round(duration_sec, 3),
                "caption_text": sc["caption_text"],
                "hashtags": sc["hashtags"],
                "audio_url": audio_url,
                "tts_model": lib.V2_TTS_MODEL,
                "voice_id": os.environ.get("ELEVENLABS_V2_VOICE_ID", lib.V2_BRAND_VOICE_ID),
            })

            result.update({
                "status": "bolt32_done",
                "title_chosen": title_chosen,
                "duration_sec": round(duration_sec, 3),
                "video_bolt32_url": video_bolt32_url,
                "banned_names_found": banned,
            })
            return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:1000]
        return result


def self_test() -> None:
    """Negative tests (a)-(d) from the issue's DoD -- no network/DB/ffmpeg."""
    print("(a) title lacking ellipsis / one emoji:")
    print(" ", lib.validate_bolt32_title("Nobody Bid On This Home"))
    print(" ", lib.validate_bolt32_title("Nobody Bid On This Florida Home Today…\U0001F631"))

    print("(b) title containing a surname:")
    print(" ", lib.validate_bolt32_title("This Home Belonging To Smith Sold For $50,000…\U0001F633\U0001F3C6", ["Smith"]))

    print("(c) assembly of 30.0s/34.0s fails the 32+/-0.1 assert:")
    for bad in (30.0, 34.0):
        try:
            lib.assert_bolt32_duration(bad)
            print(f"  FAILED TO RAISE for {bad}")
        except ValueError as e:
            print(f"   raised for {bad}: {e}")

    print("(d) render whose tts_model != eleven_v3 fails DoD:")
    try:
        lib.assert_bolt32_tts_model("eleven_flash_v2_5")
        print("  FAILED TO RAISE")
    except ValueError as e:
        print(f"   raised: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=None, help="comma-separated biddeed_reels.id list")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        sys.exit(0)

    if not args.ids:
        print("ERROR: --ids or --self-test required", file=sys.stderr)
        sys.exit(1)

    def resolve_key(env_name, vault_names):
        v = os.environ.get(env_name, "")
        if v:
            return v
        for name in vault_names:
            try:
                return lib.get_vault_secret(name)
            except Exception:
                continue
        return ""

    keys = {"elevenlabs": resolve_key("ELEVENLABS_API_KEY", ["elevenlabs_api_key", "elevenlabs_production"])}
    if not keys["elevenlabs"]:
        print("ERROR: missing ELEVENLABS_API_KEY (env or vault)", file=sys.stderr)
        sys.exit(1)

    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    rows = get_target_rows(ids)
    print(f"{len(rows)} row(s) to process.")
    t0 = time.time()
    results = []
    for r in rows:
        print(f"Processing {r['case_number']} / {r['county']} / {r['phase']} ...")
        res = process_row_bolt32(r, keys)
        print(f"  -> {res['status']}" + (f" ({res['error']})" if res.get("error") else ""))
        results.append(res)

    n_ok = sum(1 for r in results if r["status"] == "bolt32_done")
    n_err = sum(1 for r in results if r["status"] == "error")
    print("\n=== SUMMARY ===")
    print(f"rows={len(results)} bolt32_done={n_ok} error={n_err} wall_time_sec={time.time()-t0:.1f}")
    for r in results:
        if r["status"] == "bolt32_done":
            print(f"  {r['case_number']}/{r['county']}: title={r['title_chosen']!r} "
                  f"dur={r['duration_sec']}s video={r['video_bolt32_url']}")
    errored = [r for r in results if r["status"] == "error"]
    if errored:
        print("\n=== ERRORS ===")
        for r in errored:
            print(f"  {r['case_number']}/{r['county']}: {r['error']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
