"""
Solid-colour PNGs for Dopple's required profile and banner uploads.

No Pillow needed — just writes minimal valid PNGs to ./assets/.
"""

from __future__ import annotations

import random
import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
ASSETS.mkdir(exist_ok=True)


def write_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = bytes(rgb) * width
    raw = bytearray()
    for _ in range(height):
        raw.append(0)
        raw.extend(row)
    idat = zlib.compress(bytes(raw), 9)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))
    print(f"  wrote {path.name} ({width}x{height}, {path.stat().st_size} bytes)")


def generate_assets(
    profile_rgb: tuple[int, int, int] | None = None,
    banner_rgb: tuple[int, int, int] | None = None,
) -> None:
    profile = profile_rgb or (37, 99, 235)
    banner = banner_rgb or (15, 23, 42)
    write_png(ASSETS / "profile.png", 512, 512, profile)
    write_png(ASSETS / "banner.png", 1024, 512, banner)


def random_assets() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    profile = (random.randint(40, 200), random.randint(40, 200), random.randint(40, 200))
    banner = (random.randint(10, 80), random.randint(10, 80), random.randint(30, 120))
    generate_assets(profile, banner)
    return profile, banner


if __name__ == "__main__":
    generate_assets()
    print("Done.")
