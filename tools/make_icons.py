#!/usr/bin/env python3
"""Generate the LeafBlitz icons (no image libraries needed).

Writes:
  favicon.svg          -- crisp brutalist leaf badge for modern browsers
  apple-touch-icon.png -- 180x180 raster for iOS home screens

Run from the repo root:
    python3 tools/make_icons.py
"""

from __future__ import annotations

import math
import os
import struct
import zlib

LIME = (0xCC, 0xFF, 0x00)
INK = (0x0B, 0x0B, 0x0B)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <title>LeafBlitz</title>
  <rect x="2" y="2" width="60" height="60" rx="12" fill="#CCFF00" stroke="#0B0B0B" stroke-width="4"/>
  <g transform="rotate(-40 32 32)" fill="#0B0B0B">
    <ellipse cx="32" cy="26" rx="12" ry="18"/>
    <rect x="29.5" y="41" width="5" height="15" rx="2.5"/>
  </g>
  <g transform="rotate(-40 32 32)" stroke="#CCFF00" stroke-width="2" stroke-linecap="round" fill="none">
    <path d="M32 10 V40"/>
    <path d="M32 19 L24.5 14.5 M32 19 L39.5 14.5"/>
    <path d="M32 27 L24.5 22.5 M32 27 L39.5 22.5"/>
    <path d="M32 35 L26 31.5 M32 35 L38 31.5"/>
  </g>
</svg>
"""


def dist_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def leaf_pixel(x: float, y: float, size: int) -> bool:
    """True when (x, y) is inside the leaf body or stem."""
    c = size / 2.0
    # Rotate into leaf-local space (leaf points up-left at -40 degrees).
    ang = math.radians(40)
    lx = (x - c) * math.cos(ang) - (y - c) * math.sin(ang) + c
    ly = (x - c) * math.sin(ang) + (y - c) * math.cos(ang) + c
    rx, ry = size * 0.1875, size * 0.281          # leaf blade radii
    cx, cy = c, c - size * 0.094                  # blade centre
    if ((lx - cx) / rx) ** 2 + ((ly - cy) / ry) ** 2 <= 1.0:
        return True
    # stem
    sw = size * 0.039
    if abs(lx - cx) <= sw and cy + ry * 0.85 <= ly <= cy + ry + size * 0.14:
        return True
    return False


def vein_pixel(x: float, y: float, size: int) -> bool:
    """True when (x, y) sits on a leaf vein (drawn back in lime)."""
    c = size / 2.0
    ang = math.radians(40)
    lx = (x - c) * math.cos(ang) - (y - c) * math.sin(ang) + c
    ly = (x - c) * math.sin(ang) + (y - c) * math.cos(ang) + c
    cx, cy = c, c - size * 0.094
    ry = size * 0.281
    w = max(1.0, size * 0.016)
    if abs(lx - cx) <= w and cy - ry * 0.9 <= ly <= cy + ry * 0.9:
        return True                                   # midrib
    for frac in (-0.42, 0.0, 0.42):                   # side veins
        oy = cy + ry * frac
        for sign in (-1, 1):
            ax, ay = cx, oy
            bx, by = cx + sign * size * 0.15, oy - size * 0.085
            if dist_to_segment(lx, ly, ax, ay, bx, by) <= w:
                return True
    return False


def render_png(size: int = 180) -> bytes:
    border = max(6, size // 15)
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            if x < border or y < border or x >= size - border or y >= size - border:
                rgb = INK
            elif leaf_pixel(x + 0.5, y + 0.5, size):
                rgb = LIME if vein_pixel(x + 0.5, y + 0.5, size) else INK
            else:
                rgb = LIME
            row += bytes(rgb)
        rows.append(bytes(row))

    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    svg_path = os.path.join(root, "favicon.svg")
    png_path = os.path.join(root, "apple-touch-icon.png")
    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(SVG)
    with open(png_path, "wb") as fh:
        fh.write(render_png(180))
    print(f"wrote {svg_path} ({os.path.getsize(svg_path)} bytes)")
    print(f"wrote {png_path} ({os.path.getsize(png_path)} bytes)")


if __name__ == "__main__":
    main()
