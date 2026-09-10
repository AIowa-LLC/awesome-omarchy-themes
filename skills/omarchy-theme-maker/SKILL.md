---
name: omarchy-theme-maker
description: Build an Omarchy theme from any image - palette extraction, hand-tuning, WCAG contrast checks, wallpaper, real preview capture, and a PR-ready theme directory.
version: 1.0.1
author: AIowa LLC
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Omarchy, Theming, Hyprland, Desktop]
---

# Omarchy Theme Maker

Turn source artwork (a wallpaper, photo, poster, or brand asset) into a complete,
contrast-checked Omarchy theme: a `colors.toml` palette derived from the image's
dominant colors as a **first pass only** and then hand-tuned to the artwork's
actual visual identity, the image installed as the theme background, a genuinely
captured preview, and a validator-clean theme directory ready for a pull request.

This is the same workflow used to build the themes in this collection, published
as the canonical public reference implementation. It never edits stock themes
under `/usr/share/omarchy/` and does not cover general Omarchy configuration.

## When to Use

- "Make an Omarchy theme from this image/wallpaper"
- "Theme my desktop from this photo"
- "Build a custom Omarchy palette matching this artwork"
- "Create a theme named X and add it to a theme collection repo"

## Prerequisites

- **Omarchy installed** for the live apply/preview steps - verify with
  `omarchy version`. The palette, contrast, and validation steps also work on a
  machine without Omarchy (CI does exactly that).
- **Python 3.10+ with Pillow** for palette extraction (`python3 -c "import PIL"`),
  and **Python 3.11+** for the contrast report script (uses stdlib `tomllib`).
- **`grim`** (screenshot) and **`foot`** (terminal) for preview capture - Omarchy
  ships both.
- The source image as a local file (jpg/png/webp/...). If handed a URL, download
  it to a temp directory first.

## Loading this skill

**Hermes agents**: if the skill is installed in Hermes, load it with
`skill_view(name="omarchy-theme-maker")` and resolve the script under the
skill's install directory (default profile: `~/.hermes/skills/...`; named
profiles: `~/.hermes/profiles/<profile>/skills/...`). When working in this
repository, prefer the repository-owned copy - this file - as the source of
truth if the two ever differ.

**Other coding agents**: read this file top to bottom, plus
[references/preview-capture.md](references/preview-capture.md) and
[references/preview-compositing.md](references/preview-compositing.md) when you
reach the preview step. Run the scripts with `python3`; every script supports
`--help` and fails loudly rather than guessing.

**Humans**: start at [README.md](README.md) next to this file for the
friendly overview; this file remains the operational source of truth.

Paths below assume the repository root as the working directory
(`skills/omarchy-theme-maker/...`). Substitute your skill install directory if
you are not working from a clone.

## Quick Reference

- `omarchy version` / `omarchy theme current` / `omarchy theme list`
- `python3 skills/omarchy-theme-maker/scripts/palette_to_theme.py IMAGE --name NAME [--mode dark|light|auto] [--out DIR] [--force] [--print]`
- `python3 skills/omarchy-theme-maker/scripts/contrast_report.py themes/<slug>/colors.toml`
- `omarchy theme set <slug>` - apply ("Tokyo Night" and "tokyo-night" both work)
- `omarchy theme bg next` - cycle the theme's backgrounds
- `omarchy dev theme-preview <colors.toml|slug> --no-osc` - ramp + contrast readout without applying
- `omarchy theme set <stock-name>` - revert to a stock theme

## Procedure

1. **Branch.** From an up-to-date `main`: `git checkout -b <theme-slug>`. Other
   themes merge mid-review and GitHub flips stale PRs to behind/conflicted -
   always start from fresh `main`.
2. **Inspect the source artwork before extracting anything.** Look at the image
   (vision-capable tool, or your own eyes): identify the visual identity - the
   brand color(s), the dominant mood, whether it reads dark or light, and any
   wordmark/logo that a preview must not occlude. Busy or ambiguous images
   warrant an explicit `--mode dark` or `--mode light` later instead of auto.
3. **First-pass extraction (script, then stop trusting it).** Run
   `palette_to_theme.py` with `--out themes` (or its default
   `~/.config/omarchy/themes/`) to get a complete 26-key draft:

   ```bash
   python3 skills/omarchy-theme-maker/scripts/palette_to_theme.py \
     /path/to/artwork.png --name "My Theme" --out themes
   ```

   It extracts dominant colors via median-cut quantization, picks dark/light
   from weighted luminance, builds the neutral ramp centered on
   `background -> bright_foreground`, and auto-adjusts accent + named colors to
   >= 3:1 contrast. Palette HSL targets are calibrated against the stock themes
   named in the Reference section.
4. **Hand-tune to the artwork's identity.** This pass is the difference between
   a generated palette and a real theme. Quantization picks *dominant* pixels,
   not *identity* colors - it has been observed to pick green as the accent for
   a red/black poster because dark pixels dominated the cut. When the artwork
   (or its brand) states a visual identity, author the palette to THAT identity
   and verify contrast afterwards. Rules of the craft:
   - **Mode**: dark or light must match how the artwork actually reads. Light
     images need `--mode light`; auto thresholds on weighted luminance and can
     guess wrong on mixed images.
   - **Neutral ramp** (dark): monotonic by WCAG relative luminance,
     `darker_background <= dark_background <= background <= lighter_background
     <= selection <= muted <= dark_foreground <= foreground <=
     light_foreground <= bright_foreground`.
   - **Light-mode relationships** (current Omarchy stock light themes do not
     share one key order; `omarchy dev theme-preview` sorts neutrals by
     luminance, so check relationships, not order): `background` is the
     lightest surface stop; `muted` sits between the surfaces and the primary
     foregrounds; `foreground`/`bright_foreground` are darker than every
     surface.
   - **ANSI normal/bright tuning**: dark themes keep the usual convention -
     bright variants lighter than normals. **Light themes invert it**: normals
     are deepened saturations and brights are the darker tones; artwork-luminous
     brights on a porcelain background fail readability.
   - **Selection / muted**: `selection` about 6% of lightness away from
     `background` toward the foreground side (matching stock spacing); `muted`
     darker than the surfaces (dark mode) or between surfaces and foregrounds
     (light mode). Selected text must stay readable: `bright_foreground` vs
     `selection` >= 3:1.
   - **Accent + foreground targets**: validator floor is 3:1 vs `background`
     for both; daily-driver targets are foreground >= 10:1 and accent >= 4:1.
5. **Write the final `colors.toml`** into `themes/<slug>/` - the 26-key baseline
   contract (groups in this order):

   ```toml
   mode = "dark"            # or "light"

   accent = "…"
   selection = "…"
   muted = "…"

   background = "…"
   dark_background = "…"
   darker_background = "…"
   lighter_background = "…"

   foreground = "…"
   dark_foreground = "…"
   light_foreground = "…"
   bright_foreground = "…"

   red = "…"
   yellow = "…"
   orange = "…"
   green = "…"
   cyan = "…"
   blue = "…"
   magenta = "…"
   brown = "…"

   bright_red = "…"
   bright_yellow = "…"
   bright_green = "…"
   bright_cyan = "…"
   bright_blue = "…"
   bright_magenta = "…"
   ```

   Hex `#rrggbb` lowercase everywhere; `mode` is the only non-color value.
   The extraction script emits exactly this shape; hand-edits are expected and
   welcome (it refuses to overwrite an existing file without `--force`).
6. **Verify contrast from code, never by eyeball or hand-transcription.** Run
   the contrast report over the final palette:

   ```bash
   python3 skills/omarchy-theme-maker/scripts/contrast_report.py themes/<slug>/colors.toml
   ```

   It prints the full cross-product of text/ink roles (`muted`, foregrounds,
   accent, ANSI colors) against actual surfaces (background ramp + `selection`)
   and exits non-zero if a mandated floor fails. Paste its output into the theme
   README and the PR body - a minimum ratio derived from a partial spot-check
   ships a stale number that independent recomputation later overturns. With
   Omarchy available, cross-check the ramp ordering with
   `omarchy dev theme-preview themes/<slug>/colors.toml --no-osc`.
7. **Backgrounds.** Copy the artwork into `themes/<slug>/backgrounds/` with an
   indexed name (`0-<short-name>.<ext>`) - `omarchy theme set` sorts
   backgrounds and cycles them with `omarchy theme bg next`. Formats:
   jpg/jpeg/png/gif/bmp/webp. Keep each wallpaper <= 8 MB (re-encode at
   quality ~85 JPEG/webp, preserving aspect ratio, if larger). More backgrounds
   can be added later; the index defines cycle order.
8. **Icons.** `themes/<slug>/icons.theme` holds exactly one line naming a stock
   icon set (e.g. `Yaru-red`), paired with the theme's accent. **Verify against
   the install, not intuition**: `ls /usr/share/icons/` and
   `cat /usr/share/omarchy/themes/*/icons.theme` - intuitive names are often
   absent (there is no `Yaru-green`; Omarchy's green stock themes use
   `Yaru-sage`). The defensible choice is what stock themes in the same accent
   family already use.
9. **Preview.** Capture a real desktop session - wallpaper + themed bar +
   themed terminal - at exactly 1800x1012, and never fabricate UI. The capture
   procedure, including the mandatory window-safety protocol, lives in
   [references/preview-capture.md](references/preview-capture.md); the
   compositing fallback (busy desktop, unreliable geometry) lives in
   [references/preview-compositing.md](references/preview-compositing.md).
   Quantize to <= 256 colors; target 300-800 KB.
10. **Theme README.** Write `themes/<slug>/README.md` with the palette table
    and the contrast ratios generated in step 6, plus credits, compatibility,
    and the rights framing from the Licensing section below.
11. **Validate.** From the repo root:

    ```bash
    python3 -m unittest discover -s tests
    python3 scripts/validate.py            # everything
    python3 scripts/validate.py <slug>     # just your theme
    python3 -m py_compile scripts/validate.py
    ```

    Fix until exit 0. CI runs the same commands, so a green local run means a
    green PR check.
12. **Live apply test (when Omarchy is available).**

    ```bash
    cp -r themes/<slug> ~/.config/omarchy/themes/
    omarchy theme set <slug>
    omarchy theme current        # must print the new slug
    omarchy dev theme-preview <slug> --no-osc
    ```

    Revert afterwards with `omarchy theme set <previous-theme>`.
13. **Index + PR.** Add exactly one row to the Themes table in the repo's root
    `README.md`, commit, push, open the PR against `main` with the repo's
    template (contrast ratios listed), watch CI - and **stop**. The maintainer
    merges; agents never merge their own PRs. If a maintainer asks for a rebase
    mid-review: fetch, verify `origin/main` matches the stated SHA, rebase,
    confirm `git diff origin/main...HEAD --name-status` is still exactly the
    intended file set, re-run the gate, push with `--force-with-lease` (never
    plain `--force`), re-verify CI.

## Window-safety protocol (mandatory before ANY Hyprland window operation)

Preview capture tempts agents to move/close "the preview window" with Hyprland
dispatchers. On current Omarchy (quattro), `hyprctl` is a Lua shim, and several
of its window dispatchers act on **the focused window** - not the window you
meant. During two earlier theme builds in this collection, focus-dependent
`window.kill()`/`window.move` calls aimed at a preview terminal closed the
user's live browser instead. These rules are therefore mandatory, not advisory:

1. **Identify the exact target window before acting.** List clients with
   `hyprctl clients -j` and select the window whose address, class/app-id,
   AND title match the terminal you spawned. Give the spawned terminal a
   distinctive app-id at creation (`foot --app-id=theme-preview-<slug>`) and
   record its address/PID at spawn time.
2. **Verify before every operation.** Re-read `hyprctl clients -j` and confirm
   the window you are about to act on still exists, still matches the recorded
   address/class/title, and - for any API that acts on the focused window -
   carries the `focused` flag on that exact address. One stale focus state is
   all it takes.
3. **Prefer explicitly targeted mechanisms over focus-dependent ones:**
   - output-targeted capture (`grim -o <output>`) instead of window capture;
   - workspace-indexed switches (`hl.dsp.focus{workspace=N}`) instead of
     moving windows between workspaces;
   - self-terminating preview terminals (bounded `sleep` in the spawned shell,
     or `SIGTERM`/`SIGKILL` to the exact PID you spawned and recorded) instead
     of `window.kill()`/`window.close()`;
   - window rules registered **before** spawn
     (`hyprctl repl 'local r = hl.window_rule{class=…, size={w,h}, position={x,y}, floating=true} return "ok"'`
     - creating the rule object registers it; rules apply to NEW windows only)
     instead of floating/moving/resizing after the fact.
4. **Never** call a focus-dependent dispatcher (`window.kill`, `window.close`,
   `window.move`, `window.float`, ...) against "whatever is focused" without
   the verification in step 2, and never use a destructive dispatcher when a
   targeted alternative exists.
5. **Stop if the target is ambiguous**: multiple candidate windows, no matching
   client, or a mismatched title/class/address. Do not guess; do not "try it
   and see". Fall back to the compositing recipe instead.
6. **"Restore the user's browser afterward" is not a safety mechanism.**
   Prevent the damage; recovery is not a control. If a capture has already gone
   wrong, verify which clients remain (`hyprctl clients -j`) before making any
   further dispatcher call.

## Hyprland (quattro) facts you will need

- `hyprctl` on current Omarchy is a Lua shim, not the classic dispatcher CLI:
  `hyprctl dispatch <name> <args>` fails with a parse error, and
  `hyprctl keyword windowrule ...` is rejected ("keyword can't work with
  non-legacy parsers. Use eval."). Use `hyprctl repl 'return …'` with the
  `hl.*` Lua API.
- Dispatchers live under `hl.dsp.*`: `window.float()`, `window.center()`,
  `window.close()`, `window.kill()`, `focus{direction=…}`, `workspace.*`.
  **They act on the focused window** - see the safety protocol.
- `hl.dsp.focus{workspace=N}` targets the focused monitor: focus the target
  monitor first (`focus{direction="left"}`), then switch workspace. A newly
  spawned window lands on the focused workspace, so focus the empty workspace
  BEFORE spawning the preview terminal - do not move the window there after
  the fact.
- A window spawned on an empty workspace can come up tiled/maximized despite
  `-w WxH`; a pre-registered floating window rule is the reliable fix.
  `window.resize` may still be refused - when exact geometry control is
  unreliable, do not fight it: capture the terminal full-bleed and composite.

## Licensing, branding, and trademarks

- Only commit images you have the right to redistribute, and **state the source
  and redistribution license** in the theme README and PR body.
- A generated composition can be licensed by its creator/supplier, but that
  grant does **not** magically relicense third-party names, logos, or marks
  embedded in it. If brand assets appear, carve them out explicitly: they stay
  with their respective owners.
- For unofficial tribute themes, say so: no ownership, endorsement,
  sponsorship, or official affiliation claimed.
- A preview derived from a wallpaper carries the same third-party-mark caveats
  as that wallpaper.
- Do not infer or invent licenses for upstream logos/assets. If redistribution
  rights are unclear, stop and resolve them before committing the asset.

## Reference

### Stock themes used for calibration

- Dark: `/usr/share/omarchy/themes/tokyo-night`
- Light: `/usr/share/omarchy/themes/catppuccin-latte`

### Theme structure

```
<theme>/
├── colors.toml        # required
├── backgrounds/       # required (>=1 redistributable indexed image)
├── preview.png        # recommended, 1800x1012
├── icons.theme        # optional, one stock Yaru-* name
└── README.md          # recommended, palette + credits/license
```

### Notes

- Theme slugs: lowercase kebab-case, e.g. `my-theme`.
- Background names: indexed, e.g. `0-main.png`, `1-alt.webp`.
- `palette_to_theme.py` is intentionally conservative and incomplete as an
  aesthetic tool; it is a starting point, never the final authority.
