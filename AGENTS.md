# AGENTS.md

Operating instructions for autonomous coding agents (Hermes, Codex, Copilot, …) working in this repository. Human contributors: see [CONTRIBUTING.md](CONTRIBUTING.md).

## "I was asked to add a new Omarchy theme." Do this.

1. `git checkout -b <theme-slug>` from an up-to-date `main`.
2. Build the theme at `themes/<slug>/` — exact format, palette rules, and preview requirements: [docs/theme-creation.md](docs/theme-creation.md).
3. Run the validator and make it pass: `python3 scripts/validate.py` (exit 0 = pass).
4. Add **one row** to the Themes table in `README.md`.
5. Commit, push the branch, open a PR against `main` using the PR template.
6. **Stop.** Report the PR URL. Do not merge, do not start follow-up work.

## Global hard rules (apply to EVERY task, no exceptions)

- **Never merge your own PR.** `main` is protected; the human maintainer merges after review. Agents open PRs and stop.
- **Never push directly to `main`** and never rewrite or force-push published history.
- **No secrets, credentials, or machine-specific data** (e.g. `/home/<user>` paths) in any committed file. The validator scans tracked files for both.
- **Stay inside the explicitly authorized task scope.** What that scope contains depends on the task type (below). When a needed change falls outside your authorized scope, describe it in the PR description instead of making it.

## Task scope

### Add-a-theme tasks (the default)

Unless the task explicitly says otherwise, you are doing an add-a-theme task. Your owned scope is exactly:

- `themes/<your-slug>/**` — everything inside your theme directory
- **one** new row in the `README.md` Themes table (and fixing that same row if review asks)

Everything else — `.github/`, `scripts/`, `tests/`, `docs/`, other themes, `LICENSE`, other README content — is **not owned by a theme task**. Do not modify those files to accommodate a theme; flag anything they need in the PR description instead.

### Repo-maintenance / review-fix tasks (only when explicitly authorized)

When the maintainer explicitly assigns maintenance (e.g. "fix the review findings on PR #N", "update the validator", "harden CI"), the agent **may modify the specific repo files that task requires** — including `AGENTS.md`, `scripts/`, `tests/`, `.github/`, and `docs/` — and nothing unrelated to that task. Maintenance files are not permanently untouchable; they are protected from *scope creep by theme tasks*, not from *authorized maintenance*.

Rules that still apply: PR-only workflow, no self-merge, no direct pushes to `main`, no unrelated drive-by changes, and the change must be plausibly required by the assigned task.

## Validation — deterministic, no Omarchy required

```bash
python3 -m unittest discover -s tests   # validator regression suite
python3 scripts/validate.py             # all themes + repo-level checks
python3 scripts/validate.py <slug>      # one theme (name under themes/, or a path)
```

CI runs both on every PR. **Definition of done** = tests green + validator exits 0 + the PR template checklist is complete. When a local Omarchy install *is* available, also apply the theme live (`cp -r themes/<slug> ~/.config/omarchy/themes/ && omarchy theme set <slug>`) and verify `omarchy theme current` — but the validator is the required gate.

## Theme format in one screen

```
themes/<kebab-case-slug>/
├── colors.toml        # REQUIRED. 26-key baseline palette; see below for optional Omarchy extensions
├── backgrounds/       # REQUIRED (≥1 redistributable wallpaper). jpg/jpeg/png/gif/bmp/webp, indexed names (0-…)
├── preview.png        # RECOMMENDED. 1800×1012 switcher thumbnail
├── icons.theme         # OPTIONAL. one line, e.g. "Yaru-red"
└── README.md          # RECOMMENDED. palette table + contrast ratios + credits & license
```

This repository's own policy (stricter than upstream, on purpose): ship **color files only** — no `*.lua`, no terminal configs (`alacritty.toml`, `foot.ini`, `ghostty.conf`, `kitty.conf`), no `vscode.json`, and no full `shell.toml` overrides. Note: current Omarchy *keeps* `shell.toml` when installing from a git clone (it drops only code-capable files), and this repo's documented install path is a plain directory copy that Omarchy stages in full trust — so the restriction here is **this collection's safety policy**, not an Omarchy behavior. Section overrides (`shell.<section>.toml`, colour-only) are allowed but only when a theme genuinely needs one.

Palette contract (validator-enforced):

- **Required baseline**: the 26 canonical keys (`mode`, `accent`, `selection`, `muted`, 4 backgrounds, 4 foregrounds, 8 named, 6 bright) — every theme in this collection ships all of them.
- **Optional current-Omarchy extensions** (allowed, format-checked): `hyprland_active_border`, `hyprland_inactive_border` (solid `#rrggbb` or Hyprland gradient `rgba(…) rgba(…) Ndeg`), `active_border_color`, `active_tab_background`, plus legacy short names (`bg`, `fg`, …).
- Anything else is rejected.

Contrast floors (WCAG-computed): `foreground` and `accent` ≥ 3:1 against `background`; aim much higher for daily-driver readability (e.g. foreground ≥ 10:1).

## Naming

- Theme directory/slug: lowercase `kebab-case`, regex `^[a-z0-9][a-z0-9-]*$`, matching the name users type: `omarchy theme set <slug>`.
- Backgrounds: `<index>-<short-name>.<ext>` (e.g. `0-hermes-bloodline.png`) — `omarchy theme set` sorts and cycles them.
- Branches: the theme slug (or a descriptive name for maintenance tasks).

## Hermes agents specifically

Load the `omarchy-theme-maker` skill (`skill_view(name="omarchy-theme-maker")`) and use its script to derive a first-pass palette from the source image, then **hand-tune to the artwork's actual identity** — auto-extraction quantizes dominant pixels and can pick a wrong accent (it once chose green for a red/black poster). Full workflow including preview capture: [docs/theme-creation.md](docs/theme-creation.md).

## When in doubt

The validator is the contract: if `python3 scripts/validate.py` exits 0, the tests pass, and you touched only your authorized scope, you are done. Open the PR and stop.
