#!/usr/bin/env python3
"""BOLT32 BRIDGE -- agents/reel_studio/bolt32_bridge.py (issue #19782 Phase B).

Calls the bolt32 assembler (scripts/biddeed_reels_lib.py, landed via
issue #19779) with ONE reel_variant's own title/script/voice_tags instead
of bolt32's own title generator -- so each variant renders as its own
distinct 32s video, using the parent property's already-fetched imagery
(bolt32 never re-fetches Maps imagery; neither does this).

This is a thin adapter, not a fork: it reuses build_bolt32_beat_map(),
assemble_video_bolt32(), elevenlabs_tts_v3(), assert_bolt32_duration(),
assert_bolt32_tts_model() unchanged from scripts/biddeed_reels_lib.py.

Cost note: each call makes one real ElevenLabs TTS call (small, a few
cents for a ~32s script) and one real ffmpeg render. Per CLAUDE.md's
"spend_over_10: STOP and confirm", this module is written to be called
per-variant deliberately (not looped unattended over all pending variants)
until Ariel authorizes full Phase B batch rendering.

CLI:
  python3 bolt32_bridge.py render --variant-id UUID
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse as up

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402


def _nearest_beat_line(beats: list[dict], target_start_s: float) -> str:
    if not beats:
        return ""
    best = min(beats, key=lambda b: abs(float(b.get("start_s", 0)) - target_start_s))
    return str(best.get("line", ""))


def fetch_variant_and_reel(variant_id: str) -> tuple[dict, dict]:
    vrows = lib.run_sql(f"""
        select id, reel_id, variant_key, variant_dna, title, script, caption_groups,
               voice_tags, hashtags, short_code, short_url, status, lang
        from winnerdata.reel_variants where id = {lib.sql_str(variant_id)};
    """)
    if not vrows:
        raise ValueError(f"no reel_variants row for id={variant_id}")
    variant = vrows[0]
    for col in ("variant_dna", "script", "caption_groups", "voice_tags"):
        if isinstance(variant.get(col), str):
            variant[col] = json.loads(variant[col])

    rrows = lib.run_sql(f"""
        select id, case_number, county, sale_type, auction_date, condition_json,
               aerial_wide_url, aerial_tight_url, street_url, short_url
        from winnerdata.biddeed_reels where id = {lib.sql_str(variant['reel_id'])};
    """)
    if not rrows:
        raise ValueError(f"no parent biddeed_reels row for reel_id={variant['reel_id']}")
    reel = rrows[0]
    if isinstance(reel.get("condition_json"), str):
        reel["condition_json"] = json.loads(reel["condition_json"])
    return variant, reel


def render_variant_bolt32(variant_id: str, mode: str = "final") -> dict:
    """mode='final' (default, unchanged behavior) uses eleven_v3/V2_BRAND_VOICE_ID
    and writes is_draft=false/render_mode='final'. mode='draft' (issue #19793
    PART 1) uses kokoro (voice keyed off the row's own `lang`, $0, no
    ElevenLabs credit spent), burns the DRAFT AUDIO watermark, and writes
    is_draft=true/render_mode='draft'/pending_final_voice=true so the
    re-render queue is explicit once ElevenLabs credits are topped up."""
    if mode not in ("draft", "final"):
        raise ValueError(f"mode must be 'draft' or 'final', got {mode!r}")
    is_draft = mode == "draft"

    variant, reel = fetch_variant_and_reel(variant_id)
    result = {"variant_id": variant_id, "variant_key": variant["variant_key"], "mode": mode, "status": None, "error": None}

    if variant.get("status") == "approved":
        result.update(status="blocked_approved_row", error="M8: refusing to touch an already-approved variant")
        return result

    if not (reel.get("aerial_wide_url") and reel.get("aerial_tight_url") and reel.get("street_url")):
        result.update(status="error", error="parent reel missing imagery -- run v2/presale pipeline on the reel first")
        return result

    lang = variant.get("lang") or "en"

    beats = variant["script"].get("beats", [])
    title_chosen = variant["title"]
    setup_line = _nearest_beat_line(beats, 4.0)
    payoff_line = _nearest_beat_line(beats, 24.0)
    loop_line = _nearest_beat_line(beats, 29.5)
    script_text_v3 = " ".join(b.get("line", "") for b in sorted(beats, key=lambda b: float(b.get("start_s", 0))))
    eleven_tags = (variant.get("voice_tags") or {}).get("eleven_v3_tags") or []
    if eleven_tags and not is_draft:
        script_text_v3 = " ".join(eleven_tags[:1]) + " " + script_text_v3

    beat_map = lib.build_bolt32_beat_map(title_chosen, setup_line, payoff_line, loop_line)
    condition = reel.get("condition_json") or {}

    date_key = reel["auction_date"].isoformat() if hasattr(reel["auction_date"], "isoformat") else reel["auction_date"]
    case_key = up.quote(reel["case_number"].replace(" ", "_").replace("/", "-"), safe="")
    mode_dir = "draft" if is_draft else "final"
    prefix = f"{date_key}/{case_key}/variant_{variant['variant_key']}_{lang}_{mode_dir}"

    with tempfile.TemporaryDirectory() as tmp:
        wide_path = os.path.join(tmp, "aerial_wide.png")
        tight_path = os.path.join(tmp, "aerial_tight.png")
        street_path = os.path.join(tmp, "street.jpg")
        lib.fetch_url_to_file(reel["aerial_wide_url"], wide_path)
        lib.fetch_url_to_file(reel["aerial_tight_url"], tight_path)
        lib.fetch_url_to_file(reel["street_url"], street_path)

        qr_path = os.path.join(tmp, "qr.png")
        lib.generate_qr_png(variant["short_url"], qr_path)
        chip_path = os.path.join(tmp, "chip.png")
        lib.build_cta_chip_png(variant["short_url"].replace("https://", "").replace("http://", ""),
                                "See this deal ->", chip_path)
        qrplate_path = os.path.join(tmp, "qrplate.png")
        lib.build_qr_plate_png(variant["short_url"], "Scan for the deal", qrplate_path)

        if is_draft:
            wav_path = os.path.join(tmp, "voice_bolt32_raw.wav")
            tts_model = "kokoro"
            voice_used = lib.kokoro_tts(script_text_v3, wav_path, lang=lang)
            # biddeed-reels storage bucket's mime allow-list doesn't include
            # audio/wav (live-confirmed this session, HTTP 415) -- transcode
            # to mp3 so the same storage_upload() path every other audio
            # asset in this pipeline uses works unchanged for kokoro too.
            audio_path = os.path.join(tmp, "voice_bolt32.mp3")
            _transcode = subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-qscale:a", "2", audio_path],
                capture_output=True, text=True,
            )
            if _transcode.returncode != 0:
                raise RuntimeError(f"ffmpeg wav->mp3 transcode failed: {_transcode.stderr[-2000:]}")
        else:
            key = os.environ.get("ELEVENLABS_API_KEY") or lib.get_vault_secret("elevenlabs_api_key")
            audio_path = os.path.join(tmp, "voice_bolt32.mp3")
            tts_model = lib.V2_TTS_MODEL
            voice_used = os.environ.get("ELEVENLABS_V2_VOICE_ID", lib.V2_BRAND_VOICE_ID)
            lib.elevenlabs_tts_v3(script_text_v3, key, audio_path)

        audio_url = lib.storage_upload(audio_path, f"{prefix}/voice_bolt32.mp3", "audio/mpeg")

        overlays = {
            "county": lib.county_display(reel["county"]).replace(" County", ""),
            "sale_type_label": (reel.get("sale_type") or "").replace("_", " ").upper(),
            "condition_tier": condition.get("general_condition_tier"),
            "payoff_text": payoff_line,
            "loop_line_text": loop_line,
        }
        images = {"aerial_wide": wide_path, "aerial_tight": tight_path, "street": street_path}
        video_path = os.path.join(tmp, "reel_bolt32.mp4")
        duration_sec = lib.assemble_video_bolt32(images, audio_path, overlays, chip_path, qrplate_path,
                                                   video_path, title_chosen, is_draft=is_draft)

        lib.assert_bolt32_duration(duration_sec)
        lib.assert_bolt32_tts_model(tts_model, is_draft=is_draft)

        video_url = lib.storage_upload(video_path, f"{prefix}/reel_bolt32.mp4", "video/mp4")

        lib.run_sql(f"""
            update winnerdata.reel_variants
            set video_url = {lib.sql_str(video_url)}, tts_model = {lib.sql_str(tts_model)},
                is_draft = {lib.sql_bool(is_draft)}, render_mode = {lib.sql_str(mode)},
                pending_final_voice = {lib.sql_bool(is_draft)},
                updated_at = now()
            where id = {lib.sql_str(variant_id)};
        """)

        result.update(status="bolt32_done", duration_sec=round(duration_sec, 3),
                       video_url=video_url, audio_url=audio_url, beat_map=beat_map,
                       tts_model=tts_model, voice_used=voice_used, is_draft=is_draft, lang=lang)
        return result


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--variant-id", required=True)
    r.add_argument("--mode", choices=["draft", "final"], default="final")
    args = ap.parse_args()
    if args.cmd == "render":
        print(json.dumps(render_variant_bolt32(args.variant_id, mode=args.mode), indent=2, default=str))


if __name__ == "__main__":
    main()
