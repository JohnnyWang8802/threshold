#!/usr/bin/env python3
"""Extract the tone/character grid the web + video renderers animate."""
import argparse, base64, io, json, numpy as np
from PIL import Image
import mosaic as D

SEED_MAX = 1100   # 嵌入网页的演示图边长上限，和 web/app.html 里 WORK_MAX 对齐

COLS = 200
CELL_ASPECT = 1.46          # height / width of one character cell

p = argparse.ArgumentParser()
p.add_argument("--src", default="input/source.png")
p.add_argument("--out", default="out/grid.json")
a = p.parse_args()

img = Image.open(a.src).convert("RGB")
W, H = img.size
boosted = Image.fromarray(D.prep(img, 2.2))

rows = max(1, int(round(COLS * (H / W) / CELL_ASPECT)))
px = np.asarray(boosted.resize((COLS, rows), Image.LANCZOS), np.float64)
lum = px @ np.array([.2126, .7152, .0722])

a_p, b_p = np.percentile(lum, 0.5), np.percentile(lum, 99.5)
stretched = np.clip((lum - a_p) / max(b_p - a_p, 1e-6), 0, 1)
order = lum.ravel().argsort().argsort().reshape(lum.shape)
tone = (0.75 * stretched + 0.25 * order / (lum.size - 1)) ** 1.35

ink = 0.306                                   # measured coverage of '0'/'1'
target = D.filmic(tone * (0.66 / ink) * 0.85) * 255
rgb = px * (target / np.maximum(lum, 1e-6))[..., None]
m = rgb.mean(2, keepdims=True)
rgb = np.clip(m + (rgb - m) * 1.5, 0, 255).astype(np.uint8)

ch = D.dither(tone, 2).astype(np.uint8)       # 0 -> '1'(light), 1 -> '0'(dark)

buf = np.dstack([rgb, ch[..., None]]).astype(np.uint8).tobytes()

# 顺带塞一份瘦身版原图（未经 CLAHE 的那张 img，不是 boosted）。
# 网页版加载演示图时会拿它重新跑一遍自己的 prepped()，跟真实上传
# 走同一条代码路径——这样密度/反差这两个滑杆在演示图上也能用，
# 不用另开一条只服务预埋场景的算法分支。
seed_img = img.copy()
seed_img.thumbnail((SEED_MAX, SEED_MAX), Image.LANCZOS)
seed_buf = io.BytesIO()
seed_img.save(seed_buf, "JPEG", quality=84)
seed_src = "data:image/jpeg;base64," + base64.b64encode(seed_buf.getvalue()).decode()

payload = {"cols": COLS, "rows": rows,
           "data": base64.b64encode(buf).decode(),
           "src": seed_src}
json.dump(payload, open(a.out, "w"))
print(f"grid {COLS}x{rows}  cells={COLS*rows}  base64={len(payload['data'])//1024}KB"
      f"  seed={seed_img.size[0]}x{seed_img.size[1]}  {len(seed_src)//1024}KB")
