"""Committed regression tests for scripts/validate.py.

Run: python3 -m unittest discover   (from the repository root)

Uses the stdlib unittest framework. Pillow is a required dependency of the
validator (requirements-validator.txt) and is used by these tests for
decodability cross-checks. Fixtures are built in tmp dirs from a known-good
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


def png_bytes(width: int, height: int, *, complete: bool = True, bad_crc: bool = False,
              with_idat: bool = True, idat_first: bool = True, dup_ihdr: bool = False) -> bytes:
    """Minimal genuinely-valid PNG (IHDR + IDAT + IEND), or deliberately broken."""
    def chunk(ctype: bytes, data: bytes, corrupt: bool = False) -> bytes:
        crc = (zlib.crc32(ctype + data) & 0xFFFFFFFF) ^ (1 if corrupt else 0)
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    # real (zlib-compressed) scanline data: filter byte + raw RGB rows
    raw = b"".join(b"\x00" + b"\x80\x60\x30" * width for _ in range(min(height, 4)))
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")

    if dup_ihdr:
        body = b"\x89PNG\r\n\x1a\n" + ihdr + ihdr + idat + iend
    elif not idat_first:
        body = b"\x89PNG\r\n\x1a\n" + idat + ihdr + iend
    elif not with_idat:
        body = b"\x89PNG\r\n\x1a\n" + ihdr + iend
    else:
        body = b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend
    if bad_crc:
        ihdr_bad = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0), corrupt=True)
        body = b"\x89PNG\r\n\x1a\n" + ihdr_bad + idat + iend
    if not complete:
        body = b"\x89PNG\r\n\x1a\n" + ihdr + idat  # no IEND
    return body


def jpeg_bytes(width: int, height: int, *, with_scan: bool = True, empty_scan: bool = False) -> bytes:
    """Minimal JPEG: SOI + SOF0 + (SOS + entropy) + EOI, or deliberately broken."""
    sof = struct.pack(">HH", height, width) + b"\x03\x01\x11\x00"
    parts = [
        b"\xff\xd8",                                        # SOI
        b"\xff\xc0" + struct.pack(">H", 2 + len(sof)) + sof,  # SOF0
    ]
    if with_scan:
        sos_body = b"\x01" + bytes([1, 0x00, 0x00])  # 1 component, id 1, DC/AC table 0
        parts.append(b"\xff\xda" + struct.pack(">H", 2 + len(sos_body)) + sos_body)
        if not empty_scan:
            parts.append(b"\x80\x60\x30" * 8 + b"\x55" * 4)  # entropy bytes
    parts.append(b"\xff\xd9")                              # EOI
    return b"".join(parts)


# Tripwires are constructed at RUNTIME so committed test sources never
# contain contiguous scanner signatures (the hygiene scan has no exemptions).
SECRET_FIXTURE = ("gh" + "p_") + "1234567890abcdef"
SECRET_DOC = ("to" + "ken: g") + "hp_1234567890abcdef\n"
APIKEY_SCRATCH = ("ap" + "i_key") + "=abc123 " + ("/ho" + "me/tony/") + "secret\n"
MACHINE_PATH_DOC = ("lives in /ho" + "me/tony/") + "projects\n"

import base64

import io as _io

import PIL.Image
import PIL.ImageFile

PIL.ImageFile.LOAD_TRUNCATED_IMAGES = False


def corrupt_payload_png(w: int = 100, h: int = 100) -> bytes:
    """Structurally valid PNG whose IDAT contains garbage (correct CRCs)."""
    def chunk(ctype: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + ctype + data
                + struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF))
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    garbage_idat = chunk(b"IDAT", bytes(range(256)) * 4)  # non-zlib payload
    return b"\x89PNG\r\n\x1a\n" + ihdr + garbage_idat + chunk(b"IEND", b"")


def corrupt_payload_jpeg() -> bytes:
    """Real JPEG with its DHT (Huffman table) payload replaced by zeros."""
    jpeg_real = real_image("jpeg")
    dht_at = jpeg_real.find(b"\xff\xc4")
    seglen = int.from_bytes(jpeg_real[dht_at + 2:dht_at + 4], "big")
    return jpeg_real[:dht_at + 4] + b"\x00" * (seglen - 2) + jpeg_real[dht_at + 2 + seglen:]


def corrupt_payload_gif() -> bytes:
    """Real GIF with its LZW image-data bytes replaced by garbage."""
    gif_real = real_image("gif")
    desc_at = gif_real.find(b"\x2c")
    iflags = gif_real[desc_at + 9]
    lzw_at = desc_at + 10 + (3 * (2 ** ((iflags & 0x07) + 1)) if iflags & 0x80 else 0) + 1
    block_size = gif_real[lzw_at]
    return (gif_real[:lzw_at] + bytes([block_size]) + b"\xff" * block_size
            + gif_real[lzw_at + 1 + block_size:])


def corrupt_payload_webp() -> bytes:
    """Structurally valid VP8L chunk whose compressed payload is garbage."""
    bits = (63 & 0x3FFF) | ((63 & 0x3FFF) << 14)
    payload = b"\x2f" + b"\xde\xad\xbe\xef" + b"\xff" * 4  # sig byte + garbage
    chunk = b"VP8L" + len(payload).to_bytes(4, "little") + payload + b"\x00"  # odd pad
    return b"RIFF" + (4 + len(chunk)).to_bytes(4, "little") + b"WEBP" + chunk


# Real minimal images generated with Pillow, embedded as base64. Truncation
# fixtures are derived from these real bytes at runtime.
JPEG_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDiqKKK8k9wKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA/9k="
GIF_B64 = "R0lGODdhQABAAIEAAHg8HgAAAAAAAAAAACwAAAAAQABAAEAIaQABCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPHjyBDihxJsqTJkyhTqlzJsqXLlzBjypxJs6bNmzhz6tzJs6fPn0CDCh1KtKjRo0iTKl3KtKnTp1CjSp1KtarVq1izagUQEAA7"
BMP_B64 = "Qk02MAAAAAAAADYAAAAoAAAAQAAAAEAAAAABABgAAAAAAAAwAADEDgAAxA4AAAAAAAAAAAAAHjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4Hjx4"
WEBP_B64 = "UklGRkoAAABXRUJQVlA4ID4AAADQAwCdASpAAEAAPm02mEkkIyKhIggAgA2JaQB2AAAjPuOsAFeIUwAA/vDEC/+6DLOHB7//cGZ9XX+AAAAAAA=="


def real_image(kind: str) -> bytes:
    return base64.b64decode({"jpeg": JPEG_B64, "gif": GIF_B64, "bmp": BMP_B64, "webp": WEBP_B64}[kind])


def gif_bytes(w: int = 4, h: int = 4, *, complete: bool = True, with_image: bool = True,
              empty_data: bool = False) -> bytes:
    """Structural GIF for negative tests (header/table/walk defects)."""
    header = b"GIF89a" + w.to_bytes(2, "little") + h.to_bytes(2, "little") + b"\x80\x00\x00"
    gct = b"\x00" * 6
    image = b""
    if with_image:
        image = b"\x2c" + (0).to_bytes(2, "little") + (0).to_bytes(2, "little") \
                + w.to_bytes(2, "little") + h.to_bytes(2, "little") + b"\x00"
        image += b"\x02"      # LZW min code size
        if empty_data:
            image += b"\x00"  # immediately-empty data chain
        else:
            image += b"\x01\x44"  # sub-block: size 1, one data byte
            image += b"\x00"      # sub-block terminator
    trailer = b"\x3b"
    if not complete:
        return header + gct + image  # no trailer
    return header + gct + image + trailer


def bmp_bytes(w: int = 4, h: int = 4, *, complete: bool = True) -> bytes:
    """Minimal structurally-valid BMP v3 (24bpp, BI_RGB) or truncated."""
    row = ((w * 24 + 31) // 32) * 4
    pixel_off = 14 + 40
    pixel_data = (b"\x80" * (row * h)) if complete else (b"\x80" * max(0, row * h // 3))
    total = pixel_off + len(pixel_data)
    fh = b"BM" + total.to_bytes(4, "little") + b"\x00\x00\x00\x00" + pixel_off.to_bytes(4, "little")
    dib = (40).to_bytes(4, "little") + w.to_bytes(4, "little", signed=True) \
        + h.to_bytes(4, "little", signed=True) + (1).to_bytes(2, "little") \
        + (24).to_bytes(2, "little") + (0).to_bytes(4, "little") \
        + (len(pixel_data)).to_bytes(4, "little") + (2835).to_bytes(4, "little") \
        + (2835).to_bytes(4, "little") + (0).to_bytes(4, "little") + (0).to_bytes(4, "little")
    return fh + dib + pixel_data


def webp_bytes(w: int = 4, h: int = 4, *, complete: bool = True, vp8x_only: bool = False,
               anmf_meta_only: bool = False, drop_padding: bool = False) -> bytes:
    """Minimal lossless WEBP (VP8L), or metadata-only / broken variants."""
    def chunk(ctype: bytes, payload: bytes) -> bytes:
        c = ctype + len(payload).to_bytes(4, "little") + payload
        if len(payload) & 1:
            c += b"\x00"  # required odd-size padding
        return c

    bits = ((w - 1) & 0x3FFF) | (((h - 1) & 0x3FFF) << 14)
    vp8l = chunk(b"VP8L", b"\x2f" + bits.to_bytes(4, "little") + b"\x00" * 4)
    vp8x = chunk(b"VP8X", b"\x00" + b"\x00" * 3 + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little"))
    anmf_meta = chunk(b"ANMF", b"\x00" * 6 + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little") + b"\x00" * 7)

    if vp8x_only:
        payload = vp8x
    elif anmf_meta_only:
        payload = vp8x + anmf_meta
    else:
        payload = vp8l

    riff_size = 4 + len(payload)
    out = b"RIFF" + riff_size.to_bytes(4, "little") + b"WEBP" + payload
    if drop_padding:
        # strip the mandatory odd-chunk pad byte while keeping RIFF size honest
        # to the (now unpadded) payload — chunk walker must reject the layout
        out = out[:-1]
        out = out[:4] + (riff_size - 1).to_bytes(4, "little") + out[8:]
    if not complete:
        return out[: len(out) - 6]
    return out


def make_theme(root: Path, slug: str = "test-theme", palette: dict | None = None,
               bg_name: str | None = "0-x.png", bg_bytes: bytes | None = None,
               files: dict[str, bytes | str] | None = None, bg_files: list[tuple[str, bytes]] | None = None,
               raw_palette_lines: list[str] | None = None, bg_dirs: list[str] | None = None) -> Path:
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
    lines += raw_palette_lines or []
    (d / "colors.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if bg_name is not None:
        (d / "backgrounds" / bg_name).write_bytes(bg_bytes if bg_bytes is not None else png_bytes(100, 100))
    for name, content in (files or {}).items():
        target = d / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode()
        if target.suffix == ".png" and isinstance(content, bytes) and content[:4] == b"\xff\xd8\xff":
            pass  # allow deliberate mismatches
        target.write_bytes(content)
    for name, content in (bg_files or []):
        (d / "backgrounds" / name).write_bytes(content)
    for name in (bg_dirs or []):
        (d / "backgrounds" / name).mkdir(parents=True)
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

    def test_upstream_solitude_style_border_values_pass(self):
        """Exact values from current omacom/omarchy quattro stock themes."""
        d = make_theme(self.root, palette={
            # themes/solitude/colors.toml
            "hyprland_active_border": "rgba(798186ee) rgba(caccccee)",   # no angle
            "hyprland_inactive_border": "rgb(1e1e1e)",                   # rgb() hex form
            "active_border_color": "#a8adb0",
            "active_tab_background": "#798186",
        })
        rep = self.rep(d)
        self.assertEqual(errors_of(rep), [], f"solitude-style values must pass: {rep.errors}")

    def test_upstream_last_horizon_style_border_values_pass(self):
        d = make_theme(self.root, palette={
            # themes/last-horizon/colors.toml
            "hyprland_active_border": "rgba(8a8588ee) rgba(e2dddcee)",
            "hyprland_inactive_border": "rgba(584e51aa)",                # single rgba stop
        })
        rep = self.rep(d)
        self.assertEqual(errors_of(rep), [], f"last-horizon-style values must pass: {rep.errors}")

    def test_upstream_hackerman_angle_gradient_passes(self):
        d = make_theme(self.root, palette={
            # themes/hackerman/colors.toml
            "hyprland_active_border": "rgba(26a269ee) rgba(2ec27eee) 45deg",
        })
        rep = self.rep(d)
        self.assertEqual(errors_of(rep), [], f"angle-bearing gradient must pass: {rep.errors}")

    def test_optional_gradient_key_rejects_garbage(self):
        d = make_theme(self.root, palette={"hyprland_active_border": "not a color"})
        self.assertTrue(any("hyprland_active_border" in e for e in errors_of(self.rep(d))))

    def test_optional_gradient_rejects_partial_garbage_stop(self):
        d = make_theme(self.root, palette={"hyprland_active_border": "rgba(798186ee) nonsensestop"})
        self.assertTrue(any("hyprland_active_border" in e for e in errors_of(self.rep(d))))

    def test_non_string_optional_value_fails_cleanly(self):
        d = make_theme(self.root, raw_palette_lines=["hyprland_active_border = 123"])
        rep = self.rep(d)
        self.assertTrue(any("expected a color/gradient string" in e for e in rep.errors),
                        f"must produce a validator error, not a crash: {rep.errors}")

    def test_optional_gradient_accepts_decimal_rgb_and_0x_forms(self):
        d = make_theme(self.root, palette={
            # decimal rgb() forms are unspaced, matching upstream parse_gradient
            # (read -ra splits on whitespace, so spaces inside parens would break it)
            "hyprland_active_border": "rgb(42,162,105) rgba(26,162,105,0.9) 45deg",
            "hyprland_inactive_border": "0x1e1e1eff",
        })
        self.assertEqual(errors_of(self.rep(d)), [])

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

    # -- light-theme validation (relationship model, no key ordering) ---------

    def _light_palette(self) -> dict:
        p = dict(BASELINE)
        p.update({
            "mode": "light",
            "accent": "#2e6fe8", "selection": "#ccd6e4", "muted": "#77818f",
            "background": "#f5f3ec", "dark_background": "#ebe9e0",
            "darker_background": "#ddd9cd", "lighter_background": "#e3e1d8",
            "foreground": "#1b2a3a", "dark_foreground": "#5d6b7d",
            "light_foreground": "#28394c", "bright_foreground": "#0f1c2b",
            "red": "#b8344a", "yellow": "#9a7420", "orange": "#b06028",
            "green": "#3c7a3f", "cyan": "#177b8a", "blue": "#2e5fb8",
            "magenta": "#7d4fb5", "brown": "#8a5f3c",
            "bright_red": "#992638", "bright_yellow": "#7c5c14",
            "bright_green": "#2c6330", "bright_cyan": "#0f6270",
            "bright_blue": "#1f4a9e", "bright_magenta": "#66389c",
        })
        return p

    def test_valid_light_palette_lupine_order_passes(self):
        """lupine/rose-pine key order: lighter_background before dark_background."""
        p = self._light_palette()
        p["dark_background"], p["lighter_background"] = "#e3e1d8", "#ebe9e0"
        d = make_theme(self.root, palette=p)
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_valid_light_palette_latte_order_passes(self):
        """catppuccin-latte/flexoki-light key order: dark_background before lighter."""
        d = make_theme(self.root, palette=self._light_palette())
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_light_palette_with_tied_selection_and_lighter_passes(self):
        """Stock `white` ties selection and lighter_background — must pass."""
        p = self._light_palette()
        p["lighter_background"] = p["selection"]
        d = make_theme(self.root, palette=p)
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_invalid_light_palette_fails(self):
        """selection lighter than background (selected area brighter than the
        base surface) is broken on a light theme and must fail."""
        p = self._light_palette()
        p["selection"] = "#fdfdf9"  # lighter than background #f5f3ec
        d = make_theme(self.root, palette=p)
        errs = errors_of(self.rep(d))
        self.assertTrue(any("lightest surface" in e for e in errs), f"expected failure: {errs}")

    def test_invalid_light_palette_dark_fg_on_dark_surface_fails(self):
        """muted must be darker than every surface; a muted tone lighter than
        the darkest surface would be unreadable on that surface."""
        p = self._light_palette()
        p["muted"] = "#e2ded2"  # lum ~0.73 > darker_background #ddd9cd ~0.69
        d = make_theme(self.root, palette=p)
        errs = errors_of(self.rep(d))
        self.assertTrue(any("muted must be darker" in e for e in errs), f"expected failure: {errs}")

    def test_dark_theme_ramp_validation_unchanged(self):
        """Dark ramp rule still enforces monotonic rise (regression guard)."""
        d = make_theme(self.root, palette={"lighter_background": "#050505"})
        self.assertTrue(any("dark: must rise" in e for e in errors_of(self.rep(d))))

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
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=real_image("jpeg"))
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_jpeg_truncated_before_scan_fails(self):
        good = real_image("jpeg")
        sof_at = good.find(b"\xff\xc0")
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=good[:sof_at])
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_jpeg_truncated_after_dimensions_fails(self):
        good = real_image("jpeg")
        sof_at = good.find(b"\xff\xc0")
        seglen = int.from_bytes(good[sof_at + 2:sof_at + 4], "big")
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=good[:sof_at + 2 + seglen])
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_png_without_idat_fails(self):
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=png_bytes(100, 100, with_idat=False))
        self.assertTrue(any("no IDAT" in e for e in errors_of(self.rep(d))))

    def test_png_ihdr_not_first_fails(self):
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=png_bytes(100, 100, idat_first=False))
        self.assertTrue(any("first chunk must be IHDR" in e for e in errors_of(self.rep(d))))

    def test_png_duplicate_ihdr_fails(self):
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=png_bytes(100, 100, dup_ihdr=True))
        self.assertTrue(any("duplicate IHDR" in e for e in errors_of(self.rep(d))))

    def test_png_fixture_is_genuinely_valid(self):
        """The synthetic positive PNG fixture must actually decode."""
        im = PIL.Image.open(_io.BytesIO(png_bytes(100, 100)))
        im.load()
        self.assertEqual(im.size, (100, 100))

    # -- corrupt-payload (structurally plausible, undecodable) ---------------

    def test_corrupt_payload_png_fails(self):
        """Structurally valid PNG (correct CRCs, non-empty IDAT) whose IDAT
        is garbage must fail full validation via the decode layer."""
        d = make_theme(self.root, bg_name="0-x.png", bg_bytes=corrupt_payload_png())
        errs = errors_of(self.rep(d))
        self.assertTrue(any("not a valid image" in e and "0-x.png" in e for e in errs),
                        f"expected decode failure: {errs}")

    def test_corrupt_payload_jpeg_fails(self):
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=corrupt_payload_jpeg())
        errs = errors_of(self.rep(d))
        self.assertTrue(any("not a valid image" in e for e in errs),
                        f"expected decode failure: {errs}")

    def test_corrupt_payload_gif_fails(self):
        d = make_theme(self.root, bg_name="0-x.gif", bg_bytes=corrupt_payload_gif())
        errs = errors_of(self.rep(d))
        self.assertTrue(any("not a valid image" in e for e in errs),
                        f"expected decode failure: {errs}")

    def test_corrupt_payload_webp_fails(self):
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=corrupt_payload_webp())
        errs = errors_of(self.rep(d))
        self.assertTrue(any("not a valid image" in e for e in errs),
                        f"expected decode failure: {errs}")

    def test_corrupt_payload_preview_fails(self):
        d = make_theme(self.root, files={"preview.png": corrupt_payload_png(1800, 1012)})
        errs = errors_of(self.rep(d))
        self.assertTrue(any("preview.png" in e for e in errs),
                        f"expected preview decode failure: {errs}")

    # -- real repository assets must fully decode ------------------------------

    def test_hermes_bloodline_wallpaper_fully_decodes(self):
        p = REPO / "themes" / "hermes-bloodline" / "backgrounds" / "0-hermes-bloodline.png"
        im = PIL.Image.open(p)
        im.load()
        self.assertEqual(im.format, "PNG")
        self.assertEqual(im.size, (1672, 941))

    def test_hermes_bloodline_preview_fully_decodes(self):
        p = REPO / "themes" / "hermes-bloodline" / "preview.png"
        im = PIL.Image.open(p)
        im.load()
        self.assertEqual(im.format, "PNG")
        self.assertEqual(im.size, (1800, 1012))

    def test_all_real_fixtures_fully_decode(self):
        for kind, ext, size in [("jpeg", ".jpg", None), ("gif", ".gif", None),
                                ("bmp", ".bmp", None), ("webp", ".webp", None)]:
            with self.subTest(kind=kind):
                im = PIL.Image.open(_io.BytesIO(real_image(kind)))
                im.load()
                self.assertEqual(im.format, validate.EXPECTED_FORMAT[ext])

    def test_jpeg_without_sos_fails(self):
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=jpeg_bytes(640, 480, with_scan=False))
        self.assertTrue(any("no SOS" in e for e in errors_of(self.rep(d))))

    def test_jpeg_sos_without_entropy_fails(self):
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=jpeg_bytes(640, 480, empty_scan=True))
        self.assertTrue(any("no scan entropy data" in e for e in errors_of(self.rep(d))))

    def test_jpeg_missing_eoi_fails(self):
        good = real_image("jpeg")
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=good[:-2])  # drop EOI
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_jpeg_malformed_segment_length_fails(self):
        good = bytearray(real_image("jpeg"))
        sof_at = good.find(b"\xff\xc0")
        good[sof_at + 2:sof_at + 4] = (0).to_bytes(2, "big")  # length < 2
        d = make_theme(self.root, bg_name="0-x.jpg", bg_bytes=bytes(good))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_gif_valid_passes(self):
        d = make_theme(self.root, bg_name="0-x.gif", bg_bytes=real_image("gif"))
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_gif_header_only_fails(self):
        header = b"GIF89a" + (64).to_bytes(2, "little") + (64).to_bytes(2, "little") + b"\x00\x00\x00"
        d = make_theme(self.root, bg_name="0-x.gif", bg_bytes=header)
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_gif_truncated_no_trailer_fails(self):
        d = make_theme(self.root, bg_name="0-x.gif", bg_bytes=gif_bytes(64, 64, complete=False))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_gif_trailer_without_image_fails(self):
        d = make_theme(self.root, bg_name="0-x.gif", bg_bytes=gif_bytes(64, 64, with_image=False))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_bmp_valid_passes(self):
        d = make_theme(self.root, bg_name="0-x.bmp", bg_bytes=real_image("bmp"))
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_bmp_header_only_fails(self):
        full = real_image("bmp")
        d = make_theme(self.root, bg_name="0-x.bmp", bg_bytes=full[:26])  # header, no body
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_bmp_truncated_pixels_fails(self):
        d = make_theme(self.root, bg_name="0-x.bmp", bg_bytes=bmp_bytes(64, 64, complete=False))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_webp_valid_passes(self):
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=real_image("webp"))
        self.assertEqual(errors_of(self.rep(d)), [])

    def test_webp_truncated_fails(self):
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=webp_bytes(64, 64, complete=False))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_webp_lying_riff_size_fails(self):
        good = bytearray(real_image("webp"))
        good[4:8] = (int.from_bytes(good[4:8], "little") * 4).to_bytes(4, "little")
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=bytes(good))
        self.assertTrue(any("not a valid image" in e for e in errors_of(self.rep(d))))

    def test_gif_empty_data_chain_fails(self):
        d = make_theme(self.root, bg_name="0-x.gif", bg_bytes=gif_bytes(64, 64, empty_data=True))
        self.assertTrue(any("no LZW data" in e for e in errors_of(self.rep(d))))

    def test_webp_vp8x_only_fails(self):
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=webp_bytes(64, 64, vp8x_only=True))
        self.assertTrue(any("no image bitstream" in e for e in errors_of(self.rep(d))))

    def test_webp_anmf_metadata_only_fails(self):
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=webp_bytes(64, 64, anmf_meta_only=True))
        self.assertTrue(any("bitstream" in e for e in errors_of(self.rep(d))))

    def test_webp_missing_padding_fails(self):
        d = make_theme(self.root, bg_name="0-x.webp", bg_bytes=webp_bytes(64, 64, drop_padding=True))
        errs = errors_of(self.rep(d))
        self.assertTrue(any("not a valid image" in e for e in errs), f"expected failure: {errs}")

    def test_background_directory_entry_fails_cleanly(self):
        d = make_theme(self.root, bg_name=None, bg_dirs=["0-wallpaper.png"])
        rep = self.rep(d)
        self.assertTrue(any("directory" in e.lower() for e in rep.errors),
                        f"directory-shaped background must fail cleanly: {rep.errors}")

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
        (self.root / "SCRATCH.md").write_text(APIKEY_SCRATCH, encoding="utf-8")
        rep = validate.validate_repo(self.root)
        self.assertEqual(rep.errors, [], f"untracked files must not affect hygiene: {rep.errors}")

    def test_tracked_machine_path_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "docs" ).mkdir(exist_ok=True)
        (self.root / "docs" / "note.md").write_text(MACHINE_PATH_DOC, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "add note"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("machine-specific path" in e for e in rep.errors))

    def test_tracked_secret_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "theme-doc.md").write_text(SECRET_DOC, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "add doc"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("possible secret" in e for e in rep.errors))

    def test_tracked_secret_under_tests_also_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / "tests" / "leaked.py").write_text(f"KEY = '{SECRET_FIXTURE}'\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "leak"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("possible secret" in e and "tests/leaked.py" in e for e in rep.errors),
                        f"tests/ must be scanned: {rep.errors}")

    def test_tracked_machine_path_under_tests_also_fails(self):
        make_theme(self.root)
        self.readme_with(["| [`test-theme`](themes/test-theme/) | dark | test |"])
        git_repo_with_theme(self.root)
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / "tests" / "pathleak.py").write_text(f"HOME_DOC = '{MACHINE_PATH_DOC.strip()}'\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "leak path"], cwd=self.root, check=True, capture_output=True)
        rep = validate.validate_repo(self.root)
        self.assertTrue(any("machine-specific path" in e and "tests/pathleak.py" in e for e in rep.errors),
                        f"tests/ must be scanned: {rep.errors}")

    def test_committed_test_suite_itself_passes_hygiene(self):
        """The validator's own committed test source must survive its scan."""
        rep = validate.validate_repo(REPO)
        self.assertEqual(rep.errors, [], f"repo (incl. tests/) must be hygiene-clean: {rep.errors}")


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
