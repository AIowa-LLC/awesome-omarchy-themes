# Contributing to Awesome Omarchy Themes

Thanks for contributing! These guidelines supplement the [organization-wide defaults](https://github.com/AIowa-LLC/.github/blob/main/CONTRIBUTING.md). Autonomous coding agents should follow [AGENTS.md](AGENTS.md) instead; it is the operational contract for agent work in this repo.

## Validate before opening a PR

Install the pinned validator dependency once, then run the same required gate CI runs on every PR:

```bash
python3 -m pip install -r requirements-validator.txt
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
```

Both the regression suite and the repository validator must pass.

## Theme structure

Every theme lives in its own directory under `themes/`:

```
themes/<theme-name>/
├── colors.toml      # required - the palette
├── backgrounds/     # REQUIRED - >=1 redistributable wallpaper; cycled with `omarchy theme bg next`
└── preview.png      # optional - thumbnail for the theme switcher
```

Rules:

1. **`colors.toml` is required** and must parse as valid TOML. Follow the required 26-key baseline this collection mandates (matching [Omarchy's stock themes](https://github.com/omacom/omarchy/tree/quattro/usr/share/omarchy/themes): `mode`, `accent`, `selection`, `muted`, background/foreground ramps, named and bright colors), plus optionally the current-Omarchy extension keys (`hyprland_active_border` etc.) documented in [docs/theme-creation.md](docs/theme-creation.md).
2. **`theme-name` must be a lowercase slug** (`kebab-case`), matching the directory name.
3. **Contrast:** keep `foreground` and `accent` at >= 3:1 contrast against `background` so text stays readable. If you derived the palette programmatically, note the tool used. Want help generating a compliant palette from your artwork? This repo ships the [Omarchy Theme Maker skill](skills/omarchy-theme-maker/); hand [`skills/omarchy-theme-maker/SKILL.md`](skills/omarchy-theme-maker/SKILL.md) to your coding agent or follow it manually.
4. **Backgrounds:** every theme ships **at least one** redistributable wallpaper (`backgrounds/` is required, not optional). Keep total theme size reasonable; images larger than 8 MB fail validation. Only include images you have the right to redistribute, and state the source **and redistribution license** in the theme README and PR description.
5. **No executable/config files:** no `.lua`, terminal configs (`alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf`), or `vscode.json` at all, and no full `shell.toml` overrides. Current Omarchy keeps colour files like `shell.toml` even from git installs; this stricter rule is **this collection's** safety policy because our documented install path is a plain directory copy that Omarchy stages in full trust. Colour-only section overrides (`shell.<section>.toml`) are allowed when a theme genuinely needs one.

## Before opening a pull request

1. Check existing issues and PRs for related work.
2. Install your theme locally (`cp -r themes/<name> ~/.config/omarchy/themes/`) and verify it applies: `omarchy theme set <name>`, then check `omarchy theme current`.
3. For a new theme, add exactly one row to the matching **Dark themes** or **Light themes** table in the root `README.md`.
4. Keep the PR focused: one theme or one fix per PR.
5. Never include secrets, credentials, or personal data.
6. Run the full validation gate above immediately before pushing the final revision.

## Pull request expectations

For every PR:

- keep the diff scoped to the stated change
- make both required validation commands pass
- explain any intentional deviation from repository conventions

For theme PRs specifically:

- list the palette's key contrast ratios (foreground and accent vs background)
- include a screenshot of the applied theme if practical
- for new backgrounds, state the image source and redistribution license
- mark theme-only checklist items as N/A on maintenance/docs PRs rather than inventing values

## Reporting bugs

Open an issue using the Bug report template. Include your Omarchy version (`omarchy version`) and the theme name. Suspected security vulnerabilities should be reported privately according to [SECURITY.md](SECURITY.md), not through a public issue.
