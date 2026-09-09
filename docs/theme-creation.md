# Theme creation workflow

Everything an agent or human needs to go from "an image and an idea" to a merged theme. For repo-wide rules (branching, PRs, merge policy) see [AGENTS.md](../AGENTS.md); for the human-facing contribution guide see [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. Branch

```bash
git checkout main && git pull && git checkout -b <theme-slug>
```

## 2. Build the theme

Target layout (all paths relative to `themes/<slug>/`):

```
colors.toml        REQUIRED  26 canonical palette keys — the entire theme derives from it
backgrounds/       REQUIRED  ≥1 image; indexed names; see "Asset rules" below
preview.png        RECOMMENDED  1800×1012 thumbnail for the theme switcher
icons.theme        OPTIONAL  exactly one line naming a stock icon set (e.g. Yaru-red)
README.md          RECOMMENDED  palette table, contrast ratios, credits, compatibility
```

Forbidden files (validator rejects): `*.lua`, `alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf`, `vscode.json`, `shell.toml` (full overrides), `.git*`. Omarchy's theme installer filters exactly these for git-installed themes — ship color, not code.

### colors.toml

The 26 canonical keys (groups in this order):

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
- The neutral ramp must be **monotonic by relative luminance**: for dark themes darkest→lightest is `darker_background ≤ dark_background ≤ background ≤ lighter_background ≤ selection ≤ … ≤ bright_foreground` (light themes: reverse). The validator computes WCAG luminances and enforces this.
- `foreground` and `accent` ≥ 3:1 contrast vs `background` (validator floor). Daily-driver target: foreground ≥ 10:1, accent ≥ 4:1.
- Deriving from an image? See "Palette derivation" below.

### Asset rules

- Formats: `jpg` `jpeg` `png` `gif` `bmp` `webp`. Wallpaper supplied as the canonical asset stays as-is unless it exceeds **8 MB** — then re-encode (quality ~85 JPEG or webp) preserving aspect ratio and visual fidelity, and say so in the PR.
- Names: `<index>-<short-name>.<ext>`, index starting at `0` — Omarchy sorts and cycles (`omarchy theme bg next`).
- Only redistributable images. AI-generated art with no third-party claim is fine. State source + license in the PR description. No Hermes/Nous branding unless the maintainer supplies it for the theme.
- `preview.png`: 1800×1012 (stock switcher format), PNG, target 300–800 KB (quantize to ≤256 colors if heavier). Content: wallpaper + themed shell surfaces; never fabricated UI.

## 3. Palette derivation (Hermes)

Use the `omarchy-theme-maker` skill and its `palette_to_theme.py` for the first pass, then review and hand-tune: quantization picks *dominant* pixels, not *identity* colors (it chose green for the red/black Hermes Bloodline poster). Verify the ramp and contrast with `omarchy dev theme-preview <colors.toml> --no-osc` when Omarchy is available; otherwise rely on `scripts/validate.py`, which recomputes the same ratios.

## 4. Preview capture (Omarchy installed)

Capture a real session, not a mockup: empty workspace → themed terminal running `omarchy dev theme-preview` → `grim` screenshot → resize to 1800×1012 → quantize. Keep the user's live windows out of frame. If the desktop is busy, composite the terminal over a wallpaper-only capture (see the skill's preview-capture section). Without Omarchy, defer the preview and note it in the PR.

## 5. Update the index

Add exactly one row to the Themes table in the root `README.md`:

```markdown
| [`<slug>`](themes/<slug>/) | dark | <≤8-word identity description> |
```

## 6. Validate

```bash
python3 scripts/validate.py            # everything
python3 scripts/validate.py <slug>     # just your theme
```

Fix until exit 0. The lints it runs are listed in `scripts/validate.py`'s docstring; CI runs the same command, so a green local run means a green PR check.

## 7. Definition of done

- [ ] `themes/<slug>/` contains `colors.toml` + `backgrounds/` (+ recommended files)
- [ ] `python3 scripts/validate.py` exits 0
- [ ] README Themes table has the new row
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
