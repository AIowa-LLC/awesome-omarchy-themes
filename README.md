# Awesome Omarchy Themes

A community collection of themes for [Omarchy](https://omarchy.org) — the batteries-included Hyprland desktop from Basecamp.

Each theme is a self-contained directory with a [`colors.toml`](https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md) palette and its own backgrounds, ready to install into `~/.config/omarchy/themes/` and apply with `omarchy theme set`.

## Installing a theme

Omarchy does not ship a remote theme installer yet, so installation is a plain copy:

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
| [`nous-noir`](themes/nous-noir/) | dark | Ink black, graphite, bone white — strict museum-noir monochrome. |

Each theme lists its palette contrast ratios and components in its own README.

## What is in a theme?

A theme directory may contain:

| File | Purpose |
| --- | --- |
| `colors.toml` | The palette. Required — this is the theme. |
| `backgrounds/` | Wallpaper images cycled with `omarchy theme bg next`. |
| `preview.png` | Thumbnail shown in the theme switcher (optional). |

Palettes define `mode`, `accent`, `selection`, `muted`, a `background`/`foreground` ramp, and named colors (`red`, `green`, `blue`, …) plus bright variants. See the [official theming documentation](https://github.com/basecamp/omarchy/blob/quattro/docs/theming.md) for the full key list and staging behavior.

Keep foreground/accent colors at ≥ 3:1 contrast against `background` so terminal and UI text stays readable.

## Contributing

New themes and palette improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the theme structure rules and pull request expectations.

## License

[MIT](LICENSE)
