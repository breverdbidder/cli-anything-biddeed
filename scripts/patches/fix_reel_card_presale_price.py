#!/usr/bin/env python3
"""Reel cards must never show a bare em-dash where the money line goes.

Why
---
33 of the 62 reels that have a playable video are phase='presale': the property
has not sold yet, so sold_amount is NULL. reelCardHtml() renders
`fmtMoney(reel.sold_amount)`, whose local fmtMoney returns `&mdash;` for null --
so a third of the /reels gallery and every presale watch page shows a dash where
the number belongs. Live-reproduced on /reels/uaTb7r before this patch:

    <div class="price">&mdash;</div>

Fix
---
Fall back down a chain of figures that each carry a citable primary source
(mandate M10 -- no number on a public page without one):

    sold_amount     -> "$185,000"                (clerk sale record)
    assessed_value  -> "County assessed $188,162" (county tax roll)
    auction_date    -> "Auction Sep 8"            (clerk calendar)
    otherwise        -> em-dash, as today

24 of the 33 presale rows carry assessed_value and all 33 carry auction_date, so
after this no card renders a bare dash. list_public_reels() was widened in the
same change to return assessed_value and phase (get_reel_by_code() already
returned assessed_value).

Idempotent: exits 0 with "already applied" on a second run.
"""
import sys

MARKER = "const moneyLine = "

ANCHOR_CALC = """  const deltaLine = deltaPct == null ? '' : `${deltaPct < 0 ? '-' : '+'}${Math.abs(deltaPct).toFixed(0)}% vs assessed`;
"""

NEW_CALC = """  const deltaLine = deltaPct == null ? '' : `${deltaPct < 0 ? '-' : '+'}${Math.abs(deltaPct).toFixed(0)}% vs assessed`;
  // A presale reel has no sold_amount -- the property has not sold yet -- so the
  // money line fell through to fmtMoney(null) and rendered a bare em-dash on a
  // third of the gallery. Walk a fallback chain instead, every rung of which is
  // a figure with a citable primary source (mandate M10): the clerk sale record,
  // then the county tax roll, then the clerk auction calendar.
  const _auctionLabel = (() => {
    if (!reel.auction_date) return '';
    const d = new Date(String(reel.auction_date) + 'T12:00:00Z');
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  })();
  const moneyLine = reel.sold_amount != null
    ? fmtMoney(reel.sold_amount)
    : (reel.assessed_value != null
        ? `<span class="price-label">County assessed</span> ${fmtMoney(reel.assessed_value)}`
        : (_auctionLabel ? `<span class="price-label">Auction</span> ${escHtml(_auctionLabel)}` : '&mdash;'));
"""

ANCHOR_LINE = """    <div class="price">${fmtMoney(reel.sold_amount)}</div>
"""

NEW_LINE = """    <div class="price">${moneyLine}</div>
"""

ANCHOR_CSS = """.reel-view-link{display:block;text-align:center;background:#ffffff;color:#005EB8;font-weight:700;padding:.6rem;border-radius:8px;text-decoration:none;margin-top:.7rem;font-size:.85rem}
"""

NEW_CSS = """.reel-view-link{display:block;text-align:center;background:#ffffff;color:#005EB8;font-weight:700;padding:.6rem;border-radius:8px;text-decoration:none;margin-top:.7rem;font-size:.85rem}
.price-label{display:block;font-size:.62em;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#0A2540;opacity:.72}
"""


def main(path):
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("already applied")
        return 0

    for old, new, what in ((ANCHOR_CALC, NEW_CALC, "money-line calc"),
                           (ANCHOR_LINE, NEW_LINE, "price div"),
                           (ANCHOR_CSS, NEW_CSS, "price-label css")):
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"{what} anchor matched {n} times, expected 1")
        src = src.replace(old, new, 1)

    open(path, "w", encoding="utf-8").write(src)

    if '<div class="price">${fmtMoney(reel.sold_amount)}</div>' in src:
        raise SystemExit("old price div still present")
    for needle in ("const moneyLine = ", "County assessed", "price-label"):
        if needle not in src:
            raise SystemExit(f"missing after patch: {needle!r}")
    print(f"patched {path}: presale money-line fallback + .price-label")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"))
