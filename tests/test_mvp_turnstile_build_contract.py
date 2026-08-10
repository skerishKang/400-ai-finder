from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_live_cloudflare_build_contains_turnstile_client(tmp_path: Path) -> None:
    """The live Pages build must publish the exact Turnstile client/bridge assets."""

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_cloudflare_pages.py",
            "--mode",
            "live",
            "--out-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    source_static = REPO_ROOT / "src" / "web" / "static"
    built_static = tmp_path / "static"

    for filename in ("citizen-mvp-bridge.js", "citizen-turnstile.js"):
        source = source_static / filename
        built = built_static / filename
        assert source.is_file(), f"missing source asset: {source}"
        assert built.is_file(), f"missing live-build asset: {built}"
        assert built.read_bytes() == source.read_bytes(), (
            f"live build must copy {filename} verbatim from src/web/static"
        )

    bridge_text = (built_static / "citizen-mvp-bridge.js").read_text(encoding="utf-8")
    assert 'var TURNSTILE_CLIENT_SRC = "/static/citizen-turnstile.js";' in bridge_text

    shell_text = (built_static / "citizen-first-use-shell.js").read_text(encoding="utf-8")
    assert "citizen-mvp-bridge.js" in shell_text

    mvp_html = (tmp_path / "mvp" / "index.html").read_text(encoding="utf-8")
    assert 'u.searchParams.set("mvp", "1")' in mvp_html

    # Header/CSP policy is deployment configuration, not an implicit build side
    # effect. If a Cloudflare _headers policy is introduced later, it must be
    # reviewed explicitly for the Turnstile script/frame origins.
    assert not (tmp_path / "_headers").exists(), (
        "live build must not invent an unreviewed Cloudflare _headers policy"
    )
