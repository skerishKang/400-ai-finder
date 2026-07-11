"""Deterministic loaders for committed Buk-gu official-page snapshots."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "official_snapshots"
    / "bukgu_gwangju"
)

_ROUTE_ID_RE = re.compile(r"^[a-z0-9-]+$")
_ROW_KEYS = ("department", "team", "position", "phone", "duty")


class OfficialSnapshotError(ValueError):
    """Raised when a committed official snapshot violates its schema."""


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OfficialSnapshotError(f"{label} must be a non-empty string")
    return value.strip()


def _validate_department_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate the original organization-table snapshot shape."""
    page = snapshot["page"]
    columns = page.get("columns")
    if not isinstance(columns, list) or [column.get("key") for column in columns] != list(_ROW_KEYS):
        raise OfficialSnapshotError("page.columns must preserve the official five-column order")
    rows = page.get("rows")
    if not isinstance(rows, list) or not rows:
        raise OfficialSnapshotError("page.rows must be a non-empty list")
    if page.get("row_count") != len(rows):
        raise OfficialSnapshotError("page.row_count must equal the complete row list")
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping) or tuple(row.keys()) != _ROW_KEYS:
            raise OfficialSnapshotError(f"page.rows[{index}] must preserve the official column order")
        for key in _ROW_KEYS:
            if not isinstance(row.get(key), str):
                raise OfficialSnapshotError(f"page.rows[{index}].{key} must be a string")

    representative = snapshot.get("representative_contact")
    if not isinstance(representative, Mapping):
        raise OfficialSnapshotError("representative_contact must be an object")
    for field in ("department", "phone_display", "phone", "fax_display", "fax"):
        _require_text(representative.get(field), f"representative_contact.{field}")


def _validate_content_page_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate a complete sanitized official content-page capture."""
    if snapshot.get("snapshot_kind") != "official_content_page":
        raise OfficialSnapshotError("snapshot_kind must be official_content_page")
    page = snapshot["page"]
    _require_text(page.get("section_title"), "page.section_title")
    _require_text(page.get("content_html"), "page.content_html")

    breadcrumbs = page.get("breadcrumbs")
    if not isinstance(breadcrumbs, list) or not breadcrumbs:
        raise OfficialSnapshotError("page.breadcrumbs must be a non-empty list")
    for index, label in enumerate(breadcrumbs, start=1):
        _require_text(label, f"page.breadcrumbs[{index}]")

    for field in ("text_length", "table_count", "table_row_count"):
        value = page.get(field)
        if not isinstance(value, int) or value < 0:
            raise OfficialSnapshotError(f"page.{field} must be a non-negative integer")
    if page["text_length"] == 0:
        raise OfficialSnapshotError("page.text_length must describe non-empty official content")

    content_info = page.get("content_info_text")
    if not isinstance(content_info, list):
        raise OfficialSnapshotError("page.content_info_text must be a list")
    if "<script" in page["content_html"].lower():
        raise OfficialSnapshotError("page.content_html must not contain scripts")

    rewrites = page.get("asset_rewrites", {})
    hashes = page.get("asset_sha256", {})
    if not isinstance(rewrites, Mapping) or not isinstance(hashes, Mapping):
        raise OfficialSnapshotError("page asset metadata must be objects")
    for source_url, local_path in rewrites.items():
        if not str(source_url).startswith("https://bukgu.gwangju.kr/"):
            raise OfficialSnapshotError("asset rewrite sources must use the official Buk-gu domain")
        if not str(local_path).startswith("/static/images/"):
            raise OfficialSnapshotError("asset rewrite targets must use local static images")
        digest = hashes.get(local_path)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise OfficialSnapshotError("each localized asset must have a lowercase SHA-256")


def validate_official_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate common provenance plus the route-specific canonical shape."""
    schema_version = snapshot.get("schema_version")
    if schema_version not in (1, 2):
        raise OfficialSnapshotError("schema_version must be 1 or 2")
    route_id = _require_text(snapshot.get("route_id"), "route_id")
    if not _ROUTE_ID_RE.fullmatch(route_id):
        raise OfficialSnapshotError("route_id contains unsupported characters")
    for field in ("snapshot_id", "site_id", "site_name", "page_id"):
        _require_text(snapshot.get(field), field)

    source = snapshot.get("source")
    if not isinstance(source, Mapping):
        raise OfficialSnapshotError("source must be an object")
    for field in ("url", "title", "captured_at", "verified_at", "source_updated_at"):
        _require_text(source.get(field), f"source.{field}")
    if not str(source["url"]).startswith("https://bukgu.gwangju.kr/"):
        raise OfficialSnapshotError("source.url must use the official Buk-gu domain")

    page = snapshot.get("page")
    if not isinstance(page, Mapping):
        raise OfficialSnapshotError("page must be an object")
    if schema_version == 1:
        _validate_department_snapshot(snapshot)
    else:
        _validate_content_page_snapshot(snapshot)


def canonical_snapshot_sha256(snapshot: Mapping[str, Any]) -> str:
    """Return a stable checksum over the complete canonical JSON value."""
    validate_official_snapshot(snapshot)
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=None)
def load_official_snapshot(route_id: str) -> dict[str, Any]:
    """Load one route snapshot without any network or runtime fallback."""
    if not isinstance(route_id, str) or not _ROUTE_ID_RE.fullmatch(route_id):
        raise OfficialSnapshotError("invalid route_id")
    path = SNAPSHOT_ROOT / f"{route_id}.json"
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OfficialSnapshotError(f"official snapshot not found: {route_id}") from exc
    except json.JSONDecodeError as exc:
        raise OfficialSnapshotError(f"invalid official snapshot JSON: {route_id}") from exc
    if not isinstance(snapshot, dict):
        raise OfficialSnapshotError("official snapshot root must be an object")
    validate_official_snapshot(snapshot)
    if snapshot["route_id"] != route_id:
        raise OfficialSnapshotError("snapshot route_id does not match its filename")
    return snapshot


def build_snapshot_answer(route_id: str) -> str:
    """Compose resident-facing guidance from canonical snapshot fields."""
    snapshot = load_official_snapshot(route_id)
    page = snapshot["page"]
    contact = snapshot["representative_contact"]
    return (
        f"공동주택 관련 문의는 {contact['department']}에서 담당합니다. "
        f"부서 대표전화는 {contact['phone']}, FAX는 {contact['fax']}입니다. "
        f"왼쪽 조직 및 업무안내에서 전체 {page['row_count']}명의 담당 업무와 "
        "전화번호를 공식 표 그대로 확인할 수 있습니다."
    )


def build_snapshot_result(route_id: str) -> dict[str, str]:
    """Build the deterministic quest result metadata from the snapshot."""
    snapshot = load_official_snapshot(route_id)
    page = snapshot["page"]
    source = snapshot["source"]
    return {
        "service": f"{snapshot['representative_contact']['department']} 조직 및 업무안내",
        "surface": f"전체 {page['row_count']}명 공식 업무 및 연락처",
        "stop": "사용자 확인 후 공식 채널에서 직접 진행",
        "snapshot_id": snapshot["snapshot_id"],
        "source_url": source["url"],
        "source_updated_at": source["source_updated_at"],
    }


def build_snapshot_model_guidance(route_id: str) -> str:
    """Return compact, canonical model instructions for one route."""
    snapshot = load_official_snapshot(route_id)
    contact = snapshot["representative_contact"]
    page = snapshot["page"]
    return (
        f"   - 담당 부서: {contact['department']}\n"
        f"   - 부서 대표전화: {contact['phone']}\n"
        f"   - FAX: {contact['fax']}\n"
        f"   - 조직 및 업무안내에는 공식 순서의 전체 {page['row_count']}명 표가 있습니다.\n"
        "   - 과장 행의 전화번호를 부서 대표전화라고 부르지 마세요.\n"
    )
