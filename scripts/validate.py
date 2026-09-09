#!/usr/bin/env python3
"""Theme and repository validator for awesome-omarchy-themes.

Deterministic gate for theme PRs. stdlib-only; no Omarchy install required.
Exit 0 = pass. CI runs this same file on every PR.

Theme-level checks (per themes/<slug>/):
  structure   colors.toml present; backgrounds/ with >=1 image; no forbidden
              files (*.lua, terminal configs, vscode.json, shell.toml, .git*)
  palette     26 canonical keys exactly; #rrggbb lowercase; mode dark|light
  contrast    foreground and accent >= 3:1 vs background (WCAG relative
              luminance); ramp monotonic by luminance in the mode's direction
  assets      background formats jpg/jpeg/png/gif/bmp/webp; indexed names
              (N-name.ext); wallpaper <= 8 MB; preview.png 1800x1012 PNG if
              present
Repo-level checks:
  index       every themes/<slug>/ has exactly one matching row in README.md's
              Themes table (and no orphan rows)
  hygiene     no machine-specific paths (/home/<user>, /Users/<user>) and no
              obvious secret patterns in committed text files
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEMES = REPO / "themes"

CANONICAL_KEYS = [
    "mode", "accent", "selection", "muted",
    "background", "dark_background", "darker_background", "lighter_background",
    "foreground", "dark_foreground", "light_foreground", "bright_foreground",
    "red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown",
    "bright_red", "bright_yellow", "bright_green", "bright_cyan",
    "bright_blue", "bright_magenta",
]
RAMP = [
    "darker_background", "dark_background", "background",
    "lighter_background", "selection",
]
FG_LADDER = ["muted", "dark_foreground", "foreground", "light_foreground", "bright_foreground"]
BG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
FORBIDDEN = re.compile(
    r"^(.*\.lua|alacritty\.toml|foot\.ini|ghostty\.conf|kitty\.conf|vscode\.json|shell\.toml|\.git.*)$"
)
INDEXED = re.compile(r"^[0-9]+-[a-z0-9-]+\.(jpg|jpeg|png|gif|bmp|webp)$")
HEX = re.compile(r"^#[0-9a-f]{6}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECRET = re.compile(
    r"(api[_-]?key|sk-[a-z0-9]{20}|ghp_[A-Za-z0-9]|gho_[A-Za-z0-9]|AKIA[0-9A-Z]{16}|xox[baprs]-)"
)
MACHINE_PATH = re.compile(r"(/home/[a-z][a-z0-9_-]*/|/Users/[a-z][a-z0-9_-]*/)")


class Report:
    def __init__(self, name: str) -> None:
        self.name = name
        self.errors: list[str] = []
        self.notes: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def srgb_to_lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexcol: str) -> float:
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def validate_theme(theme_dir: Path, slug: str) -> Report:
    rep = Report(f"theme:{slug}")

    # -- structure ----------------------------------------------------------
    colors = theme_dir / "colors.toml"
    if not colors.is_file():
        rep.error("missing colors.toml")
        return rep

    try:
        data = tomllib.loads(colors.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        rep.error(f"colors.toml is not valid TOML: {e}")
        return rep

    bgdir = theme_dir / "backgrounds"
    if not bgdir.is_dir() or not any(bgdir.iterdir()):
        rep.error("backgrounds/ missing or empty (>=1 wallpaper required)")

    if not SLUG.fullmatch(slug):
        rep.error(f"directory name '{slug}' is not a lowercase kebab-case slug")

    for p in theme_dir.rglob("*"):
        rel = p.relative_to(theme_dir).as_posix()
        if FORBIDDEN.fullmatch(rel) or FORBIDDEN.fullmatch(p.name):
            rep.error(f"forbidden file for a git-distributed theme: {rel}")
        if p.is_symlink():
            rep.error(f"symlinks are dropped by Omarchy at staging: {rel}")

    # -- palette ------------------------------------------------------------
    missing = [k for k in CANONICAL_KEYS if k not in data]
    extra = [k for k in data if k not in CANONICAL_KEYS]
    if missing:
        rep.error(f"colors.toml missing keys: {', '.join(missing)}")
    if extra:
        rep.error(f"colors.toml has non-canonical keys: {', '.join(extra)}")
    if missing:
        return rep

    mode = data["mode"]
    if mode not in ("dark", "light"):
        rep.error(f"mode must be 'dark' or 'light', got {mode!r}")

    for k, v in data.items():
        if k == "mode":
            continue
        if not isinstance(v, str) or not HEX.fullmatch(v):
            rep.error(f"{k}: expected lowercase #rrggbb, got {v!r}")

    if rep.errors:
        return rep

    # -- contrast -----------------------------------------------------------
    fg_r = contrast(data["foreground"], data["background"])
    acc_r = contrast(data["accent"], data["background"])
    if fg_r < 3.0:
        rep.error(f"foreground contrast {fg_r:.2f}:1 < 3:1")
    if acc_r < 3.0:
        rep.error(f"accent contrast {acc_r:.2f}:1 < 3:1")
    rep.note(f"foreground {fg_r:.2f}:1, accent {acc_r:.2f}:1 vs background")

    order = RAMP + FG_LADDER
    lums = {k: luminance(data[k]) for k in order}
    seq = [lums[k] for k in order]
    if mode == "dark" and any(b < a for a, b in zip(seq, seq[1:])):
        rep.error("neutral ramp not monotonic (dark: must rise darker_background -> bright_foreground)")
    if mode == "light" and any(b > a for a, b in zip(seq, seq[1:])):
        rep.error("neutral ramp not monotonic (light: must fall darker_background -> bright_foreground)")

    sel_r = contrast(data["bright_foreground"], data["selection"])
    if sel_r < 3.0:
        rep.error(f"selected-text contrast (bright_foreground vs selection) {sel_r:.2f}:1 < 3:1")

    # -- assets -------------------------------------------------------------
    if bgdir.is_dir():
        for p in sorted(bgdir.iterdir()):
            if not INDEXED.fullmatch(p.name):
                rep.error(f"background name must be N-short-name.ext: {p.name}")
            if p.suffix.lower() not in BG_EXTS:
                rep.error(f"background format not allowed: {p.name}")
            if p.stat().st_size > 8 * 1024 * 1024:
                rep.error(f"background exceeds 8 MB: {p.name} ({p.stat().st_size // 1024} KB)")

    preview = theme_dir / "preview.png"
    if preview.is_file():
        size = preview.stat().st_size
        if size > 2 * 1024 * 1024:
            rep.error(f"preview.png exceeds 2 MB ({size // 1024} KB); quantize to <=256 colors")
        with preview.open("rb") as fh:
            head = fh.read(33)
        if not (head.startswith(b"\x89PNG\r\n\x1a\n")):
            rep.error("preview.png is not a PNG")
        elif size > 24 and head[12:16] == b"IHDR":
            w = int.from_bytes(head[16:20], "big")
            h = int.from_bytes(head[20:24], "big")
            if (w, h) != (1800, 1012):
                rep.error(f"preview.png must be 1800x1012, got {w}x{h}")

    return rep


def validate_repo() -> Report:
    rep = Report("repo")

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    m = re.search(r"## Themes\n\n\|(?:.*\n)+?", readme)
    table_rows = re.findall(r"^\| \[`([a-z0-9-]+)`\]", readme, re.M)

    themes = sorted(p.name for p in THEMES.iterdir() if p.is_dir()) if THEMES.is_dir() else []
    for slug in themes:
        if slug not in table_rows:
            rep.error(f"README Themes table missing row for '{slug}'")
    for slug in table_rows:
        if slug not in themes:
            rep.error(f"README Themes table has row for unknown theme '{slug}'")
    if themes and not m:
        rep.error("README.md is missing the Themes table section")

    if not table_rows and not themes:
        rep.note("no themes yet")

    # hygiene scan over text files, skipping binaries by extension
    text_ext = {".md", ".toml", ".py", ".yml", ".yaml", ".gitignore", ".editorconfig", ".theme"}
    for p in REPO.rglob("*"):
        if not p.is_file() or ".git/" in p.as_posix():
            continue
        if p.suffix.lower() not in text_ext and p.name not in (".gitignore", ".editorconfig", "LICENSE"):
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        rel = p.relative_to(REPO).as_posix()
        for match in SECRET.finditer(content):
            rep.error(f"possible secret in {rel}: {match.group(0)[:12]}…")
        for match in MACHINE_PATH.finditer(content):
            rep.error(f"machine-specific path in {rel}: {match.group(0)}")

    return rep


def main() -> int:
    if not THEMES.is_dir():
        THEMES.mkdir(exist_ok=True)  # tolerate repos predating the first theme

    targets = sys.argv[1:]
    if targets:
        reports = []
        for t in targets:
            p = Path(t) if "/" in t else THEMES / t
            if not p.is_dir():
                reports.append(Report(f"theme:{t}"))
                reports[-1].error("theme directory not found")
                continue
            reports.append(validate_theme(p, p.name))
    else:
        reports = [validate_theme(d, d.name) for d in sorted(THEMES.iterdir()) if d.is_dir()]
        reports.append(validate_repo())

    failed = False
    for rep in reports:
        for note in rep.notes:
            print(f"  [{rep.name}] {note}")
        if rep.ok:
            print(f"PASS {rep.name}")
        else:
            failed = True
            for e in rep.errors:
                print(f"FAIL {rep.name}: {e}", file=sys.stdout)

    total = len(reports)
    passed = sum(1 for r in reports if r.ok)
    print(f"\n{passed}/{total} passed" + ("" if not failed else " — fix the failures above"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
