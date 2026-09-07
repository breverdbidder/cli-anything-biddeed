#!/usr/bin/env python3
"""Coerce money/score fields to float before arithmetic in the reels library.

Why
---
On 2026-09-06 `winnerdata.biddeed_reels` held 71 rows stuck at status='error',
all phase='postsale', with three error strings that are one bug wearing three
hats:

    unsupported operand type(s) for -: 'str' and 'int'        x50
    '>' not supported between instances of 'str' and 'int'    x11
    Unknown format code 'f' for object of type 'str'          x10

All three come out of build_script_and_caption() in scripts/biddeed_reels_lib.py:

    if assessed_value and assessed_value > 0:                 # -> '>' str/int
        delta_pct = round((sold_amount - assessed_value) ...) # -> '-' str/int
    hook = f"... for ${sold_amount:,.0f}."                    # -> format code 'f'

The post-sale pipeline (scripts/biddeed_reels_pipeline.py) hands these values
straight through -- `sighting.get("sold_amount")` from the sighting SQL and
`parcel.get("val_assessed")` from zw_parcels -- while every later pipeline
(v2, bolt32, presale) wraps the same fields in float(). Whenever either source
returns the numeric as a JSON/text string, the row dies before condition
scoring (condition_score is NULL on all 71).

Fix
---
Coerce in the library rather than at one call site, so every caller is covered:
add lib.as_num() and apply it at the top of build_script_and_caption(),
build_script_and_caption_v2() and rank_score().

Idempotent: exits 0 with "already applied" on a second run.
"""
import sys

MARKER = "def as_num(v):"

HELPER_ANCHOR = '''def sql_num(v):
    return "null" if v is None else str(v)
'''

HELPER = '''def sql_num(v):
    return "null" if v is None else str(v)


def as_num(v):
    """Best-effort float for a money/score field that may arrive as text.

    PostgREST/RPC round-trips hand `numeric` columns back as JSON strings, and
    zw_parcels.val_assessed is text in some county loads. Every arithmetic and
    ",.0f" format site in this module goes through here first so a string never
    reaches a `-`, a `>` or a format spec (issue: 71 postsale reels stuck at
    status='error' on 2026-09-06). Returns None for None/blank/unparseable so
    the existing `if assessed_value and ...` guards keep working unchanged.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "").replace("$", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None
'''

PATCHES = [
    # build_script_and_caption
    ('''                              assessed_value: float | None, condition: dict) -> dict:
    county_name = county_display(county_slug)''',
     '''                              assessed_value: float | None, condition: dict) -> dict:
    sold_amount = as_num(sold_amount)
    assessed_value = as_num(assessed_value)
    county_name = county_display(county_slug)'''),
    # build_script_and_caption_v2
    ('''    controlled fields are ever interpolated."""
    county_name = county_display(county_slug)''',
     '''    controlled fields are ever interpolated."""
    sold_amount = as_num(sold_amount)
    assessed_value = as_num(assessed_value)
    county_name = county_display(county_slug)'''),
    # rank_score
    ('''    discount_component = max(0.0, -(delta_pct or 0.0))''',
     '''    delta_pct = as_num(delta_pct)
    condition_score = as_num(condition_score)
    sold_amount = as_num(sold_amount)
    discount_component = max(0.0, -(delta_pct or 0.0))'''),
]


def main(path):
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("already applied")
        return 0

    if src.count(HELPER_ANCHOR) != 1:
        raise SystemExit(f"helper anchor matched {src.count(HELPER_ANCHOR)} times, expected 1")
    src = src.replace(HELPER_ANCHOR, HELPER, 1)

    for old, new in PATCHES:
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"anchor matched {n} times, expected 1: {old[:60]!r}")
        src = src.replace(old, new, 1)

    open(path, "w", encoding="utf-8").write(src)

    # self-audit: the three crash sites must now be preceded by coercion
    for fn in ("def build_script_and_caption(", "def build_script_and_caption_v2(", "def rank_score("):
        i = src.index(fn)
        body = src[i:i + 1400]
        if "as_num(" not in body:
            raise SystemExit(f"{fn} not coerced")
    print(f"patched {path}: as_num() added, 3 call sites coerced")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "scripts/biddeed_reels_lib.py"))
