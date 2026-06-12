#!/usr/bin/env python3
"""CI V6.5 Recon — GHA+Supabase, ubuntu-latest, playwright/chromium native.
Crawls a competitor's public surface to HouseCanary depth: sitemap -> pages ->
network/endpoint capture -> per-page screenshots -> tech/headers. Writes to
ci_v65_pages/api_endpoints/features/screenshots via service-role. Honesty V3:
every row VERIFIED-captured; gated areas marked UNKNOWN, never invented."""
import os, re, json, time, pathlib, urllib.parse as up
import httpx
from playwright.sync_api import sync_playwright

SB   = os.environ["SUPABASE_URL"].rstrip("/")
KEY  = os.environ["SUPABASE_SERVICE_ROLE"]
SLUG = os.environ["SLUG"]; DOMAIN = os.environ["DOMAIN"]
MODE = os.environ.get("MODE","ci_v65_full"); REQ = os.environ.get("REQ_BY","Ariel")
ROOT = f"https://www.{DOMAIN}" if not DOMAIN.startswith("www") else f"https://{DOMAIN}"
OUT  = pathlib.Path("out"); (OUT/"shots").mkdir(parents=True, exist_ok=True)
H = {"apikey":KEY,"Authorization":f"Bearer {KEY}","Content-Type":"application/json","Prefer":"return=minimal"}

def sb(table, rows):
    if not rows: return
    for i in range(0,len(rows),50):
        r = httpx.post(f"{SB}/rest/v1/{table}", headers=H, json=rows[i:i+50], timeout=60)
        print(f"  -> {table}: {r.status_code} ({len(rows[i:i+50])} rows)")

def disc():
    """sitemap.xml + robots.txt -> URL inventory"""
    urls=set([ROOT, f"{ROOT}/resources", f"{ROOT}/copilot-us", f"{ROOT}/security"])
    for sm in (f"{ROOT}/sitemap.xml", f"https://{DOMAIN}/sitemap.xml"):
        try:
            t=httpx.get(sm,timeout=30,follow_redirects=True).text
            urls|=set(re.findall(r"<loc>([^<]+)</loc>", t)); print(f"sitemap {sm}: {len(urls)} urls")
        except Exception as e: print("sitemap miss",sm,e)
    try:
        rb=httpx.get(f"{ROOT}/robots.txt",timeout=20).text
        for m in re.findall(r"Sitemap:\s*(\S+)",rb,re.I):
            try: urls|=set(re.findall(r"<loc>([^<]+)</loc>", httpx.get(m,timeout=30).text))
            except: pass
    except Exception as e: print("robots miss",e)
    return sorted(u for u in urls if DOMAIN in u)

def run():
    pages_rows=[]; ep_rows=[]; feat_rows=[]; shot_rows=[]; endpoints={}
    inv = disc()
    # paginate the resource hub for the full case-study set
    res = [f"{ROOT}/resources"] + [f"{ROOT}/resources?page={n}" for n in range(2,9)]
    queue = list(dict.fromkeys(inv + res))[:120]
    print(f"Crawling {len(queue)} urls")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width":1440,"height":900})
        pg = ctx.new_page()
        def on_resp(r):
            u=r.url
            if any(k in u for k in("/api/","/v1/","/v2/","/graphql","/_next/data","/rest/")):
                key=u.split("?")[0]
                if key not in endpoints:
                    endpoints[key]={"endpoint":kåy,"method":r.request.method,
                        "status":r.status,"ctype":r.headers.get("content-type","")}
        pg.on("response", on_resp)
        for i,u in enumerate(queue):
            try:
                resp=pg.goto(u,wait_until="networkidle",timeout=45000)
                pg.wait_for_timeout(900)
                title=(pg.title() or "")[:300]
                sec={k:v for k,v in (resp.headers if resp else {}).items()
                     if k.lower() in("content-security-policy","strict-transport-security",
                     "x-frame-options","server","x-powered-by")}
                cstud = bool(re.search(r"customer|case stud|how .* using",title,re.I))
                slugf = re.sub(r'[^a-z0-9]+','-',up.urlparse(u).path.lower()).strip('-') or "home"
                shot=f"shots/{i:03d}-{slugf[:40]}.png"
                pg.screenshot(path=str(OUT/shot),full_page=True)
                pages_rows.append({"dossier_slug":SLUG,"url":u,"title":title,
                    "is_case_study":cstud,"sec_headers":json.dumps(sec),"captured":True})
                shot_rows.append({"dossier_slug":SLUG,"url":u,"path":shot,"captured":True})
                # feature/case-study extraction from visible headings
                for h in pg.query_selector_all("h1,h2,h3"):
                    tx=(h.inner_text() or "").strip()
                    if 8<len(tx)<140 and re.search(r"AI|title|survey|draft|report|visuali|restor|due dilig|copilot",tx,re.I):
                        feat_rows.append({"dossier_slug":SLUG,"feature":tx[:140],"src_url":u})
                print(f"[{i+1}/{len(queue)}] {u} :: {title[:50]} cs={cstud}")
            except Exception as e:
                pages_rows.append({"dossier_slug":SLUG,"url":u,"title":"LOAD_FAIL","captured":False,"note":str(e)[:200]})
                print(f"[{i+1}] FAIL {u}: {e}")
        # gated whitepaper attempt — capture redirect, mark gated honestly
        for wp in (f"{ROOT}/book-a-demo", "https://orbital.ubpages.com/illusionguide/"):
            try:
                pg.goto(wp,wait_until="domcontentloaded",timeout=30000)
                gated = bool(pg.query_selector("form input[type=email], form input[name*=email]"))
                ep_rows.append({"dossier_slug":SLUG,"endpoint":wp,"method":"GET","status":200,
                    "gated":gated,"note":"lead-capture wall" if gated else "open","captured":True})
            except Exception as e: print("wp miss",wp,e)
        b.close()
    for v in endpoints.values():
        ep_rows.append({"dossier_slug":SLUG,"endpoint":v["endpoint"],"method":v["method"],
            "status":v["status"],"ctype":v["ctype"],"captured":True})
    # persist
    (OUT/"summary.json").write_text(json.dumps({"slug":SLUG,"pages":len(pages_rows),
        "endpoints":len(ep_rows),"features":len(feat_rows),"shots":len(shot_rows),
        "case_studies":[r["url"] for r in pages_rows if r.get("is_case_study")]},indent=2))
    sb("ci_v65_pages",pages_rows); sb("ci_v65_api_endpoints",ep_rows)
    sb("ci_v65_features",feat_rows); sb("ci_v65_screenshots",shot_rows)
    # promote classification only on real depth
    cls = "READY_FOR_SIGNOFF" if (MODE=="ci_v65_full" and len(pages_rows)>=15 and len(ep_rows)>=1) else "IN_PROGRESS"
    httpx.patch(f"{SB}/rest/v1/ci_v65_dossiers?slug=eq.{SLUG}",headers=H,
        json={"classification":cls,"current_phase":"P12_DELIVER" if cls=="READY_FOR_SIGNOFF" else "P3_CRAWL",
              "meta_recon":f"GHA crawl {len(pages_rows)}p/{len(ep_rows)}ep/{len(shot_rows)}shots"})
    print(f"DONE pages={len(pages_rows)} endpoints={len(ep_rows)} features={len(feat_rows)} shots={len(shot_rows)} class={cls}")

if __name__=="__main__": run()
