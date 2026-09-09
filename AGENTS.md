# AGENTS.md

Operating instructions for autonomous coding agents (Hermes, Codex, Copilot, …) working in this repository. Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md).

## "I was asked to add a new Omarchy theme." Do this.

1. `git checkout -b <theme-slug>` from an up-to-date `main`.
2. Build the theme at `themes/<slug>/` — exact format, palette rules, and preview requirements: [docs/theme-creation.md](docs/theme-creation.md).
3. Run the validator and make it pass: `python3 scripts/validate.py` (exit 0 = pass).
4. Add **one row** to the Themes table in `README.md`.
5. Commit, push the branch, open a PR against `main` using the PR template.
6. **Stop.** Report the PR URL. Do not merge, do not start follow-up work.

## Hard rules

- **Never merge your own PR.** `main` is protected; the human maintainer merges after review. Agents open PRs and stop.
- **Never push to `main`** or rewrite published history.
- **Touch only what the task owns**: `themes/<your-slug>/**` and the one new row in `README.md`'s Themes table. Everything else — `.github/`, `scripts/`, docs, other themes, `LICENSE` — is read-only. If a change there seems required, describe it in the PR description instead of making it.
- **No secrets, credentials, or machine-specific paths** (e.g. `/home/<user>`) in any committed file. The validator scans for this.
- **Assets must be redistributable.** Only commit images the repo may publish; state source and license in the PR. No Hermes/Nous Research branded artwork unless the maintainer supplies it for a specific theme.

## Validation — deterministic, no Omarchy required

```bash
python3 scripts/validate.py              # all themes + repo-level checks
python3 scripts/validate.py <slug>       # one theme (name under themes/, or a path)
```

CI runs the same command on every PR. **Definition of done** = validator exits 0 + the PR template checklist is complete. When a local Omarchy install *is* available, also apply the theme live (`cp -r themes/<slug> ~/.config/omarchy/themes/ && omarchy theme set <slug>`) and verify `omarchy theme current` — but the validator is the required gate.

## Theme format in one screen

```
themes/<kebab-case-slug>/
├── colors.toml        # REQUIRED. 26 canonical keys; the whole theme derives from it
├── backgrounds/       # REQUIRED (≥1). jpg/jpeg/png/gif/bmp/webp, indexed names (0-…)
├── preview.png        # RECOMMENDED. 1800×1012 switcher thumbnail
├── icons.theme        # OPTIONAL. one line, e.g. "Yaru-red"
└── README.md          # RECOMMENDED. palette table + contrast ratios + credits
```

Ship **color files only** — no `*.lua`, no terminal configs (`alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf`), no `vscode.json`. Omarchy drops those at staging when a theme comes from a git checkout, and this repo rejects them outright (validator enforces).

Palette floors (validator enforces, WCAG-computed): `foreground` and `accent` ≥ 3:1 against `background`; aim much higher for daily-driver readability (e.g. foreground ≥ 10:1).

## Naming

- Theme directory/slug: lowercase `kebab-case`, `^[[a-z0-9][a-z0-9-]*$`, matches the name users type: `omarchy theme set <slug>`.
- Backgrounds: `<index>-<short-name>.<ext>` (e.g. `0-hermes-bloodline.png`) — `omarchy theme set` sorts and cycles them.
- Branches: the theme slug (or `agent-<slug>` for non-theme changes).

## Hermes agents specifically

Load the `omarchy-theme-maker` skill (`skill_view(name="omarchy-theme-maker")`) and use its script to derive a first-pass palette from the source image, then **hand-tune to the artwork's actual identity** — auto-extraction quantizes dominant pixels and can pick a wrong accent (it once chose green for a red/black poster). Full workflow including preview capture: [docs/theme-creation.md](docs/theme-creation.md).

## When in doubt

The validator is the contract: if `python3 scripts/validate.py` exits 0 and you touched only your theme dir + the README table row, you are done. Open the PR and stop.
