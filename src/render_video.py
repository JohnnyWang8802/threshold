#!/usr/bin/env python3
"""Render the four animation modes to an MP4, headlessly."""
import argparse, base64, json, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont
from mosaic import find_font          # 同一份跨平台字体查找，别再抄一遍

FONT_PATH, FONT_INDEX = find_font()
CW, CH, FPS = 8, 12, 30
SECONDS_PER_MODE = 6

p = argparse.ArgumentParser()
p.add_argument("--grid", default="out/grid.json")
p.add_argument("--out", default="out/threshold.mp4")
a = p.parse_args()
OUT = a.out

g = json.load(open(a.grid))
COLS, ROWS = g["cols"], g["rows"]
raw = np.frombuffer(base64.b64decode(g["data"]), np.uint8).reshape(ROWS, COLS, 4)
RGB = np.clip(raw[..., :3].astype(np.float32) * 1.42, 0, 255)
BASE = raw[..., 3].copy()
LUM = (RGB @ np.array([.2126, .7152, .0722], np.float32)) / 255.0

# ---- glyph masks: index 0 -> '1', index 1 -> '0' ---------------------
font = ImageFont.truetype(FONT_PATH, int(CW * 1.6), index=FONT_INDEX)
masks = []
for ch in ("1", "0"):
    tile = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(tile).text((CW / 2, CH / 2), ch, 255, font, anchor="mm")
    masks.append(np.asarray(tile, np.float32) / 255.0)
M0, M1 = masks                                   # (CH, CW)

cur = BASE.copy()
rng = np.random.default_rng(7)

# resolve order for decode: bright cells first, so the figure precedes the room
key = LUM * 0.62 + rng.random(LUM.shape).astype(np.float32) * 0.38
ORDER = (-key).ravel().argsort().argsort().reshape(LUM.shape) / (LUM.size - 1)

col_pos = -rng.random(COLS).astype(np.float32) * ROWS * 1.6
col_spd = 7 + rng.random(COLS).astype(np.float32) * 16
col_len = 9 + rng.random(COLS).astype(np.float32) * 22

YY = np.arange(ROWS, dtype=np.float32)[:, None]

def frame_pixels(boost):
    col = np.clip(RGB * boost[..., None], 0, 255)
    sel = np.where(cur[:, None, :, None] == 1, M0[None, :, None, :], M1[None, :, None, :])
    px = sel[..., None] * col[:, None, :, None, :]
    return px.reshape(ROWS * CH, COLS * CW, 3).astype(np.uint8)

def step(mode, dt):
    global col_pos, decode_p, scan_y
    boost = np.ones((ROWS, COLS), np.float32)

    if mode == "shimmer":
        w = 4 * LUM * (1 - LUM) * 0.10
        cur[rng.random(LUM.shape) < w] ^= 1

    elif mode == "rain":
        col_pos += col_spd * dt
        done = col_pos - col_len > ROWS
        col_pos[done] = -rng.random(done.sum()).astype(np.float32) * ROWS * 0.5
        d = (col_pos[None, :] - YY) / col_len[None, :]
        inb = (d >= 0) & (d <= 1)
        boost += np.where(inb, (1 - d) ** 2 * 2.4, 0)
        boost += np.where((col_pos[None, :] - YY >= 0) & (col_pos[None, :] - YY < 1.2), 1.8, 0)
        cur[inb & (rng.random(LUM.shape) < 0.30)] ^= 1

    elif mode == "decode":
        decode_p += 0.16 * dt * 2.6
        if decode_p > 1.55:
            decode_p = 0.0
        p = min(decode_p, 1.0)
        locked = ORDER < p - 0.05
        front = (~locked) & (ORDER < p + 0.10)
        ahead = ~(locked | front)
        cur[locked] = BASE[locked]
        boost[front] = 1 + (1 - np.abs(ORDER[front] - p) / 0.10) * 1.9
        boost[ahead] = 0.30
        cur[front & (rng.random(LUM.shape) < 0.5)] ^= 1
        cur[ahead & (rng.random(LUM.shape) < 0.10)] ^= 1

    elif mode == "scan":
        scan_y += 26 * dt
        if scan_y > ROWS + 22:
            scan_y = -22.0
        f = np.clip(1 - np.abs(YY - scan_y) / 9.0, 0, 1) * np.ones((1, COLS), np.float32)
        boost += f ** 2 * 2.0
        cur[rng.random(LUM.shape) < 0.22 * f] ^= 1

    return boost

decode_p, scan_y = 0.0, -22.0
W, H = COLS * CW, ROWS * CH
proc = subprocess.Popen(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
     "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
     "-c:v", "libx264", "-preset", "slow", "-crf", "17",
     "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT],
    stdin=subprocess.PIPE)

for mode in ("decode", "shimmer", "rain", "scan"):
    cur[:] = BASE
    if mode == "decode":
        decode_p = 0.0
    if mode == "scan":
        scan_y = -22.0
    for _ in range(FPS * SECONDS_PER_MODE):
        proc.stdin.write(frame_pixels(step(mode, 1 / FPS)).tobytes())
    print(f"  {mode} done")

proc.stdin.close()
proc.wait()
print(f"{OUT}  {W}x{H}  {4*SECONDS_PER_MODE}s @ {FPS}fps")
