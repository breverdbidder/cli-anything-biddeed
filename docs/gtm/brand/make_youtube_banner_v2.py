from PIL import Image, ImageDraw, ImageFont, ImageFilter
F="inter/extras/ttf/"
NAVY=(2,6,23); NAVY2=(11,18,32); AMBER=(245,158,11); CREAM=(245,240,232)

def parcel_outline(d, cx, cy, s, width, color):
    pts=[(cx-0.9*s,cy-0.55*s),(cx+0.8*s,cy-0.7*s),(cx+0.95*s,cy+0.5*s),(cx-0.7*s,cy+0.7*s)]
    d.line(pts+[pts[0]],fill=color,width=width,joint="curve")
    for p in pts: d.ellipse([p[0]-width,p[1]-width,p[0]+width,p[1]+width],fill=color)

def draw_mark(d, x0, y0, S):
    """The avatar mark (B + parcel outline + AI tag) scaled into an SxS box at (x0,y0)."""
    k=S/800
    parcel_outline(d, x0+S/2, y0+S/2+10*k, 300*k, max(2,int(10*k)), (70,50,16))
    parcel_outline(d, x0+S/2, y0+S/2+10*k, 300*k, max(2,int(7*k)), AMBER)
    fb=ImageFont.truetype(F+"Inter-Black.ttf",int(470*k))
    bb=d.textbbox((0,0),"B",font=fb); bw=bb[2]-bb[0]; bh=bb[3]-bb[1]
    d.text((x0+S/2-bw/2-bb[0], y0+S/2-bh/2-bb[1]+8*k),"B",font=fb,fill=CREAM)
    fs=ImageFont.truetype(F+"Inter-Bold.ttf",int(86*k))
    tb=d.textbbox((0,0),"AI",font=fs)
    d.rounded_rectangle([x0+S/2+95*k,y0+S/2+120*k,x0+S/2+95*k+(tb[2]-tb[0])+44*k,y0+S/2+120*k+(tb[3]-tb[1])+30*k],radius=int(18*k),fill=AMBER)
    d.text((x0+S/2+117*k-tb[0],y0+S/2+133*k-tb[1]),"AI",font=fs,fill=NAVY)

W,H=2560,1440
img=Image.new("RGB",(W,H),NAVY); d=ImageDraw.Draw(img)
for y in range(H):
    t=y/H; c=tuple(int(NAVY[i]+(NAVY2[i]-NAVY[i])*t) for i in range(3)); d.line([(0,y),(W,y)],fill=c)
g=(18,28,48)
for x in range(0,W,80): d.line([(x,0),(x,H)],fill=g,width=1)
for y in range(0,H,80): d.line([(0,y),(W,y)],fill=g,width=1)
glow=Image.new("RGB",(W,H),(0,0,0)); gd=ImageDraw.Draw(glow)
gd.ellipse([W/2-900,H/2-380,W/2+900,H/2+380],fill=(60,38,6)); glow=glow.filter(ImageFilter.GaussianBlur(160))
img=Image.blend(img,Image.composite(glow,img,glow.convert("L").point(lambda v:min(255,v*3))),0.35)
d=ImageDraw.Draw(img)

# safe area x 507..2053, y 508..931 (1546x423)
sx0,sy0,sx1,sy1=507,508,2053,931
M=400                     # mark box
fw=ImageFont.truetype(F+"Inter-Black.ttf",168)
ft=ImageFont.truetype(F+"Inter-Bold.ttf",44)
fu=ImageFont.truetype(F+"Inter-Black.ttf",78)
name,ai="BidDeed"," AI"
wn=d.textlength(name,font=fw); wa=d.textlength(ai,font=fw)
tag="REAL AUCTIONS.  REAL NUMBERS.  EVERY DAY."; tw=d.textlength(tag,font=ft)
u="biddeed.ai"; uw=d.textlength(u,font=fu)
textw=max(wn+wa,tw,uw); gap=60
groupw=M+gap+textw
gx=(W-groupw)/2
# mark, vertically centred in safe area
my=(sy0+sy1)/2-M/2
draw_mark(d, gx, my, M)
tx=gx+M+gap
# text block heights: wordmark ~ 168*1.2, rule, tag, url  -> total ~ 330; centre it
ty=(sy0+sy1)/2-190
d.text((tx,ty),name,font=fw,fill=CREAM); d.text((tx+wn,ty),ai,font=fw,fill=AMBER)
d.rectangle([tx,ty+205,tx+textw,ty+210],fill=AMBER)
d.text((tx,ty+228),tag,font=ft,fill=CREAM)
d.text((tx,ty+286),u,font=fu,fill=AMBER)
# assert inside safe area
assert gx>=sx0 and gx+groupw<=sx1, (gx, gx+groupw)
img.save("biddeed_youtube_banner_2560x1440.png",optimize=True)
img.crop((sx0,sy0,sx1,sy1)).save("banner_safe_area_preview.png")
print("ok", gx, gx+groupw)
