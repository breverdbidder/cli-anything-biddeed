#!/usr/bin/env python3
"""Contact resolution cascade v2 (issue #19454) -- wires the paid assets the
issue audit found provisioned but never called: HUNTER_API_KEY (GH secret,
verified live 2026-08-25: Free plan, 50 domain-search/email-finder credits,
100 verification credits) and apify_api_token (Supabase vault, verified live
2026-08-25: FREE plan, $5/mo cap, ~$3.36 remaining after this account's prior
usage). ZoomInfo and Endato/EnformionGO were checked live the same session:
no MCP server is registered (`claude mcp list` -> "No MCP servers
configured") and no credential exists under any plausible name in GH secrets
or the Supabase vault (vault_secret() returned null for zoominfo_api_key,
zoominfo_client_id, zoominfo_username, zoominfo_password, endato_api_key,
enformion_api_key, enformiongo_api_key -- all checked live). Those two tiers
are therefore honest BLOCKED_NO_CREDENTIAL stubs, not fabricated
integrations -- see resolve_zoominfo()/resolve_endato() below.

Tier 1 (business identity), in cascade order:
  1. Apify Google Maps (compass/crawler-google-places, pay-per-event:
     $0.007 actor-start + $0.004/place) -- VERIFIED live 2026-08-25 against
     "E&M Plumbing of Miami Inc, Miami FL" -> real phone (786) 712-2809 +
     website emplumbingmiami.com. Contractors/property companies almost
     always have a GMB listing; this is the highest-yield leg for this
     buyer population.
  2. Hunter.io domain-search on the domain Apify found (or a company-name
     search if Apify found nothing) -- returns Hunter's own indexed emails
     for that domain plus an accept-all/pattern flag. VERIFIED live: for a
     small single-domain contractor site (emplumbingmiami.com) Hunter's
     crawl index had ZERO emails -- small-business sites are frequently
     outside Hunter's crawl. Do not assume Hunter always has data; report
     "0 emails indexed" honestly when that's what the API returns.
  3. Hunter email-finder(domain, first, last) -- only called when a
     principal name is known (from the Sunbiz identity cascade) AND
     domain-search returned zero emails but a non-null pattern, to avoid
     burning credits guessing at a name Hunter has no signal for.
  4. Hunter email-verifier on whatever candidate email tier 2/3 produced --
     never deliver a Hunter email-finder result without this pass.
  5. OSS email-permutation + MX/SMTP RCPT validation (no vendor) -- last
     resort. VERIFIED live 2026-08-25: MX lookup works everywhere (dig +short
     MX), but RCPT-TO probing against a real target (emplumbingmiami.com,
     hosted on Hostinger) returned "554 5.7.1 Relay access denied" for
     EVERY candidate including obviously-plausible ones -- Hostinger (and
     most shared-hosting mail platforms) reject RCPT probing outright as
     an anti-enumeration measure, independent of whether the address is
     real. This is a genuine, permanent ceiling for this method against
     shared-hosting domains, not a bug to retry around. Per the issue's own
     rule ("Never deliver an unverified permutated email. Validate or
     drop.") any candidate that gets an inconclusive/relay-denied RCPT
     response is DROPPED, never delivered as a guess.

Tier 2 (natural persons): Tracerfy enhanced trace (scripts/tracerfy_client.py,
unchanged, already proven 88% hit rate against a buyer's own prior-deed
mailing address) + Endato/EnformionGO fallback (BLOCKED_NO_CREDENTIAL, see
above).

Every resolve_* function returns a result dict with at minimum:
  {resolved: bool, tier, source, confidence, verified_at, sources_tried: [...]}
verified_at is populated by the caller (batch runner) with a real UTC
timestamp at call time -- this module has no clock access requirement itself
so it stays trivially testable.
"""
from __future__ import annotations

import json
import os
import re
import smtplib
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")
UA = "contact-resolver-v2/1.0 (BidDeed.AI)"

_SUFFIX_STOP = {"INC", "LLC", "CORP", "LTD", "PL", "PLC", "LC", "LP", "PA",
                "THE", "OF", "AND", "CO", "COMPANY", "TRUSTEE", "TRUST"}


def log(msg: str) -> None:
    print(f"[contact_resolver] {msg}", flush=True)


def _sig_tokens(name: str) -> set[str]:
    """Significant-word set for cheap name-similarity checks: uppercase,
    strip punctuation, drop legal-suffix/filler words. Deliberately coarse
    (token-set overlap, not fuzzy string distance) -- good enough to catch
    a Google Maps / Hunter mismatch pointing at a completely unrelated
    business, which is the actual failure mode observed live 2026-08-25
    ('770 PRO INC' search returned an unrelated FL state-government listing;
    'LY AUCTION PROPERTIES INVESTORS, CORP' returned an unrelated 'Elite
    Auctions' listing -- zero token overlap in both real cases)."""
    cleaned = re.sub(r"[.,&]", " ", name.upper())
    return {t for t in cleaned.split() if t not in _SUFFIX_STOP and len(t) > 1}


def name_match(entity_name: str, candidate_title: str | None) -> bool:
    """True only if the candidate shares at least half of the entity's
    significant tokens (and at least one). Prevents an unrelated listing
    (wrong business entirely) from silently becoming this buyer's phone/
    domain -- see _sig_tokens docstring for the live false-positive this
    guards against."""
    e = _sig_tokens(entity_name)
    c = _sig_tokens(candidate_title or "")
    if not e or not c:
        return False
    overlap = e & c
    return len(overlap) >= 1 and len(overlap) / len(e) >= 0.5


# ---------------------------------------------------------------------------
# Tier 1, leg 1: Apify Google Maps (compass/crawler-google-places)
# ---------------------------------------------------------------------------

def apify_google_maps(business_name: str, city: str | None, state: str, apify_token: str, timeout: int = 90) -> dict | None:
    """One place, pay-per-event ($0.007 start + $0.004 scraped, ~$0.011/call).
    Returns {title, phone, phone_e164, website, name_matched} or None if
    Apify returned no place / the call failed. name_matched (see name_match())
    gates whether the caller may trust phone/website as belonging to this
    buyer -- a Google Maps text-search hit is NOT proof of identity by
    itself, especially with a weak query (no city, e.g. no fl_parcels
    mailing-address history for this buyer). VERIFIED live 2026-08-25: an
    unguarded weak-query match returned an entirely unrelated business for
    2 of the first 15 buyers tried (see _sig_tokens docstring) -- both were
    caught and reverted only because this field was added after the fact.
    Never trust phone/website from this function without checking
    name_matched first."""
    if not apify_token:
        return None
    query = f"{business_name}, {city}, {state}" if city else f"{business_name}, {state}"
    payload = {
        "searchStringsArray": [query],
        "maxCrawledPlacesPerSearch": 1,
        "language": "en",
        "skipClosedPlaces": False,
    }
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items?token={apify_token}&timeout={timeout}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            items = json.loads(resp.read())
    except Exception as e:
        log(f"  Apify Google Maps call failed for '{business_name}': {e}")
        return None
    if not items:
        log(f"  Apify Google Maps: no listing found for '{business_name}' ({query})")
        return None
    it = items[0]
    matched = name_match(business_name, it.get("title"))
    if not matched:
        log(f"  Apify Google Maps: listing '{it.get('title')}' for query '{query}' "
            f"does NOT name-match '{business_name}' -- discarding (not used for phone/domain)")
    return {
        "title": it.get("title"),
        "phone": it.get("phone"),
        "phone_e164": it.get("phoneUnformatted"),
        "website": it.get("website"),
        "address": it.get("address"),
        "name_matched": matched,
    }


# ---------------------------------------------------------------------------
# Tier 1, legs 1b/1c: Apify leads-finder + waterfall-contact-enricher
# (issue #19563 P0, added 2026-08-28) -- both require FULL_PERMISSIONS on the
# Apify account (unlike Google Maps' LIMITED_PERMISSIONS), which can only be
# granted by a human clicking approve at console.apify.com -- verified live
# 2026-08-28: both return HTTP 403 full-permission-actor-not-approved until
# that happens. These functions surface that as an explicit blocked state
# (never silently treated as "no data") and start working automatically the
# moment the account owner approves, no code change required.
# ---------------------------------------------------------------------------

_PERMISSION_APPROVAL_URLS = {
    "code_crafter~leads-finder": "https://console.apify.com/actors/IoSHqwTR9YGhzccez?approvePermissions=true",
    "fatihtahta~waterfall-contact-enricher": "https://console.apify.com/actors/FpuoTo0ktReRORcMq?approvePermissions=true",
}


def _apify_run_and_wait(actor_id: str, payload: dict, apify_token: str,
                         max_total_charge_usd: float = 0.5, timeout: int = 120) -> dict:
    """POST /runs -> poll /actor-runs/{id} -> GET /datasets/{id}/items. Returns
    {"items": [...]} on success, {"blocked": True, "reason": ...} on the
    full-permission-actor-not-approved 403, or {"error": ...} on any other
    failure. Never raises -- callers treat all three as "no usable data"
    except blocked, which is surfaced distinctly for honest reporting."""
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{actor_id}/runs?token={apify_token}&maxTotalChargeUsd={max_total_charge_usd}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            start = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 403 and "full-permission-actor-not-approved" in body:
            log(f"  {actor_id}: BLOCKED -- account owner must approve {_PERMISSION_APPROVAL_URLS.get(actor_id, actor_id)}")
            return {"blocked": True, "reason": "FULL_PERMISSIONS_NOT_APPROVED",
                     "approval_url": _PERMISSION_APPROVAL_URLS.get(actor_id)}
        log(f"  {actor_id} run start HTTP {e.code}: {body[:300]}")
        return {"error": f"HTTP {e.code}: {body[:300]}"}
    except Exception as e:
        log(f"  {actor_id} run start failed: {e}")
        return {"error": str(e)}

    run_id = start["data"]["id"]
    dataset_id = start["data"]["defaultDatasetId"]
    deadline = time.time() + timeout
    status = "READY"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(f"https://api.apify.com/v2/actor-runs/{run_id}?token={apify_token}",
                                        headers={"User-Agent": UA}), timeout=20) as resp:
                status = json.loads(resp.read())["data"]["status"]
        except Exception as e:
            log(f"  {actor_id} run poll failed: {e}")
            break
        if status not in ("READY", "RUNNING"):
            break
        time.sleep(5)
    if status != "SUCCEEDED":
        return {"error": f"run ended status={status}"}

    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={apify_token}",
                                    headers={"User-Agent": UA}), timeout=30) as resp:
            items = json.loads(resp.read())
    except Exception as e:
        log(f"  {actor_id} dataset fetch failed: {e}")
        return {"error": str(e)}
    return {"items": items}


def apify_leads_finder(business_name: str, domain: str | None, apify_token: str) -> dict:
    """Apollo-style leads: domain-filtered if a domain is already known
    (higher confidence), otherwise falls back to a company_keywords search
    on the business name's significant tokens -- weaker signal, so callers
    MUST gate any returned company_name through name_match() before trusting
    phone/email (same discipline as apify_google_maps)."""
    if not apify_token:
        return {"error": "no_token"}
    payload = {"fetch_count": 5, "file_name": f"ff-resolve-{business_name[:40]}"}
    keyword_mode = not domain
    if domain:
        payload["company_domain"] = [domain]
    else:
        tokens = list(_sig_tokens(business_name))[:4]
        if not tokens:
            return {"error": "no_usable_tokens"}
        payload["company_keywords"] = tokens
        payload["contact_location"] = ["united states"]
    result = _apify_run_and_wait("code_crafter~leads-finder", payload, apify_token)
    if result.get("blocked") or result.get("error"):
        return result
    candidates = []
    for it in result.get("items", []):
        cname = it.get("company_name") or it.get("organization_name") or it.get("company")
        if keyword_mode and not name_match(business_name, cname):
            continue
        email = it.get("email") or it.get("work_email") or it.get("business_email")
        phone = it.get("phone") or it.get("company_phone") or it.get("mobile_phone")
        if email or phone:
            candidates.append({"company_name": cname, "email": email, "phone": phone,
                                "website": it.get("website") or it.get("company_domain")})
    return {"items": result.get("items", []), "candidates": candidates}


def apify_waterfall_enricher(domain: str, apify_token: str) -> dict:
    """Domain-only enrichment -- only callable once a domain is already known
    (e.g. from apify_google_maps)."""
    if not apify_token or not domain:
        return {"error": "no_token_or_domain"}
    payload = {"domains": [domain], "maxResults": 5}
    result = _apify_run_and_wait("fatihtahta~waterfall-contact-enricher", payload, apify_token)
    if result.get("blocked") or result.get("error"):
        return result
    candidates = []
    for it in result.get("items", []):
        email = it.get("email") or it.get("work_email")
        phone = it.get("phone") or it.get("company_phone")
        if email or phone:
            candidates.append({"company_name": it.get("organization_name") or it.get("company_name"),
                                "email": email, "phone": phone, "website": domain})
    return {"items": result.get("items", []), "candidates": candidates}


# ---------------------------------------------------------------------------
# Tier 1, legs 2-4: Hunter.io
# ---------------------------------------------------------------------------

def hunter_account() -> dict | None:
    if not HUNTER_API_KEY:
        return None
    req = urllib.request.Request(f"https://api.hunter.io/v2/account?api_key={HUNTER_API_KEY}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())["data"]
    except Exception as e:
        log(f"  Hunter account check failed: {e}")
        return None


def _hunter_get(path: str, params: dict) -> dict | None:
    if not HUNTER_API_KEY:
        return None
    params = {**params, "api_key": HUNTER_API_KEY}
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"https://api.hunter.io/v2/{path}?{q}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        log(f"  Hunter {path} HTTP {e.code}: {body}")
        return None
    except Exception as e:
        log(f"  Hunter {path} failed: {e}")
        return None


def hunter_domain_search(domain: str | None = None, company: str | None = None) -> dict | None:
    """1 search credit. domain OR company (Hunter resolves company->domain
    itself when only company is given)."""
    params = {}
    if domain:
        params["domain"] = domain
    if company:
        params["company"] = company
    resp = _hunter_get("domain-search", params)
    if not resp or "data" not in resp:
        return None
    return resp["data"]


def hunter_email_finder(domain: str, first_name: str, last_name: str) -> dict | None:
    """1 search credit. Only call when a real principal name is known."""
    resp = _hunter_get("email-finder", {"domain": domain, "first_name": first_name, "last_name": last_name})
    if not resp or "data" not in resp:
        return None
    return resp["data"]


def hunter_verify_email(email: str) -> dict | None:
    """1 verification credit (separate 100-credit pool from search)."""
    resp = _hunter_get("email-verifier", {"email": email})
    if not resp or "data" not in resp:
        return None
    return resp["data"]


# ---------------------------------------------------------------------------
# Tier 1, leg 5: OSS email-permutation + MX/SMTP RCPT validation (no vendor)
# ---------------------------------------------------------------------------

def mx_hosts(domain: str) -> list[str]:
    try:
        out = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=10).stdout
    except Exception as e:
        log(f"  dig MX lookup failed for {domain}: {e}")
        return []
    hosts = []
    for line in out.strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                hosts.append((int(parts[0]), parts[1].rstrip(".")))
            except ValueError:
                continue
    return [h for _, h in sorted(hosts)]


def smtp_rcpt_check(mx_host: str, email: str, from_addr: str = "verify@biddeed.ai") -> tuple[int | None, str]:
    """Returns (smtp_code, message). code 250 = accepted (best signal of a
    real mailbox, still not 100% -- catch-all domains accept anything).
    code 550/551/553 = rejected (mailbox does not exist). Anything else
    (554 relay-denied, connection refused, timeout) is INCONCLUSIVE -- most
    shared-hosting mail platforms (Hostinger, GoDaddy, etc.) reject RCPT
    probing outright regardless of validity; treat as unverifiable, never
    as a pass."""
    try:
        s = smtplib.SMTP(timeout=8)
        s.connect(mx_host, 25)
        s.helo("biddeed.ai")
        s.mail(from_addr)
        code, msg = s.rcpt(email)
        s.quit()
        return code, msg.decode("utf-8", "replace") if isinstance(msg, bytes) else str(msg)
    except Exception as e:
        return None, str(e)


def permutate_candidates(first: str, last: str, domain: str) -> list[str]:
    first, last = first.lower().strip(), last.lower().strip()
    if not first or not last:
        return []
    f, l = first[0], last[0]
    return [
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{f}{last}@{domain}",
        f"{first}@{domain}",
        f"{first}{l}@{domain}",
    ]


def oss_permutate_and_validate(first: str, last: str, domain: str) -> dict:
    """Never returns a candidate as 'resolved' unless SMTP RCPT genuinely
    accepted it (250). Everything else is reported as attempted-but-dropped
    per the issue's 'validate or drop' rule."""
    result = {"resolved": False, "candidates_tried": [], "domain_accept_all_risk": False}
    hosts = mx_hosts(domain)
    if not hosts:
        result["reason"] = "NO_MX_RECORD"
        return result
    candidates = permutate_candidates(first, last, domain)
    for cand in candidates:
        code, msg = smtp_rcpt_check(hosts[0], cand)
        result["candidates_tried"].append({"email": cand, "smtp_code": code, "smtp_msg": msg[:150]})
        if code == 250:
            result["resolved"] = True
            result["email"] = cand
            result["source"] = "oss_permutation_smtp_rcpt"
            return result
        if code is not None and code not in (250,) and code >= 500:
            continue  # explicit reject, try next candidate
    result["reason"] = "SMTP_RCPT_INCONCLUSIVE_OR_RELAY_DENIED_ALL_CANDIDATES"
    return result


# ---------------------------------------------------------------------------
# Tier 1 / Tier 2 legs with no credential (checked live 2026-08-25)
# ---------------------------------------------------------------------------

def resolve_zoominfo(*_args, **_kwargs) -> dict:
    return {
        "resolved": False, "tier": "zoominfo", "blocked": True,
        "reason": "No ZoomInfo MCP server registered (`claude mcp list` -> "
                   "'No MCP servers configured', checked live 2026-08-25) and no "
                   "ZOOMINFO_API_KEY/zoominfo_* credential in GH secrets or Supabase "
                   "vault (vault_secret() returned null for zoominfo_api_key, "
                   "zoominfo_client_id, zoominfo_username, zoominfo_password, "
                   "checked live 2026-08-25). Cannot call ZoomInfo this session.",
    }


def resolve_endato(*_args, **_kwargs) -> dict:
    return {
        "resolved": False, "tier": "endato_enformion", "blocked": True,
        "reason": "No endato_api_key / enformion_api_key / enformiongo_api_key "
                   "credential in GH secrets or Supabase vault (checked live "
                   "2026-08-25, all returned null). Cannot call Endato/EnformionGO "
                   "this session.",
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def resolve_business_contact(entity_name: str, city: str | None, state: str, apify_token: str,
                              principal_name: str | None = None, hunter_credits_remaining: list[int] | None = None) -> dict:
    """Cascades Apify -> Hunter -> OSS permutation for ONE business entity.
    hunter_credits_remaining is a 1-element list used as a mutable counter so
    the caller can pre-check Hunter's account credits once and this function
    can decrement/stop without re-querying the account endpoint per buyer."""
    out = {"entity_name": entity_name, "phone": None, "email": None, "sources_tried": []}

    gmaps = apify_google_maps(entity_name, city, state, apify_token)
    out["sources_tried"].append("apify_google_maps")
    domain = None
    if gmaps and not gmaps.get("name_matched"):
        out["apify_dropped_no_name_match"] = {"title": gmaps.get("title"), "phone": gmaps.get("phone"), "website": gmaps.get("website")}
        gmaps = None  # do not let an unrelated listing's phone/domain leak into this buyer's record
    if gmaps:
        if gmaps.get("phone"):
            out["phone"] = {"value": gmaps["phone"], "e164": gmaps.get("phone_e164"),
                             "tier": 1, "source": "apify_google_maps", "confidence": "high",
                             "detail": f"Google Maps listing (name-matched): {gmaps.get('title')}"}
        if gmaps.get("website"):
            domain = re.sub(r"^https?://(www\.)?", "", gmaps["website"]).split("/")[0]

    if domain and HUNTER_API_KEY:
        if hunter_credits_remaining is None or hunter_credits_remaining[0] >= 3:
            ds = hunter_domain_search(domain=domain)
            out["sources_tried"].append("hunter_domain_search")
            if hunter_credits_remaining is not None:
                hunter_credits_remaining[0] -= 1
            if ds:
                emails = ds.get("emails") or []
                candidate = emails[0]["value"] if emails else None
                if not candidate and principal_name and ds.get("pattern") and hunter_credits_remaining and hunter_credits_remaining[0] >= 2:
                    parts = principal_name.strip().split()
                    if len(parts) >= 2:
                        finder = hunter_email_finder(domain, parts[0], parts[-1])
                        out["sources_tried"].append("hunter_email_finder")
                        hunter_credits_remaining[0] -= 1
                        if finder and finder.get("email"):
                            candidate = finder["email"]
                if candidate:
                    verified = hunter_verify_email(candidate)
                    out["sources_tried"].append("hunter_email_verifier")
                    if hunter_credits_remaining is not None:
                        hunter_credits_remaining[0] -= 1
                    status = (verified or {}).get("status")
                    if status in ("valid", "accept_all"):
                        out["email"] = {"value": candidate, "tier": 1, "source": "hunter_io",
                                         "confidence": "high" if status == "valid" else "medium",
                                         "detail": f"Hunter verifier status={status}"}
                    else:
                        out["email_dropped"] = {"value": candidate, "reason": f"hunter_verifier_status={status}"}
        else:
            out["sources_tried"].append("hunter_SKIPPED_credit_ceiling")

    if apify_token and not out["phone"] and not out["email"]:
        attempts = []
        if domain:
            attempts.append(("apify_waterfall_enricher", lambda: apify_waterfall_enricher(domain, apify_token)))
            attempts.append(("apify_leads_finder_domain", lambda: apify_leads_finder(entity_name, domain, apify_token)))
        else:
            attempts.append(("apify_leads_finder_keyword", lambda: apify_leads_finder(entity_name, None, apify_token)))
        for label, call in attempts:
            if out["phone"] and out["email"]:
                break
            res = call()
            out["sources_tried"].append(label)
            if res.get("blocked"):
                out[f"{label}_blocked"] = res
                continue
            if res.get("error"):
                out[f"{label}_error"] = res["error"]
                continue
            cands = res.get("candidates") or []
            if not cands:
                out[f"{label}_no_candidates"] = True
                continue
            best = cands[0]
            if not out["phone"] and best.get("phone"):
                out["phone"] = {"value": best["phone"], "tier": 1, "source": label,
                                 "confidence": "medium", "detail": f"{label}: {best.get('company_name')}"}
            if not out["email"] and best.get("email"):
                out["email"] = {"value": best["email"], "tier": 1, "source": label,
                                 "confidence": "medium", "detail": f"{label}: {best.get('company_name')}"}

    if not out["email"] and domain:
        pname = principal_name or ""
        parts = pname.strip().split()
        if len(parts) >= 2:
            oss = oss_permutate_and_validate(parts[0], parts[-1], domain)
            out["sources_tried"].append("oss_permutation_smtp")
            if oss.get("resolved"):
                out["email"] = {"value": oss["email"], "tier": 3, "source": "oss_permutation_smtp_rcpt",
                                 "confidence": "medium", "detail": "SMTP RCPT 250 accepted"}
            else:
                out["email_dropped_oss"] = oss

    return out


def resolve_person_contact(name: str, mailing_address: str | None, city: str | None, state: str, zipcode: str | None) -> dict:
    """Tier 2: Tracerfy enhanced trace (existing client) + Endato stub."""
    import tracerfy_client
    out = {"name": name, "phone": None, "email": None, "sources_tried": []}
    if mailing_address:
        trace = tracerfy_client.trace_lead(name, mailing_address, city or "", state, zipcode or "")
        out["sources_tried"].append("tracerfy_enhanced_trace")
        out["tracerfy_raw"] = trace
        if trace.get("phone"):
            out["phone"] = {"value": trace["phone"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "high"}
        if trace.get("email"):
            out["email"] = {"value": trace["email"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "high"}
    else:
        out["sources_tried"].append("tracerfy_SKIPPED_no_mailing_address")

    if not out["phone"]:
        endato = resolve_endato()
        out["sources_tried"].append("endato_enformion")
        out["endato_result"] = endato

    return out


if __name__ == "__main__":
    import sys
    acct = hunter_account()
    print("Hunter account:", json.dumps(acct, indent=2) if acct else "UNAVAILABLE")
    if len(sys.argv) > 1:
        print(json.dumps(apify_google_maps(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None,
                                            "FL", os.environ.get("APIFY_API_TOKEN", "")), indent=2))
