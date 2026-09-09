#!/usr/bin/env python3
"""Theme and repository validator for awesome-omarchy-themes.

Deterministic gate for theme PRs. stdlib-only; no Omarchy install required.
Exit 0 = pass. CI runs the unit tests (tests/) and then this file on every PR.

Theme-level checks (per themes/<slug>/):
  structure   colors.toml present; backgrounds/ with >=1 valid image; no
              forbidden files (see FORBIDDEN — this repository's own policy:
              code-capable files plus full shell.toml overrides)
  palette     required 26-key baseline (this collection's contract); optional
              current-Omarchy extension keys allowed with format validation;
              #rrggbb lowercase (or Hyprland gradient strings where supported)
  contrast    foreground and accent >= 3:1 vs background (WCAG relative
              luminance); ramp monotonic by luminance in the mode's direction
  assets      backgrounds are real, complete images (signature, dimensions,
              truncation) in jpg/jpeg/png/gif/bmp/webp with indexed names
              (N-name.ext); wallpaper <= 8 MB; preview.png is a complete PNG
              with valid IHDR, exactly 1800x1012
Repo-level checks:
  index       every themes/<slug>/ has exactly one matching row in README.md's
              Themes table; missing, duplicate, and orphan rows all fail
  hygiene     Git-TRACKED text files only (deterministic across machines and
              CI): no machine-specific paths, no obvious secret patterns
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
THEMES_DIR_NAME = "themes"

REQUIRED_KEYS = [
    "mode", "accent", "selection", "muted",
    "background", "dark_background", "darker_background", "lighter_background",
    "foreground", "dark_foreground", "light_foreground", "bright_foreground",
    "red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown",
    "bright_red", "bright_yellow", "bright_green", "bright_cyan",
    "bright_blue", "bright_magenta",
]
# Optional palette extensions supported by current Omarchy (quattro). Stock
# themes ship these; docs/theming.md documents the gradient-capable pair.
OPTIONAL_SOLID_KEYS = {"active_border_color", "active_tab_background"}
OPTIONAL_GRADIENT_KEYS = {"hyprland_active_border", "hyprland_inactive_border"}
# Legacy short names remain supported upstream (canonical wins when both set).
LEGACY_ALIASES = {
    "bg": "background", "dark_bg": "dark_background",
    "darker_bg": "darker_background", "lighter_bg": "lighter_background",
    "fg": "foreground", "dark_fg": "dark_foreground",
    "light_fg": "light_foreground", "bright_fg": "bright_foreground",
}
RAMP = [
    "darker_background", "dark_background", "background",
    "lighter_background", "selection",
]
FG_LADDER = ["muted", "dark_foreground", "foreground", "light_foreground", "bright_foreground"]
BG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# This repository's own policy. Omarchy (quattro) drops code-capable files
# (*.lua, alacritty.toml, foot.ini, ghostty.conf, kitty.conf, vscode.json)
# only from themes installed via `omarchy theme install` (git clone) and KEEPS
# colour files including shell.toml. This collection's documented install path
# is a plain directory copy, which Omarchy stages in full trust — so the repo
# itself forbids code-capable files AND full shell.toml overrides. Section
# overrides (shell.<section>.toml) remain allowed: they are colour-only.
OMARCHY_DENIED = ["alacritty.toml", "foot.ini", "ghostty.conf", "kitty.conf", "vscode.json"]
FORBIDDEN = re.compile(
    r"^(.*\.lua|alacritty\.toml|foot\.ini|ghostty\.conf|kitty\.conf|vscode\.json|shell\.toml|\.git.*)$"
)
INDEXED = re.compile(r"^[0-9]+-[a-z0-9-]+\.(jpg|jpeg|png|gif|bmp|webp)$")
HEX = re.compile(r"^#[0-9a-f]{6}$")

# --- Upstream color-stop grammar -------------------------------------------
# Mirrors parse_gradient()/color_to_shell_hex() in current omacom/omarchy
# quattro (bin/omarchy-theme-set-templates): a border value is one or more
# color stops separated by whitespace, plus an optional trailing angle.
# Accepted stop forms (case-insensitive, matching upstream):
#   #rrggbb / #rrggbbaa
#   rgb(rrggbb) / rgba(rrggbbaa)
#   rgb(r,g,b) / rgba(r,g,b[,a])   (decimal, 0-255 each)
#   0xrrggbbaa
_STOP = re.compile(
    r"^(#[0-9a-f]{6}(?:[0-9a-f]{2})?"
    r"|rgba?\([0-9a-f]{6}(?:[0-9a-f]{2})?\)"
    r"|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*\d+(\.\d+)?\s*)?\)"
    r"|0x[0-9a-f]{8})$",
    re.IGNORECASE,
)
_ANGLE = re.compile(r"^-?\d+(?:\.\d+)?deg$", re.IGNORECASE)


def valid_border_value(value: str) -> bool:
    """True if `value` is a valid upstream border color/gradient string."""
    stops = 0
    for part in value.split():
        if _ANGLE.fullmatch(part):
            continue
        if not _STOP.fullmatch(part):
            return False
        stops += 1
    return stops >= 1
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SECRET = re.compile(
    r"(api[_-]?key|sk-[a-z0-9]{20}|ghp_[A-Za-z0-9]|gho_[A-Za-z0-9]|AKIA[0-9A-Z]{16}|xox[baprs]-)"
)
MACHINE_PATH = re.compile(r"(/home/[a-z][a-z0-9_-]*/|/Users/[a-z][a-z0-9_-]*/)")
PREVIEW_SIZE = (1800, 1012)
MAX_BG_BYTES = 8 * 1024 * 1024
MAX_PREVIEW_BYTES = 2 * 1024 * 1024


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


# ---------------------------------------------------------------- images ----

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png_info(data: bytes, require_complete: bool = True) -> tuple[int, int]:
    """Walk PNG chunks; return (width, height). ValueError on any defect."""
    if not data.startswith(PNG_SIG):
        raise ValueError("bad PNG signature")
    pos, seen_ihdr, width, height = 8, False, 0, 0
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("truncated PNG (chunk header cut)")
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if len(body) < length:
            raise ValueError("truncated PNG (chunk body cut)")
        if pos + 8 + length + 4 > len(data):
            raise ValueError("truncated PNG (CRC cut)")
        crc = int.from_bytes(data[pos + 8 + length:pos + 12 + length], "big")
        if zlib.crc32(ctype + body) & 0xFFFFFFFF != crc:
            raise ValueError(f"PNG chunk {ctype!r} failed CRC")
        if ctype == b"IHDR":
            if length != 13:
                raise ValueError("bad IHDR length")
            width, height = int.from_bytes(body[0:4], "big"), int.from_bytes(body[4:8], "big")
            seen_ihdr = True
        pos += 12 + length
        if ctype == b"IEND":
            if not seen_ihdr:
                raise ValueError("PNG has IEND but no IHDR")
            if width <= 0 or height <= 0:
                raise ValueError("PNG has non-positive dimensions")
            return width, height
    if require_complete:
        raise ValueError("truncated PNG (no IEND)")
    if not seen_ihdr:
        raise ValueError("PNG missing IHDR")
    if width <= 0 or height <= 0:
        raise ValueError("PNG has non-positive dimensions")
    return width, height


def _jpeg_info(data: bytes) -> tuple[int, int]:
    """Walk JPEG segments; require SOS and a following EOI for completeness."""
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        raise ValueError("bad JPEG signature")
    pos, width, height, saw_sof = 2, 0, 0, False
    while pos + 2 <= len(data):
        if data[pos] != 0xFF:
            raise ValueError("corrupt JPEG (missing marker prefix)")
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0xD9:  # EOI
            if not saw_sof:
                raise ValueError("JPEG EOI before any frame header")
            if width <= 0 or height <= 0:
                raise ValueError("JPEG has non-positive dimensions")
            return width, height
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # standalone markers
            pos += 2
            continue
        if pos + 4 > len(data):
            raise ValueError("truncated JPEG (segment length cut)")
        seglen = int.from_bytes(data[pos + 2:pos + 4], "big")
        if seglen < 2:
            raise ValueError("malformed JPEG segment length (< 2)")
        if pos + 2 + seglen > len(data):
            raise ValueError("truncated JPEG (segment body cut)")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if seglen < 7:
                raise ValueError("malformed JPEG SOF segment")
            height = int.from_bytes(data[pos + 5:pos + 7], "big")
            width = int.from_bytes(data[pos + 7:pos + 9], "big")
            saw_sof = True
            if width <= 0 or height <= 0:
                raise ValueError("JPEG has non-positive dimensions")
        if marker == 0xDA:  # SOS: scan data follows until a real marker
            scan = pos + 2 + seglen
            while scan + 1 < len(data):
                if data[scan] == 0xFF and data[scan + 1] not in (0x00,) and not (0xD0 <= data[scan + 1] <= 0xD7):
                    break  # candidate segment marker inside/after scan
                scan += 1
            pos = scan
            continue
        pos += 2 + seglen
    raise ValueError("truncated JPEG (no EOI)")


def _gif_info(data: bytes) -> tuple[int, int]:
    """Walk GIF blocks; require an image descriptor and the 0x3B trailer."""
    if len(data) < 13 or data[0:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("bad GIF signature")
    w = int.from_bytes(data[6:8], "little")
    h = int.from_bytes(data[8:10], "little")
    if w <= 0 or h <= 0:
        raise ValueError("GIF has non-positive dimensions")
    flags = data[10]
    pos = 13
    if flags & 0x80:  # global color table
        pos += 3 * (2 ** ((flags & 0x07) + 1))
    if pos > len(data):
        raise ValueError("truncated GIF (global color table cut)")
    saw_image = False
    while pos < len(data):
        b = data[pos]
        if b == 0x3B:  # trailer — complete
            if not saw_image:
                raise ValueError("GIF trailer with no image data")
            return w, h
        if b == 0x21:  # extension block
            if pos + 2 > len(data):
                raise ValueError("truncated GIF (extension header cut)")
            pos += 2  # skip label + sub-block-introducer position
            pos = _gif_skip_subblocks(data, pos)
        elif b == 0x2C:  # image descriptor
            if pos + 10 > len(data):
                raise ValueError("truncated GIF (image descriptor cut)")
            iflags = data[pos + 9]
            pos += 10
            if iflags & 0x80:
                pos += 3 * (2 ** ((iflags & 0x07) + 1))
            if pos >= len(data):
                raise ValueError("truncated GIF (local color table cut)")
            pos += 1  # LZW minimum code size
            pos = _gif_skip_subblocks(data, pos)
            saw_image = True
        else:
            raise ValueError(f"corrupt GIF (unknown block introducer 0x{b:02x})")
    raise ValueError("truncated GIF (no trailer)")


def _gif_skip_subblocks(data: bytes, pos: int) -> int:
    while pos < len(data):
        size = data[pos]
        pos += 1
        if size == 0:
            return pos
        pos += size
        if pos > len(data):
            raise ValueError("truncated GIF (sub-block cut)")
    raise ValueError("truncated GIF (unterminated sub-block chain)")


def _bmp_info(data: bytes) -> tuple[int, int]:
    """Validate BMP header consistency and pixel-data reachability."""
    if len(data) < 26 or data[0:2] != b"BM":
        raise ValueError("bad BMP signature")
    declared = int.from_bytes(data[2:6], "little")
    if declared < 26 or declared > len(data):
        raise ValueError("truncated BMP (declared size exceeds file)")
    w = int.from_bytes(data[18:22], "little", signed=True)
    h = abs(int.from_bytes(data[22:26], "little", signed=True))
    if w <= 0 or h <= 0:
        raise ValueError("BMP has non-positive dimensions")
    if len(data) < 30:
        raise ValueError("truncated BMP (DIB header cut)")
    dib = int.from_bytes(data[14:18], "little")
    bpp_off = 28
    if dib >= 12 and len(data) >= bpp_off + 2:
        bpp = int.from_bytes(data[bpp_off:bpp_off + 2], "little")
        if bpp == 0:
            raise ValueError("BMP declares 0 bits per pixel")
        row = ((w * bpp + 31) // 32) * 4
        pixel_off = int.from_bytes(data[10:14], "little")
        if dib >= 40 and len(data) >= 38:
            comp = int.from_bytes(data[30:34], "little")
            if comp not in (0, 1, 2, 3):  # BI_RGB, RLE8, RLE4, BITFIELDS
                raise ValueError(f"BMP declares unsupported compression {comp}")
        needed = pixel_off + row * h
        if pixel_off < 26 or pixel_off > len(data):
            raise ValueError("truncated BMP (pixel offset beyond file)")
        if needed > len(data):
            raise ValueError("truncated BMP (pixel data incomplete)")
    return w, h


def _webp_info(data: bytes) -> tuple[int, int]:
    """Walk RIFF chunks; verify declared sizes/padding and payload bounds."""
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("bad WEBP signature")
    riff_size = int.from_bytes(data[4:8], "little")
    if riff_size < 4:
        raise ValueError("malformed WEBP (RIFF size too small)")
    riff_end = 8 + riff_size
    if riff_end > len(data):
        raise ValueError("truncated WEBP (RIFF size exceeds file)")
    pos, width, height = 12, 0, 0
    while pos + 8 <= riff_end:
        ctype = data[pos:pos + 4]
        clen = int.from_bytes(data[pos + 4:pos + 8], "little")
        body_start = pos + 8
        body_end = body_start + clen
        if body_end > riff_end:
            raise ValueError("truncated WEBP (chunk exceeds RIFF bounds)")
        body = data[body_start:body_end]
        if ctype == b"VP8X" and len(body) >= 10:
            width = (int.from_bytes(body[4:7], "little") & 0xFFFFFF) + 1
            height = (int.from_bytes(body[7:10], "little") & 0xFFFFFF) + 1
        elif ctype == b"VP8 " and len(body) >= 10:
            # lossy frame: 3-byte frame tag, then sync code 0x9d 0x01 0x2a
            if body[3:6] != b"\x9d\x01\x2a":
                raise ValueError("corrupt WEBP (bad VP8 sync code)")
            width = int.from_bytes(body[6:8], "little") & 0x3FFF
            height = int.from_bytes(body[8:10], "little") & 0x3FFF
        elif ctype == b"VP8L" and len(body) >= 5:
            if body[0] != 0x2f:
                raise ValueError("corrupt WEBP (bad VP8L signature)")
            bits = int.from_bytes(body[1:5], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
        elif ctype == b"ANMF" and len(body) >= 16 and width == 0:
            width = (int.from_bytes(body[6:9], "little") & 0xFFFFFF) + 1
            height = (int.from_bytes(body[9:12], "little") & 0xFFFFFF) + 1
        pos = body_end + (clen & 1)  # chunks are padded to even sizes
    if pos < riff_end and riff_end - pos > 1:
        raise ValueError("truncated WEBP (unparsed trailing bytes inside RIFF)")
    if width <= 0 or height <= 0:
        raise ValueError("WEBP has no frame with positive dimensions")
    return width, height


def probe_image(data: bytes, ext: str) -> tuple[str, int, int]:
    """Validate image bytes for the format claimed by `ext`.

    Returns (format, width, height). Raises ValueError on zero-byte, invalid
    signature, truncation, corrupt structure, or non-positive dimensions.
    """
    if not data:
        raise ValueError("empty (zero-byte) file")
    probes: dict[str, tuple[str, object]] = {
        ".png": ("PNG", _png_info),
        ".jpg": ("JPEG", _jpeg_info),
        ".jpeg": ("JPEG", _jpeg_info),
        ".gif": ("GIF", _gif_info),
        ".bmp": ("BMP", _bmp_info),
        ".webp": ("WEBP", _webp_info),
    }
    if ext not in probes:
        raise ValueError(f"unsupported extension {ext!r}")
    fmt, fn = probes[ext]
    width, height = fn(data)  # type: ignore[operator]
    if width <= 0 or height <= 0:
        raise ValueError("non-positive dimensions")
    return fmt, width, height


# ---------------------------------------------------------------- themes ----

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
        if FORBIDDEN.fullmatch(p.name) or FORBIDDEN.fullmatch(rel) or rel.endswith(".lua"):
            rep.error(
                f"forbidden by this repository's color-only theme policy: {rel} "
                f"(Omarchy drops code files only from git-cloned installs; this repo's "
                f"copy-install path stages everything, so the policy is stricter)"
            )
        if p.is_symlink():
            rep.error(f"symlinks are dropped by Omarchy when staging git-installed themes: {rel}")

    # -- palette: required baseline ------------------------------------------
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        rep.error(f"colors.toml missing required baseline keys: {', '.join(missing)}")
        return rep

    mode = data["mode"]
    if mode not in ("dark", "light"):
        rep.error(f"mode must be 'dark' or 'light', got {mode!r}")

    allowed = set(REQUIRED_KEYS) | OPTIONAL_SOLID_KEYS | OPTIONAL_GRADIENT_KEYS | set(LEGACY_ALIASES)
    for k, v in data.items():
        if k == "mode":
            continue
        if k in OPTIONAL_GRADIENT_KEYS or k in OPTIONAL_SOLID_KEYS:
            if not isinstance(v, str):
                rep.error(f"{k}: expected a color/gradient string, got {type(v).__name__} {v!r}")
            elif not valid_border_value(v):
                rep.error(
                    f"{k}: not a valid current-Omarchy color/gradient value: {v!r} "
                    f"(stops: #rrggbb[aa], rgb()/rgba() hex or decimal, 0xrrggbbaa; "
                    f"multi-stop gradients with optional Ndeg angle)"
                )
        elif not isinstance(v, str) or not HEX.fullmatch(v):
            rep.error(f"{k}: expected lowercase #rrggbb, got {v!r}")
    extra = [k for k in data if k not in allowed]
    if extra:
        rep.error(f"colors.toml has keys neither in the required baseline nor the supported optional set: {', '.join(sorted(extra))}")
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
                continue
            if p.is_dir():
                rep.error(f"background entry is a directory, not an image file: {p.name}/")
                continue
            if p.is_symlink():
                rep.error(f"background entry is a symlink, not a regular file: {p.name}")
                continue
            if not p.is_file():
                rep.error(f"background entry is not a regular file: {p.name}")
                continue
            ext = p.suffix.lower()
            if ext not in BG_EXTS:
                rep.error(f"background format not allowed: {p.name}")
                continue
            size = p.stat().st_size
            if size > MAX_BG_BYTES:
                rep.error(f"background exceeds 8 MB: {p.name} ({size // 1024} KB)")
            try:
                fmt, w, h = probe_image(p.read_bytes(), ext)
                if size <= MAX_BG_BYTES:
                    rep.note(f"background {p.name}: {fmt} {w}x{h}, {size // 1024} KB")
            except ValueError as e:
                rep.error(f"background is not a valid image: {p.name}: {e}")

    preview = theme_dir / "preview.png"
    if preview.is_file():
        size = preview.stat().st_size
        if size > MAX_PREVIEW_BYTES:
            rep.error(f"preview.png exceeds 2 MB ({size // 1024} KB); quantize to <=256 colors")
        try:
            w, h = _png_info(preview.read_bytes(), require_complete=True)
            if (w, h) != PREVIEW_SIZE:
                rep.error(f"preview.png must be {PREVIEW_SIZE[0]}x{PREVIEW_SIZE[1]}, got {w}x{h}")
        except ValueError as e:
            rep.error(f"preview.png is not a valid complete PNG: {e}")

    return rep


# ------------------------------------------------------------------ repo ----

def _tracked_files(root: Path) -> list[Path]:
    """Deterministically enumerate Git-tracked files. Fails closed."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"cannot enumerate tracked files (git required): {e}") from e
    return [root / rel for rel in out.split("\0") if rel]


def validate_repo(root: Path | None = None) -> Report:
    root = root or REPO
    rep = Report("repo")
    themes_dir = root / THEMES_DIR_NAME

    readme = root / "README.md"
    if not readme.is_file():
        rep.error("README.md missing")
        table_rows: list[str] = []
    else:
        table_rows = re.findall(r"^\| \[`([a-z0-9-]+)`\]", readme.read_text(encoding="utf-8"), re.M)

    themes = sorted(p.name for p in themes_dir.iterdir() if p.is_dir()) if themes_dir.is_dir() else []
    for slug in themes:
        count = table_rows.count(slug)
        if count == 0:
            rep.error(f"README Themes table missing row for '{slug}'")
        elif count > 1:
            rep.error(f"README Themes table has {count} rows for '{slug}' (exactly one required)")
    for slug in table_rows:
        if slug not in themes:
            rep.error(f"README Themes table has row for unknown theme '{slug}'")
    if themes and not table_rows:
        rep.error("README.md is missing the Themes table section")
    if not table_rows and not themes:
        rep.note("no themes yet")

    # hygiene: tracked text files only — same result locally and in CI.
    # No directory is exempt: tripwire-shaped strings needed by the test
    # suite are constructed at runtime there so committed sources stay clean.
    text_ext = {".md", ".toml", ".py", ".yml", ".yaml", ".gitignore", ".editorconfig", ".theme"}
    try:
        files = _tracked_files(root)
    except RuntimeError as e:
        rep.error(str(e))
        return rep
    for p in files:
        if p.suffix.lower() not in text_ext and p.name not in (".gitignore", ".editorconfig", "LICENSE"):
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        rel = p.relative_to(root).as_posix()
        for match in SECRET.finditer(content):
            rep.error(f"possible secret in {rel}: {match.group(0)[:12]}…")
        for match in MACHINE_PATH.finditer(content):
            rep.error(f"machine-specific path in {rel}: {match.group(0)}")

    return rep


def main() -> int:
    themes_dir = REPO / THEMES_DIR_NAME
    if not themes_dir.is_dir():
        themes_dir.mkdir(exist_ok=True)  # tolerate repos predating the first theme

    targets = sys.argv[1:]
    if targets:
        reports = []
        for t in targets:
            p = Path(t) if "/" in t else themes_dir / t
            if not p.is_dir():
                reports.append(Report(f"theme:{t}"))
                reports[-1].error("theme directory not found")
                continue
            reports.append(validate_theme(p, p.name))
    else:
        reports = [validate_theme(d, d.name) for d in sorted(themes_dir.iterdir()) if d.is_dir()]
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
                print(f"FAIL {rep.name}: {e}")

    total = len(reports)
    passed = sum(1 for r in reports if r.ok)
    print(f"\n{passed}/{total} passed" + ("" if not failed else " — fix the failures above"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
