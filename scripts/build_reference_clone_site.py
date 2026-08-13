"""Build the #1303 G2-B Seo-gu faithful-clone candidate site (offline).

Reads the committed G2-A semantic ``clone-model.json`` for the Seo-gu reference
capture and renders the deterministic local clone structure under the Seo-gu
route namespace (``/seogu/``) using the generic
``src/official_clone/reference_clone_renderer.py``.

Zero network. The renderer is model-driven and site-generic; this script only
selects the Seo-gu canonical fixture as the G2-B build input.

Usage:
    python scripts/build_reference_clone_site.py [--out-dir DIR] [--model PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_renderer():
    """Import the generic renderer by file path (no site-specific coupling)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "reference_clone_renderer",
        _REPO_ROOT / "src" / "official_clone" / "reference_clone_renderer.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default_model_path() -> Path:
    return (
        _REPO_ROOT
        / "data"
        / "official_clone_fixtures"
        / "seogu_gwangju"
        / "g1"
        / "20260812T231018-0900"
        / "clone-model.json"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Build the Seo-gu G2-B clone candidate site")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: dist/seogu-clone)")
    parser.add_argument(
        "--model",
        default=str(default_model_path()),
        help="Path to the G2-A clone-model.json (default: Seo-gu canonical fixture)",
    )
    parsed = parser.parse_args(args)

    out_dir = Path(parsed.out_dir) if parsed.out_dir else (_REPO_ROOT / "dist" / "seogu-clone")
    model_path = Path(parsed.model)
    if not model_path.is_file():
        print(f"REFERENCE_CLONE_SITE_ERROR: model not found: {model_path}")
        return 2

    renderer = _load_renderer()
    model = renderer.load_model(model_path)
    written = renderer.write_site(model, out_dir)
    checksum = renderer.model_checksum(model)
    print(f"WROTE {len(written)} clone routes -> {out_dir}")
    print(f"SITE_CHECKSUM {checksum}")
    for path in sorted(written):
        try:
            rel = path.relative_to(_REPO_ROOT)
        except ValueError:
            rel = path
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
