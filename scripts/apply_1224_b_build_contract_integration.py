from pathlib import Path

path = Path("tests/test_build_cloudflare_pages.py")
text = path.read_text(encoding="utf-8")
marker = "def test_live_build_publishes_turnstile_assets_and_keeps_headers_explicit("
if marker not in text:
    block = r'''

# ---------------------------------------------------------------------------
# #1224-B Turnstile live-build boundary
# ---------------------------------------------------------------------------


def test_live_build_publishes_turnstile_assets_and_keeps_headers_explicit(live_build_dir):
    """LIVE output must publish Turnstile assets without inventing CSP headers."""
    source_static = Path(_REPO_ROOT) / "src" / "web" / "static"
    built_static = Path(live_build_dir) / "static"

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

    shell_text = (built_static / SHELL_SCRIPT).read_text(encoding="utf-8")
    assert "citizen-mvp-bridge.js" in shell_text

    mvp_html = (Path(live_build_dir) / "mvp" / "index.html").read_text(encoding="utf-8")
    assert LIVE_INJECTOR in mvp_html

    # Header/CSP policy is deployment configuration, not an implicit build side
    # effect. A future _headers policy must be reviewed explicitly for Turnstile.
    assert not (Path(live_build_dir) / "_headers").exists(), (
        "live build must not invent an unreviewed Cloudflare _headers policy"
    )
'''
    if "from pathlib import Path\n" not in text:
        anchor = "import tempfile\n"
        if anchor not in text:
            raise SystemExit("import anchor missing")
        text = text.replace(anchor, anchor + "from pathlib import Path\n", 1)
    text = text.rstrip() + block + "\n"
    path.write_text(text, encoding="utf-8")
    print("Turnstile build contract integrated into existing CI-owned test file")
else:
    print("Turnstile build contract already integrated")
