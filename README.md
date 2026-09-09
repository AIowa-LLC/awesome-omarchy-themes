# Awesome Omarchy Themes

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

Each theme lists its palette contrast ratios and components in its own README.

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
