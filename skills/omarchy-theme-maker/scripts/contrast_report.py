#!/usr/bin/env python3
"""contrast_report.py -- WCAG contrast report for an Omarchy colors.toml.

Computes and prints the full cross-product of every ink color against every
surface color, plus the specifically mandated floors, using WCAG relative
luminance. Exits non-zero when a mandated floor fails, so it can gate CI or a
theme-building agent.

Generate documented numbers from code, never hand-transcribe: a minimum ratio
derived from a partial spot-check ships a stale number that independent
recomputation later overturns. Paste this script's output into the theme
README and the PR body.

Mandated floors (matching awesome-omarchy-themes' validator):
  - foreground  vs background          >= 3:1   (daily-driver target >= 10:1)
  - accent      vs background          >= 3:1   (daily-driver target >=  4:1)
  - bright_foreground vs selection     >= 3:1

Usage:
  contrast_report.py COLORS_TOML [--floor FG ACCENT SEL] [--quiet]

Only stdlib (tomllib) is required. Works on any machine -- no Omarchy needed.
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

SURFACES = [
    "background", "dark_background", "darker_background",
    "lighter_background", "selection", "muted",
]
INKS = [
    "foreground", "dark_foreground", "light_foreground", "bright_foreground",
    "accent", "red", "yellow", "orange", "green", "cyan", "blue",
    "magenta", "brown", "bright_red", "bright_yellow", "bright_green",
    "bright_cyan", "bright_blue", "bright_magenta",
]


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


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Full WCAG contrast cross-product for an Omarchy colors.toml.",
        epilog="Exit 0 = all mandated floors met. Non-zero = a floor failed (or bad input).",
    )
    ap.add_argument("colors", type=Path, help="Path to a colors.toml")
    ap.add_argument("--floor", type=float, nargs=3, metavar=("FG", "ACCENT", "SEL"),
                    default=[3.0, 3.0, 3.0],
                    help="Mandated floors for foreground/accent vs background and "
                         "bright_foreground vs selection (default: 3 3 3)")
    ap.add_argument("--quiet", action="store_true",
                    help="Print only failures and the summary line")
    args = ap.parse_args()

    p = args.colors.expanduser().resolve()
    if not p.is_file():
        sys.exit(f"not a file: {p}")
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"{p} is not valid TOML: {e}")

    missing = [k for k in ["mode", *SURFACES, *INKS] if k not in data]
    if missing:
        sys.exit(f"{p} is missing keys: {', '.join(missing)}")

    fg_floor, acc_floor, sel_floor = args.floor
    failures = 0

    print(f"# contrast report: {p.name} (mode={data['mode']})")
    print()

    mandated = [
        ("foreground vs background", "foreground", "background", fg_floor),
        ("accent vs background", "accent", "background", acc_floor),
        ("bright_foreground vs selection", "bright_foreground", "selection", sel_floor),
    ]
    for label, ink, surf, floor in mandated:
        r = contrast(data[ink], data[surf])
        ok = r >= floor
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label:38s} {r:6.2f}:1  (floor {floor:.0f}:1)")

    print()
    print(f"{'ink':17s} " + " ".join(f"{s[:9]:>9s}" for s in SURFACES))
    minimums: dict[str, float] = {}
    for ink in INKS:
        row = [contrast(data[ink], data[surf]) for surf in SURFACES]
        minimums[ink] = min(row)
        if not args.quiet:
            print(f"{ink:17s} " + " ".join(f"{v:9.2f}" for v in row))

    print()
    print("minimum ratio per ink (across all surfaces):")
    for ink in INKS:
        print(f"  {ink:17s} {minimums[ink]:6.2f}:1")

    print()
    if failures:
        print(f"RESULT: FAIL ({failures} mandated floor(s) not met)")
        return 1
    print("RESULT: PASS (all mandated floors met)")
    return 0


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # die quietly when piped to head/less
    raise SystemExit(main())
