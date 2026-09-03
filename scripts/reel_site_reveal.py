#!/usr/bin/env python3
"""bolt32 "site reveal" segment (issue #19785) -- self-contained renderer
module. Does NOT edit scripts/biddeed_reels_lib.py or
scripts/biddeed_reels_pipeline_bolt32.py (owned by #19779/#19782); this
module only *reads* their public constants/helpers and hands back data
those files' own call sites can splice in behind BOLT32_SITE_REVEAL_ENABLED.

What this captures: the REAL deal page at 1080x1920 DPR2 with ?reel=1 (a
query flag the Worker is expected to honour to hide cookie/chat widgets --
this module cannot make the Worker honour it, it only appends the flag and
records whatever comes back). Output = a hero PNG + a short scroll capture
via Playwright's built-in video recorder, plus the QA verdict the issue's
guard rail requires (non-200 or error state = FAIL, not silently skipped).

PID safety (per docs/intent/19678.md's HARD RULES, applied to Chromium
instead of node/next since that's what this module launches): every
capture uses `with sync_playwright() as p:` + try/finally `browser.close()`
-- Playwright's own driver owns the subprocess lifecycle end-to-end, so
there is never a bash-level `pkill`/`killall` by process name anywhere in
this file. One page open at a time (single BrowserContext per capture,
closed before the next one starts) per the issue comment's memory-budget
instruction.

CLI:
  python scripts/reel_site_reveal.py --capture <landing_url> --out <dir>
  python scripts/reel_site_reveal.py --self-test   (offline, no network)
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VIEWPORT = {"width": 1080, "height": 1920}
DEVICE_SCALE_FACTOR = 2
SCROLL_CAPTURE_SECONDS = 3.5
EMAIL_FIELD_SELECTORS = [
    "input[type=email]",
    "input[name*=email i]",
    "input[placeholder*=email i]",
]

# Beat timings this module owns (issue #19785 Part 1). The base bolt32
# beat_map (build_bolt32_beat_map in biddeed_reels_lib.py, owned by #19779)
# keeps its existing "payoff" entry at 20000-28000ms untouched -- this
# module never imports or mutates that function. Splicing (shortening
# payoff to 24000 and inserting site_reveal at 24000-28000) happens only in
# bolt32_beat_map_with_site_reveal() below, which the #19779/#19782 call
# site can opt into.
PAYOFF_SPLIT_MS = 24000
SITE_REVEAL_START_MS = 24000
SITE_REVEAL_END_MS = 28000


def capture_site_reveal(landing_url: str, out_dir: str) -> dict:
    """Loads `landing_url` (with ?reel=1 appended) in a fresh, isolated
    Chromium context, captures a hero PNG + a short scroll-capture MP4, and
    returns the QA verdict. Never raises on a non-200/error page -- that is
    the FAIL case the caller's QA gate must see, not an exception to catch
    around it.
    """
    os.makedirs(out_dir, exist_ok=True)
    sep = "&" if "?" in landing_url else "?"
    capture_url = f"{landing_url}{sep}reel=1"

    result = {
        "page_capture_url": capture_url,
        "page_http_status": None,
        "capture_ms": None,
        "hero_path": None,
        "scroll_video_path": None,
        "has_email_capture": False,
        "qa_pass": False,
        "qa_reason": None,
    }

    t0 = time.perf_counter()
    try:
        _capture_site_reveal_inner(capture_url, out_dir, result)
    finally:
        result["capture_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


def _capture_site_reveal_inner(capture_url: str, out_dir: str, result: dict) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport=VIEWPORT,
                device_scale_factor=DEVICE_SCALE_FACTOR,
                record_video_dir=out_dir,
                record_video_size=VIEWPORT,
            )
            try:
                page = context.new_page()
                try:
                    response = page.goto(capture_url, wait_until="domcontentloaded", timeout=15000)
                    status = response.status if response else None
                    result["page_http_status"] = status

                    if status is None or status >= 400:
                        result["qa_pass"] = False
                        result["qa_reason"] = f"non-200 response ({status}) -- reel FAILS QA per issue guard rail"
                        return

                    hero_path = os.path.join(out_dir, "site_reveal_hero.png")
                    page.screenshot(path=hero_path, full_page=False)
                    result["hero_path"] = hero_path

                    has_email = False
                    for sel in EMAIL_FIELD_SELECTORS:
                        try:
                            if page.locator(sel).first.is_visible(timeout=1000):
                                has_email = True
                                break
                        except Exception:
                            continue
                    result["has_email_capture"] = has_email

                    scroll_target = page.evaluate("document.body.scrollHeight") or VIEWPORT["height"]
                    steps = 12
                    step_pause = SCROLL_CAPTURE_SECONDS / steps
                    for i in range(steps):
                        page.evaluate(f"window.scrollTo(0, {int(scroll_target * (i + 1) / steps)})")
                        page.wait_for_timeout(int(step_pause * 1000))
                        if has_email:
                            for sel in EMAIL_FIELD_SELECTORS:
                                try:
                                    loc = page.locator(sel).first
                                    if loc.is_visible(timeout=200):
                                        loc.click(timeout=500)
                                        break
                                except Exception:
                                    continue

                    result["qa_pass"] = True
                    result["qa_reason"] = "200 OK" if has_email else "200 OK but no email-capture field visible (QA WARN, not FAIL)"
                finally:
                    video = page.video
                    page.close()
                    if video is not None:
                        try:
                            result["scroll_video_path"] = video.path()
                        except Exception:
                            pass
            finally:
                context.close()
        finally:
            browser.close()


def bolt32_beat_map_with_site_reveal(base_beat_map: list[dict]) -> list[dict]:
    """Pure function -- does not mutate `base_beat_map`. Splits the
    "payoff" beat (20000-28000ms in biddeed_reels_lib.build_bolt32_beat_map)
    into a shorter payoff (20000-24000) and inserts "site_reveal"
    (24000-28000). Every other beat is copied through unchanged, including
    their exact start_ms/end_ms, so "loop_line" (28000-31000) and "end"
    (31000-32000) are untouched -- total duration stays 32.0s.
    """
    out = []
    for beat in base_beat_map:
        if beat.get("beat") == "payoff":
            out.append({**beat, "end_ms": PAYOFF_SPLIT_MS})
            out.append({
                "beat": "site_reveal",
                "start_ms": SITE_REVEAL_START_MS,
                "end_ms": SITE_REVEAL_END_MS,
                "text": "every number you just heard is on the page for this address",
            })
        else:
            out.append(dict(beat))
    return out


def bolt32_segments_with_site_reveal(base_segments: list[dict], site_reveal_img: str) -> list[dict]:
    """Pure function -- splits BOLT32_SEGMENTS' 8.0s "payoff" entry into a
    4.0s payoff + a 4.0s "site_reveal" entry pointing at the captured
    still. Every other segment (hook/setup/tension x2/loop_line/end) passes
    through unchanged, so total duration stays 32.0s.
    """
    out = []
    for seg in base_segments:
        if seg["beat"] == "payoff":
            out.append({**seg, "seconds": seg["seconds"] / 2})
            out.append({"beat": "site_reveal", "img": site_reveal_img, "seconds": seg["seconds"] / 2})
        else:
            out.append(dict(seg))
    return out


def make_phone_frame(hero_png: str, out_path: str, frame_w: int = 680, frame_h: int = 1360,
                      corner_radius: int = 48, bezel_px: int = 14) -> str:
    """Composites the captured hero screenshot into a rounded-corner,
    bezelled phone-inset PNG with a soft drop shadow on a transparent
    canvas, ready for ffmpeg overlay. Pure PIL -- no ffmpeg dependency for
    this step so it's independently testable.
    """
    from PIL import Image, ImageDraw, ImageFilter

    hero = Image.open(hero_png).convert("RGB")
    hero_ratio = frame_w / hero.width
    hero = hero.resize((frame_w, int(hero.height * hero_ratio)))
    hero = hero.crop((0, 0, frame_w, min(frame_h, hero.height)))
    if hero.height < frame_h:
        pad = Image.new("RGB", (frame_w, frame_h), (2, 6, 23))
        pad.paste(hero, (0, 0))
        hero = pad

    mask = Image.new("L", (frame_w, frame_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, frame_w, frame_h], radius=corner_radius, fill=255)

    canvas_w, canvas_h = frame_w + bezel_px * 2 + 40, frame_h + bezel_px * 2 + 40
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [20, 28, 20 + frame_w + bezel_px * 2, 28 + frame_h + bezel_px * 2],
        radius=corner_radius + bezel_px, fill=(0, 0, 0, 140),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow)

    bezel = Image.new("RGBA", (frame_w + bezel_px * 2, frame_h + bezel_px * 2), (0, 0, 0, 0))
    ImageDraw.Draw(bezel).rounded_rectangle(
        [0, 0, frame_w + bezel_px * 2, frame_h + bezel_px * 2],
        radius=corner_radius + bezel_px, fill=(15, 23, 42, 255),
    )
    canvas.alpha_composite(bezel, (20, 20))

    hero_rgba = Image.new("RGBA", (frame_w, frame_h))
    hero_rgba.paste(hero, (0, 0))
    hero_rgba.putalpha(mask)
    canvas.alpha_composite(hero_rgba, (20 + bezel_px, 20 + bezel_px))

    canvas.save(out_path)
    return out_path


def self_test() -> None:
    """Offline, no network/ffmpeg/Playwright calls -- pure-function checks only."""
    base_beat_map = [
        {"beat": "hook", "start_ms": 0, "end_ms": 2000, "text": "x"},
        {"beat": "setup", "start_ms": 2000, "end_ms": 8000, "text": "y"},
        {"beat": "tension", "start_ms": 8000, "end_ms": 20000, "cuts": 2},
        {"beat": "payoff", "start_ms": 20000, "end_ms": 28000, "text": "z"},
        {"beat": "loop_line", "start_ms": 28000, "end_ms": 31000, "text": "w"},
        {"beat": "end", "start_ms": 31000, "end_ms": 32000, "text": "biddeed.ai"},
    ]
    spliced = bolt32_beat_map_with_site_reveal(base_beat_map)
    assert [b["beat"] for b in spliced] == ["hook", "setup", "tension", "payoff", "site_reveal", "loop_line", "end"], spliced
    payoff = next(b for b in spliced if b["beat"] == "payoff")
    reveal = next(b for b in spliced if b["beat"] == "site_reveal")
    assert payoff["start_ms"] == 20000 and payoff["end_ms"] == 24000, payoff
    assert reveal["start_ms"] == 24000 and reveal["end_ms"] == 28000, reveal
    assert spliced[-1] == base_beat_map[-1], "end beat must be untouched"
    assert spliced[-2] == base_beat_map[-2], "loop_line beat must be untouched"
    total_ms = spliced[-1]["end_ms"] - spliced[0]["start_ms"]
    assert total_ms == 32000, total_ms
    assert base_beat_map[3]["end_ms"] == 28000, "input list must not be mutated"

    base_segments = [
        {"beat": "hook", "img": "aerial_wide", "seconds": 2.0},
        {"beat": "payoff", "img": "aerial_tight", "seconds": 8.0},
        {"beat": "end", "img": "aerial_wide", "seconds": 1.0},
    ]
    spliced_seg = bolt32_segments_with_site_reveal(base_segments, "site_reveal.png")
    assert [s["beat"] for s in spliced_seg] == ["hook", "payoff", "site_reveal", "end"]
    assert spliced_seg[1]["seconds"] == 4.0 and spliced_seg[2]["seconds"] == 4.0
    assert base_segments[1]["seconds"] == 8.0, "input list must not be mutated"

    print("reel_site_reveal self-test: OK (7 assertions)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", help="landing_url to capture")
    ap.add_argument("--out", default="/tmp/site_reveal", help="output dir for capture artifacts")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    if args.capture:
        result = capture_site_reveal(args.capture, args.out)
        print(json.dumps(result, indent=2))
        if result["hero_path"] and os.path.exists(result["hero_path"]):
            frame_out = os.path.join(args.out, "site_reveal_phone_frame.png")
            make_phone_frame(result["hero_path"], frame_out)
            print(f"phone_frame: {frame_out}")
        sys.exit(0 if result["qa_pass"] else 1)

    ap.print_help()


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# WIRING (documented, NOT applied to biddeed_reels_lib.py or
# biddeed_reels_pipeline_bolt32.py -- both are owned by #19779/#19782 and the
# issue's SEQUENCING note says do not refactor their files; treated as
# unconditional here even though docs/spec/19779.md is present on main,
# because the note is ambiguous about that case and the conservative read
# costs nothing). Behind BOLT32_SITE_REVEAL_ENABLED so #19779/#19782's own
# next session can apply this diff when they choose to:
#
#   # in biddeed_reels_pipeline_bolt32.py, process_row_bolt32(), after the
#   # existing `beat_map = lib.build_bolt32_beat_map(...)` call:
#   if os.environ.get("BOLT32_SITE_REVEAL_ENABLED") == "1":
#       import reel_site_reveal as reveal
#       capture = reveal.capture_site_reveal(row["landing_url"], f"/tmp/{row['id']}_reveal")
#       if not capture["qa_pass"]:
#           raise RuntimeError(f"site_reveal QA FAIL: {capture['qa_reason']}")
#       beat_map = reveal.bolt32_beat_map_with_site_reveal(beat_map)
#       images["site_reveal"] = reveal.make_phone_frame(capture["hero_path"], f"/tmp/{row['id']}_reveal/frame.png")
#       fields_out = {
#           "page_capture_url": capture["page_capture_url"],
#           "page_http_status": capture["page_http_status"],
#           "capture_ms": capture["capture_ms"],
#       }
#
#   # BOLT32_SEGMENTS itself is a module-level constant read by
#   # assemble_video_bolt32(); the additive segment list needed for the new
#   # beat is reveal.bolt32_segments_with_site_reveal(lib.BOLT32_SEGMENTS,
#   # images["site_reveal"]) -- assemble_video_bolt32() would need that list
#   # passed in instead of reading the module constant directly, which is a
#   # (small, mechanical) signature change to a function this module does
#   # not own. Left for #19779/#19782 to apply alongside the above.
# ---------------------------------------------------------------------------
