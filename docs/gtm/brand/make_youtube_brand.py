from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
F="inter/extras/ttf/"
NAVY=(2,6,23); NAVY2=(11,18,32); AMBER=(245,158,11); CREAM=(245,240,232); MUTED=(120,130,150)

def parcel_outline(d, cx, cy, s, width, color):
    # irregular quadrilateral "parcel" like a county plat lot
    pts=[(cx-0.9*s,cy-0.55*s),(cx+0.8*s,cy-0.7*s),(cx+0.95*s,cy+0.5*s),(cx-0.7*s,cy+0.7*s)]
    d.line(pts+[pts[0]],fill=color,width=width,joint="curve")
    for p in pts: d.ellipse([p[0]-width,p[1]-width,p[0]+width,p[1]+width],fill=color)

# ---------- BANNER 2560x1440, safe area 1546x423 centered ----------
W,H=2560,1440
img=Image.new("RGB",(W,H),NAVY)
d=ImageDraw.Draw(img)
# vertical gradient
for y in range(H):
    t=y/H; c=tuple(int(NAVY[i]+(NAVY2[i]-NAVY[i])*t) for i in range(3))
    d.line([(0,y),(W,y)],fill=c)
# faint plat grid
g=(18,28,48)
for x in range(0,W,80): d.line([(x,0),(x,H)],fill=g,width=1)
for y in range(0,H,80): d.line([(0,y),(W,y)],fill=g,width=1)
# glow behind safe area
glow=Image.new("RGB",(W,H),(0,0,0)); gd=ImageDraw.Draw(glow)
gd.ellipse([W/2-900,H/2-380,W/2+900,H/2+380],fill=(60,38,6))
glow=glow.filter(ImageFilter.GaussianBlur(160))
img=Image.blend(img,Image.composite(glow,img,glow.convert("L").point(lambda v:min(255,v*3))),0.35)
d=ImageDraw.Draw(img)
# decorative parcel outlines outside the safe area (left & right of it)
parcel_outline(d, 330, 720, 150, 4, (60,45,20))
parcel_outline(d, 2230, 720, 150, 4, (60,45,20))
parcel_outline(d, 330, 720, 150, 3, (245,158,11))
parcel_outline(d, 2230, 720, 150, 3, (245,158,11))
# safe area box: x 507..2053, y 508..931
sx0,sy0,sx1,sy1=507,508,2053,931
fw=ImageFont.truetype(F+"Inter-Black.ttf",190)
ft=ImageFont.truetype(F+"Inter-Bold.ttf",54)
fu=ImageFont.truetype(F+"Inter-SemiBold.ttf",40)
cx=W/2
# wordmark
name="BidDeed"; ai=" AI"
wn=d.textlength(name,font=fw); wa=d.textlength(ai,font=fw)
x=cx-(wn+wa)/2; y=sy0+20
d.text((x,y),name,font=fw,fill=CREAM); d.text((x+wn,y),ai,font=fw,fill=AMBER)
# amber rule
d.rectangle([cx-260,y+235,cx+260,y+241],fill=AMBER)
# tagline (tracked)
tag="REAL AUCTIONS.  REAL NUMBERS.  EVERY DAY."
tw=d.textlength(tag,font=ft)
d.text((cx-tw/2,y+268),tag,font=ft,fill=CREAM)
# url
u="biddeed.ai"; uw=d.textlength(u,font=fu)
d.text((cx-uw/2,y+345),u,font=fu,fill=AMBER)
img.save("biddeed_youtube_banner_2560x1440.png",optimize=True)

# ---------- AVATAR 800x800 ----------
S=800
av=Image.new("RGB",(S,S),NAVY); d=ImageDraw.Draw(av)
for y in range(S):
    t=y/S; c=tuple(int(NAVY[i]+(NAVY2[i]-NAVY[i])*t) for i in range(3))
    d.line([(0,y),(S,y)],fill=c)
# parcel outline ring behind the mark
parcel_outline(d, S/2, S/2+10, 300, 10, (70,50,16))
parcel_outline(d, S/2, S/2+10, 300, 7, AMBER)
fb=ImageFont.truetype(F+"Inter-Black.ttf",470)
bb=d.textbbox((0,0),"B",font=fb); bw=bb[2]-bb[0]; bh=bb[3]-bb[1]
d.text((S/2-bw/2-bb[0], S/2-bh/2-bb[1]+8),"B",font=fb,fill=CREAM)
# small AI tag
fs=ImageFont.truetype(F+"Inter-Bold.ttf",86)
tb=d.textbbox((0,0),"AI",font=fs)
d.rounded_rectangle([S/2+95,S/2+120,S/2+95+(tb[2]-tb[0])+44,S/2+120+(tb[3]-tb[1])+30],radius=18,fill=AMBER)
d.text((S/2+117-tb[0],S/2+133-tb[1]),"AI",font=fs,fill=NAVY)
av.save("biddeed_youtube_avatar_800x800.png",optimize=True)
# preview of banner safe-area crop (what mobile shows)
img.crop((sx0,sy0,sx1,sy1)).save("banner_safe_area_preview.png")
print("ok")
