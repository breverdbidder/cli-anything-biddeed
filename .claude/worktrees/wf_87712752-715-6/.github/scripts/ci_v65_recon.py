#!/usr/bin/env python3
"""CI V6.5 Recon — GHA+Supabase, ubuntu-latest, playwright/chromium native.
Crawls a competitor public surface to HouseCanary depth and writes to the REAL
ci_v65_* schema (dossier_id FK, page_title/host/path/feature_name). Honesty V3:
honesty_marker on every row; gated areas marked, never invented."""
import os, re, json, pathlib, urllib.parse as up
import httpx
from playwright.sync_api import sync_playwright

SB   = os.environ["SUPABASE_URL"].rstrip("/")
KEY  = os.environ["SUPABASE_SERVICE_ROLE"]
SLUG = os.environ["SLUG"]; DOMAIN = os.environ["DOMAIN"]
MODE = os.environ.get("MODE","ci_v65_full")
ROOT = f"https://www.{DOMAIN}" if not DOMAIN.startswith("www") else f"https://{DOMAIN}"
OUT  = pathlib.Path("out"); (OUT/"shots").mkdir(parents=True, exist_ok=True)
H = {"apikey":KEY,"Authorization":f"Bearer {KEY}","Content-Type":"application/json","Prefer":"return=representation"}

def resolve_dossier_id():
    r = httpx.get(f"{SB}/rest/v1/ci_v65_dossiers?slug=eq.{SLUG}&select=id",headers=H,timeout=30)
    j = r.json()
    if not j: raise SystemExit(f"FATAL: no ci_v65_dossiers row for slug={SLUG}")
    return j[0]["id"]

DID = resolve_dossier_id()
print(f"dossier_id={DID}")

def sb(table, rows):
    """Insert and FAIL LOUD on error — no ghost success."""
    out=[]
    for i in range(0,len(rows),40):
        chunk=rows[i:i+40]
        r = httpx.post(f"{SB}/rest/v1/{table}", headers=H, json=chunk, timeout=90)
        if r.status_code >= 300:
            print(f"  !! {table} INSERT FAILED {r.status_code}: {r.text[:300]}")
            raise SystemExit(f"FATAL writeback {table}: {r.status_code}")
        out += r.json() if r.text else []
        print(f"  -> {table}: {r.status_code} ({len(chunk)} rows)")
    return out

def disc():
    urls=set([ROOT, f"{ROOT}/resources", f"{ROOT}/copilot-us", f"{ROOT}/security",
              f"{ROOT}/about", f"{ROOT}/witness", f"{ROOT}/residential-uk"])
    for sm in (f"{ROOT}/sitemap.xml", f"https://{DOMAIN}/sitemap.xml"):
        try:
            t=httpx.get(sm,timeout=30,follow_redirects=True).text
            urls|=set(re.findall(r"<loc>([^<]+)</loc>", t)); print(f"sitemap {sm}: {len(urls)}")
        except Exception as e: print("sitemap miss",sm,e)
    try:
        rb=httpx.get(f"{ROOT}/robots.txt",timeout=20).text
        for m in re.findall(r"Sitemap:\s*(\S+)",rb,re.I):
            try: urls|=set(re.findall(r"<loc>([^<]+)</loc>", httpx.get(m,timeout=30).text))
            except: pass
    except Exception as e: print("robots miss",e)
    return sorted(u for u in urls if DOMAIN in u)

def run():
    inv = disc()
    res = [f"{ROOT}/resources"] + [f"{ROOT}/resources?page={n}" for n in range(2,9)]
    queue = list(dict.fromkeys(inv + res))[:120]
    print(f"Crawling {len(queue)} urls")
    pages_rows=[]; feat_seen=set(); feat_rows=[]; endpoints={}; gated_rows=[]; shot_specs=[]
    with sync_playwright() as p:
        b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1440,"height":900}); pg=ctx.new_page()
        def on_resp(r):
            u=r.url
            if any(k in u for k in("/api/","/v1/","/v2/","/graphql","/_next/data","/rest/")):
                pr=up.urlparse(u); key=f"{pr.netloc}{pr.path}"
                if key not in endpoints:
                    endpoints[key]={"host":pr.netloc,"path":pr.path[:500],"method":r.request.method,
                        "status":r.status,"ctype":r.headers.get("content-type","")[:120],
                        "third":DOMAIN not in pr.netloc}
        pg.on("response", on_resp)
        for i,u in enumerate(queue):
            try:
                resp=pg.goto(u,wait_until="networkidle",timeout=45000); pg.wait_for_timeout(800)
                title=(pg.title() or "")[:400]
                body=pg.inner_text("body") if pg.query_selector("body") else ""
                wc=len(body.split())
                il=len(pg.query_selector_all("a[href^='/'], a[href*='"+DOMAIN+"']"))
                el=len(pg.query_selector_all("a[href^='http']"))-il
                cstud = bool(re.search(r"customer|case stud|how .* using|raising the bar",title,re.I))
                kind = "case_study" if cstud else ("resource" if "/resources" in u else
                       ("product" if any(s in u for s in("copilot","witness","residential")) else "marketing"))
                slugf = re.sub(r'[^a-z0-9]+','-',up.urlparse(u).path.lower()).strip('-') or "home"
                shot=f"shots/{i:03d}-{slugf[:40]}.png"; pg.screenshot(path=str(OUT/shot),full_page=True)
                pages_rows.append({"dossier_id":DID,"url":u,"page_slug":slugf[:120],"page_title":title,
                    "http_status":(resp.status if resp else None),"page_kind":kind,"is_authenticated":False,
                    "word_count":wc,"internal_links":json.dumps({"count":il}),"external_links":json.dumps({"count":max(el,0)}),
                    "honesty_marker":"V"})
                shot_specs.append((u, shot, (OUT/shot).stat().st_size if (OUT/shot).exists() else 0))
                for h in pg.query_selector_all("h1,h2,h3"):
                    tx=(h.inner_text() or "").strip()
                    if 8<len(tx)<140 and re.search(r"AI|title|survey|draft|report|visuali|restor|due dilig|copilot|insur",tx,re.I):
                        if tx.lower() not in feat_seen:
                            feat_seen.add(tx.lower())
                            feat_rows.append({"dossier_id":DID,"feature_name":tx[:140],
                                "feature_category":"product","description":f"surfaced on {u}",
                                "source_evidence":u,"our_parity_status":"not_planned","honesty_marker":"V"})
                print(f"[{i+1}/{len(queue)}] {u} :: {title[:46]} cs={cstud} wc={wc}")
            except Exception as e:
                pages_rows.append({"dossier_id":DID,"url":u,"page_slug":"load-fail","page_title":"LOAD_FAIL",
                    "http_status":None,"page_kind":"error","word_count":0,"honesty_marker":"UNK"})
                print(f"[{i+1}] FAIL {u}: {e}")
        for wp in (f"{ROOT}/book-a-demo","https://orbital.ubpages.com/illusionguide/"):
            try:
                pg.goto(wp,wait_until="domcontentloaded",timeout=30000)
                gated=bool(pg.query_selector("form input[type=email], form input[name*=email]"))
                pr=up.urlparse(wp)
                gated_rows.append({"dossier_id":DID,"host":pr.netloc,"path":pr.path[:500],"method":"GET",
                    "resource_kind":"gated_form" if gated else "page","status":200 if False else None,
                    "honesty_marker":"UNK" if gated else "V"})
            except Exception as e: print("wp miss",wp,e)
        b.close()
    # endpoints -> real columns
    ep_rows=[{"dossier_id":DID,"host":v["host"],"path":v["path"],"method":v["method"],
        "resource_kind":"api","is_3rd_party":v["third"],"observed_count":1,
        "honesty_marker":"V","sample_response_body":None} for v in endpoints.values()]
    ep_rows += [{"dossier_id":DID,"host":g["host"],"path":g["path"],"method":g["method"],
        "resource_kind":g["resource_kind"],"honesty_marker":g["honesty_marker"]} for g in gated_rows]
    # persist (fail-loud)
    inserted_pages = sb("ci_v65_pages", pages_rows)
    if ep_rows: sb("ci_v65_api_endpoints", ep_rows)
    if feat_rows: sb("ci_v65_features", feat_rows)
    url2pid={r["url"]:r["id"] for r in inserted_pages}
    shot_rows=[{"page_id":url2pid[u],"viewport_kind":"desktop","viewport_width":1440,"viewport_height":900,
        "storage_path":sp,"file_size_bytes":sz} for (u,sp,sz) in shot_specs if u in url2pid]
    if shot_rows: sb("ci_v65_screenshots", shot_rows)
    (OUT/"summary.json").write_text(json.dumps({"slug":SLUG,"pages":len(pages_rows),
        "endpoints":len(ep_rows),"features":len(feat_rows),"shots":len(shot_rows),
        "case_studies":[r["url"] for r in pages_rows if r["page_kind"]=="case_study"]},indent=2))
    cls = "READY_FOR_SIGNOFF" if (MODE=="ci_v65_full" and len(pages_rows)>=15 and len(ep_rows)>=1) else "IN_PROGRESS"
    httpx.patch(f"{SB}/rest/v1/ci_v65_dossiers?slug=eq.{SLUG}",headers={**H,"Prefer":"return=minimal"},
        json={"classification":cls,"current_phase":"P12_DELIVER" if cls=="READY_FOR_SIGNOFF" else "P3_CRAWL",
              "meta":json.dumps({"recon":f"GHA {len(pages_rows)}p/{len(ep_rows)}ep/{len(shot_rows)}shots",
                                 "case_study_count":sum(1 for r in pages_rows if r['page_kind']=='case_study')})})
    print(f"DONE pages={len(pages_rows)} endpoints={len(ep_rows)} features={len(feat_rows)} shots={len(shot_rows)} class={cls}")

if __name__=="__main__": run()
