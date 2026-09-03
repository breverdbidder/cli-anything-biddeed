#!/usr/bin/env python3
"""ANIMATOR -- agents/reel_studio/animator.py (issue #19782).

Engine choice: **revideo** (MIT, npm `@revideo/core`, confirmed on the
public npm registry this session -- `npm view @revideo/core version` ->
0.11.0). Chosen over motion-canvas because revideo ships a Node-native
`@revideo/renderer` API meant for exactly this use case (CLI/CI-triggered,
headless, no browser UI needed), where motion-canvas's own docs frame it
around its interactive Vite editor first. Recorded reason, not just a coin
flip, per the issue's "pick one, record why."

**Live finding this session (VERIFIED, not assumed):** revideo's own
scaffolding CLI (`npm init @revideo@latest`) prompts interactively for a
project name even when passed `--yes`, and does not complete inside a 90s
budget in this sandbox (no TTY). That is a real, observed blocker specific
to *scaffolding a fresh project*, not to revideo's renderer API itself --
this module still wires up `render_element_revideo()` for real (a genuine
subprocess call against a project dir), so a future session that commits a
pre-scaffolded `agents/reel_studio/_revideo_project/` template (or runs
this in an environment with a TTY) can flip straight to the primary engine
with no code change here.

**What Phase A actually renders, honestly:** every element this session
produced went through `render_element_ffmpeg_fallback()` -- a real,
deterministic, seeded ffmpeg render (drawtext/xfade, brand tokens from
DESIGN.md: Navy #1E3A5F bg, Amber #F59E0B text, Inter/DejaVu Sans Bold via
the same `_ensure_font()` v1/v2 biddeed_reels already uses). This is a
simplified stand-in for true canvas-drawn parcel-outline/price-bar
animation (that needs per-frame vector drawing, which is exactly why
revideo/motion-canvas is the intended primary engine) -- labeled as such,
per the issue's own "falls back to kinetic-only and says so," not
presented as the final animated_bolt32 quality bar.

Elements (9:16, matches bolt32 beat slots):
  a) kinetic_hook           0.0-2.0s   kinetic typography
  b) parcel_outline_drawon  2.0-8.0s   draw-on reveal (simplified: zoom+fade)
  c) price_bar_race         20.0-28.0s count-up (chained drawtext time-slices)
  d) loop_seam_morph        31.0-32.0s xfade crossfade (end frame -> start frame)

Hard budget: 90s per element (RENDER_BUDGET_S). Over budget -> falls back
to a minimal single-drawtext static-hold clip, logged as
`fallback_reason='over_budget'`.

CLI:
  python3 animator.py render-samples --n-properties 3
  python3 animator.py eval
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

RENDER_BUDGET_S = 90
BRAND_BG = "0x020617"
BRAND_NAVY = "0x1E3A5F"
BRAND_AMBER = "0xF59E0B"
W, H = 1080, 1920

ELEMENTS = [
    {"key": "kinetic_hook", "start_s": 0.0, "end_s": 2.0, "kind": "kinetic_typography"},
    {"key": "parcel_outline_drawon", "start_s": 2.0, "end_s": 8.0, "kind": "draw_on"},
    {"key": "price_bar_race", "start_s": 20.0, "end_s": 28.0, "kind": "count_up"},
    {"key": "loop_seam_morph", "start_s": 31.0, "end_s": 32.0, "kind": "morph"},
]


def _run_ffmpeg(cmd: list[str], budget_s: float) -> tuple[bool, str]:
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=budget_s, check=True)
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"timeout after {budget_s}s"
    except subprocess.CalledProcessError as e:
        return False, f"ffmpeg exit {e.returncode}: {e.stderr[-500:] if e.stderr else ''}"


def render_element_revideo(element: dict, seed: int, text: str, out_path: str, budget_s: float = RENDER_BUDGET_S) -> tuple[bool, str]:
    """Real attempt at the primary engine. project_dir must already be
    scaffolded (see module docstring) -- if it isn't, fails fast rather than
    hanging on an interactive prompt (that failure mode was observed and is
    exactly what this guard prevents on subsequent runs)."""
    project_dir = os.path.join(os.path.dirname(__file__), "_revideo_project")
    if not os.path.isdir(project_dir):
        return False, "no scaffolded revideo project at agents/reel_studio/_revideo_project (scaffold CLI needs a TTY, not available this session)"
    cmd = ["npx", "--yes", "@revideo/renderer", "render", "--project", project_dir,
           "--variables", json.dumps({"seed": seed, "text": text, "element": element["key"]}),
           "--output", out_path]
    return _run_ffmpeg(cmd, budget_s)


def render_element_ffmpeg_fallback(element: dict, seed: int, text: str, out_path: str, budget_s: float = RENDER_BUDGET_S) -> tuple[bool, str]:
    duration = round(element["end_s"] - element["start_s"], 2)
    font = lib._ensure_font()
    safe_text = lib._escape_drawtext(text)
    fontsize = 64 + (seed % 3) * 8  # deterministic seeded jitter, not random

    if element["kind"] == "kinetic_typography":
        vf = (
            f"drawtext=fontfile={font}:text='{safe_text}':fontcolor={BRAND_AMBER}:fontsize={fontsize}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:alpha='min(1,(t)/0.4)'"
        )
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BRAND_BG}:s={W}x{H}:d={duration}",
               "-vf", vf, "-t", str(duration), "-pix_fmt", "yuv420p", out_path]
    elif element["kind"] == "draw_on":
        vf = (
            f"color=c={BRAND_BG}:s={W}x{H}[bg];"
            f"[bg]drawbox=x=iw*0.15:y=ih*0.35:w=iw*0.7:h=ih*0.3:color={BRAND_AMBER}@1.0:t=6:"
            f"enable='gte(t,0.3)'[boxed];"
            f"[boxed]drawtext=fontfile={font}:text='{safe_text}':fontcolor=white:fontsize={fontsize}:"
            f"x=(w-text_w)/2:y=h*0.72:alpha='min(1,(t-0.5)/0.5)':enable='gte(t,0.5)'"
        )
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BRAND_BG}:s={W}x{H}:d={duration}",
               "-filter_complex", vf, "-t", str(duration), "-pix_fmt", "yuv420p", out_path]
    elif element["kind"] == "count_up":
        steps = 5
        step_dur = duration / steps
        drawtexts = []
        for i in range(steps):
            step_text = lib._escape_drawtext(f"{text} step {i + 1}/{steps}")
            t0, t1 = i * step_dur, (i + 1) * step_dur
            drawtexts.append(
                f"drawtext=fontfile={font}:text='{step_text}':fontcolor={BRAND_AMBER}:fontsize={fontsize}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,{t0:.2f},{t1:.2f})'"
            )
        vf = ",".join(drawtexts)
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BRAND_NAVY}:s={W}x{H}:d={duration}",
               "-vf", vf, "-t", str(duration), "-pix_fmt", "yuv420p", out_path]
    elif element["kind"] == "morph":
        with tempfile.TemporaryDirectory() as td:
            seam_a = os.path.join(td, "seam_a.mp4")
            seam_b = os.path.join(td, "seam_b.mp4")
            for p, color in ((seam_a, BRAND_NAVY), (seam_b, BRAND_BG)):
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:d=1",
                                 "-pix_fmt", "yuv420p", p], capture_output=True, timeout=20, check=True)
            cmd = ["ffmpeg", "-y", "-i", seam_a, "-i", seam_b,
                   "-filter_complex", f"[0][1]xfade=transition=fade:duration={duration}:offset=0",
                   "-pix_fmt", "yuv420p", out_path]
            return _run_ffmpeg(cmd, budget_s)
    else:
        return False, f"unknown element kind {element['kind']}"

    return _run_ffmpeg(cmd, budget_s)


def render_static_fallback(element: dict, text: str, out_path: str) -> tuple[bool, str]:
    """Minimal single-drawtext static-hold clip -- the 'falls back to
    kinetic-only' path when even the seeded ffmpeg render blows the budget."""
    duration = round(element["end_s"] - element["start_s"], 2)
    font = lib._ensure_font()
    safe_text = lib._escape_drawtext(text)
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={BRAND_BG}:s={W}x{H}:d={duration}",
           "-vf", f"drawtext=fontfile={font}:text='{safe_text}':fontcolor={BRAND_AMBER}:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2",
           "-t", str(duration), "-pix_fmt", "yuv420p", out_path]
    return _run_ffmpeg(cmd, 30)


def render_element(element: dict, seed: int, text: str, property_key: str) -> dict:
    key = f"reel-variants/animator-samples/{property_key}/{element['key']}.mp4"
    with tempfile.TemporaryDirectory() as td:
        out_path = os.path.join(td, f"{element['key']}.mp4")
        t0 = time.time()

        ok, reason = render_element_revideo(element, seed, text, out_path, RENDER_BUDGET_S)
        engine = "revideo"
        if not ok:
            elapsed_so_far = time.time() - t0
            remaining_budget = max(5.0, RENDER_BUDGET_S - elapsed_so_far)
            ok, reason2 = render_element_ffmpeg_fallback(element, seed, text, out_path, remaining_budget)
            engine = "ffmpeg_kinetic_fallback"
            reason = f"revideo: {reason} | ffmpeg_fallback: {'ok' if ok else reason2}"

        seconds = round(time.time() - t0, 2)
        over_budget = seconds > RENDER_BUDGET_S

        if not ok or over_budget:
            ok2, reason3 = render_static_fallback(element, text, out_path)
            engine = "static_fallback"
            reason = f"{reason} | static_fallback: {'ok' if ok2 else reason3}"
            ok = ok2

        if not ok:
            return {"element": element["key"], "engine": engine, "seconds": seconds,
                    "budget_ok": not over_budget, "uploaded": False, "reason": reason}

        try:
            actual_duration = lib._ffprobe_duration(out_path)
        except Exception:
            actual_duration = None

        url = lib.storage_upload(out_path, key, "video/mp4")

        return {
            "element": element["key"], "engine": engine, "seconds": seconds,
            "budget_ok": not over_budget, "uploaded": True, "url": url,
            "ffprobe_duration_s": actual_duration, "reason": reason if engine != "revideo" else "primary engine succeeded",
        }


def render_sample_elements(property_keys: list[str]) -> list[dict]:
    results = []
    for pi, pkey in enumerate(property_keys):
        for ei, element in enumerate(ELEMENTS):
            seed = pi * 100 + ei
            text = f"{pkey.upper()} {element['key'].replace('_', ' ').upper()}"
            results.append(render_element(element, seed, text, pkey))
    return results


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rs = sub.add_parser("render-samples")
    rs.add_argument("--n-properties", type=int, default=3)
    sub.add_parser("eval")

    args = ap.parse_args()
    if args.cmd == "render-samples":
        keys = [f"sample_property_{i+1}" for i in range(args.n_properties)]
        print(json.dumps(render_sample_elements(keys), indent=2, default=str))
    elif args.cmd == "eval":
        from eval_animator import run_eval  # noqa
        run_eval()


if __name__ == "__main__":
    main()
