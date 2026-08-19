# threshold

Rewrite any image as a picture made of `0`s and `1`s — drop it in a browser tab and it's done, exportable as a crisp PNG or a looping GIF.

**[Try it live → threshold-rho-seven.vercel.app](https://threshold-rho-seven.vercel.app)**

*[中文说明 →](README.zh.md)*

The name is one word doing two jobs. In image binarization, the step that carves continuous tone into pure black-or-white is called *thresholding*. The source photo is Book 21 of the *Odyssey* — the great hall's doors barred, Odysseus standing on the threshold with the bow drawn, the killing not yet begun. One meaning is a technical operation, the other a narrative moment; the project sits exactly where the two overlap.

## Web app: drop an image in

`web/app.html` is a single file with no dependencies and no server. Double-click it, drop any image in, and the whole pipeline runs in your own browser — nothing is ever uploaded anywhere.

- **Upload** — drag-and-drop, click to pick a file, or paste with ⌘V
- **Bilingual** — every string on the page comes from one dictionary; defaults to your browser's language
- **Light / dark by the clock** — 06:00–18:00 is light, the rest is dark; no toggle, no system preference
- **Live tuning** — density (60–320 columns) and contrast rebuild in real time
- **Five views** — still (default) / shimmer / rain / decode / scan, speed adjustable
- **The picture is a pool of water** — run your pointer across it and ripples spread, characters refract around them, and the water settles back to the original once it stills
- **Export PNG** — a crisp still up to 3200px, backed by a blurred copy of the source (a "woven" texture)
- **Export GIF** — a 40-frame loop; quantization, LZW, and the container format are all hand-written, no external library

The original Python pipeline's CLAHE, percentile stretch, rank equalization, filmic exposure compensation, and Floyd–Steinberg dithering all have an equivalent JS implementation inside `web/app.html`.

## Command line

```bash
pip install -r requirements.txt
make web                  # builds out/live.html with input/source.png baked in
make grid                 # export just the tone grid
make still                # 5440×3795 PNG via src/mosaic.py
make video                # 24s MP4 (needs ffmpeg on PATH)
make                      # all four, same as `make all`
```

`still` and `video` need a bold monospace font on the machine; `src/mosaic.py`'s
`find_font()` checks a short list of common paths (DejaVu on Linux, Menlo on macOS,
Consolas on Windows) and fails with a clear message if none are found — add yours
to the list rather than hardcoding a path that only exists on one OS.

`make web` produces `out/live.html` — the same app as above, plus a baked-in default image. Open it and Odysseus is already there, fully interactive: density and contrast work on the demo photo exactly as they would on your own, because the source image is embedded too (downscaled to `SEED_MAX=1100`, encoded as JPEG). Earlier builds only embedded the pre-computed grid — no source pixels — so those two sliders were permanently grayed out on first load, which is a rough first impression for anyone trying the live demo. Now `export_grid.py` embeds a lightweight copy of the untouched source, and the app runs it through the exact same `prepped()` path a real upload takes.

## Pipeline

```
any image ──► web/app.html ──┬──► PNG still
  (in-browser, no server)     └──► GIF loop

source.png ─► export_grid.py ─► grid.json ─► build_web.py ─► out/live.html
                200×95 grid                    (bakes the grid into app.html)
                4 bytes per cell: R G B base-character
```

## Three things that had to be solved

**1. Dark photos need local exposure lift before anything else.** The source sits around median brightness 90, with huge swaths near pure black — converting it directly erases the face and the bowstring entirely. CLAHE runs on the L channel in LAB space, so hue is untouched.

**2. Ink coverage decides the exposure math.** `0` and `1` only fill about 31% of their cell — without compensation the whole image drops to roughly a third of the source's brightness and reads as flat gray at a distance. The fix measures actual glyph coverage, inverts it into an exposure multiplier, then runs a filmic curve to keep highlights from clipping:

```python
ink   = measured_coverage(charset)      # ≈ 0.31
target = filmic(tone * (0.66 / ink) * 0.85) * 255
```

**3. With only two glyphs, every gray level comes from dithering.** Floyd–Steinberg spreads quantization error to neighboring cells, so the grid has to be dense enough (≥ 400 columns for stills, 200 for animation) or midtones band visibly.

## Why the animation never falls apart

The brightness map is baked into `grid.json` and never changes; the only thing that moves is whether each cell shows a `0` or a `1`. However the characters flip and flow, the image stays standing.

The default view is **still** — frozen on the dithered result, the same state a downloaded PNG captures (characters settled, no animation-driven brightness boost). That frame is drawn once and never redrawn — 19,000 characters don't need repainting 60 times a second for no reason. Because nothing is moving, speed, pause, and GIF export are all grayed out in this mode.

The other four are motion:

- **Shimmer** — flip probability weighted by `4L(1-L)`, so midtones are the most restless and shadows stay quiet
- **Rain** — each column has its own speed and trail length; the base image always shows through
- **Decode** — resolve order is sorted by brightness, so **the figure arrives before the room does**
- **Scan** — a bright band sweeps down the frame, scrambling and lifting whatever falls inside it

## The text is a pool of water

Run your pointer across the picture and the characters refract, the way anything looks bent when you view it through water.

**This interaction was completely undiscoverable at first** — a canvas made of characters gives no hint that it does anything, so nobody thought to touch it. The fix isn't burying "try dragging your pointer across it" inside the background-reading paragraph at the bottom of the page (most people never scroll that far). It's a small hint card that surfaces in the corner of the canvas once an image loads, and fades out for good the first time someone actually touches the water. A discovery hint and a background explanation are two different jobs and shouldn't be crammed into the same paragraph.

Underneath, a height field the same size as the character grid runs a classic **2D wave equation**: each cell's next frame comes from the average of its four neighbors and its own previous frame, times a damping factor. The pointer drops energy into the water as it moves, and the ripple spreads, interferes with itself, and bounces off the edges on its own. A spring wouldn't do this — springs bounce independently with no coupling between them, which would just make each character twitch in place. **For a ripple to actually travel, neighboring cells have to be coupled**, and that's exactly what the wave equation gives you.

The height field turns into three things on screen: characters shift sideways along the height **gradient** (refraction), wave crests get **brighter**, and cells disturbed past a threshold **flip** between 0 and 1 (the water gets stirred up). Energy dropped in scales with pointer speed — a slow pass makes a ripple, a fast swipe makes a splash, and a click drops a stone.

Two implementation traps:

- **The rest condition has to watch peak amplitude, not total energy.** As a ripple spreads, total energy actually *increases* (26 → 118 in one measurement) — but what decides "is this still visible" is the tallest remaining peak. Using total energy as the stopping condition left the render loop awake for hundreds of wasted frames.
- **Still mode has to re-derive from the base state every frame.** That's what lets the picture settle back to exactly its original state once the water calms — measured: 0 cells still carrying an offset after settling. An image someone touched never stays smudged.

Water is flattened (`calmWater()`) before every export: a PNG is a frozen still, and during a GIF recording the pointer isn't over the canvas anyway — any leftover ripple would get baked into the output. The system "reduce motion" preference turns the whole pool off.

### On tuning this

Partway through, I retuned it around the idea that "bigger coverage, longer decay" would feel more like water: peak displacement dropped from 18px to 3.4px, affected area went from 2% to 25%, visible duration stretched from 0.3s to 3.9s. **Every number on paper got better, and it felt wrong** — it turned into one big, slow, sluggish surge instead of a splash. Reverted to the original values.

The lesson worth keeping: only a hand can judge whether an effect like this feels right. Coverage area and duration were metrics I invented myself, and they had nothing to do with whether it actually felt satisfying. Quantify to catch real defects (leftover residue, idle spinning, blown-out amplitude) — never to define the feel.

Three knobs, all at the top of `web/app.html`: **`DAMP`** how long the ripple lingers, **`WARP`** how strong the displacement is, **`LIFT`** how bright the crest gets.

Current measurements: 18.4px peak displacement, 0.5s visible, settles in 1.35s, 0 cells left offset once still, 0.37ms per frame (2.2% of a 60fps frame budget).

## The logo

The mark is a **step function**: flat, a vertical jump, flat again.

I chose it because it's both halves of the project's name at once — mathematically it's the definition of a threshold (output 0 below the cutoff, 1 above it, no transition in between); visually it's a **doorstep**, the exact spot Odysseus is standing on. The README opens by saying the project sits where those two meanings overlap; the mark had to *be* that overlap, not just illustrate it.

Two decisions in how it's drawn:

- **The jump is drawn at half the stroke weight of the flat segments.** A step's transition is instantaneous and zero-width in the math; this also happens to give the mark the same stroke contrast as the serif wordmark next to it, so the two read as one voice. It's also the only place in the whole logo carrying the accent color — the instant the threshold is crossed.
- **The mark's height equals the type's ascender height (0.757em)**, with its low segment sitting on the baseline and its high segment level with the tops of t/h/l/d. So it isn't "an icon parked next to some letters" — it's one geometric object locked to the type, and it holds together across languages and breakpoints.

The same mark doubles as the favicon (inline SVG with its own light/dark rule). The step still reads at 16px.

## On light mode

Light mode isn't dark mode inverted — it's a separate palette built around the idea of an exhibition catalogue: warm paper white, warm ink black, the same torch-amber accent.

**But the picture itself stays dark in both modes.** That's not laziness — the entire exposure pipeline is built on "the characters are the light source":

```
target = filmic(tone * (0.66 / ink) * 0.85)   # work out how much light each cell should emit
rgb    = px * (target / lum)                  # then scale the color to that brightness
```

The characters are additive — they emit light themselves. Flipping that to white paper would mean switching to a subtractive ink model, which is a different piece, not a reskin of the same one. So in light mode the picture is presented as **a mounted photograph**: a dark print on warm white paper, with a thin frame and a faint drop shadow. An empty frame shows the mount board's own color; it only goes dark once a picture is loaded.

The logo's palette follows suit: the flat strokes use whatever ink color the current theme defines; the jump is always torch amber.

Contrast was checked against WCAG AA (body text ≥ 4.5:1) in both themes.

## How the GIF encoder works

Browsers don't ship a GIF encoder, so this part is hand-written: **median-cut quantization → LZW → GIF89a container**.

The trouble is that a digit mosaic is about the worst possible input for LZW — every cell is a different color, anti-aliased on top of that, so a whole frame is close to noise. Forty frames straight out came to 9.1 MB. The fix is the frame-differencing GIF already supports natively:

- write only the pixels that changed from the previous frame; everything else gets the transparent index and lets the frame underneath show through (disposal method set to "keep")
- crop each frame to the bounding box of what actually changed
- reserve one palette slot for transparency — 256 colors becomes 255

Shimmer mode only flips a few hundred cells per frame, so after differencing most of a frame is the same transparent index repeated — exactly the long run LZW is best at. Same 40 frames, same 800×576: **9.1 MB down to 1.0 MB**.

## Performance

The web app redraws all 19,000 characters every frame. Switching `fillStyle` per cell would choke, so colors are quantized into 32 buckets and the fill style is switched once per bucket instead of once per character — measured at 0.85ms/frame.

## Tuning knobs

`src/mosaic.py`:

| Parameter | Effect |
|---|---|
| `cols` | Grid density. Higher looks more like the source, less like digits |
| `charset` | `"01"` binary / `"0123456789"` decimal / any character set |
| `mode` | `dark` glowing on black / `woven` source image showing through as a fabric texture |
| `gamma` | Higher pushes blacks deeper, more dramatic |
| `eq` | Weight of rank equalization — 0 keeps the original tonal curve, 1 forces a flat spread across the full range |
