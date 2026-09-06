#!/usr/bin/env python3
"""CMO FACTORY (issue #19777) -- compliance gate.

Runs the compliance checks named in docs/gtm/MISSION.md (checks 1-6) plus
the CONTENT_SOP.md SS6 P2/P6/P7/P8/P9/P17/P18 checks added in SPR-01
(issue #19826) over a given set of artifact files (marketing copy, JSON,
HTML -- anything text-based a GTM lane produces), plus optional live
page/render checks.

Markers (stdout, one per line, only on PASS of that specific thing):
    GTM_COMPLIANCE_PASSED   -- all compliance checks passed
    GTM_PAGE_200            -- only emitted if --check-url was passed and it returned 200
    GTM_RENDER_OK           -- only emitted if --check-render-file was passed and it parsed non-empty

Absence of a marker for something you asked this script to check = FAIL.
Absence of a marker for something you did NOT ask it to check is simply
not applicable -- this script never fabricates a marker for a check it did
not run. merge.py and doctor.py must not assume a marker exists unless the
corresponding --check-* flag was passed.

Exit code: 0 if every check that WAS run passed, 1 otherwise.
"""
import argparse
import json
import os
import re
import sys
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MISSION_MD = os.path.join(REPO_ROOT, "docs", "gtm", "MISSION.md")
CANON_MD = os.path.join(REPO_ROOT, "docs", "gtm", "BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md")

VENDOR_NAMES = [
    "Tracerfy", "Bright Data", "Apify", "OpenRouter", "ElevenLabs",
    "skip-trace", "skip trace", "summitleads",
]
HOMEOWNER_CONTACT_PATTERNS = [
    r"\bmailer\b", r"\btext (the|a) (homeowner|seller)\b",
    r"\bcall the (homeowner|seller)\b", r"\bforeclosure.?relief\b",
    r"\bsave your home\b", r"\bmortgage.?relief\b",
    # CONTENT_SOP.md SS6 P4 -- second-person-to-owner phrasing (SPR-01, issue #19826)
    r"\byour home\b", r"\bbehind on your\b", r"\bfacing foreclosure\b",
    r"\bstop the sale\b",
]
PERSON_NAME_FIELD_KEYS = {"buyer_name", "owner_name", "bidder_name", "winner_name", "defendant_name"}

# Founder carve-out (M7 amended, docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md ##M7).
# Ariel Shapira's own name/roles are the ONLY person allowed in public assets.
# agents/reel_studio/hook_writer.py intentionally keeps its OWN stricter
# no-names-at-all rule for reels (BANNED_PERSON_NAMES includes "Ariel Shapira")
# -- that is independent of this allowlist and must not be "fixed" (SOP SS6 P3).
FOUNDER_NAME = "Ariel Shapira"
FOUNDER_ROLES = [
    "Founder", "Developer", "Builder", "Property Manager",
    "Inventor of ZoneWise.AI", "The Real Estate AI Oracle™",
]

# Widened from the original (won by|owned by|bidder was|purchased by) per
# CONTENT_SOP.md SS6 P3 ("prose regex is narrow -> SPR-01 widens"). Deliberately
# does NOT include a bare "by" trigger -- that false-positives on ordinary
# brand phrasing ("Powered by Winner Data").
PERSON_NAME_PROSE_RE = re.compile(
    r"\b(won by|owned by|bidder was|purchased by|said|according to|"
    r"quoted by|written by|authored by|founded by|narrated by)\s+"
    r"([A-Z][a-z]+\s+[A-Z][a-z]+)\b"
)
INSURANCE_RE = re.compile(r"\binsurance\b", re.IGNORECASE)
PROTECTION_PARTNERS_RE = re.compile(r"Protection Partners", re.IGNORECASE)
CERTIFIED_COUNT_RE = re.compile(r"(\d+)\s*(?:certified|gold[- ]standard)\s*counties", re.IGNORECASE)

# --- SPR-01 additions (issue #19826, CONTENT_SOP.md SS6 P2/P6/P7/P8/P9/P17/P18) ---

# Canon hard rule 1 (docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md): the
# incumbent's name in both spellings. Strings live in code only, never in prose.
COMPETITOR_TERMS = ["propertyonion", "property onion"]

# Canon: "RETIRED -- never use again: 'Know your number before the gavel.'"
RETIRED_LINES = ["Know your number before the gavel."]

# MISSION SS3 / CONTENT_SOP P2: "S5" and prior internal-shorthand product
# names must never appear publicly -- the public name is always
# "SIGNAL$ Property Report".
RETIRED_PRODUCT_NAME_RE = re.compile(r"\bS5\b")
# "Shapira Max Bid" retired 2026-09-06 (issue #20058) -- public name is
# always "SIGNAL$ Max Bid".
RETIRED_PRODUCT_NAME_PHRASES = ["Shapira Analysis", "Shapira Formula", "Shapira Max Bid"]

# CONTENT_SOP P6: default is no patent mention at all. If unavoidable, exactly
# one of these two phrases -- anything else containing "patent" fails,
# including "12 provisional", "14 patents", "patented", "patent-pending".
PATENT_ALLOWED_PHRASES = [
    "provisional patent application, 14 claims",
    "provisional patent application",
]

URGENCY_PHRASES = ["act now", "limited time", "hurry", "don't miss", "dont miss"]
_TAG_STRIP_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# CONTENT_SOP P9: canon rule 5 is "US county" / "nationwide" -- never these.
POSITIONING_FAIL_PHRASES = ["all 50 states", "3,000 counties", "3000 counties"]

# CONTENT_SOP P17 (N4) -- regex seed given verbatim in the SOP.
CONTEMPT_RE = re.compile(
    r"you'?re doing it wrong|still using spreadsheets|if you'?re still|"
    r"\bamateur\b|rookie mistake|most bidders are too (?:lazy|dumb)",
    re.IGNORECASE,
)

# CONTENT_SOP P18 (N5) -- buzzword denylist given verbatim in the SOP.
BUZZWORD_RE = re.compile(
    r"comprehensive solution|next-gen\b|cutting-edge|streamlined|seamless|"
    r"revolutionary|industry-leading|best-in-class|\bleverage\b|\bsynergy\b|"
    r"robust platform",
    re.IGNORECASE,
)

# Fallback canon strings (as committed 2026-09-03/04) used only if
# docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md is unreadable -- fails
# closed to the last-known canon rather than skipping the check silently.
_CANON_STRINGS_FALLBACK = [
    "EVERY FORECLOSURE. EVERY TAX DEED. YOURS TO WIN.",
    "OUTBID THE GUESSWORK.",
    "For Everyone. Everywhere.",
    "THE BEST PRICES IN US REAL ESTATE ARE SET AT FORECLOSURE AND TAX DEED AUCTIONS.",
    "Our data is your unfair advantage at every US county auction.",
    "We fought in the trenches for over two decades so you don't have to.",
]


def read_artifact_text(paths):
    chunks = []
    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            chunks.append(f.read())
    return "\n".join(chunks)


def check_banned_terms(text):
    hits = [name for name in VENDOR_NAMES if name.lower() in text.lower()]
    return (len(hits) == 0, {"hits": hits})


def check_vendor_name_detector(text):
    # Same source list as banned_terms -- kept as a distinct named check per
    # docs/gtm/MISSION.md's compliance-checks table (#4 in the NEVER-list
    # maps to both banned_terms's phrasing check and this structural check).
    hits = [name for name in VENDOR_NAMES if name.lower() in text.lower()]
    return (len(hits) == 0, {"hits": hits})


def check_person_name_detector(text):
    prose_hits = []
    for m in PERSON_NAME_PROSE_RE.finditer(text):
        if m.group(2) == FOUNDER_NAME:
            continue
        prose_hits.append(m.group(0))
    json_hits = []
    try:
        data = json.loads(text)
        found = _find_keys(data, PERSON_NAME_FIELD_KEYS)
        json_hits = [p for p, v in found if v != FOUNDER_NAME]
    except (json.JSONDecodeError, ValueError):
        pass
    ok = not prose_hits and not json_hits
    return (ok, {"prose_hits": prose_hits, "json_key_hits": json_hits})


def _find_keys(obj, keys, path=""):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k in keys and v:
                found.append((p, v))
            found.extend(_find_keys(v, keys, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_find_keys(v, keys, f"{path}[{i}]"))
    return found


def check_homeowner_contact_scan(text):
    hits = [pat for pat in HOMEOWNER_CONTACT_PATTERNS if re.search(pat, text, re.IGNORECASE)]
    return (len(hits) == 0, {"pattern_hits": hits})


def check_certified_county_count_match(text, supabase_url=None, supabase_key=None):
    matches = CERTIFIED_COUNT_RE.findall(text)
    if not matches:
        # Nothing to check -- no county-count claim in this artifact set.
        return (True, {"claims_found": [], "note": "no certified-county count literal present"})
    supabase_url = supabase_url or os.environ.get("SUPABASE_URL")
    supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        return (False, {"claims_found": matches, "error": "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set -- cannot re-query v_certified_counties live, failing closed"})
    req = urllib.request.Request(
        f"{supabase_url}/rest/v1/v_certified_counties?select=county_slug&consecutive_gold=gte.1",
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Prefer": "count=exact",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_range = resp.headers.get("Content-Range", "")
            live_count = int(content_range.split("/")[-1]) if "/" in content_range else None
    except Exception as e:  # noqa: BLE001 -- report as a failed check, not a crash
        return (False, {"claims_found": matches, "error": f"live query failed: {e}"})
    claimed_counts = {int(m) for m in matches}
    ok = live_count is not None and claimed_counts == {live_count}
    return (ok, {"claims_found": matches, "live_count": live_count})


def check_insurance_exclusivity_scan(text):
    bad_spans = []
    for m in INSURANCE_RE.finditer(text):
        window = text[max(0, m.start() - 200): m.end() + 200]
        if not PROTECTION_PARTNERS_RE.search(window):
            bad_spans.append(text[max(0, m.start() - 30): m.end() + 30])
    return (len(bad_spans) == 0, {"unscoped_mentions": bad_spans})


def check_competitor_terms(text):
    """CONTENT_SOP P2 / canon hard rule 1 -- incumbent's name, both spellings."""
    hits = [t for t in COMPETITOR_TERMS if t.lower() in text.lower()]
    return (len(hits) == 0, {"hits": hits})


def check_retired_lines_and_product_names(text):
    """CONTENT_SOP P2 -- retired tagline + retired/internal product-name strings."""
    line_hits = [ln for ln in RETIRED_LINES if ln.lower() in text.lower()]
    s5_hits = RETIRED_PRODUCT_NAME_RE.findall(text)
    phrase_hits = [p for p in RETIRED_PRODUCT_NAME_PHRASES if p.lower() in text.lower()]
    ok = not line_hits and not s5_hits and not phrase_hits
    return (ok, {"retired_line_hits": line_hits, "s5_hits": s5_hits, "product_name_hits": phrase_hits})


def check_patent_phrasing(text):
    """CONTENT_SOP P6 -- PATENT_RE. Mask the two allowed phrases, anything
    containing "patent" left over is a FAIL."""
    masked = text
    for phrase in sorted(PATENT_ALLOWED_PHRASES, key=len, reverse=True):
        masked = re.sub(re.escape(phrase), "", masked, flags=re.IGNORECASE)
    remaining_hits = [m.group(0) for m in re.finditer(r".{0,25}patent\w*.{0,25}", masked, re.IGNORECASE)]
    return (len(remaining_hits) == 0, {"remaining_patent_mentions": remaining_hits})


def _extract_fenced_block(canon_text, header_regex):
    m = re.search(header_regex + r".*?```\n(.*?)```", canon_text, re.DOTALL)
    return m.group(1) if m else None


def _parse_hero_lines(hero_block):
    lines_out = []
    current = None
    for raw in hero_block.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        lm = re.match(r"Line \d+\s+(.*)", stripped)
        if lm:
            if current is not None:
                lines_out.append(current)
            current = lm.group(1).strip()
        elif current is not None:
            current += " " + stripped
    if current is not None:
        lines_out.append(current)
    return lines_out


def load_canon_strings(canon_path=None):
    """CONTENT_SOP P7 -- CANON_STRINGS read from the canon file, not hardcoded.
    Falls back to the last-known-good list (fails closed) if the canon file
    can't be read."""
    canon_path = canon_path or CANON_MD
    try:
        with open(canon_path, "r", encoding="utf-8") as f:
            canon_text = f.read()
    except OSError:
        return list(_CANON_STRINGS_FALLBACK)

    strings = []
    hero_block = _extract_fenced_block(canon_text, r"## HERO COPY STACK")
    if hero_block:
        strings.extend(_parse_hero_lines(hero_block))
    banner_block = _extract_fenced_block(canon_text, r"## Channel \+ banner \(ship this\)")
    if banner_block:
        # Skip the bare brand name / domain lines ("BidDeed AI", "biddeed.ai")
        # -- those are not distinctive canon copy and would false-positive
        # against any ordinary prose mention of the brand name.
        strings.extend(
            ln.strip() for ln in banner_block.splitlines()
            if ln.strip() and ln.count(" ") >= 2
        )
    m = re.search(r"Short forms:(.*)", canon_text)
    if m:
        strings.extend(re.findall(r"\*\*(.+?)\*\*", m.group(1)))
    m = re.search(r"^>\s*(Every foreclosure.*)$", canon_text, re.MULTILINE)
    if m:
        strings.append(m.group(1).strip())
    return strings or list(_CANON_STRINGS_FALLBACK)


def check_canon_strings(text):
    """CONTENT_SOP P7 -- when a canon string appears, it must be case- and
    punctuation-exact. Absence of a canon string is not a failure."""
    violations = []
    for s in load_canon_strings():
        if not s:
            continue
        pattern = re.compile(re.escape(s), re.IGNORECASE)
        for m in pattern.finditer(text):
            if m.group(0) != s:
                violations.append({"canon": s, "found": m.group(0)})
    return (len(violations) == 0, {"violations": violations})


def _visible_text(text):
    stripped = _TAG_STRIP_RE.sub(" ", text)
    return _HTML_TAG_RE.sub(" ", stripped)


def check_energy_rules(text):
    """CONTENT_SOP P8 -- <=1 '!' in visible text, no manufactured urgency."""
    visible = _visible_text(text)
    bang_count = visible.count("!")
    urgency_hits = [p for p in URGENCY_PHRASES if p in visible.lower()]
    ok = bang_count <= 1 and not urgency_hits
    return (ok, {"exclamation_count": bang_count, "urgency_hits": urgency_hits})


def check_positioning(text):
    """CONTENT_SOP P9 -- never "all 50 states" / "3,000 counties" until live."""
    hits = [p for p in POSITIONING_FAIL_PHRASES if p in text.lower()]
    return (len(hits) == 0, {"hits": hits})


def check_contempt_scan(text):
    """CONTENT_SOP P17 (N4) -- no line shames the reader for the status quo."""
    hits = [m.group(0) for m in CONTEMPT_RE.finditer(text)]
    return (len(hits) == 0, {"hits": hits})


def check_buzzword_scan(text):
    """CONTENT_SOP P18 (N5) -- vividness: buzzword denylist."""
    hits = [m.group(0) for m in BUZZWORD_RE.finditer(text)]
    return (len(hits) == 0, {"hits": hits})


CHECKS = [
    ("banned_terms", check_banned_terms),
    ("person_name_detector", check_person_name_detector),
    ("vendor_name_detector", check_vendor_name_detector),
    ("homeowner_contact_scan", check_homeowner_contact_scan),
    ("certified_county_count_match", check_certified_county_count_match),
    ("insurance_exclusivity_scan", check_insurance_exclusivity_scan),
    ("competitor_terms_scan", check_competitor_terms),
    ("retired_lines_and_product_names_scan", check_retired_lines_and_product_names),
    ("patent_phrasing_scan", check_patent_phrasing),
    ("canon_strings_scan", check_canon_strings),
    ("energy_rules_scan", check_energy_rules),
    ("positioning_scan", check_positioning),
    ("contempt_scan", check_contempt_scan),
    ("buzzword_scan", check_buzzword_scan),
]


def run_compliance_checks(text):
    results = {}
    all_ok = True
    for name, fn in CHECKS:
        ok, detail = fn(text)
        results[name] = {"passed": ok, "detail": detail}
        all_ok = all_ok and ok
    return all_ok, results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", nargs="*", default=[], help="artifact files to run the compliance checks over")
    ap.add_argument("--check-url", default=None, help="optional URL to GET and require 200 for GTM_PAGE_200")
    ap.add_argument("--check-render-file", default=None, help="optional path to a rendered artifact; non-empty required for GTM_RENDER_OK")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON result summary to stderr")
    args = ap.parse_args()

    overall_ok = True
    summary = {}

    if args.paths:
        text = read_artifact_text(args.paths)
        compliance_ok, results = run_compliance_checks(text)
        summary["compliance"] = results
        if compliance_ok:
            print("GTM_COMPLIANCE_PASSED")
        else:
            overall_ok = False
            failed = [k for k, v in results.items() if not v["passed"]]
            print(f"COMPLIANCE FAIL: {', '.join(failed)}", file=sys.stderr)
    else:
        print("no --paths given -- compliance checks not run, GTM_COMPLIANCE_PASSED withheld", file=sys.stderr)
        overall_ok = False

    if args.check_url:
        try:
            req = urllib.request.Request(args.check_url, headers={"User-Agent": "BidDeed-GTM-Gate/1.0 (+https://biddeed.ai)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
        except Exception as e:  # noqa: BLE001
            status = None
            summary["page_check_error"] = str(e)
        summary["page_status"] = status
        if status == 200:
            print("GTM_PAGE_200")
        else:
            overall_ok = False
            print(f"PAGE CHECK FAIL: status={status} error={summary.get('page_check_error')}", file=sys.stderr)

    if args.check_render_file:
        try:
            with open(args.check_render_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            render_ok = len(content.strip()) > 0
        except OSError as e:
            render_ok = False
            summary["render_check_error"] = str(e)
        if render_ok:
            print("GTM_RENDER_OK")
        else:
            overall_ok = False
            print("RENDER CHECK FAIL: empty or unreadable", file=sys.stderr)

    if args.json:
        print(json.dumps(summary, indent=2), file=sys.stderr)

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
