#!/usr/bin/env python3
"""Colored digit mosaic v3 — ink-coverage exposure compensation."""
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SRC = ("/mnt/user-data/uploads/Johnnywang_The_great_hall_doors_barred_suitors"
       "_turning_in_daw_52469dd8-77bf-4269-8d2d-0db611a40ea4_3.png")

def ramp_and_coverage(charset, cw, chh, fsize):
    """Order glyphs by ink coverage; also return mean coverage in the cell."""
    f = ImageFont.truetype(FONT, fsize); cov = {}
    for c in charset:
        im = Image.new("L", (cw, chh), 0)
        ImageDraw.Draw(im).text((cw//2, chh//2), c, 255, f, anchor="mm")
        cov[c] = np.asarray(im).mean()/255
    ramp = "".join(sorted(charset, key=lambda c: cov[c]))
    return ramp, float(np.mean([cov[c] for c in charset]))

def prep(img, clip=2.2, tiles=10):
    lab = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(clip, (tiles, tiles)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

def dither(v, n):
    v = v.astype(np.float64)*(n-1); h, w = v.shape; out = np.zeros((h, w), int)
    for y in range(h):
        for x in range(w):
            q = min(max(int(round(v[y, x])), 0), n-1); out[y, x] = q
            e = v[y, x]-q
            if x+1 < w: v[y, x+1] += e*7/16
            if y+1 < h:
                if x: v[y+1, x-1] += e*3/16
                v[y+1, x] += e*5/16
                if x+1 < w: v[y+1, x+1] += e*1/16
    return out

def filmic(x):
    """Soft shoulder so the exposure boost doesn't clip highlights flat."""
    return x*(2.51*x+.03)/(x*(2.43*x+.59)+.14)

def render(out, cols=340, cell=16, charset="0123456789", mode="woven",
           sat=1.5, gamma=0.85, eq=0.55, clip=2.2):
    img = Image.open(SRC).convert("RGB"); W, H = img.size
    boosted = Image.fromarray(prep(img, clip))

    cw, chh = cell, int(cell*1.46)
    fsize = int(cell*1.58)
    ramp, ink = ramp_and_coverage(charset, cw, chh, fsize)
    font = ImageFont.truetype(FONT, fsize)
    rows = max(1, int(round(cols*(H/W)*(cw/chh))))

    px = np.asarray(boosted.resize((cols, rows), Image.LANCZOS), np.float64)
    lum = px @ np.array([.2126, .7152, .0722])

    a, b = np.percentile(lum, 0.5), np.percentile(lum, 99.5)
    stretched = np.clip((lum-a)/max(b-a, 1e-6), 0, 1)
    order = lum.ravel().argsort().argsort().reshape(lum.shape)   # rank equalise
    tone = ((1-eq)*stretched + eq*order/(lum.size-1)) ** gamma
    idx = dither(tone, len(ramp))

    if mode == "woven":                 # bg 0.75x + ink 1.9x  ->  averages to 1x
        bg_k, ink_k = 0.75, (1-0.75*(1-ink))/ink
    else:                               # all the light comes from the glyphs
        bg_k, ink_k = 0.0, 1/ink

    target = filmic(tone*ink_k*0.85)*255
    scale = (target/np.maximum(lum, 1e-6))[..., None]
    rgb = px*scale
    m = rgb.mean(2, keepdims=True)
    rgb = np.clip(m+(rgb-m)*sat, 0, 255).astype(np.uint8)

    OW, OH = cols*cw, rows*chh
    if bg_k:
        bgim = boosted.resize((OW, OH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(cell*0.55))
        canvas = Image.fromarray(np.clip(np.asarray(bgim)*bg_k, 0, 255).astype(np.uint8))
    else:
        canvas = Image.new("RGB", (OW, OH), (6, 7, 10))
    d = ImageDraw.Draw(canvas)
    for y in range(rows):
        for x in range(cols):
            d.text((x*cw+cw//2, y*chh+chh//2), ramp[idx[y, x]],
                   fill=tuple(int(v) for v in rgb[y, x]), font=font, anchor="mm")
    canvas.save(out, quality=95)
    print(f"{out} {OW}x{OH} grid {cols}x{rows} ink={ink:.3f} ramp '{ramp}'")

if __name__ == "__main__":
    render("/mnt/user-data/outputs/archer_digits_woven.png", mode="woven")
    render("/mnt/user-data/outputs/archer_digits_dark.png",  mode="dark")
