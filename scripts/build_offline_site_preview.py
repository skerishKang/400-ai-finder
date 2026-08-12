"""CLI: build the generic offline structural preview from a Site Model bundle.

Usage:
  python scripts/build_offline_site_preview.py \
    --bundle tests/fixtures/platform/site-model/seogu.json \
    --out-dir <TEMP_DIR>

- loads the bundle JSON (no network);
- calls the generic deterministic renderer;
- writes exactly the expected files below the out-dir:
    index.html
    routes/<route_id>.html   (one per non-root route)
    preview-manifest.json
- never writes outside the out-dir;
- unsafe / symlink output paths fail closed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.site_profiles.offline_preview import (  # noqa: E402
    OfflinePreviewError,
    build_offline_preview,
)


def _validate_rel(rel: str) -> None:
    """Reject absolute paths and any path-traversal segment."""
    if not rel:
        raise ValueError("empty output path")
    if rel.startswith("/") or (os.path.altsep and rel.startswith(os.path.altsep)):
        raise ValueError(f"absolute output path rejected: {rel}")
    parts = rel.split("/")
    if ".." in parts:
        raise ValueError(f"path traversal rejected: {rel}")


def _safe_target(out_dir: str, rel: str) -> Path:
    _validate_rel(rel)
    out_abs = os.path.abspath(out_dir)
    target = os.path.abspath(os.path.join(out_abs, rel))
    if target != out_abs and not target.startswith(out_abs + os.sep):
        raise ValueError(f"output path escapes out-dir: {rel}")
    return Path(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle", required=True, help="Path to a Site Model bundle JSON file."
    )
    parser.add_argument(
        "--out-dir", required=True, help="Directory to write preview files into."
    )
    args = parser.parse_args(argv)

    bundle_path = Path(args.bundle)
    if not bundle_path.is_file():
        print(f"error: bundle not found: {bundle_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir.is_symlink():
        print("error: out-dir must not be a symlink", file=sys.stderr)
        return 2

    try:
        with bundle_path.open("r", encoding="utf-8") as fh:
            bundle = json.load(fh)
        result = build_offline_preview(bundle)
    except OfflinePreviewError as exc:
        print(f"error: offline preview rejected: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"error: failed to build offline preview: {exc}", file=sys.stderr)
        return 1

    manifest = result["manifest"]
    pages = result["pages"]

    written = []
    for rel, html_text in pages.items():
        target = _safe_target(str(out_dir), rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")
        written.append(rel)

    manifest_target = _safe_target(str(out_dir), "preview-manifest.json")
    manifest_target.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    written.append("preview-manifest.json")

    print(
        "offline preview built: "
        f"{manifest['route_count']} routes, "
        f"{manifest['action_count']} modeled actions, "
        f"{len(written)} files -> {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
