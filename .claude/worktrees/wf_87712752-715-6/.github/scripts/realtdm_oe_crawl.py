#!/usr/bin/env python3
"""RealTDM public O&E crawl - GHA+Supabase, ubuntu-latest, playwright/chromium.
Crawls {subdomain}.realtdm.com/public/cases/list (NO AUTH, statutory public record)
-> case list -> per-case detail/O&E -> writes realtdm_case + realtdm_oe_sample.
Honesty V3: honesty_marker on every row; unknowns marked, never fabricated.
v0 selectors are defensive and validated against the live DOM on first run
(captures screenshots + label inventory so the next pass can tune selectors)."""
import os, re, json, pathlib, urllib.parse as up
import httpx
from playwright.sync_api import sync_playwright

SB   = os.environ["SUPABASE_URL"].rstrip("/")
KEY  = os.environ["SUPABASE_SERVICE_ROLE"]
SUB  = os.environ.get("SUBDOMAIN","miamidade")
MAXC = int(os.environ.get("MAX_CASES","40"))
BASE = f"https://{SUB}.realtdm.com"
LIST = f"{BASE}/public/cases/list"
OUT  = pathlib.Path("out"); (OUT/"shots").mkdir(parents=True, exist_ok=True)
H = {"apikey":KEY,"Authorization":f"Bearer {KEY}","Content-Type":"application/json","Prefer":"return=representation"}

def sb(table, rows, on_conflict=None):
    """Insert/upsert. FAIL LOUD on error - no ghost success."""
    out=[]
    url=f"{SB}/rest/v1/{table}"
    hdr=dict(H)
    if on_conflict:
        url+=f"?on_conflict={on_conflict}"; hdr["Prefer"]="resolution=merge-duplicates,return=representation"
    for i in range(0,len(rows),40):
        chunk=rows[i:i+40]
        r=httpx.post(url,headers=hdr,json=chunk,timeout=90)
        if r.status_code>=300:
            print(f"  !! {table} FAILED {r.status_code}: {r.text[:300]}")
            raise SystemExit(f"FATAL writeback {table}: {r.status_code}")
        out += r.json() if r.text else []
        print(f"  -> {table}: {r.status_code} ({len(chunk)})")
    return out

def tx(el):
    try: return (el.inner_text() or "").strip()
    except Exception: return ""

def run():
    detail_links=[]; oe_rows=[]; n_cases=0
    with sync_playwright() as p:
        b=p.chromium.launch(); ctx=b.new_context(viewport={"width":1440,"height":900}); pg=ctx.new_page()
        print(f"GET {LIST}")
        try:
            pg.goto(LIST,wait_until="networkidle",timeout=60000); pg.wait_for_timeout(1500)
        except Exception as e:
            print("list load issue:",e)
        pg.screenshot(path=str(OUT/"shots/000-list.png"),full_page=True)
        for a in pg.query_selector_all("a[href*='case'], a[href*='detail'], a[href*='/public/']"):
            href=a.get_attribute("href") or ""
            if href and ("case" in href.lower() or "detail" in href.lower()):
                detail_links.append(up.urljoin(BASE, href))
        detail_links=list(dict.fromkeys(detail_links))[:MAXC]
        print(f"detail_links found: {len(detail_links)}")
        for i,du in enumerate(detail_links):
            try:
                pg.goto(du,wait_until="networkidle",timeout=45000); pg.wait_for_timeout(800)
                pg.screenshot(path=str(OUT/f"shots/{i+1:03d}-case.png"),full_page=True)
                body=pg.inner_text("body") if pg.query_selector("body") else ""
                labels=[tx(x) for x in pg.query_selector_all("th, label, dt, b, strong")]
                labels=[l for l in labels if 2<len(l)<60][:60]
                oe=None
                for a in pg.query_selector_all("a[href$='.pdf'], a[href*='title'], a[href*='earch'], a[href*='OE']"):
                    h=a.get_attribute("href") or ""
                    if h: oe=up.urljoin(BASE,h); break
                folio=None; m=re.search(r"folio[^0-9]{0,8}([0-9\-]{6,})", body, re.I)
                if m: folio=m.group(1)
                cn=None; m2=re.search(r"case[^A-Za-z0-9]{0,6}([0-9A-Za-z\-]{4,})", body, re.I)
                if m2: cn=m2.group(1)
                ins=sb("realtdm_case",[{"county":SUB,"case_no":cn,"folio":folio,"detail_url":du,
                    "oe_doc_url":oe,"raw":json.dumps({"labels":labels}),
                    "honesty_marker":"INFERRED"}], on_conflict="county,case_no")
                cid=ins[0]["id"] if ins else None
                oe_rows.append({"case_id":cid,"county":SUB,"folio":folio,"oe_doc_url":oe,
                    "field_inventory":json.dumps({"labels":labels}),
                    "honesty_marker":"INFERRED" if oe else "UNKNOWN"})
                n_cases+=1
                print(f"[{i+1}/{len(detail_links)}] {du} folio={folio} oe={'y' if oe else 'n'}")
            except Exception as e:
                print(f"[{i+1}] FAIL {du}: {e}")
        b.close()
    if oe_rows: sb("realtdm_oe_sample", oe_rows)
    with_oe=sum(1 for r in oe_rows if r["oe_doc_url"])
    (OUT/"summary.json").write_text(json.dumps({"subdomain":SUB,"detail_links":len(detail_links),
        "cases_written":n_cases,"with_oe":with_oe},indent=2))
    print(f"DONE detail_links={len(detail_links)} cases={n_cases} with_oe={with_oe}")
    if len(detail_links)==0:
        print("NOTE v0: zero detail links - list-page selectors need tuning vs live DOM (see shots/000-list.png artifact).")

if __name__=="__main__": run()
