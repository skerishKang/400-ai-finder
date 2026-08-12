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
- unsafe output paths fail closed *before* any file is written:
    * the out-dir itself must not be a symlink;
    * no existing path component beneath the out-dir may be a symlink
      (e.g. a pre-created ``OUT/routes -> /elsewhere`` is rejected, not
      followed);
    * the final target must not be an existing symlink;
    * every resolved target parent must stay inside the resolved out-dir.
  Symlinks are never silently unlinked or replaced - they are rejected.
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

MANIFEST_REL = "preview-manifest.json"

EXIT_OK = 0
EXIT_RENDER_REJECTED = 1
EXIT_UNSAFE_OUTPUT = 2
EXIT_BAD_INPUT = 2


class UnsafeOutputPath(Exception):
    """Raised when an output path is not provably inside the out-dir."""


def _validate_rel(rel: str) -> list[str]:
    """Reject absolute paths, traversal and odd segments; return components."""
    if not isinstance(rel, str) or not rel:
        raise UnsafeOutputPath("empty output path")
    if "\\" in rel:
        raise UnsafeOutputPath(f"backslash in output path rejected: {rel}")
    if rel.startswith("/") or os.path.isabs(rel) or ":" in rel:
        raise UnsafeOutputPath(f"absolute output path rejected: {rel}")
    parts = rel.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise UnsafeOutputPath(f"unsafe path segment rejected: {rel}")
    return parts


def _require_inside(path: Path, out_root: Path, rel: str) -> None:
    """Fail closed unless ``path`` resolves to ``out_root`` or below it."""
    resolved = path.resolve()
    if resolved != out_root and out_root not in resolved.parents:
        raise UnsafeOutputPath(f"output path escapes out-dir: {rel} -> {resolved}")


def _safe_target(
    out_dir: Path, out_root: Path, rel: str, *, create_parents: bool
) -> Path:
    """Resolve ``rel`` beneath ``out_dir`` fail-closed.

    Walks the component chain top-down and inspects each component with lstat
    (``is_symlink``) *before* following it, so an unsafe component is rejected
    instead of traversed. ``Path.resolve()`` alone is not sufficient here: it
    would happily follow an escaping symlink and report a path that merely
    looks settled. The symlink itself is the fail-closed condition.
    """
    parts = _validate_rel(rel)

    current = out_dir
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise UnsafeOutputPath(
                f"symlinked path component rejected: {rel} ({current})"
            )
        if current.exists():
            if not current.is_dir():
                raise UnsafeOutputPath(
                    f"non-directory path component rejected: {rel} ({current})"
                )
        elif create_parents:
            current.mkdir()
            if current.is_symlink():  # pragma: no cover - defensive
                raise UnsafeOutputPath(
                    f"symlinked path component rejected: {rel} ({current})"
                )
        if current.exists():
            _require_inside(current, out_root, rel)

    target = current / parts[-1]
    if target.is_symlink():
        raise UnsafeOutputPath(f"symlinked output target rejected: {rel} ({target})")
    if target.exists() and not target.is_file():
        raise UnsafeOutputPath(f"output target is not a regular file: {rel}")
    if target.parent.exists():
        _require_inside(target.parent, out_root, rel)
        _require_inside(target.parent.resolve() / target.name, out_root, rel)
    return target


def _write_bytes_nofollow(target: Path, payload: bytes) -> None:
    """Write ``payload`` without ever following a symlink at the final path."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0)
    fd = os.open(target, flags, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(payload)


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
        return EXIT_BAD_INPUT

    out_dir = Path(args.out_dir)
    # Check before any mkdir so an unsafe out-dir has zero side effects.
    if out_dir.is_symlink():
        print("error: out-dir must not be a symlink", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create out-dir: {exc}", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT
    if out_dir.is_symlink() or not out_dir.is_dir():
        print("error: out-dir must be a real directory", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT
    out_root = out_dir.resolve(strict=True)

    try:
        with bundle_path.open("r", encoding="utf-8") as fh:
            bundle = json.load(fh)
        result = build_offline_preview(bundle)
    except OfflinePreviewError as exc:
        print(f"error: offline preview rejected: {exc}", file=sys.stderr)
        return EXIT_RENDER_REJECTED
    except Exception as exc:  # noqa: BLE001
        print(f"error: failed to build offline preview: {exc}", file=sys.stderr)
        return EXIT_RENDER_REJECTED

    manifest = result["manifest"]
    pages = result["pages"]

    payloads: list[tuple[str, bytes]] = [
        (rel, html_text.encode("utf-8")) for rel, html_text in pages.items()
    ]
    payloads.append(
        (
            MANIFEST_REL,
            (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )
    )

    # Phase 1: validate every target before writing anything, so a rejected
    # path never leaves a partially written preview behind.
    try:
        for rel, _payload in payloads:
            _safe_target(out_dir, out_root, rel, create_parents=False)
    except UnsafeOutputPath as exc:
        print(f"error: unsafe output path: {exc}", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT

    # Phase 2: create parents safely and write.
    written = []
    try:
        for rel, payload in payloads:
            target = _safe_target(out_dir, out_root, rel, create_parents=True)
            _write_bytes_nofollow(target, payload)
            written.append(rel)
    except UnsafeOutputPath as exc:
        print(f"error: unsafe output path: {exc}", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT
    except OSError as exc:
        print(f"error: refused to write output: {exc}", file=sys.stderr)
        return EXIT_UNSAFE_OUTPUT

    print(
        "offline preview built: "
        f"{manifest['route_count']} routes, "
        f"{manifest['action_count']} modeled actions, "
        f"{len(written)} files -> {out_dir}"
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
