"""LinkedIn B2B agent (CMO Factory CP3g, issue #19789).

Draft generator + T1 validator for .claude/skills/linkedin-b2b-agent/.
Pulls real, re-queryable numbers from public.multi_county_auctions this run
(same query shape as supabase/functions/social-content-generator/index.ts's
generateForCounty()), builds up to 3 drafts across distinct content
pillars, validates each, and writes passing drafts to
public.social_content_queue as status='pending_approval',
target_platform='linkedin_company' -- never higher than pending_approval (M8),
never the legacy 'linkedin_personal' path.

Usage:
    python3 scripts/linkedin_b2b_agent.py            # generate + validate + write
    python3 scripts/linkedin_b2b_agent.py --dry-run   # generate + validate only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
LANDING_URL = "https://biddeed.ai/auctions"

# M3/M7: internal vendor/tool names and homeowner-relief framing that must
# never reach a client-facing surface, same posture as reel-edit-bolt's T1.
_VENDOR_NAMES = [
    "skip-trace", "skip trace", "firecrawl", "deepseek", "glm", "tracerfy",
    "summitleads", "summit leads", "cliproxy", "gemini flash",
]
_HOMEOWNER_PHRASES = [
    "save your home", "facing foreclosure", "foreclosure relief",
    "before you lose your home", "lose your home", "avoid foreclosure",
]
_ENGAGEMENT_BAIT = [
    "comment yes", "drop a", "tag someone who", "like if", "comment below",
]
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
_ISSUE_REF_RE = re.compile(r"#\d{3,6}\b")
_NUMBER_TOKEN_RE = re.compile(r"\$[\d,]+(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+\b|\b\d+(?:\.\d+)?%")


def _rest(path: str, method: str = "GET", body=None, params: str = "", extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    headers = {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"PostgREST {method} {path} -> {e.code}: {e.read().decode()[:500]}") from e


def rpc(name: str, args: dict):
    return _rest(f"rpc/{name}", method="POST", body=args)


def fetch_evidence() -> dict:
    """Real, live aggregate numbers -- pagination-safe: uses
    /rest/v1/rpc/... would need a bespoke function, so this pulls the same
    three columns social-content-generator already relies on but paginates
    with Range headers instead of assuming <1000 rows, since
    multi_county_auctions is 98K+ rows live."""
    rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=opening_bid,assessed_value,sale_type,county&auction_status=eq.upcoming"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": SUPABASE_KEY or "",
                "Authorization": f"Bearer {SUPABASE_KEY or ''}",
                "Range": f"{offset}-{offset + page_size - 1}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.loads(resp.read())
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
        if offset > 200_000:  # hard stop -- never loop unbounded on a data anomaly
            break

    total = len(rows)
    fc = [r for r in rows if r["sale_type"] == "foreclosure"]
    td = [r for r in rows if r["sale_type"] == "tax_deed"]

    def avg(vals):
        vals = [float(v) for v in vals if v is not None and float(v) > 0]
        return round(sum(vals) / len(vals)) if vals else None

    county_counts: dict[str, int] = {}
    for r in rows:
        county_counts[r["county"]] = county_counts.get(r["county"], 0) + 1
    top_county, top_county_count = max(county_counts.items(), key=lambda kv: kv[1]) if county_counts else (None, 0)

    return {
        "total_upcoming": total,
        "fc_count": len(fc),
        "td_count": len(td),
        "avg_opening_bid": avg([r["opening_bid"] for r in rows]),
        "avg_assessed_value": avg([r["assessed_value"] for r in rows]),
        "td_avg_opening": avg([r["opening_bid"] for r in td]),
        "td_avg_assessed": avg([r["assessed_value"] for r in td]),
        "fc_avg_opening": avg([r["opening_bid"] for r in fc]),
        "fc_avg_assessed": avg([r["assessed_value"] for r in fc]),
        "top_county": (top_county or "").replace("_", " ").title(),
        "top_county_count": top_county_count,
    }


def _money(n):
    return f"${n:,.0f}"


def generate_market_pulse_draft(ev: dict) -> str:
    fc_share_pct = round(ev["fc_count"] / ev["total_upcoming"] * 100)
    return (
        f"Florida auction pipeline, right now: {ev['total_upcoming']:,} upcoming lots across the "
        f"counties we track -- {ev['fc_count']:,} mortgage foreclosure, {ev['td_count']:,} tax deed. "
        f"Foreclosure sales make up about {fc_share_pct}% of everything currently on the calendar.\n\n"
        f"{ev['top_county']} County alone carries {ev['top_county_count']:,} of those lots -- the single "
        f"largest concentration in our data right now, well ahead of most other counties we cover.\n\n"
        f"Average opening bid across all upcoming lots sits at {_money(ev['avg_opening_bid'])}, against an "
        f"average assessed value of {_money(ev['avg_assessed_value'])}. Those two numbers move very "
        f"differently by sale type, which is the point of tomorrow's post -- averaging them together "
        f"statewide hides more than it reveals.\n\n"
        f"We re-pull this pipeline daily. If your business touches title, insurance, financing, or "
        f"acquisition around Florida auction property, this is the raw volume you're planning against, "
        f"not a curated highlight reel.\n\n"
        f"Numbers are as of today, pulled directly from our own tracked auction dataset -- happy to "
        f"walk through methodology with anyone who asks."
    )


def generate_data_observation_draft(ev: dict) -> str:
    fc_gap_pct = round((ev["fc_avg_opening"] - ev["fc_avg_assessed"]) / ev["fc_avg_assessed"] * 100)
    td_gap_pct = round((1 - ev["td_avg_opening"] / ev["td_avg_assessed"]) * 100)
    return (
        f"A data observation from this week's Florida auction pipeline that surprises people who assume "
        f"'auction' always means 'discount': it depends entirely on sale type.\n\n"
        f"Tax deed lots: average opening bid {_money(ev['td_avg_opening'])} against an average assessed "
        f"value of {_money(ev['td_avg_assessed'])} -- roughly {td_gap_pct}% below assessed, because the "
        f"opening bid there is just the back taxes owed.\n\n"
        f"Mortgage foreclosure lots: average opening bid {_money(ev['fc_avg_opening'])} against an average "
        f"assessed value of {_money(ev['fc_avg_assessed'])} -- about {fc_gap_pct}% ABOVE assessed, because "
        f"that opening bid is anchored to the judgment amount, not the property's market value.\n\n"
        f"Same word, 'auction,' two completely different pricing mechanics. Screening sale type before "
        f"screening the property is step one for anyone underwriting this pipeline at volume -- treating "
        f"every 'auction' lot as the same kind of opportunity is how that distinction gets missed.\n\n"
        f"We're tracking {ev['fc_count']:,} foreclosure and {ev['td_count']:,} tax deed lots statewide "
        f"right now, so this isn't a small sample -- it's the shape of the whole current pipeline.\n\n"
        f"Pulled from our own live tracked dataset this week -- happy to share the query."
    )


def generate_method_draft(ev: dict) -> str:
    return (
        f"One mechanic worth understanding before you touch Florida auction property: what a sale actually "
        f"wipes out depends on whether it's a tax deed sale or a mortgage foreclosure sale.\n\n"
        f"A tax deed sale exists to collect unpaid property taxes. The opening bid is simply the back taxes "
        f"owed, and a clean tax deed sale wipes out most junior liens recorded against the property.\n\n"
        f"A mortgage foreclosure sale is different: it only wipes out liens junior to the foreclosing "
        f"mortgage. Liens senior to it -- and certain government liens -- can survive the sale and attach "
        f"to whoever buys. That's why foreclosure opening bids are anchored to the judgment amount rather "
        f"than the property's market value.\n\n"
        f"We're tracking {ev['fc_count']:,} foreclosure and {ev['td_count']:,} tax deed lots in our current "
        f"pipeline -- two very different diligence checklists wearing the same word, 'auction.'\n\n"
        f"This is informational, not legal advice -- verify lien position independently before bidding on "
        f"either sale type."
    )


def validate_linkedin_draft(text: str, evidence: dict, banned_names: list[str] | None = None) -> dict:
    reasons = []
    banned_names = banned_names or []

    if not (900 <= len(text) <= 1300):
        reasons.append(f"length {len(text)} outside 900-1300")

    lower = text.lower()
    for name in banned_names:
        if name and name.lower() in lower:
            reasons.append(f"contains banned name: {name}")
    for phrase in _HOMEOWNER_PHRASES:
        if phrase in lower:
            reasons.append(f"homeowner-relief framing: {phrase!r}")
    for phrase in _ENGAGEMENT_BAIT:
        if phrase in lower:
            reasons.append(f"engagement bait: {phrase!r}")
    for vendor in _VENDOR_NAMES:
        if vendor in lower:
            reasons.append(f"internal vendor/tool name: {vendor!r}")
    if _ISSUE_REF_RE.search(text):
        reasons.append("contains an issue/run-number-shaped reference (#NNN)")

    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if _EMOJI_RE.match(first_line.strip()):
        reasons.append("first line opens with an emoji")
    first_word = first_line.strip().split(" ", 1)[0] if first_line.strip() else ""
    if len(first_word) >= 3 and first_word.isupper() and first_word.isalpha():
        reasons.append(f"first word is ALL-CAPS shock word: {first_word!r}")

    evidence_strs = set()
    for v in evidence.values():
        if isinstance(v, (int, float)):
            evidence_strs.add(f"{v:,.0f}")
            evidence_strs.add(str(int(v)))
        elif v is not None:
            evidence_strs.add(str(v))
    # derived percentages are computed FROM evidence values in the generator
    # functions above, not independently sourced -- allow any 1-3 digit %
    # token through since it's arithmetic on verified inputs, not a new claim.
    for token in _NUMBER_TOKEN_RE.findall(text):
        if token.endswith("%"):
            continue
        clean = token.lstrip("$").replace(",", "")
        if clean not in evidence_strs and token.lstrip("$") not in evidence_strs:
            reasons.append(f"number {token!r} not traceable to this run's evidence dict")

    return {"passed": len(reasons) == 0, "reasons": reasons}


PILLARS = [
    ("market_pulse", generate_market_pulse_draft),
    ("data_observation", generate_data_observation_draft),
    ("method", generate_method_draft),
]


def run(dry_run: bool) -> list[dict]:
    evidence = fetch_evidence()
    results = []
    for pillar, generator in PILLARS:
        text = generator(evidence)
        verdict = validate_linkedin_draft(text, evidence)
        entry = {"pillar": pillar, "draft_text": text, "evidence": evidence, "validator": verdict, "queue_row_id": None}
        if not verdict["passed"]:
            results.append(entry)
            continue

        if dry_run:
            results.append(entry)
            continue

        link = rpc(
            "create_platform_short_link",
            {"p_reel_id": None, "p_platform": "linkedin_company", "p_variant_key": pillar, "p_target": LANDING_URL},
        )
        short_code = link["code"]

        row = _rest(
            "social_content_queue",
            method="POST",
            body={
                "content_hash": f"linkedin_company_{pillar}_{evidence['total_upcoming']}_{evidence['fc_count']}_{evidence['td_count']}",
                "target_platform": "linkedin_company",
                "source_type": "linkedin_b2b_agent",
                "source_ref": pillar,
                "content_text": text,
                "status": "pending_approval",
                "variant_key": pillar,
                "short_code": short_code,
                "utm_source": "linkedin_company",
                "utm_content": pillar,
                "value_source": "multi_county_auctions",
            },
            extra_headers={"Prefer": "return=representation,resolution=ignore-duplicates"},
        )
        entry["queue_row_id"] = row[0]["id"] if row else None
        results.append(entry)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = run(dry_run=args.dry_run)
    print(json.dumps(out, indent=2, default=str))
    if any(not r["validator"]["passed"] for r in out):
        sys.exit(1)
