#!/usr/bin/env python3
"""ANALYST -- agents/reel_studio/analyst.py (issue #19782).

Per-variant attribution: mints each variant its own short_code/short_url/QR
(reuses scripts/biddeed_reels_lib.gen_short_code/generate_qr_png -- same T3
pattern v1/v2 biddeed_reels already use, not reinvented), reads
winnerdata.v_variant_scoreboard, allocates tomorrow's 4 archetypes via
Thompson sampling with a 1-exploration-variant/day floor, and writes the
weekly "what went viral and why" digest.

Ground truth #1 (Ariel's LMS approve/reject, winnerdata.reel_variant_review)
is live from Phase A onward. Ground truth #2 (YouTube Analytics) is
deliberately stubbed -- fetch_youtube_analytics() raises NotImplementedError
rather than fabricate a number, per Honesty Protocol V3, until
YOUTUBE_OAUTH_REFRESH_TOKEN exists and a channel is live.

CLI:
  python3 analyst.py scoreboard [--reel-id UUID]
  python3 analyst.py allocate --n 4
  python3 analyst.py digest --week 2026-W36
  python3 analyst.py eval
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

LANDING_BASE = "https://biddeed.ai"
ARCHETYPES = [
    "shock_number", "underdog_bidder", "bank_vs_house", "mystery_nobody_bid",
    "red_flag_warning", "hidden_value_reveal", "countdown_presale",
]


# ---------------------------------------------------------------------------
# T3 -- short link + QR minting (per variant)
# ---------------------------------------------------------------------------

def mint_variant_short_link(reel: dict, variant_key: str) -> tuple[str, str, str | None]:
    """Mints a unique short_code + short_url for one variant. QR generation
    is best-effort (local `qrcode` package, same as v2's T3) -- returns
    qr_url=None rather than failing the whole variant if qrcode/storage is
    unavailable in this environment (Honesty Protocol: log it, don't crash
    variant creation over a QR PNG)."""
    for _ in range(5):
        candidate = lib.gen_short_code()
        rows = lib.run_sql(f"select 1 from winnerdata.reel_variants where short_code = {lib.sql_str(candidate)};")
        if not rows:
            code = candidate
            break
    else:
        raise RuntimeError("could not mint a unique variant short_code after 5 attempts")

    short_url = f"{LANDING_BASE}/r/{code}"

    # issue #19796 (P0): without this row, /r/{code} and /reels/{code} both
    # 404 -- resolve_reel_link()/get_reel_by_code() join on
    # winnerdata.reel_links.code, and nothing else ever wrote one for a
    # variant-minted code. GTM-6 (#20052): target defaults to the parent
    # reel's own deal page (landing_url) when known -- resolve_reel_link()
    # falls back to the /reels/{code} interstitial itself once the reel's
    # page_http_status isn't verified 200, so this row's target only needs
    # to be the *best known* destination, not re-verify liveness here.
    target_url = reel.get("landing_url") or f"{LANDING_BASE}/reels/{code}"
    lib.run_sql(f"""
        insert into winnerdata.reel_links (code, reel_id, target, utm_content)
        values ({lib.sql_str(code)}, {lib.sql_str(reel['id'])}, {lib.sql_str(target_url)}, {lib.sql_str(variant_key)})
        on conflict (code) do nothing;
    """)

    qr_url = None
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            qr_path = os.path.join(td, f"{code}.png")
            lib.generate_qr_png(short_url, qr_path)
            key = f"reel-variants/qr/{reel['id']}/{variant_key}_{code}.png"
            qr_url = lib.storage_upload(qr_path, key, "image/png")
    except Exception as e:
        print(f"WARN: QR generation/upload failed for {code}: {e}", file=sys.stderr)

    return code, short_url, qr_url


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

def scoreboard(reel_id: str | None = None) -> list[dict]:
    where = f"where reel_id = {lib.sql_str(reel_id)}" if reel_id else ""
    return lib.run_sql(f"select * from winnerdata.v_variant_scoreboard {where} order by variant_key;")


def archetype_stats() -> dict:
    """Win/loss counts per archetype from Ariel's LMS decisions (ground
    truth #1) -- the only signal available until real play/watch metrics
    accumulate. approved=win, rejected=loss, improvement_requested/no
    decision yet=neither (not counted either way)."""
    rows = lib.run_sql("""
        select rv.archetype,
               count(*) filter (where rev.decision = 'approved')  as wins,
               count(*) filter (where rev.decision = 'rejected')  as losses
        from winnerdata.reel_variants rv
        left join lateral (
            select decision from winnerdata.reel_variant_review r
            where r.variant_id = rv.id order by decided_at desc limit 1
        ) rev on true
        group by rv.archetype;
    """)
    return {r["archetype"]: {"wins": int(r["wins"]), "losses": int(r["losses"])} for r in rows}


# ---------------------------------------------------------------------------
# Thompson sampling allocation
# ---------------------------------------------------------------------------

def thompson_allocate(n: int = 4, exploration_floor: int = 1, rng: random.Random | None = None) -> list[str]:
    """Beta(wins+1, losses+1) draw per archetype -- exact Thompson sampling
    (Python's random.betavariate, not a hand-rolled approximation; Postgres
    has no native gamma/beta sampler, so this deliberately lives in Python,
    not SQL). Picks the top-n archetypes by drawn sample, without
    replacement, then forces at least `exploration_floor` archetype(s) with
    zero observations (wins+losses==0) into the set if none were drawn
    naturally -- the issue's explicit "floor of 1 exploration variant/day"."""
    rng = rng or random.Random()
    stats = archetype_stats()
    draws = []
    for a in ARCHETYPES:
        s = stats.get(a, {"wins": 0, "losses": 0})
        sample = rng.betavariate(s["wins"] + 1, s["losses"] + 1)
        draws.append((sample, a, s["wins"] + s["losses"] == 0))
    draws.sort(key=lambda t: t[0], reverse=True)

    picked = [a for _, a, _ in draws[:n]]
    unexplored_in_pick = [a for _, a, unexplored in draws[:n] if unexplored]
    if len(unexplored_in_pick) < exploration_floor:
        unexplored_all = [a for _, a, unexplored in draws if unexplored and a not in picked]
        needed = exploration_floor - len(unexplored_in_pick)
        for a in unexplored_all[:needed]:
            if len(picked) >= n:
                picked[-1] = a
            else:
                picked.append(a)
    return picked[:n]


# ---------------------------------------------------------------------------
# Ground truth #2 -- YouTube Analytics (stub, never fabricated)
# ---------------------------------------------------------------------------

def fetch_youtube_analytics(video_id: str) -> dict:
    token = os.environ.get("YOUTUBE_OAUTH_REFRESH_TOKEN")
    if not token:
        raise NotImplementedError(
            "YOUTUBE_OAUTH_REFRESH_TOKEN not set -- no YouTube channel/OAuth exists yet "
            "(issue #19782: 'stub the fetcher... do not fake data'). views_ext/avd_ext "
            "stay null until this is wired to a real channel."
        )
    raise NotImplementedError("YouTube Analytics fetch not yet implemented -- stub only")


# ---------------------------------------------------------------------------
# Weekly digest
# ---------------------------------------------------------------------------

def write_weekly_digest(iso_week: str) -> str:
    stats = archetype_stats()
    best = None
    for a, s in stats.items():
        n = s["wins"] + s["losses"]
        rate = (s["wins"] / n) if n else None
        if rate is not None and (best is None or rate > best[1]):
            best = (a, rate, n)

    lines = [f"# Reel Studio weekly digest — {iso_week}", ""]
    if best:
        lines.append(f"Best archetype this week: **{best[0]}** (approve rate {best[1]:.0%}, n={best[2]})")
    else:
        lines.append("Best archetype this week: not enough decided variants yet (UNTESTED — 0 reel_variant_review rows with a decision)")
    lines.append("")
    lines.append("| archetype | wins | losses | n |")
    lines.append("|---|---|---|---|")
    for a in ARCHETYPES:
        s = stats.get(a, {"wins": 0, "losses": 0})
        lines.append(f"| {a} | {s['wins']} | {s['losses']} | {s['wins'] + s['losses']} |")
    lines.append("")
    lines.append(
        "Note: this digest is generated from public.reel_variant_review decisions only "
        "(ground truth #1). Ground truth #2 (YouTube Analytics) is not yet wired -- see "
        "fetch_youtube_analytics(). Not surfaced to public.spi_daily this run: that table "
        "is on the M2 protected list and issue #19782 does not name it explicitly, so this "
        "digest stays a file artifact until a follow-up issue authorizes the spi_daily write."
    )

    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "gtm", "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{iso_week}.md")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sb = sub.add_parser("scoreboard")
    sb.add_argument("--reel-id", default=None)

    al = sub.add_parser("allocate")
    al.add_argument("--n", type=int, default=4)

    dg = sub.add_parser("digest")
    dg.add_argument("--week", required=True)

    sub.add_parser("eval")

    args = ap.parse_args()
    if args.cmd == "scoreboard":
        print(json.dumps(scoreboard(args.reel_id), indent=2, default=str))
    elif args.cmd == "allocate":
        print(json.dumps(thompson_allocate(args.n), indent=2))
    elif args.cmd == "digest":
        path = write_weekly_digest(args.week)
        print(json.dumps({"written": path}))
    elif args.cmd == "eval":
        from eval_analyst import run_eval  # noqa
        run_eval()


if __name__ == "__main__":
    main()
