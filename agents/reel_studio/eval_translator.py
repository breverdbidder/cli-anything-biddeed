#!/usr/bin/env python3
"""Real, code-level eval runner for translator.py (issue #19793 PART 3,
DoD negative test (c): "a translated script whose sale figure or short
link differs from the English source fails"). No eval.json exists for
translator.py (it isn't a skills/ harness), so this module is the only
executable proof for negative test (c) -- see eval_common.py for how
results land in public.skill_eval_results."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import translator as tr  # noqa: E402
import eval_common  # noqa: E402

SOURCE_BEATS = [
    {"start_s": 0, "end_s": 2, "line": "This home was assessed at $112,410."},
    {"start_s": 20, "end_s": 28, "line": "It sold for $39,600... 64.8 percent under assessed value."},
]
SHORT_URL = "https://biddeed.ai/r/abc123"


def a1_bytematch_passes_on_faithful_translation():
    translated = [
        {"start_s": 0, "end_s": 2, "line": "Esta casa fue tasada en $112,410."},
        {"start_s": 20, "end_s": 28, "line": "Se vendio por $39,600... 64.8 por ciento bajo el valor tasado. biddeed.ai/r/abc123"},
    ]
    try:
        tr.assert_figure_link_bytematch(SOURCE_BEATS, translated, SHORT_URL)
        return True, {}
    except tr.TranslationByteMatchError as e:
        return False, {"unexpected_error": str(e)}


def a2_bytematch_fails_on_dropped_figure():
    translated = [
        {"start_s": 0, "end_s": 2, "line": "Esta casa fue tasada muy alto."},  # $112,410 dropped
        {"start_s": 20, "end_s": 28, "line": "Se vendio por $39,600... 64.8 por ciento bajo el valor tasado."},
    ]
    try:
        tr.assert_figure_link_bytematch(SOURCE_BEATS, translated, SHORT_URL)
        return False, {"expected": "TranslationByteMatchError, got no error"}
    except tr.TranslationByteMatchError as e:
        return "112,410" in str(e), {"error": str(e)}


def a3_bytematch_fails_on_reformatted_figure():
    translated = [
        {"start_s": 0, "end_s": 2, "line": "Esta casa fue tasada en $112.410."},  # comma->period reformat
        {"start_s": 20, "end_s": 28, "line": "Se vendio por $39,600... 64.8 por ciento bajo el valor tasado."},
    ]
    try:
        tr.assert_figure_link_bytematch(SOURCE_BEATS, translated, SHORT_URL)
        return False, {"expected": "TranslationByteMatchError, got no error"}
    except tr.TranslationByteMatchError as e:
        return "112,410" in str(e), {"error": str(e)}


def a4_bytematch_fails_on_dropped_spoken_link():
    # No digits in either beat set here -- isolates the bare_url check from
    # the numeric-figure check (a1-a3 already cover the latter), so this
    # assertion actually proves the url-specific branch, not just "some
    # error was raised for some reason".
    no_digit_short_url = "https://biddeed.ai/r/xyzzy"  # no digits, so this isolates the bare_url
    url_only_beats = [{"start_s": 29, "end_s": 31, "line": "Go to biddeed.ai/r/xyzzy now."}]
    translated = [{"start_s": 29, "end_s": 31, "line": "Visita nuestro sitio ahora."}]  # link dropped
    try:
        tr.assert_figure_link_bytematch(url_only_beats, translated, no_digit_short_url)
        return False, {"expected": "TranslationByteMatchError, got no error"}
    except tr.TranslationByteMatchError as e:
        return "xyzzy" in str(e), {"error": str(e)}


def a5_blocked_lang_ar_raises():
    try:
        tr.translate_variant("00000000-0000-0000-0000-000000000000", "ar")
        return False, {"expected": "ValueError for BLOCKED lang 'ar'"}
    except ValueError as e:
        return "BLOCKED" in str(e) and "ar" in tr.BLOCKED_LANGS, {"error": str(e)}


def a6_blocked_lang_zh_raises():
    try:
        tr.translate_variant("00000000-0000-0000-0000-000000000000", "zh")
        return False, {"expected": "ValueError for BLOCKED lang 'zh'"}
    except ValueError as e:
        return "BLOCKED" in str(e) and "zh" in tr.BLOCKED_LANGS, {"error": str(e)}


def a7_blocked_lang_he_raises():
    try:
        tr.translate_variant("00000000-0000-0000-0000-000000000000", "he")
        return False, {"expected": "ValueError for BLOCKED lang 'he'"}
    except ValueError as e:
        return "BLOCKED" in str(e) and "he" in tr.BLOCKED_LANGS, {"error": str(e)}


def run_eval():
    assertions = [
        ("bytematch_passes_on_faithful_translation", a1_bytematch_passes_on_faithful_translation),
        ("bytematch_fails_on_dropped_figure", a2_bytematch_fails_on_dropped_figure),
        ("bytematch_fails_on_reformatted_figure", a3_bytematch_fails_on_reformatted_figure),
        ("bytematch_fails_on_dropped_spoken_link", a4_bytematch_fails_on_dropped_spoken_link),
        ("blocked_lang_ar_raises", a5_blocked_lang_ar_raises),
        ("blocked_lang_zh_raises", a6_blocked_lang_zh_raises),
        ("blocked_lang_he_raises", a7_blocked_lang_he_raises),
    ]
    return eval_common.run_assertions("reel-translator", assertions)


if __name__ == "__main__":
    run_eval()
