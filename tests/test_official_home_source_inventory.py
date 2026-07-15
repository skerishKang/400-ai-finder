"""Offline contracts for #1160 official home-route capture inventory.

Tests consume committed fixtures and pure capture helpers only.
No live network is performed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home"
META_PATH = HOME / "capture-metadata.json"
NAV_PATH = HOME / "navigation-inventory.json"
ASSET_PATH = HOME / "asset-inventory.json"
RAW_PATH = HOME / "raw-homepage.html"
NOTES_PATH = HOME / "CAPTURE-NOTES.md"
SCRIPT_PATH = ROOT / "scripts" / "capture_official_home_inventory.py"

REDACTED = "[REDACTED_SESSION_CSRF]"


def _load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_official_home_inventory", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


capture = _load_capture_module()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Committed fixture contracts ────────────────────────────────────


def test_capture_files_exist():
    for path in (META_PATH, NAV_PATH, ASSET_PATH, RAW_PATH, NOTES_PATH):
        assert path.is_file(), f"missing capture file: {path}"


def test_metadata_schema_and_exact_origin_policy():
    meta = _load_json(META_PATH)
    assert meta["schema_version"] == 1
    assert meta["inventory_kind"] == "official_home_source_inventory"
    assert meta["status"] == "capture_only"
    assert meta["route_id"] == "home"

    source = meta["source"]
    for field in (
        "requested_url",
        "final_resolved_url",
        "http_status",
        "content_type",
        "character_encoding",
        "official_page_title",
        "captured_at",
        "raw_content_sha256",
        "capture_method",
        "capture_tool",
        "sanitization_notes",
    ):
        assert field in source, f"missing source.{field}"
        assert source[field] not in (None, "", "-"), f"blank/placeholder source.{field}"

    assert capture.is_approved_bukgu_https_url(source["requested_url"])
    assert capture.is_approved_bukgu_https_url(source["final_resolved_url"])
    assert source["http_status"] == 200
    assert "html" in str(source["content_type"]).lower()
    assert source["official_page_title"].strip()
    assert source["official_page_title"] != "-"

    captured = datetime.fromisoformat(source["captured_at"])
    assert captured.tzinfo is not None

    if source.get("source_updated_at") in (None, ""):
        assert source.get("source_updated_at_absence_reason")
        assert source["source_updated_at_absence_reason"] not in ("-", "unknown")
    else:
        assert source["source_updated_at"] != "-"

    assert isinstance(source.get("redirect_chain"), list)
    assert source["redirect_chain"]
    notes = source["sanitization_notes"]
    for required in capture.SANITIZATION_NOTES:
        assert required in notes


def test_metadata_checksum_matches():
    meta = _load_json(META_PATH)
    claimed = meta["metadata_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", claimed)
    assert capture.metadata_checksum(meta) == claimed


def test_raw_snapshot_checksum_matches_sanitized_bytes():
    meta = _load_json(META_PATH)
    raw = RAW_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == meta["source"]["raw_content_sha256"]
    assert len(raw) == meta["source"]["raw_byte_length"]
    assert len(raw) > 1000
    # Committed raw must equal sanitize(decode) style LF ending
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert b"\r" not in raw


def test_navigation_inventory_hierarchy_and_labels():
    nav = _load_json(NAV_PATH)
    assert nav["schema_version"] == 1
    assert nav["route_id"] == "home"
    assert nav["item_count"] > 0
    assert len(nav["items"]) == nav["item_count"]
    assert nav["section_counts"]
    assert isinstance(nav.get("hierarchy"), list)
    assert nav["hierarchy"], "top-level hierarchy must be nonempty"

    orders = [item["order"] for item in nav["items"]]
    assert orders == sorted(orders)
    assert orders == list(range(1, len(orders) + 1))

    blank = 0
    for item in nav["items"]:
        for field in (
            "order",
            "section",
            "visible_label",
            "label_source",
            "source_url",
            "capture_result",
            "ancestor_sections",
            "hierarchy_depth",
        ):
            assert field in item
        assert item["source_url"] != "-"
        assert item["visible_label"] != "-"
        assert item["label_source"]
        if item["visible_label"] == "":
            blank += 1
            assert item.get("label_absence_reason")
            assert item["label_absence_reason"] not in ("-", "unknown", "")
        else:
            assert item.get("label_absence_reason") in (None, "")
        assert isinstance(item["ancestor_sections"], list)
        assert item["ancestor_sections"]
        assert isinstance(item["hierarchy_depth"], int)
        assert item["hierarchy_depth"] >= 0
    assert blank == nav.get("blank_label_count", blank)


def test_asset_inventory_partial_hash_scope():
    assets = _load_json(ASSET_PATH)
    assert assets["schema_version"] == 1
    assert assets["item_count"] > 0
    assert len(assets["items"]) == assets["item_count"]
    assert "partial_hash_limit_bytes" in assets
    assert assets["partial_hash_limit_bytes"] == 65536

    partial = 0
    redirected = 0
    for item in assets["items"]:
        for field in (
            "source_url",
            "resolved_url",
            "asset_type",
            "capture_result",
            "local_copy_recommendation",
        ):
            assert field in item
        assert item["source_url"] != "-"
        assert item["asset_type"] != "-"
        if item.get("capture_result") == "partial_body_hashed":
            partial += 1
            assert item.get("hash_scope") == "first_65536_bytes"
            assert isinstance(item.get("hashed_byte_count"), int)
            assert 0 < item["hashed_byte_count"] <= 65536
            assert item.get("sha256")
            assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        if item.get("redirected"):
            redirected += 1
            assert isinstance(item.get("redirect_chain"), list)
    assert partial == assets.get("partial_hash_count", partial)
    assert redirected == assets.get("redirected_asset_count", redirected)


def test_no_placeholder_dash_values_in_core_metadata_fields():
    meta = _load_json(META_PATH)
    source = meta["source"]
    for key, value in source.items():
        if isinstance(value, str):
            assert value != "-", f"source.{key} must not use '-' placeholder"
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for ek, ev in entry.items():
                        if isinstance(ev, str):
                            assert ev != "-", f"redirect_chain.{ek} must not use '-'"


def test_json_notes_have_no_private_response_secrets():
    patterns = (
        re.compile(r"set-cookie\s*:", re.I),
        re.compile(r"authorization\s*:\s*\S+", re.I),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    )
    for path in (META_PATH, NAV_PATH, ASSET_PATH, NOTES_PATH):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            assert not pattern.search(text), f"{path.name} matched {pattern.pattern}"


def test_raw_homepage_csrf_and_secret_safety():
    raw = RAW_PATH.read_text(encoding="utf-8")
    # All _csrf meta content values redacted
    meta_csrf = re.findall(
        r'<meta\b[^>]*\bname\s*=\s*["\']?_csrf["\']?[^>]*>',
        raw,
        flags=re.I,
    )
    assert meta_csrf, "expected at least one _csrf meta tag in official homepage"
    for tag in meta_csrf:
        m = re.search(r'content\s*=\s*"([^"]*)"', tag, flags=re.I)
        assert m, tag
        assert m.group(1) == REDACTED
    assert REDACTED in raw
    # No unredacted UUID-looking csrf values
    assert not re.search(
        r'name\s*=\s*["\']?_csrf["\']?[^>]*value\s*=\s*"[0-9a-fA-F-]{20,}"',
        raw,
        flags=re.I,
    )
    assert not re.search(
        r'name\s*=\s*["\']?_csrf["\']?[^>]*content\s*=\s*"[0-9a-fA-F-]{20,}"',
        raw,
        flags=re.I,
    )
    assert "Set-Cookie:" not in raw
    assert not re.search(r"Authorization\s*:\s*\S+", raw)
    assert "-----BEGIN" not in raw
    # Public source may set document.cookie — allowed
    # (do not fail on document.cookie=)


def test_boundaries_and_capture_only_status():
    meta = _load_json(META_PATH)
    b = meta["boundaries"]
    for key in (
        "firecrawl",
        "provider_api",
        "login",
        "form_submission",
        "payment",
        "pii",
        "canvas_integration",
        "route_status_change",
    ):
        assert b.get(key) is False
    notes = NOTES_PATH.read_text(encoding="utf-8")
    assert notes.count("## Sanitization") == 1
    assert "capture_required" in notes
    assert "status: exact" not in notes.lower()


def test_home_manifest_entry_remains_capture_required():
    manifest_path = ROOT / "tests" / "fixtures" / "official_site_clone_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cap = [e for e in manifest.get("capture_required", []) if e.get("route_id") == "home"]
    assert cap
    assert cap[0].get("status") == "capture_required"
    pages = [e for e in manifest.get("pages", []) if e.get("route_id") == "home"]
    assert not pages


def test_no_login_payment_submission_recorded_as_executed_action():
    meta = _load_json(META_PATH)
    assert meta["boundaries"]["login"] is False
    assert meta["boundaries"]["payment"] is False
    assert meta["boundaries"]["form_submission"] is False
    nav = _load_json(NAV_PATH)
    for item in nav["items"]:
        assert item["capture_result"] == "recorded"
        assert "executed" not in str(item.get("capture_result", "")).lower()


# ── Pure helper unit tests ─────────────────────────────────────────


def test_sanitize_public_html_crlf_cr_tabs_trailing_and_csrf():
    raw = (
        "<html>\r\n"
        "\t<meta name=\"_csrf\" content=\"abc-123-session\">\r"
        "<meta content=\"xyz-999\" name=\"_csrf\">\n"
        "<input type=\"hidden\" name=\"_csrf\" value=\"uuid-1\">  \n"
        "<input value=\"uuid-2\" name=\"_csrf\">\n"
        "<meta name=\"description\" content=\"전남광주통합특별시 북구\">\n"
        "line with trailing   \n"
        "</html>"
    )
    out = capture.sanitize_public_html(raw)
    assert "\r" not in out
    assert "\t" not in out
    assert out.endswith("\n")
    assert not out.endswith("\n\n")
    assert out.count(REDACTED) >= 4
    assert "abc-123-session" not in out
    assert "uuid-1" not in out
    assert "전남광주통합특별시 북구" in out
    assert "trailing   \n" not in out
    # deterministic
    out2 = capture.sanitize_public_html(raw)
    assert out == out2
    assert hashlib.sha256(out.encode()).hexdigest() == hashlib.sha256(out2.encode()).hexdigest()


def test_sanitize_preserves_unrelated_meta_and_final_lf():
    raw = '<meta name="viewport" content="width=device-width">\n'
    out = capture.sanitize_public_html(raw)
    assert 'name="viewport"' in out
    assert out.endswith("\n")
    assert capture.sanitize_public_html(out + "\n\n").endswith("\n")
    assert not capture.sanitize_public_html(out + "\n\n").endswith("\n\n")


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://bukgu.gwangju.kr/", True),
        ("https://bukgu.gwangju.kr/path?q=1", True),
        ("https://bukgu.gwangju.kr:443/", True),
        ("http://bukgu.gwangju.kr/", False),
        ("https://bukgu.gwangju.kr.evil.test/", False),
        ("https://evil-bukgu.gwangju.kr/", False),
        ("https://user@bukgu.gwangju.kr/", False),
        ("https://bukgu.gwangju.kr:444/", False),
        ("javascript:alert(1)", False),
        ("data:text/html,hi", False),
        ("//bukgu.gwangju.kr/", False),
        ("", False),
    ],
)
def test_approved_origin_exact_policy(url, ok):
    assert capture.is_approved_bukgu_https_url(url) is ok


def test_fetch_redirect_recording_with_mock_opener():
    class FakeResp:
        def __init__(self, status, headers, body=b"", url=""):
            self.status = status
            self.headers = headers
            self._body = body
            self._url = url

        def read(self):
            return self._body

        def geturl(self):
            return self._url

        def getcode(self):
            return self.status

    hops = {
        "https://bukgu.gwangju.kr/start": (
            302,
            {"Location": "/next", "Content-Type": "text/html"},
            b"",
        ),
        "https://bukgu.gwangju.kr/next": (
            200,
            {"Content-Type": "text/html;charset=UTF-8"},
            b"<html><title>OK</title></html>",
        ),
    }

    class FakeOpener:
        def open(self, req, timeout=0):  # noqa: ANN001
            url = req.full_url
            status, headers, body = hops[url]
            # Simulate urllib HTTPError path for redirects via our NoFollow handler:
            # we return response-like for both
            return FakeResp(status, headers, body, url)

    result = capture.fetch_with_redirect_recording(
        "https://bukgu.gwangju.kr/start",
        opener=FakeOpener(),
        timeout=5,
        max_hops=5,
        read_body=True,
    )
    assert result["status"] == 200
    assert result["final_url"] == "https://bukgu.gwangju.kr/next"
    assert result["redirected"] is True
    assert [h["status"] for h in result["redirect_chain"]] == [302, 200]
    assert result["redirect_chain"][0]["location"] == "/next"


def test_redirect_rejects_external_and_loop_and_missing_location():
    class FakeResp:
        def __init__(self, status, headers, body=b"", url=""):
            self.status = status
            self.headers = headers
            self._body = body
            self._url = url

        def read(self):
            return self._body

        def geturl(self):
            return self._url

        def getcode(self):
            return self.status

    class ExternalOpener:
        def open(self, req, timeout=0):  # noqa: ANN001
            return FakeResp(302, {"Location": "https://evil.example/"}, b"", req.full_url)

    with pytest.raises(capture.CaptureError, match="not approved"):
        capture.fetch_with_redirect_recording(
            "https://bukgu.gwangju.kr/",
            opener=ExternalOpener(),
            timeout=5,
        )

    class MissingLoc:
        def open(self, req, timeout=0):  # noqa: ANN001
            return FakeResp(302, {}, b"", req.full_url)

    with pytest.raises(capture.CaptureError, match="missing Location"):
        capture.fetch_with_redirect_recording(
            "https://bukgu.gwangju.kr/",
            opener=MissingLoc(),
            timeout=5,
        )

    class LoopOpener:
        def open(self, req, timeout=0):  # noqa: ANN001
            return FakeResp(302, {"Location": "/a"}, b"", req.full_url)

    # /a -> /a loop via relative same path after first hop from /
    class LoopOpener2:
        def open(self, req, timeout=0):  # noqa: ANN001
            if req.full_url.endswith("/a"):
                return FakeResp(302, {"Location": "/a"}, b"", req.full_url)
            return FakeResp(302, {"Location": "/a"}, b"", req.full_url)

    with pytest.raises(capture.CaptureError, match="loop"):
        capture.fetch_with_redirect_recording(
            "https://bukgu.gwangju.kr/",
            opener=LoopOpener2(),
            timeout=5,
            max_hops=5,
        )


def test_asset_redirect_to_external_not_hashed():
    items = [
        {
            "source_url": "/a.png",
            "requested_url": "https://bukgu.gwangju.kr/a.png",
            "resolved_url": "https://bukgu.gwangju.kr/a.png",
            "asset_type": "image",
            "tag": "img",
            "section": "header",
            "same_origin": True,
            "redirected": False,
            "redirect_chain": [],
            "response_status": None,
            "content_type": None,
            "size_bytes": None,
            "sha256": None,
            "hash_scope": None,
            "hashed_byte_count": None,
            "capture_result": "listed",
            "failure_reason": None,
            "local_copy_recommendation": "defer_until_exact_integration",
            "licensing_note": "x",
        }
    ]

    def fetch_fn(url: str):
        return {
            "final_url": "https://cdn.evil.test/a.png",
            "status": 200,
            "headers": {"content-type": "image/png"},
            "body": b"12345",
            "redirect_chain": [
                {"url": url, "status": 302, "location": "https://cdn.evil.test/a.png"},
                {"url": "https://cdn.evil.test/a.png", "status": 200, "location": None},
            ],
            "redirected": True,
        }

    probed = capture.probe_asset_items(items, fetch_fn=fetch_fn, probe_limit=5)
    assert probed == 1
    assert items[0]["same_origin"] is False
    assert items[0]["capture_result"] == "redirected_off_origin_unhashed"
    assert items[0]["sha256"] is None
    assert items[0]["redirected"] is True


def test_external_asset_listed_without_fetch():
    items = [
        {
            "source_url": "https://example.com/x.js",
            "requested_url": "https://example.com/x.js",
            "resolved_url": "https://example.com/x.js",
            "asset_type": "javascript",
            "tag": "script",
            "section": "document",
            "same_origin": False,
            "redirected": False,
            "redirect_chain": [],
            "response_status": None,
            "content_type": None,
            "size_bytes": None,
            "sha256": None,
            "hash_scope": None,
            "hashed_byte_count": None,
            "capture_result": "listed",
            "failure_reason": None,
            "local_copy_recommendation": "do_not_localize_external",
            "licensing_note": "x",
        }
    ]
    called = {"n": 0}

    def fetch_fn(url: str):
        called["n"] += 1
        raise AssertionError("must not fetch external")

    capture.probe_asset_items(items, fetch_fn=fetch_fn, probe_limit=5)
    assert called["n"] == 0
    assert items[0]["capture_result"] == "listed_external_unfetched"


def test_navigation_label_fallbacks_and_hierarchy():
    html = """
    <header class="top util"><a href="/u" aria-label="유틸 링크"></a></header>
    <nav class="gnb"><a href="/g" title="글로벌"><img src="/i.png" alt=""></a></nav>
    <main><a href="/m"><img src="/x.png" alt="배너 이미지"></a>
    <a href="/blank"></a></main>
    <footer><a href="/f">푸터</a></footer>
    """
    parsed = capture.parse_homepage_inventories(html, "https://bukgu.gwangju.kr/")
    labels = {(i["source_url"], i["label_source"], i["visible_label"]) for i in parsed["nav_items"]}
    assert ("/u", "aria-label", "유틸 링크") in labels
    assert ("/g", "title", "글로벌") in labels
    assert ("/m", "child_image_alt", "배너 이미지") in labels
    blank = [i for i in parsed["nav_items"] if i["source_url"] == "/blank"][0]
    assert blank["visible_label"] == ""
    assert blank["label_source"] == "absent"
    assert blank["label_absence_reason"]
    assert parsed["hierarchy"]
    assert all("ancestor_sections" in i for i in parsed["nav_items"])


def test_mocked_reproducibility_bundle(tmp_path: Path):
    html = """<!DOCTYPE html>
<html><head>
<meta name="_csrf" content="session-token-aaa">
<title>전남광주통합특별시 북구</title>
</head>
<body>
<header class="util"><a href="/menu.es?mid=a1">주요사이트</a></header>
<nav class="gnb"><a href="/menu.es?mid=a2">전자민원</a></nav>
<img src="/kor/img/logo.png" alt="로고">
<script src="https://example.com/ext.js"></script>
<footer><a href="/menu.es?mid=a3">개인정보처리방침</a></footer>
</body></html>
"""
    raw_body = html.replace("\n", "\r\n").encode("utf-8")
    captured_at = "2026-07-15T00:00:00+09:00"
    finished_at = "2026-07-15T00:00:01+09:00"

    def asset_fetch(url: str):
        assert capture.is_approved_bukgu_https_url(url)
        return {
            "final_url": url,
            "status": 200,
            "headers": {"content-type": "image/png", "content-length": "4"},
            "body": b"\x89PNG",
            "redirect_chain": [{"url": url, "status": 200, "location": None}],
            "redirected": False,
        }

    out1 = tmp_path / "run1"
    meta1 = capture.generate_capture_from_homepage_response(
        out_dir=out1,
        requested_url="https://bukgu.gwangju.kr/",
        final_url="https://bukgu.gwangju.kr/",
        status=200,
        content_type="text/html;charset=UTF-8",
        character_encoding="utf-8",
        redirect_chain=[{"url": "https://bukgu.gwangju.kr/", "status": 200, "location": None}],
        response_body=raw_body,
        captured_at=captured_at,
        capture_finished_at=finished_at,
        asset_fetch_fn=asset_fetch,
        probe_limit=5,
    )
    out2 = tmp_path / "run2"
    meta2 = capture.generate_capture_from_homepage_response(
        out_dir=out2,
        requested_url="https://bukgu.gwangju.kr/",
        final_url="https://bukgu.gwangju.kr/",
        status=200,
        content_type="text/html;charset=UTF-8",
        character_encoding="utf-8",
        redirect_chain=[{"url": "https://bukgu.gwangju.kr/", "status": 200, "location": None}],
        response_body=raw_body,
        captured_at=captured_at,
        capture_finished_at=finished_at,
        asset_fetch_fn=asset_fetch,
        probe_limit=5,
    )

    raw1 = (out1 / "raw-homepage.html").read_bytes()
    raw2 = (out2 / "raw-homepage.html").read_bytes()
    expected = capture.sanitize_public_html(raw_body.decode("utf-8")).encode("utf-8")
    assert raw1 == expected == raw2
    assert meta1["source"]["raw_content_sha256"] == hashlib.sha256(expected).hexdigest()
    assert meta1["metadata_sha256"] == meta2["metadata_sha256"]
    assert meta1["source"]["raw_content_sha256"] == meta2["source"]["raw_content_sha256"]
    notes = (out1 / "CAPTURE-NOTES.md").read_text(encoding="utf-8")
    assert notes.count("## Sanitization") == 1
    assert REDACTED in raw1.decode("utf-8")
    assert "session-token-aaa" not in raw1.decode("utf-8")
    nav1 = (out1 / "navigation-inventory.json").read_text(encoding="utf-8")
    nav2 = (out2 / "navigation-inventory.json").read_text(encoding="utf-8")
    assert nav1 == nav2
    assets1 = json.loads((out1 / "asset-inventory.json").read_text(encoding="utf-8"))
    # external script unfetched
    ext = [i for i in assets1["items"] if "example.com" in i["resolved_url"]]
    assert ext and ext[0]["capture_result"] == "listed_external_unfetched"
    # same-origin image partially hashed
    img = [i for i in assets1["items"] if i["resolved_url"].endswith("/kor/img/logo.png")][0]
    assert img["capture_result"] == "partial_body_hashed"
    assert img["hash_scope"] == "first_65536_bytes"
