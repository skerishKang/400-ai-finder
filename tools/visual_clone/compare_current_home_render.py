#!/usr/bin/env python3
"""Compare a #868 local home render with the immutable R-HOME-01 reference.

The script never resizes or edits either input. It requires both images to be
1344x756 and writes an unmodified-size overlay, absolute RGB diff, and compact
comparison metadata into the requested output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

EXPECTED_REFERENCE_SHA256 = "e851f990a710b13251700177e8355f18477fcceb5c5e8497a9504e085e2d2397"
EXPECTED_SIZE = (1344, 756)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(
            "docs/artifacts/863-reference/source/"
            "CaptureX_2026-07-05_150817_bukgu.gwangju.kr.png"
        ),
    )
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def require_image(path: Path, label: str) -> Image.Image:
    if not path.is_file():
        raise RuntimeError(f"{label} file not found: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != EXPECTED_SIZE:
        raise RuntimeError(f"{label} dimensions {image.size}; expected {EXPECTED_SIZE}")
    return image


def main() -> int:
    args = parse_args()
    reference_hash = sha256(args.reference)
    if reference_hash != EXPECTED_REFERENCE_SHA256:
        print(
            f"ERROR: reference SHA-256 mismatch: {reference_hash}",
            file=sys.stderr,
        )
        return 2

    try:
        reference = require_image(args.reference, "reference")
        render = require_image(args.render, "render")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    args.output_dir.mkdir(parents=True, exist_ok=True)
    overlay = Image.blend(reference, render, 0.5)
    diff = ImageChops.difference(reference, render)
    overlay_path = args.output_dir / "home-overlay-vs-R-HOME-01-1344x756.png"
    diff_path = args.output_dir / "home-diff-vs-R-HOME-01-1344x756.png"
    overlay.save(overlay_path, format="PNG", optimize=False)
    diff.save(diff_path, format="PNG", optimize=False)

    stat = ImageStat.Stat(diff)
    metadata = {
        "reference": str(args.reference),
        "reference_sha256": reference_hash,
        "render": str(args.render),
        "render_sha256": sha256(args.render),
        "dimensions": {"width": EXPECTED_SIZE[0], "height": EXPECTED_SIZE[1]},
        "overlay": str(overlay_path),
        "diff": str(diff_path),
        "mean_absolute_rgb_difference": [round(value, 6) for value in stat.mean],
        "max_rgb_difference": [int(value) for value in stat.extrema[0][1:2] + stat.extrema[1][1:2] + stat.extrema[2][1:2]],
        "note": "Metrics are review evidence only; they are not an automatic visual acceptance gate.",
    }
    (args.output_dir / "home-comparison-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
