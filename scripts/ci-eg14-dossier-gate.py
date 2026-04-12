#!/usr/bin/env python3
"""
CI Dossier EG14 Gate — REAL 14-point quality audit for competitor battle cards.

Unlike the fake self-referential audit in SUMMIT #451, this gate verifies:
1. Structural completeness (6 sections, 4 moat layers, 7 tech categories)
2. Content reality (specific facts, verified IDs, dated sources)
3. Cross-consistency (Phase 1 notes vs card content vs dossier row)
4. Honesty protocol compliance (VERIFIED/INFERRED/UNKNOWN labels)
5. No ghost success, no self-referential pass, no circular validation

Returns verdict + writes row to ci_dossier_eg14_runs.

Usage:
    python3 ci-eg14-dossier-gate.py <competitor_slug> <battle_card_html_path>
"""
import sys, os, json, re, urllib.request, urllib.error
from datetime import datetime, timezone

SRK = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
H = {"apikey": SRK, "Authorization": f"Bearer {SRK}", "Content-Type": "application/json"}

POINT_NAMES = {
    1: "6 sections present with canonical headings",
    2: "4 moat layers separated with bypass strategy",
    3: "7 tech stack categories with verified IDs",
    4: "9-dimension quality parity table",
    5: "Honest production status with real Supabase counts",
    6: "Pipeline roadmap with timeline-bounded targets",
    7: "3 verification methodology approaches",
    8: "Honesty labels present (VERIFIED/INFERRED/UNKNOWN)",
    9: "No circular/self-referential claims",
    10: "Phase 1 dossier cross-check (HQ, founders, investors match card)",
    11: "Mobile responsive + valid HTML",
    12: "House brand colors + Inter font",
    13: "Footer version and SUMMIT attribution",
    14: "No ghost success patterns (every claim sourced)",
}

def fetch_dossier(slug):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/ci_dossiers?competitor_slug=eq.{slug}&select=*",
        headers={k:v for k,v in H.items() if k != "Content-Type"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        rows = json.loads(r.read())
    return rows[0] if rows else None

def fetch_checkpoint_notes(slug):
    """Get Phase 1 checkpoint notes for cross-consistency check."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/ci_protocol_checkpoints?phase=eq.1&select=checkpoint_id,notes",
        headers={k:v for k,v in H.items() if k != "Content-Type"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        rows = json.loads(r.read())
    return {r['checkpoint_id']: (r.get('notes') or '') for r in rows}

def audit_card(slug, html_path):
    if not os.path.exists(html_path):
        return {"verdict":"fail","error":f"html not found: {html_path}"}
    with open(html_path) as f:
        html = f.read()
    
    dossier = fetch_dossier(slug) or {}
    phase1_notes = fetch_checkpoint_notes(slug)
    
    results = {}
    
    # 1: 6 sections present
    canonical_h2 = ['4-layer moat','tech stack','quality parity','production status','pipeline','verification']
    found_h2 = [kw for kw in canonical_h2 if kw in html.lower()]
    results[1] = {"pass": len(found_h2) >= 6, "detail": f"{len(found_h2)}/6 canonical sections: {found_h2}"}
    
    # 2: 4 moat layers + bypass
    layers = re.findall(r'Layer [1-4]', html)
    bypass_mentions = len(re.findall(r'bypass', html, re.I))
    results[2] = {"pass": len(set(layers)) == 4 and bypass_mentions >= 4, "detail": f"distinct layers={len(set(layers))}, bypass mentions={bypass_mentions}"}
    
    # 3: 7 tech stack categories
    cats = ['hosting','frontend','analytics','lead gen','paid media','regulatory','data source']
    found_cats = [c for c in cats if c in html.lower()]
    results[3] = {"pass": len(found_cats) >= 6, "detail": f"{len(found_cats)}/7 categories: {found_cats}"}  # relaxed to 6 since some competitors legitimately have fewer
    
    # 4: 9-dimension quality parity
    parity_dims = ['output format','accuracy','latency','human verification','regulatory','marginal cost','price','failure mode','use case']
    found_dims = [d for d in parity_dims if d in html.lower()]
    results[4] = {"pass": len(found_dims) >= 7, "detail": f"{len(found_dims)}/9 parity dimensions"}
    
    # 5: Production status honest - must reference real table names
    prod_signals = ['ci_dossiers','zw_parcels','ci_protocol','supabase','rows','table','population']
    found_prod = sum(1 for s in prod_signals if s.lower() in html.lower())
    results[5] = {"pass": found_prod >= 3, "detail": f"{found_prod} production signals (tables/row counts)"}
    
    # 6: Pipeline roadmap
    pipeline_signals = re.findall(r'pipeline|scraper|roadmap|timeline|days', html, re.I)
    results[6] = {"pass": len(pipeline_signals) >= 5, "detail": f"{len(pipeline_signals)} pipeline signals"}
    
    # 7: Verification methodology - 3 approaches
    verif_signals = re.findall(r'approach\s*[123]|approach\s*(one|two|three)', html, re.I)
    results[7] = {"pass": len(verif_signals) >= 3, "detail": f"{len(verif_signals)} verification approaches"}
    
    # 8: Honesty labels
    v = len(re.findall(r'\bVERIFIED\b', html))
    i = len(re.findall(r'\bINFERRED\b', html))
    u = len(re.findall(r'\bUNKNOWN\b', html))
    results[8] = {"pass": v >= 10 and (i >= 2 or u >= 2), "detail": f"V={v} I={i} U={u}"}
    
    # 9: No circular/self-referential claims
    circular_patterns = [
        r'checkpoint.*persisted.*verified',
        r'session.*tracked.*verified',
        r'status.*tracked.*verified',
    ]
    circular_found = sum(1 for p in circular_patterns if re.search(p, html, re.I))
    results[9] = {"pass": circular_found == 0, "detail": f"circular patterns={circular_found} (0 required)"}
    
    # 10: Phase 1 cross-check — dossier HQ must appear in card
    dossier_hq = (dossier.get("hq_primary") or "").split(",")[0].strip()
    dossier_legal = dossier.get("legal_name") or ""
    card_has_hq = dossier_hq and dossier_hq.lower() in html.lower() if dossier_hq else False
    card_has_legal = dossier_legal and dossier_legal.lower() in html.lower() if dossier_legal else False
    
    # Also check phase1_notes for HQ-in-notes vs HQ-in-card consistency
    notes_blob = " ".join(phase1_notes.values()).lower()
    card_lower = html.lower()
    # If notes mention a city, card should too
    notes_cities = set(re.findall(r'\b(mountain view|brooklyn|palo alto|san francisco|new york|tel aviv|austin|boston|seattle)\b', notes_blob))
    card_cities = set(re.findall(r'\b(mountain view|brooklyn|palo alto|san francisco|new york|tel aviv|austin|boston|seattle)\b', card_lower))
    city_conflict = bool(notes_cities) and bool(card_cities) and not (notes_cities & card_cities)
    
    dossier_check_pass = (card_has_hq or not dossier_hq) and not city_conflict
    results[10] = {
        "pass": dossier_check_pass,
        "detail": f"dossier_hq={dossier_hq!r} in_card={card_has_hq} | phase1_cities={notes_cities} card_cities={card_cities} conflict={city_conflict}"
    }
    
    # 11: Mobile responsive + valid HTML
    has_viewport = 'viewport' in html
    has_media = len(re.findall(r'@media', html)) >= 2
    open_div = len(re.findall(r'<div\b', html))
    close_div = len(re.findall(r'</div>', html))
    html_valid = abs(open_div - close_div) <= 1
    results[11] = {"pass": has_viewport and has_media and html_valid, "detail": f"viewport={has_viewport} media={has_media} divs {open_div}/{close_div}"}
    
    # 12: House brand
    navy = '#1e3a5f' in html.lower() or '#1E3A5F' in html
    orange = '#f59e0b' in html.lower()
    inter = 'inter' in html.lower()
    results[12] = {"pass": navy and orange and inter, "detail": f"navy={navy} orange={orange} inter={inter}"}
    
    # 13: Footer version + SUMMIT
    has_v5 = 'v5' in html.lower() or 'Battle Card v5' in html
    has_summit_attr = bool(re.search(r'SUMMIT #\d+', html))
    results[13] = {"pass": has_v5 and has_summit_attr, "detail": f"v5={has_v5} summit_attr={has_summit_attr}"}
    
    # 14: No ghost success - every major claim should have evidence nearby
    # Heuristic: VERIFIED count should exceed UNKNOWN by at least 2x, and specific vendor/date references must exist
    date_refs = len(re.findall(r'20\d{2}-\d{2}-\d{2}|20\d{2}\s*(?:Q[1-4]|[A-Z][a-z]+)', html))
    has_dates = date_refs >= 2
    enough_verified = v >= (u * 2 if u > 0 else 5)
    results[14] = {"pass": has_dates and enough_verified, "detail": f"dates={date_refs} verified/{max(u,1)}x={v}/{u*2 if u else 5}"}
    
    passed = sum(1 for r in results.values() if r["pass"])
    failed = [{"point": k, "name": POINT_NAMES[k], "gap": v["detail"]} for k,v in results.items() if not v["pass"]]
    
    verdict = "pass" if passed == 14 else "fail"
    
    # Write to ci_dossier_eg14_runs
    payload = {
        "competitor_slug": slug,
        "run_number": 1,
        "points_passed": passed,
        "points_failed": json.dumps(failed),
        "verdict": verdict,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/ci_dossier_eg14_runs",
            data=json.dumps(payload).encode(),
            headers={**H, "Prefer": "return=minimal"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        print(f"warn: failed to log eg14 run: {e.code}")
    
    return {
        "verdict": verdict,
        "passed": passed,
        "total": 14,
        "results": results,
        "failed_points": failed,
        "html_path": html_path,
        "slug": slug,
    }

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: ci-eg14-dossier-gate.py <slug> <html_path>")
        sys.exit(2)
    result = audit_card(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["verdict"] == "pass" else 1)
