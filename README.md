# Awesome Omarchy Themes

![Awesome Omarchy Themes](assets/awesome-omarchy-themes.png)

[![Omarchy](https://img.shields.io/badge/Omarchy-theme%20collection-9ECE6A?style=flat-square)](https://omarchy.org)
[![X: @tonysimons_](https://img.shields.io/badge/X-%40tonysimons__-000000?style=flat-square&logo=x&logoColor=white)](https://x.com/tonysimons_)
[![Fund via X Money](https://img.shields.io/badge/X%20Money-Fund%20the%20project-000000?style=flat-square&logo=x&logoColor=white)](https://x.com/i/money/pay/tonysimons_)
[![validate](https://github.com/AIowa-LLC/awesome-omarchy-themes/actions/workflows/validate.yml/badge.svg)](https://github.com/AIowa-LLC/awesome-omarchy-themes/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

A community collection of themes for [Omarchy](https://omarchy.org) — the batteries-included Hyprland desktop from Basecamp.

Each theme is a self-contained directory with a [`colors.toml`](https://github.com/omacom/omarchy/blob/quattro/docs/theming.md) palette and its own backgrounds, ready to install into `~/.config/omarchy/themes/` and apply with `omarchy theme set`.

## Installing a theme

Omarchy supports remote theme installation (`omarchy theme install <url>`). This collection nevertheless documents and recommends a plain copy of the individual theme directory — which is why the repo enforces its own stricter color-only safety policy: a copied theme directory stages as trusted local content with no upstream filtering.

```bash
git clone https://github.com/AIowa-LLC/awesome-omarchy-themes.git
cd awesome-omarchy-themes

# Copy the theme you want into your user themes directory
cp -r themes/<theme-name> ~/.config/omarchy/themes/

# Apply it
omarchy theme set <theme-name>
```

Revert to a stock theme at any time with `omarchy theme set <stock-theme-name>`.

## Themes

| Theme | Mode | Identity |
| --- | --- | --- |
| [`hermes-bloodline`](themes/hermes-bloodline/) | dark | Deep black, bone white, arterial red — brutalist premium editorial. |
| [`hermtang`](themes/hermtang/) | dark | Black-plum, lavender, hot magenta — cyberpunk street culture. |
| [`nous-noir`](themes/nous-noir/) | dark | Ink black, graphite, bone white — museum-noir near-monochrome. |
| [`portal-vibes`](themes/portal-vibes/) | dark | Deep navy, electric cobalt, crisp white — Nous Portal dashboard. |
| [`green-magic`](themes/green-magic/) | dark | Forest black, luminous emerald, signal red — post-training foundry. |
| [`hermachy`](themes/hermachy/) | light | Porcelain, navy-charcoal, cobalt — architectural Omarchy branding. |
| [`perfect-computer`](themes/perfect-computer/) | dark | Deep navy, Omarchy green, pale blue-white — the malleable agent OS. |
| [`nous-dayshift`](themes/nous-dayshift/) | light | Warm white, graphite, Nous cobalt — daylight community ops. |
| [`roseglass`](themes/roseglass/) | light | Pearl, wine ink, rose glass — soft power, hard systems. |
| [`codexy`](themes/codexy/) | light | Porcelain, deep ink, Codex blue — parallel agent build lab. |
| [`claudey`](themes/claudey/) | light | Warm ivory, deep ink, terracotta — computational research atelier. |
| [`tonarchy`](themes/tonarchy/) | light | Marble white, deep ink, signal red, gold — luxury Hermes chaos. |

Each theme lists its palette contrast ratios and components in its own README.

## Build Your Own Theme

This repo ships the same [Omarchy Theme Maker](skills/omarchy-theme-maker/) workflow that created the collection — palette extraction from source artwork, hand-tuning, WCAG contrast checks, real preview capture, and the validator-gated PR flow. Hand [`skills/omarchy-theme-maker/SKILL.md`](skills/omarchy-theme-maker/SKILL.md) to your coding agent, or follow it manually; see the skill's [README](skills/omarchy-theme-maker/README.md) for the friendly overview.

## What is in a theme?

A theme directory may contain:

| File | Purpose |
| --- | --- |
| `colors.toml` | Required. 26-key baseline palette (optional current-Omarchy extensions allowed). Every shell surface, terminal, editor, and app theme generates from it. |
| `backgrounds/` | Required. ≥1 redistributable wallpaper; cycled with `omarchy theme bg next`. |
| `preview.png` | Optional. Thumbnail for the theme switcher (1800×1012). |

Palettes define `mode`, `accent`, `selection`, `muted`, a `background`/`foreground` ramp, and named colors (`red`, `green`, `blue`, …) plus bright variants. See the [official theming documentation](https://github.com/omacom/omarchy/blob/quattro/docs/theming.md) for the full key list and staging behavior.

Keep foreground/accent colors at ≥ 3:1 contrast against `background` so terminal and UI text stays readable.

## Contributing

New themes and palette improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the theme structure rules and pull request expectations.

## License

[MIT](LICENSE)

Banner artwork (`assets/awesome-omarchy-themes.png`): original composition supplied by the repository owner; the Omarchy name and logos, the Arch Linux and Tux marks, and any other brand elements it depicts remain subject to their respective owners' rights — this is an unofficial community project with no endorsement or affiliation claimed.
