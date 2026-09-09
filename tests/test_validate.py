"""Committed regression tests for scripts/validate.py.

Run: python3 -m unittest discover   (from the repository root)

Stdlib unittest only. Fixtures are built in tmp dirs from a known-good
baseline palette (the integrated hermes-bloodline values), so the real
theme tree is never touched.
"""

from __future__ import annotations

import importlib.util
import struct
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATOR = REPO / "scripts" / "validate.py"

_spec = importlib.util.spec_from_file_location("validate", VALIDATOR)
validate = importlib.util.module_from_spec(_spec)
sys.modules["validate"] = validate
_spec.loader.exec_module(validate)

# Known-good baseline: the merged hermes-bloodline palette.
BASELINE = {
    "mode": "dark",
    "accent": "#da2b47", "selection": "#26161a", "muted": "#8a7d7b",
    "background": "#0a0a0a", "dark_background": "#070707",
    "darker_background": "#040404", "lighter_background": "#1b1215",
    "foreground": "#ece7dd", "dark_foreground": "#9a8f89",
    "light_foreground": "#f4f0e8", "bright_foreground": "#fffdf9",
    "red": "#d92646", "yellow": "#d9b25f", "orange": "#d98359",
    "green": "#97b380", "cyan": "#6db3a8", "blue": "#8ca3c7",
    "magenta": "#b48eb4", "brown": "#a17963",
    "bright_red": "#ee4d66", "bright_yellow": "#e8c684",
    "bright_green": "#b3cc9c", "bright_cyan": "#93ccc3",
    "bright_blue": "#adc0dd", "bright_magenta": "#cdb0cd",
}


def png_bytes(width: int, height: int, *, complete: bool = True, bad_crc: bool = False) -> bytes:
    """Minimal structurally-valid PNG (or deliberately broken)."""
    def chunk(ctype: bytes, data: bytes, corrupt: bool = False) -> bytes:
        crc = (zlib.crc32(ctype + data) & 0xFFFFFFFF) ^ (1 if corrupt else 0)
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    iend = chunk(b"IEND", b"")
    body = b"\x89PNG\r\n\x1a\n" + ihdr + iend
    if bad_crc:
        ihdr_bad = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0), corrupt=True)
        body = b"\x89PNG\r\n\x1a\n" + ihdr_bad + iend
    if not complete:
        body = b"\x89PNG\r\n\x1a\n" + ihdr  # header only, no IEND
    return body


def jpeg_bytes(width: int, height: int) -> bytes:
    """Minimal JPEG: SOI + APP0 + SOF0 with dimensions + EOI."""
    sof = struct.pack(">HH", height, width) + b"\x03\x01\x11\x00"
    parts = [
        b"\xff\xd8",                                        # SOI
        b"\xff\xc0" + struct.pack(">H", 2 + len(sof)) + sof,  # SOF0
        b"\xff\xd9",                                        # EOI
    ]
    return b"".join(parts)


def make_theme(root: Path, slug: str = "test-theme", palette: dict | None = None,
               bg_name: str = "0-x.png", bg_bytes: bytes | None = None,
               files: dict[str, bytes | str] | None = None, bg_files: list[tuple[str, bytes]] | None = None) -> Path:
    d = root / "themes" / slug
    (d / "backgrounds").mkdir(parents=True)
    data = dict(BASELINE)
    if palette:
        for k, v in palette.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
    lines = [f'{k} = "{v}"' for k, v in data.items()]
    (d / "colors.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if bg_name is not None:
        (d / "backgrounds" / bg_name).write_bytes(bg_bytes if bg_bytes is not None else png_bytes(100, 100))
    for name, content in (files or {}).items():
        target = d / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
    for name, content in (bg_files or []):
        (d / "backgrounds" / name).write_bytes(content)
    return d


def errors_of(rep) -> list[str]:
    return rep.errors


def git_repo_with_theme(tmp: Path, theme_slug: str = "test-theme") -> Path:
    """Create a real git repo (for tracked-file hygiene tests)."""
    def run(*cmd):
        subprocess.run(cmd, cwd=tmp, check=True, capture_output=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "T")
    (tmp / "README.md").write_text(
        "# R\n\n## Themes\n\n| Theme | Mode | Identity |\n| --- | --- | --- |\n"
        f"| [`{theme_slug}`](themes/{theme_slug}/) | dark | test |\n", encoding="utf-8")
    (tmp / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "init")
    return tmp


class ThemeValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def rep(self, d: Path):
        return validate.validate_theme(d, d.name)

    # -- passing baseline ---------------------------------------------------
    def test_baseline_passes(self):
        d = make_theme(self.root)
        rep = self.rep(d)
        self.assertEqual(errors_of(rep), [], f"baseline must pass: {rep.errors}")

    def test_hermes_bloodline_integrated_passes(self):
        rep = validate.validate_theme(REPO / "themes" / "hermes-bloodline", "hermes-bloodline")
        self.assertEqual(errors_of(rep), [], f"integrated hermes-bloodline must pass: {rep.errors}")

    def test_optional_omarchy_palette_extension_passes(self):
        d = make_theme(self.root, palette={
            "hyprland_active_border": "rgba(da2b47ee) rgba(ece7ddee) 45deg",
            "hyprland_inactive_border": "#26161a",
            "active_border_color": "#da2b47",
            "active_tab_background": "#1b1215",
        })
        rep = self.rep(d)
        self.assertEqual(errors_of(rep), [], f"optional upstream keys must pass: {rep.errors}")

    def test_optional_gradient_key_rejects_garbage(self):
        d = make_theme(self.root, palette={"hyprland_active_border": "not a color"})
        self.assertTrue(any("hyprland_active_border" in e for e in errors_of(self.rep(d))))

    def test_unknown_extra_key_still_rejected(self):
        d = make_theme(self.root, palette={"totally_made_up": "#123456"})
        self.assertTrue(any("totally_made_up" in e for e in errors_of(self.rep(d))))

    # -- palette failures -----------------------------------------------------
    def test_low_foreground_contrast_fails(self):
        d = make_theme(self.root, palette={"foreground": "#201a1a"})
        self.assertTrue(any("foreground contrast" in e for e in errors_of(self.rep(d))))

    def test_low_accent_contrast_fails(self):
        d = make_theme(self.root, palette={"accent": "#2a0d13"})
        self.assertTrue(any("accent contrast" in e for e in errors_of(self.rep(d))))

    def test_missing_required_key_fails(self):
        d = make_theme(self.root, palette={"brown": None})
        self.assertTrue(any("missing required baseline keys" in e and "brown" in e for e in errors_of(self.rep(d))))

    def test_invalid_hex_fails(self):
        d = make_theme(self.root, palette={"red": "#FF0000"})
        self.assertTrue(any("expected lowercase #rrggbb" in e and "red" in e for e in errors_of(self.rep(d))))

    def test_non_monotonic_ramp_fails(self):
        d = make_theme(self.root, palette={"lighter_background": "#050505"})
        self.assertTrue(any("monotonic" in e for e in errors_of(self.rep(d))))

    # -- forbidden files ------------------------------------------------------
    def test_forbidden_lua_fails(self):
        d = make_theme(self.root, files={"evil.lua": b"-- code\n"})
        self.assertTrue(any("evil.lua" in e for e in errors_of(self.rep(d))))

    def test_forbidden_terminal_config_fails(self):
        d = make_theme(self.root, files={"alacritty.toml": b"[window]\n"})
        self.assertTrue(any("alacritty.toml" in e for e in errors_of(self.rep(d))))

    def test_shell_toml_full_override_fails(self):
        d = make_theme(self.root, files={"shell.toml": b"[bar]\nsize = 30\n"})
        self.assertTrue(any("shell.toml" in e for e in errors_of(self.rep(d))))

    # -- backgrounds ----------------------------------------------------------
    def test_zero_byte_background_fails(self):
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=b"")
        self.assertTrue(any("not a valid image" in e and "empty" in e for e in errors_of(self.rep(d))))

    def test_truncated_background_fails(self):
        good = png_bytes(100, 100)
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=good[:20])
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_extension_content_mismatch_fails(self):
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=png_bytes(100, 100))
        self.assertTrue(any("not a valid image" in e and "JPEG" in e for e in errors_of(self.rep(d))))

    def test_extension_content_mismatch_jpeg_as_png_fails(self):
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=jpeg_bytes(100, 100))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_oversized_wallpaper_fails(self):
        big = png_bytes(100, 100) + b"\x00" * (9 * 1024 * 1024)
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=big)
        self.assertTrue(any("exceeds 8 MB" in e for e in errors_of(self.rep(d))))

    def test_valid_jpeg_background_passes(self):
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=jpeg_bytes(640, 480))
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_unindexed_background_name_fails(self):
        d = make_theme(self.root, bg_name="wallpaper.png", bg_bytes=png_bytes(100, 100))
        self.assertTrue(any("N-short-name.ext" in e for e in errors_of(self.rep(d))))

    # -- preview ---------------------------------------------------------------
    def test_truncated_preview_fails(self):
        d = make_theme(self.root, files={"preview.png": b"\x89PNG\r\n\x1a\n"})
        self.assertTrue(any("preview" in e.lower() for e in errors_of(self.rep(d))))

    def test_signature_only_preview_fails(self):
        d = make_theme(self.root, files={"preview.png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 32})
        self.assertTrue(any("preview" in e.lower() for e in errors_of(self.rep(d))))

    def test_wrong_preview_dimensions_fails(self):
        d = make_theme(self.root, files={"preview.png": png_bytes(100, 100)})
        self.assertTrue(any("1800x1012" in e for e in errors_of(self.rep(d))))

    def test_preview_bad_crc_fails(self):
        d = make_theme(self.root, files={"preview.png": png_bytes(1800, 1012, bad_crc=True)})
        self.assertTrue(any("CRC" in e for e in errors_of(self.rep(d))))

    def test_correct_preview_passes(self):
        d = make_theme(self.root, files={"preview.png": png_bytes(1800, 1012)})
        self.assertEqual(errors_of(self.rep(d)), [])


class RepoValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def readme_with(self, rows: list[str]) -> None:
        lines = ["# Repo", "", "## Themes", "", "| Theme | Mode | Identity |", "| --- | --- | --- |"]
        lines += rows
        (self.root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_missing_index_row_fails(self):
        make_theme(self.root)
        self.readme_with([])
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("missing row" in e for e in rep.errors))

    def test_duplicate_index_row_fails(self):
        make_theme(self.root)
        row = "| [`test-theme`](themes/test-theme/) | dark | test |"
        self.readme_with([row, row])
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("2 rows" in e and "exactly one required" in e for e in rep.errors))

    def test_orphan_index_row_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`ghost`](themes/ghost/) | dark | nope |"])
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("unknown theme 'ghost'" in e for e in rep.errors))

    def test_untracked_scratch_file_does_not_affect_hygiene(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        # drop an untracked scratch file with BOTH tripwires after the commit
        (self.root / "SCRATCH.md").write_text("api_key=abc123 /home/tony/secret\n", encoding="utf-8")
        rep = validate.validate_repo(self.root)
        self.assertEqual(rep.errors, [], f"untracked files must not affect hygiene: {rep.errors}")

    def test_tracked_machine_path_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "docs" ).mkdir(exist_ok=True)
        (self.root / "docs" / "note.md").write_text("lives in /home/tony/projects\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "add note"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("machine-specific path" in e for e in rep.errors))

    def test_tracked_secret_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "theme-doc.md").write_text("token: ghp_1234567890abcdef\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "add doc"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("possible secret" in e for e in rep.errors))

    def test_tracked_secret_in_test_dir_is_exempt_fixture(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / "tests" / "fixtures.py").write_text("SECRET = 'ghp_1234567890abcdef'\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "add fixture"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertEqual(rep.errors, [], f"tests/ fixtures are exempt by design: {rep.errors}")


class PngStructureTests(unittest.TestCase):
    """Direct unit tests for the PNG walker used by preview validation."""

    def test_complete_png_dimensions(self):
        self.assertEqual(validate._png_info(png_bytes(1800, 1012), True), (1800, 1012))

    def test_truncated_raises(self):
        with self.assertRaises(ValueError):
            validate._png_info(b"\x89PNG\r\n\x1a\n", True)

    def test_header_only_raises_when_complete_required(self):
        with self.assertRaises(ValueError):
            validate._png_info(png_bytes(10, 10, complete=False), True)

    def test_non_positive_dimensions_raise(self):
        bad = png_bytes(10, 10)
        with self.assertRaises(ValueError):
            validate._png_info(bad[:16] + b"\x00\x00\x00\x00" + bad[20:], True)


if __name__ == "__main__":
    unittest.main()
