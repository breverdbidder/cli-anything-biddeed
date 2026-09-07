#!/usr/bin/env python3
"""Rebuild the /deal/:county/:case page on the #005EB8 canon.

Implements Claude Design's deal-page handoff (worker-deal-page.html, Sep 7 2026)
against the REAL handler rather than dropping the artboard in, plus the defects
found while reading it:

- The artboard's primary CTA replaced the email capture with a purchase link.
  Ariel's call: keep both -- the purchase CTA is the single filled control, the
  email form stays below it. The lead path (POST /deal/:c/:case/lead ->
  insert_reel_lead -> lead_profiles, carrying visitor_id, reel_code and the UTM
  chain) is the M9 lead magnet and is not removed.
- The artboard's aerial is a hatch placeholder. Real pages have real photography
  (aerial_tight_url / aerial_wide_url); the placeholder is now the FALLBACK only.
- The artboard renders `TODO` chips for final judgment and opening bid. Measured:
  foreclosure_outcomes carries final_judgment on 192 of 6,290 rows (3.1%) and
  opening_bid on 290 (4.6%); since Aug 1, 24 and 1 of 374. get_reel_landing()
  does not even expose them. So the sale-record table is NOT added -- a row that
  is empty on ~95% of pages, and the literal word TODO, never reach a customer.
- The artboard's 1024px grid reserves a 380px rail that is display:none, leaving
  an empty column. Single column kept.

It also fixes a live defect this page already had: the palette sweep left the
base styles white-on-white (h1, .deal-stat .value and .deal-cta input were all
#fff on #fff), legible only after the shell's JS sets data-theme=light. The base
is now the light canon, so the page is readable before any script runs, and dark
is an explicit override.

Withheld is not missing: the five gated figures render as a solid tint row with a
bullet mask and a lock, the mask is aria-hidden, and a visually-hidden sibling
tells a screen reader what is withheld and where to get it.

Run: python3 scripts/ui-audit/apply_deal_page_005eb8.py src/worker.js
Idempotent: exits 0 with "already applied" on a second run.
"""
import sys

STYLE_ANCHOR = ".deal-preview-banner{background:#005EB8"
BODY_ANCHOR = '<body>\n<div class="deal-card">'
MARKER = "bd-signal-card"

NEW_STYLE = """<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#ffffff;color:#1A1A1A;font-family:'Inter',system-ui,sans-serif;padding:1.5rem 1rem 2.5rem;display:flex;justify-content:center;font-size:16px;line-height:1.6}
.deal-card{max-width:560px;width:100%}
.deal-preview-banner{background:#0A2540;color:#ffffff;font-weight:700;text-align:center;padding:.5rem;border-radius:8px;margin-bottom:1rem;font-size:.85rem}
.deal-greeting{background:#E6F0FA;border:1px solid #D7E3F1;border-radius:8px;padding:.75rem .9rem;margin-bottom:1rem;font-size:.85rem;color:#0A2540;display:none}
.deal-aerial{position:relative;display:flex;align-items:center;justify-content:center;aspect-ratio:16/9;overflow:hidden;background-color:#E6F0FA;background-image:repeating-linear-gradient(135deg,transparent 0 9px,rgba(10,37,64,.10) 9px 10px);border:1px solid #D7E3F1;border-radius:8px;margin-bottom:1rem;font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.06em;color:#0A2540;text-align:center;line-height:1.5}
.deal-img{width:100%;border-radius:8px;margin-bottom:1rem;border:1px solid #D7E3F1;display:block}
.deal-eyebrow{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#0A2540;margin-bottom:.4rem}
h1{font-size:1.75rem;line-height:1.2;color:#0A2540;margin-bottom:.25rem;text-wrap:pretty}
.deal-addr{color:#0A2540;font-size:1rem;margin-bottom:1rem}
.deal-sub{color:#0A2540;font-size:.95rem;margin-bottom:1rem}
.deal-stats{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:.75rem}
.deal-stat{background:#ffffff;border:1px solid #D7E3F1;border-radius:8px;padding:.85rem}
.deal-stat .label{color:#0A2540;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}
.deal-stat .value{color:#0A2540;font-family:'JetBrains Mono',monospace;font-size:1.4rem;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.01em;margin-top:.25rem}
.deal-badge{display:inline-block;background:#E6F0FA;border:1px solid #D7E3F1;color:#0A2540;font-weight:600;padding:.35rem .7rem;border-radius:8px;font-size:.9rem;margin:.5rem 0}
.deal-obs{color:#1A1A1A;font-size:.9rem;line-height:1.6;margin-bottom:1.25rem}
.deal-cta-primary{display:flex;align-items:center;justify-content:center;min-height:48px;padding:0 20px;margin:1rem 0 .5rem;background:#005EB8;color:#ffffff;border-radius:8px;font-weight:600;font-size:1rem;text-decoration:none;text-align:center}
.deal-cta-primary:hover{background:#004A92;color:#ffffff}
.deal-chat{display:flex;align-items:center;justify-content:center;min-height:44px;padding:0 16px;background:#ffffff;border:1px solid #005EB8;color:#005EB8;font-weight:600;border-radius:8px;text-decoration:none;font-size:.95rem;margin-bottom:.5rem}
.deal-chat:hover{background:#E6F0FA;color:#004A92}
.deal-locked{background:#ffffff;border:1px solid #D7E3F1;border-radius:8px;padding:1rem;margin:1rem 0 .75rem}
.deal-locked-head{display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem}
.deal-locked h2{font-size:1rem;color:#0A2540;margin:0}
.lock{display:inline-block;width:12px;height:12px;flex:none;border:2px solid #0A2540;border-radius:3px}
.deal-locked dl{display:flex;flex-direction:column;gap:.5rem;margin:0}
.masked{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:.5rem .6rem;background:#E6F0FA;border:1px solid #D7E3F1;border-radius:8px}
.masked dt{font-size:.9rem;color:#1A1A1A}
.masked dd{margin:0}
.masked b{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:400;letter-spacing:.06em;color:#0A2540;font-variant-numeric:tabular-nums}
.deal-more{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.06em;color:#0A2540;margin-top:.75rem;line-height:1.5}
.deal-reel{display:flex;gap:.75rem;align-items:center;background:#ffffff;border:1px solid #D7E3F1;border-radius:8px;padding:.75rem;margin-bottom:.75rem;text-decoration:none}
.deal-reel-thumb{position:relative;flex:none;width:60px;aspect-ratio:9/16;display:flex;align-items:center;justify-content:center;overflow:hidden;background-color:#E6F0FA;background-image:repeating-linear-gradient(135deg,transparent 0 9px,rgba(10,37,64,.10) 9px 10px);border:1px solid #D7E3F1;border-radius:8px}
.deal-reel-play{width:30px;height:30px;display:flex;align-items:center;justify-content:center;padding-left:2px;border-radius:50%;background:#005EB8;color:#ffffff;font-size:12px}
.deal-reel h2{font-size:1rem;color:#0A2540;margin:0 0 .2rem}
.deal-reel p{margin:0;font-size:.9rem;color:#0A2540;line-height:1.5}
.deal-cta{background:#ffffff;border:1px solid #D7E3F1;border-radius:8px;padding:1.1rem;margin-top:.75rem}
.deal-cta h2{font-size:1rem;color:#0A2540;margin-bottom:.5rem}
.deal-cta p{font-size:.9rem;color:#0A2540;margin-bottom:.75rem}
.deal-cta input{width:100%;min-height:44px;padding:.7rem;border-radius:8px;border:1px solid #0A2540;background:#ffffff;color:#1A1A1A;margin-bottom:.6rem;font-size:1rem}
.deal-cta button{width:100%;min-height:44px;padding:.75rem;border-radius:8px;border:1px solid #005EB8;background:#ffffff;color:#005EB8;font-weight:600;font-size:.95rem;cursor:pointer}
.deal-cta button:hover{background:#E6F0FA;color:#004A92}
.deal-thanks{color:#0A2540;font-size:.95rem}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #005EB8;outline-offset:2px}
html[data-theme=dark] body{background:#0B1119;color:#EDEDED}
html[data-theme=dark] h1,html[data-theme=dark] .deal-addr,html[data-theme=dark] .deal-locked h2,html[data-theme=dark] .deal-reel h2,html[data-theme=dark] .deal-cta h2,html[data-theme=dark] .deal-stat .value{color:#EDEDED}
html[data-theme=dark] .deal-sub,html[data-theme=dark] .deal-obs,html[data-theme=dark] .deal-eyebrow,html[data-theme=dark] .deal-stat .label,html[data-theme=dark] .masked dt,html[data-theme=dark] .masked b,html[data-theme=dark] .deal-more,html[data-theme=dark] .deal-reel p,html[data-theme=dark] .deal-cta p,html[data-theme=dark] .deal-thanks{color:#9EB2C7}
html[data-theme=dark] .deal-stat,html[data-theme=dark] .deal-locked,html[data-theme=dark] .deal-cta,html[data-theme=dark] .deal-reel{background:#111B27;border-color:#24344C}
html[data-theme=dark] .masked,html[data-theme=dark] .deal-greeting,html[data-theme=dark] .deal-badge,html[data-theme=dark] .deal-aerial,html[data-theme=dark] .deal-reel-thumb{background-color:#1B2737;border-color:#24344C;color:#EDEDED}
html[data-theme=dark] .deal-img,html[data-theme=dark] .deal-aerial{border-color:#24344C}
html[data-theme=dark] .lock{border-color:#9EB2C7}
html[data-theme=dark] .deal-cta-primary{background:#1A90FF;color:#0B1119}
html[data-theme=dark] .deal-cta-primary:hover{background:#4DA6FF;color:#0B1119}
html[data-theme=dark] .deal-chat,html[data-theme=dark] .deal-cta button{background:#111B27;border-color:#4DA6FF;color:#4DA6FF}
html[data-theme=dark] .deal-cta input{background:#111B27;border-color:#9EB2C7;color:#EDEDED}
html[data-theme=dark] .deal-preview-banner{background:#1B2737;color:#EDEDED}
</style>"""

NEW_BODY = """<body>
<div class="deal-card">
${previewBanner}
<div class="deal-greeting" id="bd-greeting"></div>
${ogImage
  ? `<img class="deal-img" src="${escHtml(ogImage)}" alt="Aerial of ${escHtml(reel.property_address || 'this property')}">`
  : `<div class="deal-aerial" role="img" aria-label="Aerial imagery not available for this property">PROPERTY AERIAL<br>${escHtml(String(reel.county || ''))} / ${escHtml(String(reel.case_number || ''))}</div>`}
<p class="deal-eyebrow">${escHtml(countyName)} County &middot; ${escHtml(saleLabel)}${reel.auction_date ? ' &middot; ' + escHtml(reel.auction_date) : ''}</p>
<h1>${escHtml(reel.property_address || soldFmt || 'Sold at auction')}</h1>
${reel.property_address && soldFmt ? `<div class="deal-addr">Sold at auction for ${escHtml(soldFmt)}</div>` : ''}
${orderedSections}
<a class="deal-cta-primary" href="/buy-report?case=${encodeURIComponent(reel.case_number || '')}&amp;county=${encodeURIComponent(reel.county || '')}">Get the full property signal report</a>
<a class="deal-chat" href="${escHtml(chatHref)}">Ask Deed about this property &rarr;</a>
<a class="deal-chat" href="${escHtml(projectHref)}">New project from this &rarr;</a>
<section class="deal-locked" aria-labelledby="bd-signal-card">
<div class="deal-locked-head"><span class="lock" aria-hidden="true"></span><h2 id="bd-signal-card">SIGNAL$ Property Report</h2></div>
<dl>
<div class="masked"><dt>Value Band</dt><dd><b aria-hidden="true">$&bull;&bull;&bull;,&bull;&bull;&bull; &ndash; $&bull;&bull;&bull;,&bull;&bull;&bull;</b><span class="sr">Value band withheld &mdash; included in the SIGNAL$ Property Report</span></dd></div>
<div class="masked"><dt>SIGNAL$ Max Bid</dt><dd><b aria-hidden="true">$&bull;&bull;&bull;,&bull;&bull;&bull;</b><span class="sr">SIGNAL$ Max Bid withheld &mdash; included in the SIGNAL$ Property Report</span></dd></div>
<div class="masked"><dt>Red Flags</dt><dd><b aria-hidden="true">&bull;&bull; found</b><span class="sr">Red flag count withheld &mdash; included in the SIGNAL$ Property Report</span></dd></div>
<div class="masked"><dt>Lien Hierarchy</dt><dd><b aria-hidden="true">&bull;&bull; liens</b><span class="sr">Lien count withheld &mdash; included in the SIGNAL$ Property Report</span></dd></div>
<div class="masked"><dt>Comps</dt><dd><b aria-hidden="true">&bull;&bull; nearby</b><span class="sr">Comparable-sale count withheld &mdash; included in the SIGNAL$ Property Report</span></dd></div>
</dl>
<p class="deal-more">5 more sections on this property &middot; included in the SIGNAL$ Property Report</p>
</section>
${shortCode ? `<a class="deal-reel" href="/reels/${encodeURIComponent(shortCode)}">
<span class="deal-reel-thumb" aria-hidden="true"><span class="deal-reel-play">&#9654;</span></span>
<span><h2>Watch the 32-second reel</h2><p>Same parcel, same numbers, read aloud.</p></span>
</a>` : ''}
<div class="deal-cta">
<h2>Prefer it by email?</h2>
<p>We will send this property&rsquo;s report to your inbox.</p>
${ctaBlock}
</div>
</div>
<script>${dealPageStickyScript(shortCode, reel.county || '', archetype || '', reel.case_number || '')}</script>
</body>"""


def main(path):
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("apply_deal_page_005eb8: already applied, nothing to do.")
        return 0

    i = src.index(STYLE_ANCHOR)
    s0 = src.rindex("<style>", 0, i)
    s1 = src.index("</style>", i) + len("</style>")
    src = src[:s0] + NEW_STYLE + src[s1:]

    b0 = src.index(BODY_ANCHOR)
    b1 = src.index("</body>", b0) + len("</body>")
    src = src[:b0] + NEW_BODY + src[b1:]

    open(path, "w", encoding="utf-8").write(src)
    print("apply_deal_page_005eb8: rebuilt the /deal/:county/:case style block and body.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src/worker.js"))
