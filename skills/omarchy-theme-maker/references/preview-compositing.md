# Preview compositing recipe (1800x1012 stock-format preview.png)

Used when live geometry control is unreliable or the desktop is busy:
composite a real wallpaper+bar capture with a real themed-terminal capture.
Both inputs must be genuine `grim` captures of the applied theme - never
fabricated UI.

## Inputs

- `wallpaper.png` - `grim -o <monitor>` on an empty workspace after
  `omarchy theme set <slug>` (wallpaper + themed bar only, no windows).
- `terminal.png` - `grim` of a foot window running
  `omarchy dev theme-preview <slug> --no-osc`; tiled full-bleed is fine.

Follow the window-safety protocol in the main [SKILL.md](../SKILL.md) while
producing the inputs.

## Steps

1. **Crop the terminal content**: diff each pixel against the terminal
   background hex (>30 per-channel sum deviation), take the content bbox, crop
   with ~14px margin, skipping the top ~40px so the shell bar stays out of the
   panel.
2. **Base**: resize the wallpaper capture to 1800x1012 (LANCZOS).
3. **Locate protected elements programmatically** - do not trust vision-model
   boxes (estimates routinely mis-place wordmarks and cost rework iterations):
   - Wordmark/text: threshold luminance < 60-80, take dense column runs in the
     band where the text sits; group contiguous runs into a bbox.
   - Logo: tight saturated mask, e.g. blue =
     `(b > r+60) & (b > g+40) & (b > 140)`. Loose thresholds match sky/water
     and poison the cost function.
4. **Place the panel**: target ~56% of canvas width (cap height at H-120).
   Search candidate positions on an 8px grid, skipping any that overlaps a
   protected bbox; score = 2 x dark-text-pixels + 3 x saturated-logo-pixels
   covered. Take the minimum.
5. **Composite**: paste the panel over a soft blurred RGBA shadow (dark ink at
   low alpha, ~10px Gaussian) so the panel reads as a floating window.
6. **Quantize**: `im.quantize(colors=256, method=Image.MEDIANCUT,
   dither=NONE)`, save with `optimize=True`; stock target ~300-800 KB.

## Verification

- One final vision pass: wordmark fully visible, logo visible, panel text
  readable, reads as a real desktop.
- Pixel-sample any vision complaint about compositing before reworking -
  "text bleeding through the panel" is usually a misread of dim artwork near
  the panel edge; sampling the panel interior against the exact bg hex (e.g.
  >90% of pixels within tolerance, max deviation <10) proves opacity.
