# Omarchy Theme Maker (skill)

The same theme-building workflow used to create the themes in
[awesome-omarchy-themes](../../) — published as a reusable skill so any agent
or human can build a theme the same way.

**[SKILL.md](SKILL.md) is the operational source of truth.** This README is
the friendly overview for GitHub visitors.

## What it does

From one piece of source artwork (wallpaper, photo, poster, brand asset), the
skill produces a complete, validator-clean Omarchy theme:

1. **Inspect the artwork** — visual identity, brand colors, dark/light reading.
2. **Extract a first-pass palette** — dominant colors via median-cut
   quantization, neutral ramp, auto contrast adjustment.
3. **Hand-tune** to the artwork's actual identity — the step that separates a
   generated palette from a real theme.
4. **Verify contrast from code** — full WCAG cross-product
   (ink × surface) with mandated floors.
5. **Assemble the theme** — `colors.toml` (26-key baseline), indexed
   backgrounds, `icons.theme` (verified against your install), theme README
   with palette table and contrast ratios.
6. **Capture a real preview** — genuine `grim` capture of the applied theme at
   1800×1012 (with a strict window-safety protocol), never fabricated UI.
7. **Validate & PR** — repo validator + unit tests, then a PR-only
   contribution flow (agents never merge).

## Prerequisites

| Need | For | Check |
| --- | --- | --- |
| Omarchy | live apply, `omarchy dev theme-preview`, preview capture | `omarchy version` |
| Python 3.10+ + Pillow | palette extraction | `python3 -c "import PIL"` |
| Python 3.11+ | contrast report (stdlib `tomllib`) | `python3 --version` |
| `grim`, `foot` | preview capture (both ship with Omarchy) | `command -v grim foot` |

Everything works without Omarchy except the live-apply/preview steps — CI
validates themes on a stock runner.

## Files

| File | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | The workflow (agent-oriented source of truth) |
| [references/preview-capture.md](references/preview-capture.md) | Real-capture recipe + mandatory window-safety protocol |
| [references/preview-compositing.md](references/preview-compositing.md) | Composite fallback for busy desktops / unreliable geometry |
| [scripts/palette_to_theme.py](scripts/palette_to_theme.py) | First-pass palette generator (image → draft `colors.toml` + background) |
| [scripts/contrast_report.py](scripts/contrast_report.py) | Full WCAG ink × surface contrast report with mandated floors |

## How Hermes users load it

If you have the skill installed in Hermes, load it with:

```
skill_view(name="omarchy-theme-maker")
```

and resolve its scripts under the skill's install directory (default profile:
`~/.hermes/skills/...`; named profiles:
`~/.hermes/profiles/<profile>/skills/...`). This repository copy is the
canonical public reference implementation; when working inside this repo,
prefer it if the two ever differ.

## How another coding agent consumes it

Read `SKILL.md` top to bottom, plus the two `references/` files when you
reach the preview step. Run the scripts with `python3`; each supports
`--help`, fails loudly rather than guessing, and performs no destructive
desktop actions. Follow the window-safety protocol in `SKILL.md` before any
Hyprland window operation — it is mandatory, not advisory.

## How a human follows it manually

Work through `SKILL.md`'s numbered Procedure as a checklist: inspect →
extract → hand-tune → verify → assemble → preview → validate → PR. The two
scripts are ordinary CLIs:

```bash
# Draft palette from artwork (writes themes/<slug>/ or ~/.config/omarchy/themes/<slug>/)
python3 skills/omarchy-theme-maker/scripts/palette_to_theme.py artwork.png --name "My Theme" --out themes

# Full contrast cross-product over the final palette
python3 skills/omarchy-theme-maker/scripts/contrast_report.py themes/my-theme/colors.toml
```

The contrast report follows this repo's validator semantics: surfaces are the
background ramp plus `selection`; text/ink roles include `muted`, the foreground
ladder, accent, and all ANSI colors. That makes muted/background and ANSI/surface
ratios directly usable in a theme README instead of treating `muted` as a
surface and omitting its text contrast.

## Running validation

```bash
python3 -m unittest discover -s tests        # validator regression suite
python3 scripts/validate.py                  # all themes + repo-level checks
python3 scripts/validate.py <slug>           # one theme
python3 -m py_compile scripts/validate.py
```

CI runs the same gate on every PR.

## License

[MIT](../../LICENSE), same as the repository. All files in this skill are
original to this repository. The two scripts are self-contained Python
(stdlib + optional Pillow) with no third-party material embedded.
