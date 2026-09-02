#!/usr/bin/env python3
"""Sunbiz identity-resolution cascade for LLC/corp buyers with no fl_parcels
prior-deed mailing address on file (the 12-of-24 bucket that sank #19447 to
0 phones -- see issue "Identity cascade + PORTFOLIO Fact Finder", 2026-08-25).

fl_parcels.own_name exact-match is step 1 of the cascade and is NOT
implemented here -- it already ran in scripts/skiptrace_20260824_phase2_leads.py
and is what produced the 12-vs-7 split this module picks up after. This
module is steps 2-5:

  2. Exa search + contents (api.exa.ai) -- returns Sunbiz/mirror pages from
     Exa's own crawl index, so no Cloudflare challenge hits our IP. VERIFIED
     live 2026-08-25: ZANO INVESTMENTS LLC -> doc L25000088440, Manager Louis
     Frazano, exact match to the issue's own proof.
  3. Sunbiz mirrors (bisprofiles.com, bizprofile.net) direct fetch -- VERIFIED
     live 2026-08-25 this returns Cloudflare interstitial (HTTP 403) from this
     sandbox's IP, contrary to the issue's "no bot protection" claim. Kept as
     a cascade leg (some pages may not be Cloudflare-fronted) but expect it to
     fail most of the time; step 2 already covers these same mirrors via Exa's
     cache.
  4. Bright Data Browser API (BRIGHTDATA_BROWSER_WSS, CDP over websocket) --
     VERIFIED live 2026-08-25: connect_over_cdp succeeds. Used only if 2+3
     both miss.
  5. Local Playwright + Chromium direct against search.sunbiz.org -- last
     resort; almost certainly blocked by the same Cloudflare challenge as
     step 3 from a datacenter IP, but the cascade must still try it before
     tagging a buyer unresolved.

Exact-name discipline: normalize(a) == normalize(b) required (see normalize()
below) -- substring/fuzzy hits are logged and discarded, never used. This is
the same rigor #19447 already applied when it discarded "CRUZ MANZANO
INVESTMENTS LLC" as a false match for "ZANO INVESTMENTS LLC".
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
BRIGHTDATA_BROWSER_WSS = os.environ.get("BRIGHTDATA_BROWSER_WSS", "")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

MIRROR_HOSTS = ["bisprofiles.com", "bizprofile.net", "opengovus.com", "corporationwiki.com"]
SUFFIX_NOISE = re.compile(r"[.,]")


def normalize(name: str) -> str:
    """Uppercase, strip periods/commas, collapse whitespace, collapse spacing
    around '&' (E & M == E&M -- pure formatting variance across sources).
    Deliberately does NOT strip legal-suffix words (LLC/INC/CORP) or drop
    words, and does NOT normalize '&' to 'AND' -- those distinctions are
    exactly what separates real matches from coincidental substring hits
    (E&M PLUMBING OF MIAMI INC != E&M PLUMBING INC, missing "OF MIAMI")."""
    if not name:
        return ""
    n = SUFFIX_NOISE.sub("", name.upper())
    n = re.sub(r"\s*&\s*", "&", n)
    return re.sub(r"\s+", " ", n).strip()


def log(msg: str) -> None:
    print(f"[identity_cascade] {msg}", flush=True)


_BIZ_SUFFIX_RE = re.compile(r"\b(LLC|INC|CORP|LP|LLP|GROUP|CO|LTD)\b", re.I)


def normalize_person_name(name: str) -> str:
    """Issue #19746 item 3: the bizprofile.net officer-prose leg of
    parse_sunbiz_text() (name_tok pattern above) can emit 'Last, First[, Sr/Jr]'
    order literally, comma included (e.g. '770 PRO INC' -> officer 'Panah,
    David'). A literal comma in principal_name breaks the fl_parcels
    self-match LIKE substring query downstream (fl_parcels.own_name never has
    a comma in that exact position for this name) and reads oddly to a human.
    Reverses ONLY the unambiguous two-part 'Word[s], Word[s]' shape into
    'First Last'; a business name that happens to contain a comma (e.g.
    'Casscap, LLC') is left untouched by checking for a legal-entity suffix
    first. Anything else (no comma, 3+ comma parts) passes through unchanged."""
    if not name or "," not in name:
        return (name or "").strip()
    if _BIZ_SUFFIX_RE.search(name):
        return name.strip()
    parts = [p.strip() for p in name.split(",")]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return name.strip()
    last, first = parts
    return f"{first} {last}"


# ---------------------------------------------------------------------------
# Step 2: Exa search + contents
# ---------------------------------------------------------------------------

def exa_search(query: str, num_results: int = 5, domains: list[str] | None = None) -> list[dict]:
    if not EXA_API_KEY:
        return []
    payload = {"query": query, "numResults": num_results, "type": "neural"}
    if domains:
        payload["includeDomains"] = domains
    req = urllib.request.Request(
        "https://api.exa.ai/search",
        data=json.dumps(payload).encode(),
        headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read()).get("results", [])
    except Exception as e:
        log(f"Exa search failed: {e}")
        return []


def exa_contents(urls: list[str]) -> list[dict]:
    if not EXA_API_KEY or not urls:
        return []
    req = urllib.request.Request(
        "https://api.exa.ai/contents",
        data=json.dumps({"urls": urls, "text": True}).encode(),
        headers={"x-api-key": EXA_API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read()).get("results", [])
    except Exception as e:
        log(f"Exa contents failed: {e}")
        return []


def parse_sunbiz_text(text: str) -> dict:
    """Parse the text Exa returns for a bisprofiles.com/bizprofile.net Sunbiz
    detail page. Handles three known site formats:
      - bisprofiles.com (current, verified live 2026-09-02): prose/headers,
        no markdown-list bullets ("Principal Address <addr>",
        "#### <Name>\\n\\nPosition <Position> Active From <City, ST>",
        "### Registered Agent is <Name>\\n\\nFrom <City, ZIP>")
      - bisprofiles.com (older markdown-list form, kept for back-compat in
        case older cached pages still use it): "- Principal Address\\n- <addr>",
        "#### <Name>\\n\\n- Position\\n- <Position> Active\\n- Address\\n- <addr>"
      - bizprofile.net: prose ("document number <N>", "principal and mailing
        address ... is situated at <addr>", "led by ... <Name> from <city>
        <ST>, holding the position of <Position>", "<Name> acts as the
        registered agent. He/She is based at <addr>")
    Returns principal_address, mailing_address, status, doc_number, and a
    list of officers [{name, position, address}]. Never invents a field it
    can't find -- unmatched fields stay None/[]."""
    out = {"principal_address": None, "mailing_address": None, "status": None,
           "doc_number": None, "officers": []}
    m = re.search(r"registered number ([A-Z0-9]+)", text) or re.search(r"document number ([A-Z0-9]+)", text, re.I)
    if m:
        out["doc_number"] = m.group(1)
    m = re.search(r"is an (Active|Inactive)", text) or re.search(r"^(Active|Inactive)\s*$", text, re.M)
    if m:
        out["status"] = m.group(1)

    m = re.search(r"Principal Address\n-\s*([^\n]+)", text)
    if m:
        out["principal_address"] = m.group(1).strip()
    m = re.search(r"Mailing Address\n-\s*([^\n]+)", text)
    if m:
        out["mailing_address"] = m.group(1).strip()
    if not out["principal_address"]:
        m = re.search(r"principal (?:and mailing )?address of the corporation is situated at ([^.]+?)(?:,\s*(?:serving|Florida)|\.)", text, re.I)
        if m:
            out["principal_address"] = m.group(1).strip()
            if "mailing" in m.group(0).lower():
                out["mailing_address"] = out["principal_address"]
    if not out["principal_address"]:
        # bisprofiles.com current prose form: "Principal Address <addr>" on
        # one line, no bullet/newline separator.
        m = re.search(r"Principal Address\s+([\d][^\n]+)", text)
        if m:
            out["principal_address"] = m.group(1).strip()

    for om in re.finditer(r"#### ([^\n]+)\n\n- Position\n- ([^\n]+)\n- (?:Address|From)\n- ([^\n]+)", text):
        name, position, addr = om.group(1).strip(), om.group(2).strip(), om.group(3).strip()
        out["officers"].append({"name": name, "position": position, "address": addr})

    # bisprofiles.com current prose officer pattern:
    # "#### <Name>\n\nPosition <Position> Active From <City, ST>"
    for om in re.finditer(r"#### ([A-Z][a-zA-Z.,'-]+(?:\s[A-Z][a-zA-Z.,'-]+){0,3})\n\nPosition ([A-Za-z /]+?) (?:Active|Inactive) From ([A-Za-z .]+,\s*[A-Z]{2})", text):
        name, position, addr = om.group(1).strip(), om.group(2).strip(), om.group(3).strip()
        out["officers"].append({"name": name, "position": position, "address": addr})

    # bizprofile.net prose officer pattern: "<Last, First[, Sr/Jr]> from <City ST>, holding the position of <Position>"
    name_tok = r"[A-Z][a-zA-Z.'-]+(?:,?\s(?:Sr|Jr)?\.?\s?[A-Z][a-zA-Z.'-]+){0,3}"
    for om in re.finditer(rf"({name_tok}) from ([A-Za-z .]+? [A-Z]{{2}}),? holding the position of ([A-Za-z /]+?)[.,]", text):
        name, city, position = om.group(1).strip().rstrip(","), om.group(2).strip(), om.group(3).strip()
        out["officers"].append({"name": name, "position": position, "address": city})
    m = re.search(rf"({name_tok}) acts as the registered agent\.\s*(?:He|She|They) is based at ([^.]+)\.", text)
    if m:
        name, addr = m.group(1).strip().rstrip(","), m.group(2).strip()
        if "same address as the corporation's principal address" in addr and out["principal_address"]:
            addr = out["principal_address"]
        out["officers"].append({"name": name, "position": "Registered Agent", "address": addr})

    # bisprofiles.com current prose registered-agent pattern:
    # "### Registered Agent is <Name>\n\nFrom <City, ZIP>"
    m = re.search(r"Registered Agent is ([A-Z][a-zA-Z.,'-]+(?:\s[A-Z][a-zA-Z.,'-]+){0,3})\n\nFrom ([A-Za-z0-9, ]+)", text)
    if m:
        name, addr = m.group(1).strip(), m.group(2).strip()
        if not any(o["name"] == name and o["position"] == "Registered Agent" for o in out["officers"]):
            out["officers"].append({"name": name, "position": "Registered Agent", "address": addr})
    return out


def resolve_via_exa(entity_name: str) -> dict | None:
    # issue #19744 root cause: the domain-restricted bare-name query finds
    # the correct exact-name mirror page far more often than the noisy
    # "... Sunbiz Florida Division of Corporations" query (verified live
    # 2026-09-02 against JAYKAILASH LLC, COY PROPERTIES LLC, QUEEN EQUITIES
    # LLC -- all real active Sunbiz entities the noisy query's neural
    # ranking pushed out in favor of similarly-named wrong companies). The
    # old code only ran the domain-restricted query when the noisy query
    # found ZERO mirror-host candidates -- but the noisy query almost always
    # finds SOME (wrong) mirror-host candidates for common LLC name
    # patterns, so the better fallback query almost never actually ran.
    # Now: always run both, domain-restricted first (more precise), and
    # dedupe by URL instead of short-circuiting.
    domain_results = exa_search(entity_name, num_results=8, domains=MIRROR_HOSTS)
    noisy_results = exa_search(f"{entity_name} Sunbiz Florida Division of Corporations", num_results=8)
    seen_urls = set()
    candidates = []
    for r in domain_results + noisy_results:
        url = r.get("url", "")
        if url in seen_urls or not any(h in url for h in MIRROR_HOSTS):
            continue
        seen_urls.add(url)
        candidates.append(r)
    target = normalize(entity_name)
    for r in candidates:
        # strip trailing " - <suffix>" / " | <suffix>" boilerplate, then require
        # the normalized entity name to be an exact, space-aligned PREFIX of the
        # normalized title (mirrors append "<City>, <ST> - filing information"
        # after the real name; this must not become a substring match anywhere).
        title_norm = normalize(re.sub(r"\s*[-|].*$", "", r.get("title", "")))
        if not (title_norm == target or title_norm[: len(target)] == target and (len(title_norm) == len(target) or title_norm[len(target)] == " ")):
            log(f"  Exa candidate '{r.get('title')}' discarded -- not an exact-name match for '{entity_name}'")
            continue
        contents = exa_contents([r["url"]])
        for c in contents:
            text = c.get("text", "")
            if not text:
                continue
            parsed = parse_sunbiz_text(text)
            if not parsed["officers"] and not parsed["principal_address"]:
                continue
            return {"source_step": "exa", "url": r["url"], "raw": parsed}
    return None


# ---------------------------------------------------------------------------
# Step 3: Sunbiz mirrors, direct fetch
# ---------------------------------------------------------------------------

def slugify(entity_name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", entity_name.lower()).strip("-")
    return s


def resolve_via_mirror_direct(entity_name: str) -> dict | None:
    slug = slugify(entity_name)
    for host in MIRROR_HOSTS:
        url = f"https://www.{host}/fl/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", "replace")
        except Exception as e:
            log(f"  mirror direct fetch {url} failed: {e}")
            continue
        if "Just a moment" in html or "challenges.cloudflare.com" in html:
            log(f"  mirror direct fetch {url}: Cloudflare interstitial, not real content")
            continue
        return {"source_step": "mirror_direct", "url": url, "raw_html": html}
    return None


# ---------------------------------------------------------------------------
# Step 4: Bright Data Browser API
# ---------------------------------------------------------------------------

def resolve_via_brightdata(entity_name: str) -> dict | None:
    if not BRIGHTDATA_BROWSER_WSS:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("  Bright Data leg skipped: playwright not importable")
        return None
    import ff_credit_ledger
    ledger = ff_credit_ledger.spend("brightdata", 1)
    if not ledger.get("granted"):
        log(f"  Bright Data leg skipped: daily ff_daily_credit_ledger cap reached ({ledger})")
        return None
    url = f"https://search.sunbiz.org/Inquiry/corporationsearch/ByName"
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(BRIGHTDATA_BROWSER_WSS, timeout=30000)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.fill("#SearchTerm", entity_name)
            page.click("input[type=submit]")
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()
        if normalize(entity_name) not in normalize(html):
            log(f"  Bright Data fetch for '{entity_name}': entity name not present in result page, no exact match")
            return None
        return {"source_step": "brightdata_browser", "url": url, "raw_html": html}
    except Exception as e:
        log(f"  Bright Data leg failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 5: local Playwright + Chromium, last resort
# ---------------------------------------------------------------------------

def resolve_via_playwright_direct(entity_name: str) -> dict | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("  Playwright-direct leg skipped: playwright not importable")
        return None
    url = "https://search.sunbiz.org/Inquiry/corporationsearch/ByName"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=UA)
            page.goto(url, timeout=20000)
            content = page.content()
            browser.close()
        if "Just a moment" in content or "challenges.cloudflare.com" in content:
            log("  Playwright-direct: Cloudflare interstitial from this IP, as expected")
            return None
        return {"source_step": "playwright_direct", "url": url, "raw_html": content}
    except Exception as e:
        log(f"  Playwright-direct leg failed: {e}")
        return None


CASCADE_STEPS = [
    ("exa", resolve_via_exa),
    ("mirror_direct", resolve_via_mirror_direct),
    ("brightdata_browser", resolve_via_brightdata),
    ("playwright_direct", resolve_via_playwright_direct),
]


def resolve_identity(entity_name: str) -> dict:
    """Runs the 4-leg cascade (Exa -> mirrors -> Bright Data -> Playwright)
    in order, stopping at the first exact-name hit. Returns:
      {resolved: bool, entity_name, source_step, sources_tried: [...],
       principal_name, principal_address, mailing_address, officers, doc_number}
    """
    sources_tried = []
    for step_name, fn in CASCADE_STEPS:
        sources_tried.append(step_name)
        try:
            hit = fn(entity_name)
        except Exception as e:
            log(f"  step {step_name} raised: {e}")
            hit = None
        if hit and hit.get("raw"):
            raw = hit["raw"]
            person_officers = [o for o in raw.get("officers", []) if not re.search(r"\bLLC\b|\bINC\b|\bCORP\b|\bLTD\b", o["name"], re.I)]
            principal_name = person_officers[0]["name"] if person_officers else (raw["officers"][0]["name"] if raw.get("officers") else None)
            if principal_name:
                principal_name = normalize_person_name(principal_name)
            return {
                "resolved": True,
                "entity_name": entity_name,
                "source_step": hit["source_step"],
                "source_url": hit.get("url"),
                "sources_tried": sources_tried,
                "principal_name": principal_name,
                "principal_address": raw.get("principal_address"),
                "mailing_address": raw.get("mailing_address"),
                "officers": raw.get("officers", []),
                "doc_number": raw.get("doc_number"),
                "status": raw.get("status"),
            }
    return {
        "resolved": False,
        "entity_name": entity_name,
        "source_step": None,
        "sources_tried": sources_tried,
        "tag": "no individual name on record",
    }


if __name__ == "__main__":
    import sys
    for name in sys.argv[1:] or ["ZANO INVESTMENTS LLC"]:
        print(json.dumps(resolve_identity(name), indent=2, default=str))
