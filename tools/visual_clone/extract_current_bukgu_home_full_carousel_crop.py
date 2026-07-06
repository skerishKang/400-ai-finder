#!/usr/bin/env python3
"""Extract the R-HOME-02 carousel banner crop for #868 full-home state alignment.

Offline only. Verifies source SHA-256 and dimensions before cropping.
Outputs one PNG to the bukgu-current directory.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "docs/artifacts/863-reference/source/CaptureX_2026-07-05_150832_bukgu.gwangju.kr_full.png"
OUTPUT = ROOT / "src/web/static/images/bukgu-current/home-alert-banner-r-home-02.png"

EXPECTED_SOURCE_HASH = "e0c1d451312056a5314fa2dc5b77d62fb53ef6dc90352797d78e4bb57eae3c49"
EXPECTED_SOURCE_SIZE = (1344, 1833)
BOX = (562, 258, 1123, 555)
EXPECTED_CROP_SIZE = (561, 297)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not SOURCE.is_file():
        print(f"ERROR: source not found: {SOURCE}", file=sys.stderr)
        return 2

    actual_hash = sha256(SOURCE)
    if actual_hash != EXPECTED_SOURCE_HASH:
        print(f"ERROR: SHA mismatch\n  expected: {EXPECTED_SOURCE_HASH}\n  actual:   {actual_hash}", file=sys.stderr)
        return 3

    with Image.open(SOURCE) as image:
        image.load()
        if image.size != EXPECTED_SOURCE_SIZE:
            print(f"ERROR: source size mismatch: {image.size}", file=sys.stderr)
            return 4

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        crop = image.crop(BOX)

        if crop.size != EXPECTED_CROP_SIZE:
            print(f"ERROR: crop size mismatch: {crop.size}", file=sys.stderr)
            return 5

        crop.save(OUTPUT, format="PNG", optimize=False)

    with Image.open(OUTPUT) as final:
        final.load()
        assert final.size == EXPECTED_CROP_SIZE, final.size

    print(OUTPUT)
    print(f"sha256={sha256(OUTPUT)}")
    print(f"size={EXPECTED_CROP_SIZE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
