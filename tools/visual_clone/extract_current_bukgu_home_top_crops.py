#!/usr/bin/env python3
"""Extract approved #868 current-home top crops from the R-HOME-01 source.

This tool is intentionally offline-only. It verifies the exact source SHA-256,
uses the approved crop rectangles from docs/design/863-current-home-crop-manifest.md,
and writes lossless PNG crops without altering the source file.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from PIL import Image

EXPECTED_SOURCE_SHA256 = "e851f990a710b13251700177e8355f18477fcceb5c5e8497a9504e085e2d2397"
EXPECTED_SOURCE_SIZE = (1344, 756)

CROPS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("home-identity.png", (220, 70, 390, 112)),
    ("home-civic-brand.png", (220, 165, 505, 220)),
    ("home-mayor-card.png", (210, 258, 555, 555)),
    ("home-alert-banner.png", (562, 258, 1123, 555)),
    ("home-quick-work.png", (379, 605, 420, 646)),
    ("home-quick-office.png", (472, 605, 513, 646)),
    ("home-quick-donation.png", (588, 605, 629, 646)),
    ("home-quick-money.png", (694, 605, 735, 646)),
    ("home-quick-reservation.png", (807, 605, 848, 646)),
    ("home-quick-waiting.png", (914, 605, 955, 646)),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            "docs/artifacts/863-reference/source/"
            "CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png"
        ),
        help="Approved R-HOME-01 source PNG.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("src/web/static/images/bukgu-current"),
        help="Directory for derived PNG crops.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify source and print planned output without writing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source

    if not source.is_file():
        print(f"ERROR: source file not found: {source}", file=sys.stderr)
        return 2

    actual_hash = sha256(source)
    if actual_hash != EXPECTED_SOURCE_SHA256:
        print(
            "ERROR: source SHA-256 mismatch\n"
            f"expected: {EXPECTED_SOURCE_SHA256}\n"
            f"actual:   {actual_hash}",
            file=sys.stderr,
        )
        return 3

    with Image.open(source) as image:
        image.load()
        if image.size != EXPECTED_SOURCE_SIZE:
            print(
                "ERROR: source dimensions mismatch\n"
                f"expected: {EXPECTED_SOURCE_SIZE}\n"
                f"actual:   {image.size}",
                file=sys.stderr,
            )
            return 4

        if args.check_only:
            for filename, (left, top, right, bottom) in CROPS:
                print(f"PLAN {filename}: {right - left}x{bottom - top} @ [{left}, {top}, {right}, {bottom})")
            return 0

        args.output_dir.mkdir(parents=True, exist_ok=True)
        for filename, box in CROPS:
            crop = image.crop(box)
            destination = args.output_dir / filename
            crop.save(destination, format="PNG", optimize=False)
            print(f"WROTE {destination} sha256={sha256(destination)} size={crop.size[0]}x{crop.size[1]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
