"""Build the #1303 G2-B faithful-clone candidate site (offline).

Reads the committed G2-A semantic ``clone-model.json`` and the G2-B
``visual-contract.json`` for a named site, then renders the deterministic
local clone structure using the generic
``src/official_clone/reference_clone_renderer.py``.

Zero network. The renderer is model-driven and site-generic; this script only
selects the site-specific fixtures as the G2-B build input.

Usage:
    python scripts/build_reference_clone_site.py --site-id seogu_gwangju \\
        [--out-dir DIR] [--model PATH] [--visual-contract PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from official_clone.visual_contract import (  # noqa: E402
    faithful_ready,
    validate_visual_contract,
)


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


def default_model_path(site_id: str) -> Path:
    return (
        _REPO_ROOT
        / "data"
        / "official_clone_fixtures"
        / site_id
        / "g1"
        / "20260812T231018-0900"
        / "clone-model.json"
    )


def default_visual_contract_path(site_id: str) -> Path:
    return (
        _REPO_ROOT
        / "data"
        / "official_clone_visual_inputs"
        / site_id
        / "g1"
        / "20260812T231018-0900"
        / "visual-contract.json"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Build a G2-B faithful-clone candidate site")
    parser.add_argument("--site-id", default="seogu_gwangju", help="Site identifier")
    parser.add_argument("--out-dir", default=None, help="Output directory")
    parser.add_argument("--model", default=None, help="Path to clone-model.json")
    parser.add_argument("--visual-contract", default=None, help="Path to visual-contract.json")
    parsed = parser.parse_args(args)

    site_id = parsed.site_id
    out_dir = Path(parsed.out_dir) if parsed.out_dir else (_REPO_ROOT / "dist" / f"{site_id}-clone")
    model_path = Path(parsed.model) if parsed.model else default_model_path(site_id)
    vc_path = Path(parsed.visual_contract) if parsed.visual_contract else default_visual_contract_path(site_id)

    # Fail-closed: model must exist.
    if not model_path.is_file():
        print(f"REFERENCE_CLONE_SITE_ERROR: model not found: {model_path}")
        return 2

    # Fail-closed: visual contract must exist AND validate against the model.
    if not vc_path.is_file():
        print(f"REFERENCE_CLONE_SITE_ERROR: visual contract not found: {vc_path}")
        return 2

    renderer = _load_renderer()
    model = renderer.load_model(model_path)
    contract = json.loads(vc_path.read_text(encoding="utf-8"))
    validated = validate_visual_contract(contract, model)
    route_prefix = f"/{site_id.split('_')[0]}/"
    written = renderer.write_site(
        model, out_dir, route_prefix=route_prefix, visual_contract=validated
    )
    checksum = renderer.model_checksum(model)
    print(f"WROTE {len(written)} clone routes -> {out_dir}")
    print(f"SITE_CHECKSUM {checksum}")
    print(f"FAITHFUL_READY {faithful_ready(validated)}")
    for path in sorted(written):
        try:
            rel = path.relative_to(_REPO_ROOT)
        except ValueError:
            rel = path
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())