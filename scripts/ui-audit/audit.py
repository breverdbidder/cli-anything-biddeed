#!/usr/bin/env python3
"""biddeed.ai parity audit harness — Chromium, both viewports, eight gates. Usage:
  python3 scripts/ui-audit/audit.py --base https://biddeed.ai --routes scripts/ui-audit/routes.json [--out report.md] [--fail-on-red]
Requires: pip install playwright && playwright install --with-deps chromium
"""
import asyncio, json, re, sys, os, argparse
from playwright.async_api import async_playwright
# Canon = biddeed-web app/globals.css :root (HSL) and its hex renderings. Two hex sets exist today because the Worker hand-converted the HSL (#f5f0e8 vs #f4efe6); #19845 collapses them to one generated file.
CANON = {"#fbfaf7","#fcfbf7","#f5f0e8","#f4efe6","#ede3d7","#ede5d9","#1f1b16","#1e1a15","#6e655e","#746b61","#ddd5c9","#b5a9a0","#9f4d32","#823f29","#1f7a3f","#14532d","#b42318","#ffffff","#000000"}
RETIRED = ["before the gavel","know your number"]
BUZZ = ["comprehensive solution","comprehensive intelligence","next-gen","cutting-edge","streamlined","seamless","revolutionary","industry-leading","best-in-class","leverage","synergy","robust platform"]
CONTEMPT = ["you're doing it wrong","still using spreadsheets","if you're still","amateur","rookie mistake","too lazy","too dumb"]
COMPET = ["propertyonion","property onion"]
BROKEN = ["internal server error","not configured","undefined","nan ","[object object]"]
JS_SWEEP = r"""() => {
  function lum(rgb){const [r,g,b]=rgb.map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*r+0.7152*g+0.0722*b}
  function parse(c){const m=c.match(/rgba?\(([^)]+)\)/);if(!m)return null;const a=m[1].split(',').map(parseFloat);return {rgb:a.slice(0,3),a:a.length>3?a[3]:1}}
  function bg(el){let e=el;while(e){const cs=getComputedStyle(e);if((cs.backgroundImage||'').includes('gradient')){const m=cs.backgroundImage.match(/rgba?\([^)]+\)/g);if(m){let best=null,bl=2;for(const c of m){const p=parse(c);if(!p)continue;const l=lum(p.rgb);if(l<bl){bl=l;best=p.rgb}}if(best)return best}}const c=parse(cs.backgroundColor);if(c&&c.a>0.5)return c.rgb;e=e.parentElement}const b=parse(getComputedStyle(document.body).backgroundColor);return (b&&b.a>0.5)?b.rgb:[255,255,255]}
  function hex(rgb){return '#'+rgb.map(v=>Math.round(v).toString(16).padStart(2,'0')).join('')}
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let bad=[],total=0,colors={};
  while(walker.nextNode()){const n=walker.currentNode;if(!n.textContent.trim())continue;const el=n.parentElement;const st=getComputedStyle(el);if(st.display==='none'||st.visibility==='hidden'||parseFloat(st.opacity)===0)continue;const r=el.getBoundingClientRect();if(!r.width||!r.height)continue;total++;const fg=parse(st.color);if(!fg)continue;const b=bg(el);colors[hex(fg.rgb)]=(colors[hex(fg.rgb)]||0)+1;colors[hex(b)]=(colors[hex(b)]||0)+1;const l1=lum(fg.rgb),l2=lum(b);const ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);if(ratio<4.5)bad.push({t:n.textContent.trim().slice(0,30),ratio:+ratio.toFixed(2),fg:hex(fg.rgb),bg:hex(b)})}
  const h1=[...document.querySelectorAll('h1')].map(h=>h.innerText.trim());
  const ld=[...document.querySelectorAll('script[type="application/ld+json"]')].map(s=>{try{const d=JSON.parse(s.textContent);return (Array.isArray(d)?d:[d]).map(x=>x['@type'])}catch(e){return ['UNPARSABLE']}}).flat();
  return {total,bad,colors,h1,ld,meta:(document.querySelector('meta[name=description]')||{}).content||'',canonical:(document.querySelector('link[rel=canonical]')||{}).href||'',text:document.body.innerText}}"""
async def run(base, routes, out, fail_on_red):
    rows=[]; red=0
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--no-sandbox","--ignore-certificate-errors"])
        for vw,vh in ((1440,900),(390,844)):
            ctx=await b.new_context(viewport={"width":vw,"height":vh}, ignore_https_errors=True, user_agent="Mozilla/5.0 (biddeed-ui-audit)")
            for route in routes:
                pg=await ctx.new_page(); status="ERR"; r={}; err=""
                try:
                    resp=await pg.goto(base+route, wait_until="networkidle", timeout=60000); status=resp.status
                    await pg.wait_for_timeout(800); r=await pg.evaluate(JS_SWEEP)
                except Exception as e: err=str(e)[:80]
                low=(r.get("text","") or "").lower()
                offpal=[c for c in r.get("colors",{}) if c not in CANON]
                gates={
                 "RENDER": status==200 and not any(k in low for k in BROKEN),
                 "PALETTE": len(offpal)==0,
                 "CONTRAST": len(r.get("bad",[]))==0,
                 "COPY": not any(x in low for x in RETIRED+BUZZ+CONTEMPT+COMPET) and low.count("!")<=1 and not re.search(r"\bS5\b", r.get("text","")),
                 "SEO": len(r.get("h1",[]))==1 and 0<len(r.get("meta",""))<=155 and bool(r.get("canonical")),
                }
                red+=sum(1 for v in gates.values() if not v)
                rows.append((route,vw,status,gates,len(r.get("bad",[])),offpal[:6],r.get("ld",[]),err))
                await pg.close()
            await ctx.close()
        await b.close()
    lines=["| Route | VP | HTTP | RENDER | PALETTE | CONTRAST | COPY | SEO | <4.5:1 | off-palette | JSON-LD |","|---|---|---|---|---|---|---|---|---|---|---|"]
    for route,vw,st,g,nb,op,ld,err in rows:
        f=lambda k: "✅" if g[k] else "❌"
        lines.append(f"| {route} | {vw} | {st} | {f('RENDER')} | {f('PALETTE')} | {f('CONTRAST')} | {f('COPY')} | {f('SEO')} | {nb} | {' '.join(op)} | {' '.join(map(str,ld))} {err} |")
    md="\n".join(lines)+f"\n\nRed gates: **{red}**\n"; print(md)
    if out: open(out,"w").write(md)
    if fail_on_red and red: sys.exit(1)
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--base",default="https://biddeed.ai"); ap.add_argument("--routes",default="scripts/ui-audit/routes.json"); ap.add_argument("--out"); ap.add_argument("--fail-on-red",action="store_true")
    a=ap.parse_args(); routes=[os.path.expandvars(r) for r in json.load(open(a.routes))]  # ${SAMPLE_REPORT_KEY} etc. come from the environment, never from git
    asyncio.run(run(a.base, routes, a.out, a.fail_on_red))
