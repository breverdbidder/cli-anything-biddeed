#!/usr/bin/env python3
"""/reels must not report "no reels published" when the database blinked.

Why
---
The gallery handler already logs a failed list_public_reels call, but it then
renders the same empty state as a genuinely empty catalogue AND caches it for
120 seconds. Live-caught 2026-09-07 04:16 UTC: Supabase answered

    HTTP 521 "Web server is down"

for about half a minute while the reels backfill was running, and /reels told
every visitor "No reels published yet." with 59 approved reels sitting in the
table. A five-second blip becomes a two-minute lie.

This is the same swallow-the-error shape just fixed in fetchAuctionCards
(#20093), where a 401 became "no auctions" for every county in Florida.

Fix
---
Thread a `failed` flag from the handler into buildReelsGalleryHtml() so the page
says the reels could not be loaded, and send `Cache-Control: no-store` on that
path so the failure is never cached.

Also fixes the gallery's <h1>, which was `color:#fff` on a `#ffffff` body with
only an `html[data-theme=light]` override -- invisible until the shell's theme
script runs, and permanently invisible without JS. Same defect class as the deal
page's base styles (#20084). Base is now ink with an explicit dark override.

Idempotent: exits 0 with "already applied" on a second run.
"""
import sys

MARKER = "reelsLoadFailed"

ANCHOR_HANDLER = """        const includePending = url.searchParams.get('preview') === '1';
        let reels = [];
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/list_public_reels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_include_pending: includePending }),
          });
          if (res.ok) reels = (await res.json()) || [];
          else await logErr(env, '/reels', 'list_public_reels non-2xx', await res.text(), res.status);
        } catch (e) {
          await logErr(env, '/reels', 'list_public_reels failed', String(e), 500);
        }
        const html = buildReelsGalleryHtml(reels, includePending);
        return new Response(method === 'HEAD' ? null : withPublicShell(html, path), {
          headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Cache-Control': includePending ? 'no-store' : 'public,max-age=120' },
        });
"""

NEW_HANDLER = """        const includePending = url.searchParams.get('preview') === '1';
        let reels = [];
        // An empty catalogue and an unreachable database are different things.
        // Supabase 520/521s under load, and caching "No reels published yet."
        // for 120s over a five-second blip is how the gallery told every
        // visitor there was nothing to watch with 59 approved reels in the
        // table (live-caught 2026-09-07 04:16 UTC).
        let reelsLoadFailed = false;
        try {
          const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/list_public_reels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` },
            body: JSON.stringify({ p_include_pending: includePending }),
          });
          if (res.ok) {
            const payload = await res.json();
            if (Array.isArray(payload)) reels = payload;
            else { reelsLoadFailed = true; await logErr(env, '/reels', 'list_public_reels non-array', JSON.stringify(payload).slice(0, 300), 500); }
          } else {
            reelsLoadFailed = true;
            await logErr(env, '/reels', 'list_public_reels non-2xx', await res.text(), res.status);
          }
        } catch (e) {
          reelsLoadFailed = true;
          await logErr(env, '/reels', 'list_public_reels failed', String(e), 500);
        }
        const html = buildReelsGalleryHtml(reels, includePending, reelsLoadFailed);
        return new Response(method === 'HEAD' ? null : withPublicShell(html, path), {
          headers: {
            'Content-Type': 'text/html;charset=UTF-8',
            'Cache-Control': (includePending || reelsLoadFailed) ? 'no-store' : 'public,max-age=120',
          },
        });
"""

ANCHOR_SIG = "function buildReelsGalleryHtml(reels, includePending) {\n"
NEW_SIG = "function buildReelsGalleryHtml(reels, includePending, loadFailed) {\n"

ANCHOR_EMPTY = """${reels.length === 0 ? '<p style="text-align:center;color:#0A2540;margin-top:3rem">No reels published yet.</p>' : ''}
"""

NEW_EMPTY = """${reels.length === 0
  ? (loadFailed
      ? '<p style="text-align:center;color:#0A2540;margin-top:3rem">We could not load the reels just now. Please refresh in a moment.</p>'
      : '<p style="text-align:center;color:#0A2540;margin-top:3rem">No reels published yet.</p>')
  : ''}
"""

ANCHOR_H1 = """h1{max-width:1200px;margin:0 auto 1.5rem;font-size:1.8rem;color:#fff;font-weight:800}
html[data-theme=light] h1{color:#1a1a1a}
${REELS_PLAYER_CSS}
"""

NEW_H1 = """h1{max-width:1200px;margin:0 auto 1.5rem;font-size:1.8rem;color:#1a1a1a;font-weight:800}
html[data-theme=dark] h1{color:#EDEDED}
${REELS_PLAYER_CSS}
"""


def main(path):
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("already applied")
        return 0

    for old, new, what in ((ANCHOR_HANDLER, NEW_HANDLER, "handler"),
                           (ANCHOR_SIG, NEW_SIG, "gallery signature"),
                           (ANCHOR_EMPTY, NEW_EMPTY, "empty state"),
                           (ANCHOR_H1, NEW_H1, "gallery h1")):
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"{what} anchor matched {n} times, expected 1")
        src = src.replace(old, new, 1)

    open(path, "w", encoding="utf-8").write(src)

    for needle in ("reelsLoadFailed", "could not load the reels just now",
                   "buildReelsGalleryHtml(reels, includePending, loadFailed)",
                   "html[data-theme=dark] h1{color:#EDEDED}"):
        if needle not in src:
            raise SystemExit(f"missing after patch: {needle!r}")
    print(f"patched {path}: /reels distinguishes an outage from an empty catalogue")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"))
