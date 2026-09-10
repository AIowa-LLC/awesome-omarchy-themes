# Theme creation workflow

Everything an agent or human needs to go from "an image and an idea" to a merged theme. For repo-wide rules (branching, PRs, merge policy) see [AGENTS.md](../AGENTS.md); for the human-facing contribution guide see [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. Branch

```bash
git checkout main && git pull && git checkout -b <theme-slug>
```

## 2. Build the theme

Target layout (all paths relative to `themes/<slug>/`):

```
colors.toml        REQUIRED  26-key baseline palette (optional current-Omarchy extensions allowed; see below)
backgrounds/       REQUIRED  >=1 image; indexed names; see "Asset rules" below
preview.png        RECOMMENDED  1800x1012 thumbnail for the theme switcher
icons.theme        OPTIONAL  exactly one line naming a stock icon set (e.g. Yaru-red)
README.md          RECOMMENDED  palette table, contrast ratios, credits, compatibility
```

Forbidden files (validator rejects): `*.lua`, `alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf`, `vscode.json`, `shell.toml` (full overrides), `.git*`. Clarification on who forbids what: **current Omarchy** drops only the code-capable files (`*.lua`, the four terminal configs, `vscode.json`) and *keeps* colour files including `shell.toml` when a theme is installed via `omarchy theme install` (git clone). **This repository** forbids the full list above as its own safety policy, because our documented install path is a plain directory copy, which Omarchy stages in full trust with no filtering. Section overrides (`shell.<section>.toml`, colour-only) are allowed when a theme genuinely needs one.

### colors.toml

The 26-key required baseline (groups in this order):

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

Rules:
- Hex `#rrggbb` lowercase everywhere; `mode` is the only non-color value.
- The neutral ramp must be **monotonic by relative luminance** for dark themes: darkest to lightest is `darker_background <= dark_background <= background <= lighter_background <= selection <= … <= bright_foreground`. The validator computes WCAG luminances and enforces this.
- **Light themes** are validated by luminance **relationships**, not key order (matching current Omarchy stock light themes, which do not share one fixed ordering; `omarchy dev theme-preview` sorts neutrals by luminance): `background` must be the lightest surface stop, `muted` must sit between the surfaces and the primary foregrounds, and `foreground`/`bright_foreground` must be darker than every surface. Check your palette with `omarchy dev theme-preview`; its "Neutral ramp (lightest -> darkest)" listing should show your stops in a sensible falling order.
- `foreground` and `accent` >= 3:1 contrast vs `background` (validator floor). Daily-driver target: foreground >= 10:1, accent >= 4:1.
- Deriving from an image? See "Palette derivation" below.

**Optional current-Omarchy extensions** (allowed in addition to the baseline; the validator format-checks them):

```toml
hyprland_active_border   = "rgba(da2b47ee) rgba(ece7ddee) 45deg"  # or solid #rrggbb
hyprland_inactive_border = "#26161a"
active_border_color      = "#da2b47"
active_tab_background    = "#1b1215"
```

These are keys current Omarchy (quattro) stock themes use for richer border/surface values; the gradient-capable pair accepts a Hyprland gradient string. Legacy short names (`bg`, `fg`, `dark_bg`, etc.) also remain valid upstream. Any key outside the baseline + this supported set is rejected; it is a policy of this collection to keep palettes within what upstream actually consumes.

### Asset rules

- **`backgrounds/` is required**: every theme in this collection ships at least one redistributable wallpaper (`0-…`). Formats: `jpg` `jpeg` `png` `gif` `bmp` `webp`. Wallpaper supplied as the canonical asset stays as-is unless it exceeds **8 MB**; then re-encode (quality ~85 JPEG or webp) preserving aspect ratio and visual fidelity, and say so in the PR.
- Names: `<index>-<short-name>.<ext>`, index starting at `0`; Omarchy sorts and cycles them with `omarchy theme bg next`.
- Only redistributable images, with **source + redistribution license stated** in the theme README and PR. AI-generated art with no third-party claim is fine (CC0 dedication by the supplier is this repo's default). No Hermes/Nous branding unless the maintainer supplies it for the theme.
- The validator verifies wallpapers are real, complete images (signature, dimensions, truncation, extension match); a corrupt or mislabeled file fails the gate.
- `preview.png`: 1800x1012 (stock switcher format), complete valid PNG, target 300-800 KB (quantize to <=256 colors if heavier). Content: wallpaper + themed shell surfaces; never fabricated UI.

## 3. Palette derivation

Derive the first pass with the repository's own [Omarchy Theme Maker skill](../skills/omarchy-theme-maker/SKILL.md) (`scripts/palette_to_theme.py`; see the skill's [README](../skills/omarchy-theme-maker/README.md) for prerequisites), then review and hand-tune. Quantization picks *dominant* pixels, not *identity* colors; it chose green for the red/black Hermes Bloodline poster. Hermes users can load the installed skill (`skill_view(name="omarchy-theme-maker")`) instead of reading the repo copy; the workflow is identical. Verify the ramp and contrast with `omarchy dev theme-preview <colors.toml> --no-osc` when Omarchy is available; otherwise rely on `scripts/validate.py`, which recomputes the same ratios, and on the skill's `contrast_report.py` for the full ink x surface cross-product.

## 4. Preview capture (Omarchy installed)

Capture a real session, not a mockup: empty workspace -> themed terminal running `omarchy dev theme-preview` -> `grim` screenshot -> resize to 1800x1012 -> quantize. Keep the user's live windows out of frame. If the desktop is busy, composite the terminal over a wallpaper-only capture (see the skill's preview-capture section). Without Omarchy, defer the preview and note it in the PR.

## 5. Update the index

Add exactly one row to the matching **Dark themes** or **Light themes** table in the root `README.md`:

```markdown
| [`<slug>`](themes/<slug>/) | dark | <short identity description> |
```

Use `light` in the mode column for light themes. Do not add a second index elsewhere; the validator requires exactly one README row per theme directory.

## 6. Validate

Install the pinned dependency once if needed, then run the required gate from the repository root:

```bash
python3 -m pip install -r requirements-validator.txt
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
```

For faster iteration on one theme, `python3 scripts/validate.py <slug>` is useful, but it does **not** replace the full gate before a PR. CI runs the regression suite and the full repository validator on every PR.

## 7. Definition of done

- [ ] `themes/<slug>/` contains `colors.toml` + `backgrounds/` (+ recommended files)
- [ ] `python3 -m unittest discover -s tests -v` passes
- [ ] `python3 scripts/validate.py` exits 0
- [ ] README Themes index has exactly one row under the correct dark/light group
- [ ] Branch pushed, PR opened against `main` with the template checklist filled
- [ ] Contrast ratios listed in the PR (validator prints them)
- [ ] **Agent stops here.** No merge, no follow-on work without instruction.

## 8. Verification with a live Omarchy (optional, when available)

```bash
cp -r themes/<slug> ~/.config/omarchy/themes/
omarchy theme set <slug>
omarchy theme current                       # must print the theme name
omarchy dev theme-preview <slug> --no-osc    # ramp + contrast readout
```

Revert with `omarchy theme set <previous-theme>`.
