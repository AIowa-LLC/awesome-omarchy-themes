# Contributing to Awesome Omarchy Themes

Thanks for contributing! These guidelines supplement the [organization-wide defaults](https://github.com/AIowa-LLC/.github/blob/main/CONTRIBUTING.md). Autonomous coding agents should follow [AGENTS.md](AGENTS.md) instead — it is the operational contract for agent work in this repo.

## Validate before opening a PR

```bash
python3 scripts/validate.py        # all themes + repo checks; exit 0 = ready
```

CI runs the same command on every PR.

## Theme structure

Every theme lives in its own directory under `themes/`:

```
themes/<theme-name>/
├── colors.toml      # required — the palette
├── backgrounds/     # optional — wallpapers cycled with `omarchy theme bg next`
└── preview.png      # optional — thumbnail for the theme switcher
```

Rules:

1. **`colors.toml` is required** and must parse as valid TOML. Follow the key set used by [Omarchy's stock themes](https://github.com/basecamp/omarchy/tree/quattro/usr/share/omarchy/themes) (`mode`, `accent`, `selection`, `muted`, background/foreground ramps, named and bright colors).
2. **`theme-name` must be a lowercase slug** (`kebab-case`), matching the directory name.
3. **Contrast:** keep `foreground` and `accent` at ≥ 3:1 contrast against `background` so text stays readable. If you derived the palette programmatically, note the tool used.
4. **Backgrounds:** keep total theme size reasonable — compress large images before committing. Only include images you have the right to redistribute, and credit the source in the PR description.
5. **No arbitrary app configs** (`shell.toml`, `hyprland.lua`, `neovim.lua`, `vscode.json`) unless the PR is specifically about them. Plain palettes stage cleanly for every user; extra config files have narrower value and more edge cases.

## Before opening a pull request

1. Check existing issues and PRs for related work.
2. Install your theme locally (`cp -r themes/<name> ~/.config/omarchy/themes/`) and verify it applies: `omarchy theme set <name>`, then check `omarchy theme current`.
3. Keep the PR focused — one theme (or one fix) per PR.
4. Never include secrets, credentials, or personal data.

## Pull request expectations

- List the palette's key contrast ratios (foreground and accent vs background).
- Include a screenshot of the applied theme if practical.
- For new backgrounds, state the image source and license.

## Reporting bugs

Open an issue using the Bug report template. Include your Omarchy version (`omarchy version`) and the theme name.
