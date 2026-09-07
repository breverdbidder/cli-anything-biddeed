#!/usr/bin/env python3
"""biddeed.ai parity audit harness — Chromium, both viewports, eight gates. Usage:
  python3 scripts/ui-audit/audit.py --base https://biddeed.ai --routes scripts/ui-audit/routes.json [--out report.md] [--fail-on-red]
Requires: pip install playwright && playwright install --with-deps chromium
"""
import asyncio, json, re, sys, os, argparse
from playwright.async_api import async_playwright
# Canon = the deployed WinnerDataAI child-brand light palette used by biddeed-web and
# the canonical Worker: cream canvas, terracotta action, black ink, muted ink, and
# warm border/tint values. The evaluator must match the production design contract;
# it must never accept retired blue output merely to reduce the red count.
CANON = {"#ffffff", "#e6f0fa", "#1a1a1a", "#0a2540", "#d7e3f1", "#005eb8", "#004a92",
         "#0b1119", "#111b27", "#1b2737", "#ededed", "#9eb2c7", "#24344c", "#1a90ff", "#4da6ff"}
RETIRED = ["before the gavel","know your number"]
BUZZ = ["comprehensive solution","comprehensive intelligence","next-gen","cutting-edge","streamlined","seamless","revolutionary","industry-leading","best-in-class","leverage","synergy","robust platform"]
CONTEMPT = ["you're doing it wrong","still using spreadsheets","if you're still","amateur","rookie mistake","too lazy","too dumb"]
COMPET = ["propertyonion","property onion"]
BROKEN = ["internal server error","not configured","undefined","nan ","[object object]"]
JS_SWEEP = r"""() => {
  function lum(rgb){const [r,g,b]=rgb.map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*r+0.7152*g+0.0722*b}
  function parse(c){const m=c.match(/rgba?\(([^)]+)\)/);if(!m)return null;const a=m[1].split(',').map(parseFloat);return {rgb:a.slice(0,3),a:a.length>3?a[3]:1}}
  function bg(el){let e=el;while(e){const cs=getComputedStyle(e);if((cs.backgroundImage||'').includes('gradient')){const m=cs.backgroundImage.match(/rgba?\([^)]+\)/g);if(m){let best=null,bl=2;for(const c of m){const p=parse(c);if(!p||p.a<0.5)continue;const l=lum(p.rgb);if(l<bl){bl=l;best=p.rgb}}if(best)return best}}const c=parse(cs.backgroundColor);if(c&&c.a>0.5)return c.rgb;e=e.parentElement}const b=parse(getComputedStyle(document.body).backgroundColor);return (b&&b.a>0.5)?b.rgb:[255,255,255]}
  function hex(rgb){return '#'+rgb.map(v=>Math.round(v).toString(16).padStart(2,'0')).join('')}
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let bad=[],total=0,colors={};
  const sym=new RegExp('^[\\p{Extended_Pictographic}\\p{S}\\s'+String.fromCharCode(8205,65039)+']+$','u');  // ZWJ + VS16 by code point: no backslash-u escapes in this source
  while(walker.nextNode()){const n=walker.currentNode;if(!n.textContent.trim()||sym.test(n.textContent.trim()))continue;const el=n.parentElement;const st=getComputedStyle(el);if(st.display==='none'||st.visibility==='hidden'||parseFloat(st.opacity)===0)continue;const r=el.getBoundingClientRect();if(!r.width||!r.height)continue;total++;const fg=parse(st.color);if(!fg||fg.a===0)continue;const b=bg(el);colors[hex(fg.rgb)]=(colors[hex(fg.rgb)]||0)+1;colors[hex(b)]=(colors[hex(b)]||0)+1;const l1=lum(fg.rgb),l2=lum(b);const ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);if(ratio<4.5)bad.push({t:n.textContent.trim().slice(0,30),ratio:+ratio.toFixed(2),fg:hex(fg.rgb),bg:hex(b)})}
  const h1=[...document.querySelectorAll('h1')].map(h=>h.innerText.trim());
  const vw=window.innerWidth; const docOverflow=document.documentElement.scrollWidth>vw+1; let textOverflow=0, offscreen=0, smallTap=0, tiny=0;
  for(const el of document.querySelectorAll('body *')){const cs=getComputedStyle(el); if(cs.display==='none'||cs.visibility==='hidden')continue; const r=el.getBoundingClientRect(); if(!r.width||!r.height)continue; const scrollable=/(auto|scroll)/.test(cs.overflowX+cs.overflow); const hidden=/hidden/.test(cs.overflowX+cs.overflow); const t=(el.innerText||'').trim();
    if(!scrollable&&!hidden&&el.children.length===0&&t&&el.scrollWidth>el.clientWidth+2)textOverflow++;
    if(r.right>vw+2&&r.width>40&&!scrollable&&!el.closest('[style*="overflow"]'))offscreen++;
    if((el.tagName==='A'||el.tagName==='BUTTON')&&t&&(r.width<32||r.height<32))smallTap++;
    if(/^(P|LI|DD)$/.test(el.tagName)&&t.length>20&&parseFloat(cs.fontSize)<(vw<600?16:15))tiny++;}
  let misaligned=0, misalignedWhere=[]; for(const dl of document.querySelectorAll('dl')){const rows={}; for(const dd of dl.querySelectorAll('dd')){const r=dd.getBoundingClientRect(); if(!r.width||!r.height)continue; const tile=dd.parentElement===dl?dd:dd.parentElement; const key=Math.round(tile.getBoundingClientRect().top/12); (rows[key]=rows[key]||[]).push({top:Math.round(r.top),t:(dd.innerText||'').trim().slice(0,14)});} for(const k in rows){const g=rows[k]; if(g.length<2)continue; const tops=g.map(x=>x.top); if(Math.max(...tops)-Math.min(...tops)>4){misaligned++; misalignedWhere.push(g.map(x=>x.t+'@'+x.top).join('/'));}}}
  const fams=new Set([...document.querySelectorAll('h1,h2,h3,p,a,button,span,li,dd')].map(e=>getComputedStyle(e).fontFamily.split(',')[0].replace(/"/g,'').trim()));
  const ld=[...document.querySelectorAll('script[type="application/ld+json"]')].map(s=>{try{const d=JSON.parse(s.textContent);return (Array.isArray(d)?d:[d]).map(x=>x['@type'])}catch(e){return ['UNPARSABLE']}}).flat();
  return {total,bad,colors,h1,ld,meta:(document.querySelector('meta[name=description]')||{}).content||'',canonical:(document.querySelector('link[rel=canonical]')||{}).href||'',text:document.body.innerText,layout:{docOverflow,textOverflow,offscreen,smallTap,tiny,misaligned,misalignedWhere:misalignedWhere.slice(0,3)},fams:[...fams]}}"""
DISPLAY={}
async def run(base, routes, out, fail_on_red):
    rows=[]; red=0
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--no-sandbox","--ignore-certificate-errors"])
        for vw,vh in ((1440,900),(390,844)):
            ctx=await b.new_context(viewport={"width":vw,"height":vh}, ignore_https_errors=True, user_agent="Mozilla/5.0 (biddeed-ui-audit)")
            for route in routes:
                pg=await ctx.new_page(); status="ERR"; r={}; err=""
                try:
                    # Use DOM readiness, not networkidle: Next/Cloudflare streams and analytics can keep
                    # networkidle from resolving and exhaust the 20-minute workflow timeout. Evidence remains
                    # bounded per route while the sweep still captures rendered DOM, styles, and layout.
                    resp=await pg.goto(base+route, wait_until="domcontentloaded", timeout=30000); status=resp.status
                    await pg.wait_for_timeout(1000); r=await pg.evaluate(JS_SWEEP)
                except Exception as e: err=str(e)[:80]
                low=(r.get("text","") or "").lower()
                offpal=[c for c in r.get("colors",{}) if c not in CANON]
                gates={
                 "RENDER": status==200 and not any(k in low for k in BROKEN),
                 "PALETTE": len(offpal)==0,
                 "CONTRAST": len(r.get("bad",[]))==0,
                 "COPY": not any(x in low for x in RETIRED+BUZZ+CONTEMPT+COMPET) and low.count("!")<=1 and not re.search(r"\bS5\b", r.get("text","")),
                 "SEO": len(r.get("h1",[]))==1 and 0<len(r.get("meta",""))<=155 and bool(r.get("canonical")),
                 "LAYOUT": (lambda L: bool(L) and not L["docOverflow"] and L["textOverflow"]==0 and L["offscreen"]==0 and L["smallTap"]==0 and L.get("misaligned",0)==0)(r.get("layout")),
                 "TYPE": (lambda L,F: bool(L) and L["tiny"]==0 and set(F) <= {"Inter","Inter Fallback","Source Serif 4","Source Serif 4 Fallback","JetBrains Mono","system-ui","serif","sans-serif","monospace","Iowan Old Style","ui-monospace","Segoe UI Emoji"})(r.get("layout"), r.get("fams",[])),
                }
                red+=sum(1 for v in gates.values() if not v)
                rows.append((route,vw,status,gates,len(r.get("bad",[])),offpal[:6],r.get("ld",[]),err+(" L="+str(r.get("layout")) if r.get("layout") and not gates["LAYOUT"] else "")+(" F="+",".join([f for f in r.get("fams",[]) if f not in {"Inter","Inter Fallback","Source Serif 4","Source Serif 4 Fallback","JetBrains Mono","system-ui"}]) if not gates["TYPE"] else "")))
                await pg.close()
            await ctx.close()
        await b.close()
    lines=["| Route | VP | HTTP | RENDER | PALETTE | CONTRAST | COPY | SEO | LAYOUT | TYPE | <4.5:1 | off-palette | JSON-LD / notes |","|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for route,vw,st,g,nb,op,ld,err in rows:
        f=lambda k: "✅" if g[k] else "❌"
        lines.append(f"| {DISPLAY.get(route, route)} | {vw} | {st} | {f('RENDER')} | {f('PALETTE')} | {f('CONTRAST')} | {f('COPY')} | {f('SEO')} | {f('LAYOUT')} | {f('TYPE')} | {nb} | {' '.join(op)} | {' '.join(map(str,ld))} {err} |")
    md="\n".join(lines)+f"\n\nRed gates: **{red}**\n"; print(md)
    if out: open(out,"w").write(md)
    if fail_on_red and red: sys.exit(1)
if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--base",default="https://biddeed.ai"); ap.add_argument("--routes",default="scripts/ui-audit/routes.json"); ap.add_argument("--out"); ap.add_argument("--fail-on-red",action="store_true")
    a=ap.parse_args(); RAW=json.load(open(a.routes)); routes=[os.path.expandvars(r) for r in RAW]  # ${SAMPLE_REPORT_KEY} etc. come from the environment, never from git
    DISPLAY.update({os.path.expandvars(r): r for r in RAW})  # never print an expanded secret
    asyncio.run(run(a.base, routes, a.out, a.fail_on_red))
