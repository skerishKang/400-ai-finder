#!/usr/bin/env python3
"""
#1172 / #1177 — Buk-gu home asset identity audit against a frozen repository
scan manifest (point-in-time historical blob universe).

Normal generation and --check never scan the current working tree / git index.
They load the committed frozen scan manifest and recompute the audit report
from inventory + that fixed eligible set.

Explicit refresh rebuilds the frozen manifest from Git object bytes at a
chosen snapshot commit:

  python scripts/audit_bukgu_home_asset_identity.py \\
    --refresh-scan-manifest --snapshot-ref <40-char-or-ref>

Network / live site / asset download are forbidden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = (
    ROOT
    / "data"
    / "official_captures"
    / "bukgu_gwangju"
    / "home"
    / "asset-inventory.json"
)
REPORT_PATH = (
    ROOT
    / "data"
    / "official_clone_asset_audits"
    / "bukgu_gwangju"
    / "home-repository-match-audit.json"
)
SCAN_MANIFEST_PATH = (
    ROOT
    / "data"
    / "official_clone_asset_audits"
    / "bukgu_gwangju"
    / "home-repository-scan-manifest.json"
)

SCAN_MANIFEST_REL = (
    "data/official_clone_asset_audits/bukgu_gwangju/home-repository-scan-manifest.json"
)
REPORT_REL = (
    "data/official_clone_asset_audits/bukgu_gwangju/home-repository-match-audit.json"
)
DOCS_REL = "docs/artifacts/1172-home-asset-identity-audit.md"
DOCS_1177_REL = "docs/artifacts/1177-home-asset-audit-frozen-manifest.md"
SCRIPT_REL = "scripts/audit_bukgu_home_asset_identity.py"
TEST_REL = "tests/test_bukgu_home_asset_identity_audit.py"

# Paths excluded from the eligible scan universe (audit self-artifacts).
EXCLUDED_PATHS = frozenset(
    {
        REPORT_REL,
        SCAN_MANIFEST_REL,
        DOCS_REL,
        DOCS_1177_REL,
        SCRIPT_REL,
        TEST_REL,
    }
)

# Historical #1172 scan used a 4-path exclusion set (no frozen manifest yet).
# Refresh at that snapshot still records whatever excluded paths exist in the
# tree; EXCLUDED_PATHS is the full current exclusion policy for future refreshes.
#
# #1177 pin: Git object (blob) bytes at DEFAULT_SNAPSHOT_COMMIT.
# The earlier #1172 working-tree pin
#   86c372bacd9a867e8407ab854b9c4766c3c0193f4c6e4244a7f613a4767eabda
# was Windows CRLF checkout-sensitive and is superseded by this blob pin.
HISTORICAL_CANONICAL_MANIFEST_SHA256 = (
    "1997cac4b492034649a0920afa2672fcf93cec287b5b685eb8ff609f1172dd0e"
)
LEGACY_WORKING_TREE_MANIFEST_SHA256 = (
    "86c372bacd9a867e8407ab854b9c4766c3c0193f4c6e4244a7f613a4767eabda"
)
DEFAULT_SNAPSHOT_COMMIT = "0a86d643b5bc8f4379bafd2aa42704c579de6c9b"
EXPECTED_REPOSITORY = "skerishKang/400-ai-finder"

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_KIND = "official_home_asset_repository_scan_manifest"
REPORT_SCHEMA_VERSION = 2
AUDIT_GENERATOR_VERSION = "2.0.1"

COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"

# Exact key sets for strict schema validation (fail closed on unknown keys).
MANIFEST_TOP_KEYS = frozenset(
    {
        "schema_version",
        "manifest_kind",
        "snapshot",
        "canonical_manifest_sha256",
        "entries",
    }
)
SNAPSHOT_KEYS = frozenset(
    {
        "repository",
        "commit_sha",
        "enumerated_tracked_path_count",
        "eligible_entry_count",
        "excluded_path_count",
        "lfs_pointer_count",
        "missing_or_unreadable_count",
    }
)
ENTRY_KEYS = frozenset({"path", "size_bytes", "sha256"})


class ManifestValidationError(ValueError):
    """Frozen scan manifest failed strict validation."""


def _is_strict_nonneg_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _run_git(args, *, cwd=None, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=cwd or ROOT,
        capture_output=True,
        check=check,
    )


def resolve_commit_sha(ref: str, *, cwd=None) -> str:
    """Resolve ref to a full lowercase 40-char commit SHA (fail closed)."""
    if not ref or not isinstance(ref, str) or not ref.strip():
        raise ManifestValidationError("snapshot ref is blank")
    result = _run_git(["rev-parse", f"{ref}^{{commit}}"], cwd=cwd, check=False)
    if result.returncode != 0:
        err = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ManifestValidationError(f"cannot resolve snapshot ref {ref!r}: {err}")
    sha = result.stdout.decode("utf-8").strip().lower()
    if not COMMIT_SHA_RE.fullmatch(sha):
        raise ManifestValidationError(f"resolved commit is not a 40-hex SHA: {sha!r}")
    return sha


def normalize_repo_path(path: str) -> str:
    """
    Strict Git tree path validation (fail closed).

    Does not rewrite separators. Paths with backslash, pipe, CR/LF/NUL, or
    other ASCII controls are rejected so canonical lines
    (`path|size|sha256\\n`) and `git cat-file --batch` input stay unambiguous.
    """
    if not isinstance(path, str) or path == "" or path.strip() == "":
        raise ManifestValidationError("path must be a non-blank string")
    for ch in path:
        code = ord(ch)
        if code < 32 or code == 127:
            raise ManifestValidationError(
                f"ASCII control character forbidden in path: {path!r}"
            )
        if ch == "\\":
            raise ManifestValidationError(f"backslash forbidden in path: {path!r}")
        if ch == "|":
            raise ManifestValidationError(f"pipe forbidden in path: {path!r}")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ManifestValidationError(f"absolute path forbidden: {path!r}")
    if path.startswith("./"):
        raise ManifestValidationError(f"path must not start with ./: {path!r}")
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ManifestValidationError(f"invalid path segment in {path!r}")
    return path


def is_lfs_pointer_bytes(data: bytes) -> bool:
    return data.startswith(LFS_POINTER_PREFIX)


def canonical_manifest_line(path: str, size_bytes: int, sha256: str) -> str:
    return f"{path}|{size_bytes}|{sha256}\n"


def compute_canonical_manifest_sha256(entries) -> str:
    hasher = hashlib.sha256()
    for entry in entries:
        line = canonical_manifest_line(
            entry["path"], entry["size_bytes"], entry["sha256"]
        )
        hasher.update(line.encode("utf-8"))
    return hasher.hexdigest()


def list_tree_paths(commit_sha: str, *, cwd=None) -> list[str]:
    result = _run_git(
        ["ls-tree", "-r", "-z", "--name-only", commit_sha],
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ManifestValidationError(f"git ls-tree failed for {commit_sha}: {err}")
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ManifestValidationError(f"non-utf8 tree path: {raw!r}") from exc
        # Do not rewrite separators; fail closed on backslash/control/pipe.
        paths.append(normalize_repo_path(path))
    return sorted(paths)


def read_git_blob(commit_sha: str, path: str, *, cwd=None) -> bytes:
    result = _run_git(
        ["cat-file", "blob", f"{commit_sha}:{path}"],
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ManifestValidationError(
            f"git cat-file blob failed for {commit_sha}:{path}: {err}"
        )
    return result.stdout


def read_git_blobs_batch(commit_sha: str, paths: list[str], *, cwd=None) -> dict[str, bytes | None]:
    """
    Batch-read blob bytes for paths at commit_sha via `git cat-file --batch`.
    Missing/unreadable paths map to None.
    """
    if not paths:
        return {}
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=cwd or ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    out: dict[str, bytes | None] = {}
    try:
        for path in paths:
            spec = f"{commit_sha}:{path}\n".encode("utf-8")
            proc.stdin.write(spec)
            proc.stdin.flush()
            header = proc.stdout.readline()
            if not header:
                out[path] = None
                continue
            # Formats:
            #   <oid> blob <size>\n<body>\n
            #   <spec> missing\n
            parts = header.decode("utf-8", errors="replace").strip().split()
            if len(parts) >= 2 and parts[-1] == "missing":
                out[path] = None
                continue
            if len(parts) < 3 or parts[1] != "blob":
                out[path] = None
                continue
            try:
                size = int(parts[2])
            except ValueError:
                out[path] = None
                continue
            body = proc.stdout.read(size)
            # trailing newline after blob body
            _nl = proc.stdout.read(1)
            if len(body) != size:
                out[path] = None
                continue
            out[path] = body
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    return out


def build_scan_manifest_from_git(
    snapshot_ref: str,
    *,
    cwd=None,
    repository: str = EXPECTED_REPOSITORY,
) -> dict:
    """
    Build a frozen scan manifest from Git object bytes only.
    Does not read working-tree file contents.
    """
    commit_sha = resolve_commit_sha(snapshot_ref, cwd=cwd)
    tracked = list_tree_paths(commit_sha, cwd=cwd)
    enumerated_count = len(tracked)

    entries = []
    excluded_count = 0
    lfs_count = 0
    missing_or_unreadable_count = 0

    candidates: list[str] = []
    for path in tracked:
        if path in EXCLUDED_PATHS:
            excluded_count += 1
            continue
        candidates.append(path)

    blobs = read_git_blobs_batch(commit_sha, candidates, cwd=cwd)
    for path in candidates:
        blob = blobs.get(path)
        if blob is None:
            missing_or_unreadable_count += 1
            continue
        if is_lfs_pointer_bytes(blob):
            lfs_count += 1
            continue
        size = len(blob)
        sha = hashlib.sha256(blob).hexdigest()
        entries.append({"path": path, "size_bytes": size, "sha256": sha})

    entries.sort(key=lambda e: e["path"])
    eligible_count = len(entries)
    if (
        eligible_count
        + excluded_count
        + lfs_count
        + missing_or_unreadable_count
        != enumerated_count
    ):
        raise ManifestValidationError(
            "partition invariant failed while building scan manifest"
        )

    canonical = compute_canonical_manifest_sha256(entries)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "snapshot": {
            "repository": repository,
            "commit_sha": commit_sha,
            "enumerated_tracked_path_count": enumerated_count,
            "eligible_entry_count": eligible_count,
            "excluded_path_count": excluded_count,
            "lfs_pointer_count": lfs_count,
            "missing_or_unreadable_count": missing_or_unreadable_count,
        },
        "canonical_manifest_sha256": canonical,
        "entries": entries,
    }


def validate_scan_manifest(manifest) -> dict:
    """Strict known-key validation; returns the same object on success."""
    if not isinstance(manifest, dict):
        raise ManifestValidationError("manifest root must be an object")

    extra = set(manifest.keys()) - MANIFEST_TOP_KEYS
    if extra:
        raise ManifestValidationError(f"unknown top-level keys: {sorted(extra)}")
    missing = MANIFEST_TOP_KEYS - set(manifest.keys())
    if missing:
        raise ManifestValidationError(f"missing top-level keys: {sorted(missing)}")

    if not isinstance(manifest["schema_version"], int) or isinstance(
        manifest["schema_version"], bool
    ):
        raise ManifestValidationError("schema_version must be a strict integer")
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ManifestValidationError(
            f"unsupported schema_version: {manifest['schema_version']}"
        )
    if manifest["manifest_kind"] != MANIFEST_KIND:
        raise ManifestValidationError(
            f"unexpected manifest_kind: {manifest['manifest_kind']!r}"
        )

    snapshot = manifest["snapshot"]
    if not isinstance(snapshot, dict):
        raise ManifestValidationError("snapshot must be an object")
    extra_s = set(snapshot.keys()) - SNAPSHOT_KEYS
    if extra_s:
        raise ManifestValidationError(f"unknown snapshot keys: {sorted(extra_s)}")
    missing_s = SNAPSHOT_KEYS - set(snapshot.keys())
    if missing_s:
        raise ManifestValidationError(f"missing snapshot keys: {sorted(missing_s)}")

    if not isinstance(snapshot["repository"], str) or not snapshot["repository"].strip():
        raise ManifestValidationError("snapshot.repository must be a non-blank string")
    if snapshot["repository"] != EXPECTED_REPOSITORY:
        raise ManifestValidationError(
            f"snapshot.repository must be exactly {EXPECTED_REPOSITORY!r}, "
            f"got {snapshot['repository']!r}"
        )
    commit_sha = snapshot["commit_sha"]
    if not isinstance(commit_sha, str) or not COMMIT_SHA_RE.fullmatch(commit_sha):
        raise ManifestValidationError(
            "snapshot.commit_sha must be lowercase 40-hex"
        )

    for key in (
        "enumerated_tracked_path_count",
        "eligible_entry_count",
        "excluded_path_count",
        "lfs_pointer_count",
        "missing_or_unreadable_count",
    ):
        if not _is_strict_nonneg_int(snapshot[key]):
            raise ManifestValidationError(f"snapshot.{key} must be a non-negative int")

    canonical = manifest["canonical_manifest_sha256"]
    if not isinstance(canonical, str) or not HEX64_RE.fullmatch(canonical):
        raise ManifestValidationError(
            "canonical_manifest_sha256 must be lowercase 64-hex"
        )

    entries = manifest["entries"]
    if not isinstance(entries, list):
        raise ManifestValidationError("entries must be a list")

    seen = set()
    prev_path = None
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ManifestValidationError(f"entries[{i}] must be an object")
        extra_e = set(entry.keys()) - ENTRY_KEYS
        if extra_e:
            raise ManifestValidationError(
                f"entries[{i}] unknown keys: {sorted(extra_e)}"
            )
        missing_e = ENTRY_KEYS - set(entry.keys())
        if missing_e:
            raise ManifestValidationError(
                f"entries[{i}] missing keys: {sorted(missing_e)}"
            )
        path = normalize_repo_path(entry["path"])
        if path != entry["path"]:
            raise ManifestValidationError(f"entries[{i}].path must be normalized")
        if path in seen:
            raise ManifestValidationError(f"duplicate path: {path}")
        seen.add(path)
        if prev_path is not None and path < prev_path:
            raise ManifestValidationError("entries paths must be sorted ascending")
        if prev_path is not None and path == prev_path:
            raise ManifestValidationError(f"duplicate path: {path}")
        prev_path = path
        if path in EXCLUDED_PATHS:
            raise ManifestValidationError(
                f"excluded audit path must not appear in eligible entries: {path}"
            )
        if not _is_strict_nonneg_int(entry["size_bytes"]):
            raise ManifestValidationError(
                f"entries[{i}].size_bytes must be a non-negative int"
            )
        sha = entry["sha256"]
        if not isinstance(sha, str) or not HEX64_RE.fullmatch(sha):
            raise ManifestValidationError(
                f"entries[{i}].sha256 must be lowercase 64-hex"
            )

    eligible = snapshot["eligible_entry_count"]
    if eligible != len(entries):
        raise ManifestValidationError(
            f"eligible_entry_count {eligible} != len(entries) {len(entries)}"
        )
    partition = (
        snapshot["eligible_entry_count"]
        + snapshot["excluded_path_count"]
        + snapshot["lfs_pointer_count"]
        + snapshot["missing_or_unreadable_count"]
    )
    if partition != snapshot["enumerated_tracked_path_count"]:
        raise ManifestValidationError(
            "snapshot partition does not sum to enumerated_tracked_path_count"
        )

    recomputed = compute_canonical_manifest_sha256(entries)
    if recomputed != canonical:
        raise ManifestValidationError(
            "canonical_manifest_sha256 does not match recomputed entries"
        )
    # Historical #1172 conclusion is pinned to this SHA for the default snapshot.
    if (
        commit_sha == DEFAULT_SNAPSHOT_COMMIT
        and canonical != HISTORICAL_CANONICAL_MANIFEST_SHA256
    ):
        raise ManifestValidationError(
            "historical snapshot canonical SHA mismatch against #1172 pin"
        )

    return manifest


def load_scan_manifest(path: Path | None = None) -> dict:
    path = path or SCAN_MANIFEST_PATH
    if not path.exists():
        raise ManifestValidationError(f"missing scan manifest: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestValidationError("scan manifest is not valid UTF-8") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"scan manifest JSON parse error: {exc}") from exc
    return validate_scan_manifest(data)


def repo_data_from_scan_manifest(manifest: dict) -> dict:
    """Build the in-memory size/hash index used by audit_inventory."""
    size_hash_index: dict[tuple[int, str], list[str]] = {}
    for entry in manifest["entries"]:
        key = (entry["size_bytes"], entry["sha256"])
        size_hash_index.setdefault(key, []).append(entry["path"])
    for key in size_hash_index:
        size_hash_index[key].sort()

    snap = manifest["snapshot"]
    return {
        "enumerated_count": snap["enumerated_tracked_path_count"],
        "eligible_count": snap["eligible_entry_count"],
        "excluded_count": snap["excluded_path_count"],
        "lfs_count": snap["lfs_pointer_count"],
        "missing_unreadable_count": snap["missing_or_unreadable_count"],
        "manifest_sha256": manifest["canonical_manifest_sha256"],
        "index": size_hash_index,
        "scan_meta": {
            "method": "frozen_repository_scan_manifest",
            "frozen_manifest_path": SCAN_MANIFEST_REL,
            "manifest_schema_version": manifest["schema_version"],
            "snapshot_repository": snap["repository"],
            "snapshot_commit_sha": snap["commit_sha"],
            "entry_count": snap["eligible_entry_count"],
            "canonical_manifest_sha256": manifest["canonical_manifest_sha256"],
            "semantics": "point_in_time_explicit_refresh",
        },
    }


def build_repo_index(tracked_files=None):
    """
    Test helper: build an in-memory index from an explicit path list relative
    to ROOT (working-tree bytes). Production normal/check never calls this.
    """
    if tracked_files is None:
        raise RuntimeError(
            "build_repo_index requires explicit tracked_files; "
            "normal/check must use load_scan_manifest / repo_data_from_scan_manifest"
        )

    enumerated_count = len(tracked_files)
    eligible_count = 0
    excluded_count = 0
    lfs_count = 0
    missing_unreadable_count = 0
    size_hash_index: dict[tuple[int, str], list[str]] = {}
    manifest_hasher = hashlib.sha256()

    for relative_path in tracked_files:
        # Test helper only: still apply strict path rules (no silent rewrite).
        path = normalize_repo_path(relative_path)
        if path in EXCLUDED_PATHS:
            excluded_count += 1
            continue
        full_path = ROOT / path
        if not full_path.exists() or not full_path.is_file():
            missing_unreadable_count += 1
            continue
        try:
            data = full_path.read_bytes()
        except OSError:
            missing_unreadable_count += 1
            continue
        if is_lfs_pointer_bytes(data):
            lfs_count += 1
            continue
        size = len(data)
        file_hash = hashlib.sha256(data).hexdigest()
        manifest_hasher.update(
            canonical_manifest_line(path, size, file_hash).encode("utf-8")
        )
        size_hash_index.setdefault((size, file_hash), []).append(path)
        eligible_count += 1

    for key in size_hash_index:
        size_hash_index[key].sort()

    if (
        eligible_count
        + excluded_count
        + lfs_count
        + missing_unreadable_count
        != enumerated_count
    ):
        print(
            "Invariant violation: eligible + excluded + lfs + missing_or_unreadable "
            "!= enumerated tracked paths"
        )
        sys.exit(1)

    return {
        "enumerated_count": enumerated_count,
        "eligible_count": eligible_count,
        "excluded_count": excluded_count,
        "lfs_count": lfs_count,
        "missing_unreadable_count": missing_unreadable_count,
        "manifest_sha256": manifest_hasher.hexdigest(),
        "index": size_hash_index,
        "scan_meta": {
            "method": "test_explicit_tracked_files",
            "frozen_manifest_path": None,
            "manifest_schema_version": None,
            "snapshot_repository": EXPECTED_REPOSITORY,
            "snapshot_commit_sha": None,
            "entry_count": eligible_count,
            "canonical_manifest_sha256": manifest_hasher.hexdigest(),
            "semantics": "test_helper_only",
        },
    }


def classify_evidence(item):
    sha = item.get("sha256")
    size = item.get("size_bytes")
    hashed_byte_count = item.get("hashed_byte_count")

    if size is not None:
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            return "invalid_evidence"

    if hashed_byte_count is not None:
        if (
            isinstance(hashed_byte_count, bool)
            or not isinstance(hashed_byte_count, int)
            or hashed_byte_count < 0
        ):
            return "invalid_evidence"

    if size is not None and hashed_byte_count is not None:
        if hashed_byte_count > size:
            return "invalid_evidence"

    if sha is None:
        return "unhashed"

    if size is None or hashed_byte_count is None:
        return "invalid_evidence"

    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return "invalid_evidence"

    if hashed_byte_count == size and size > 0:
        return "full_body_equivalent_hash"

    return "partial_prefix_hash"


def audit_inventory(inventory, repo_data, inventory_hash):
    summary = {
        "asset_total": inventory.get("item_count", 0),
        "full_body_equivalent_hash_count": 0,
        "partial_prefix_hash_count": 0,
        "unhashed_count": 0,
        "invalid_evidence_count": 0,
        "evaluated_full_hash_count": 0,
        "one_exact_candidate_count": 0,
        "multiple_exact_candidates_count": 0,
        "no_exact_match_count": 0,
        "not_evaluated_partial_count": 0,
        "not_evaluated_unhashed_count": 0,
        "not_evaluated_invalid_count": 0,
        "by_asset_type": {},
        "by_extension": {},
        "by_source_section": {},
    }

    out_items = []

    for item in inventory.get("items", []):
        evidence_class = classify_evidence(item)
        candidate_paths = []
        reason = ""

        if evidence_class == "full_body_equivalent_hash":
            key = (item.get("size_bytes"), item.get("sha256"))
            candidates = repo_data["index"].get(key, [])
            if len(candidates) == 1:
                match_status = "one_repo_exact_match_candidate"
            elif len(candidates) > 1:
                match_status = "multiple_repo_exact_match_candidates"
            else:
                match_status = "no_repo_exact_match"
            candidate_paths = candidates
            reason = (
                f"full hash evaluated; matched {len(candidates)} exact repository files"
                if candidates
                else "full hash evaluated; no equal-size/equal-sha tracked file"
            )
            summary["evaluated_full_hash_count"] += 1
            if match_status == "one_repo_exact_match_candidate":
                summary["one_exact_candidate_count"] += 1
            elif match_status == "multiple_repo_exact_match_candidates":
                summary["multiple_exact_candidates_count"] += 1
            elif match_status == "no_repo_exact_match":
                summary["no_exact_match_count"] += 1
            summary["full_body_equivalent_hash_count"] += 1

        elif evidence_class == "partial_prefix_hash":
            match_status = "not_evaluated_partial_hash"
            reason = "partial prefix hash cannot establish full-file identity"
            summary["not_evaluated_partial_count"] += 1
            summary["partial_prefix_hash_count"] += 1

        elif evidence_class == "unhashed":
            match_status = "not_evaluated_unhashed"
            reason = "no captured hash available"
            summary["not_evaluated_unhashed_count"] += 1
            summary["unhashed_count"] += 1

        elif evidence_class == "invalid_evidence":
            match_status = "not_evaluated_invalid_evidence"
            reason = "capture evidence is invalid"
            summary["not_evaluated_invalid_count"] += 1
            summary["invalid_evidence_count"] += 1

        else:
            raise ValueError(f"Unknown evidence class: {evidence_class}")

        candidate_count = len(candidate_paths)

        a_type = item.get("asset_type", "unknown")
        summary["by_asset_type"][a_type] = summary["by_asset_type"].get(a_type, 0) + 1

        url = item.get("resolved_url", "")
        path = urlparse(url).path
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        if not ext:
            ext = "none"
        summary["by_extension"][ext] = summary["by_extension"].get(ext, 0) + 1

        sec = item.get("section", "unknown")
        summary["by_source_section"][sec] = summary["by_source_section"].get(sec, 0) + 1

        out_items.append(
            {
                "source_url": item.get("source_url"),
                "requested_url": item.get("requested_url"),
                "resolved_url": item.get("resolved_url"),
                "asset_type": item.get("asset_type"),
                "content_type": item.get("content_type"),
                "size_bytes": item.get("size_bytes"),
                "sha256": item.get("sha256"),
                "hash_scope": item.get("hash_scope"),
                "hashed_byte_count": item.get("hashed_byte_count"),
                "evidence_class": evidence_class,
                "match_status": match_status,
                "candidate_paths": candidate_paths,
                "candidate_count": candidate_count,
                "reason": reason,
            }
        )

    if summary["asset_total"] != len(out_items):
        raise ValueError("Invariant violation: asset_total != len(items)")

    if (
        summary["full_body_equivalent_hash_count"]
        + summary["partial_prefix_hash_count"]
        + summary["unhashed_count"]
        + summary["invalid_evidence_count"]
        != summary["asset_total"]
    ):
        raise ValueError(
            "Invariant violation: full + partial + unhashed + invalid != asset_total"
        )

    if summary["evaluated_full_hash_count"] != summary["full_body_equivalent_hash_count"]:
        raise ValueError(
            "Invariant violation: evaluated_full_hash_count != full_body_equivalent_hash_count"
        )

    if (
        summary["one_exact_candidate_count"]
        + summary["multiple_exact_candidates_count"]
        + summary["no_exact_match_count"]
        != summary["evaluated_full_hash_count"]
    ):
        raise ValueError(
            "Invariant violation: one + multiple + no-match != evaluated_full_hash_count"
        )

    if summary["not_evaluated_partial_count"] != summary["partial_prefix_hash_count"]:
        raise ValueError(
            "Invariant violation: not_evaluated_partial_count != partial_prefix_hash_count"
        )

    if summary["not_evaluated_unhashed_count"] != summary["unhashed_count"]:
        raise ValueError(
            "Invariant violation: not_evaluated_unhashed_count != unhashed_count"
        )

    if summary["not_evaluated_invalid_count"] != summary["invalid_evidence_count"]:
        raise ValueError(
            "Invariant violation: not_evaluated_invalid_count != invalid_evidence_count"
        )

    expected_keys = {
        "asset_total",
        "full_body_equivalent_hash_count",
        "partial_prefix_hash_count",
        "unhashed_count",
        "invalid_evidence_count",
        "evaluated_full_hash_count",
        "one_exact_candidate_count",
        "multiple_exact_candidates_count",
        "no_exact_match_count",
        "not_evaluated_partial_count",
        "not_evaluated_unhashed_count",
        "not_evaluated_invalid_count",
        "by_asset_type",
        "by_extension",
        "by_source_section",
    }

    if set(summary.keys()) != expected_keys:
        raise ValueError("Invariant violation: unexpected keys in summary")

    scan_meta = repo_data.get("scan_meta") or {}
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "audit_kind": "official_home_asset_repository_identity_audit",
        "audit_generator": {
            "id": "scripts/audit_bukgu_home_asset_identity.py",
            "version": AUDIT_GENERATOR_VERSION,
        },
        "source": {
            "path": "data/official_captures/bukgu_gwangju/home/asset-inventory.json",
            "sha256": inventory_hash,
            "captured_at": inventory.get("captured_at"),
            "item_count": inventory.get("item_count"),
        },
        "scan": {
            "method": scan_meta.get("method", "frozen_repository_scan_manifest"),
            "frozen_manifest_path": scan_meta.get(
                "frozen_manifest_path", SCAN_MANIFEST_REL
            ),
            "manifest_schema_version": scan_meta.get(
                "manifest_schema_version", MANIFEST_SCHEMA_VERSION
            ),
            "snapshot_repository": scan_meta.get(
                "snapshot_repository", EXPECTED_REPOSITORY
            ),
            "snapshot_commit_sha": scan_meta.get("snapshot_commit_sha"),
            "enumerated_tracked_path_count": repo_data["enumerated_count"],
            "eligible_tracked_file_count": repo_data["eligible_count"],
            "excluded_path_count": repo_data["excluded_count"],
            "lfs_pointer_count": repo_data["lfs_count"],
            "missing_or_unreadable_count": repo_data["missing_unreadable_count"],
            "entry_count": scan_meta.get("entry_count", repo_data["eligible_count"]),
            "manifest_sha256": repo_data["manifest_sha256"],
            "canonical_manifest_sha256": scan_meta.get(
                "canonical_manifest_sha256", repo_data["manifest_sha256"]
            ),
            "semantics": scan_meta.get(
                "semantics", "point_in_time_explicit_refresh"
            ),
        },
        "summary": summary,
        "items": out_items,
    }
    return report


def dump_json_bytes(obj) -> bytes:
    """UTF-8 JSON with LF newlines (cross-platform canonical)."""
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_inventory_bytes(path: Path | None = None) -> tuple[dict, str]:
    """
    Load inventory as UTF-8 text and hash the on-disk bytes so checkout
    encoding is stable when files are committed with LF.
    Prefer raw bytes for the inventory_hash to avoid text-mode newline
    reinterpretation differences across platforms.
    """
    path = path or INVENTORY_PATH
    raw = path.read_bytes()
    inventory_hash = hashlib.sha256(raw).hexdigest()
    inventory = json.loads(raw.decode("utf-8"))
    return inventory, inventory_hash


def generate_report_from_frozen_manifest(
    *,
    inventory_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict:
    inventory, inventory_hash = load_inventory_bytes(inventory_path or INVENTORY_PATH)
    if inventory.get("item_count") != len(inventory.get("items", [])):
        raise ValueError("inventory item_count mismatch")
    manifest = load_scan_manifest(manifest_path or SCAN_MANIFEST_PATH)
    repo_data = repo_data_from_scan_manifest(manifest)
    return audit_inventory(inventory, repo_data, inventory_hash)


def write_scan_manifest(manifest: dict, path: Path | None = None) -> None:
    path = path or SCAN_MANIFEST_PATH
    validate_scan_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump_json_bytes(manifest))


def refresh_scan_manifest(snapshot_ref: str, *, path: Path | None = None) -> dict:
    manifest = build_scan_manifest_from_git(snapshot_ref)
    write_scan_manifest(manifest, path=path or SCAN_MANIFEST_PATH)
    return manifest


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Buk-gu home asset identity audit (#1172/#1177)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Recompute report from frozen manifest and compare to committed report",
    )
    parser.add_argument(
        "--refresh-scan-manifest",
        action="store_true",
        help="Explicitly rebuild frozen scan manifest from Git object bytes",
    )
    parser.add_argument(
        "--snapshot-ref",
        default=None,
        help="Git ref/commit for --refresh-scan-manifest (full commit preferred)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.refresh_scan_manifest:
        if args.check:
            print("Error: --check cannot be combined with --refresh-scan-manifest")
            sys.exit(2)
        ref = args.snapshot_ref or DEFAULT_SNAPSHOT_COMMIT
        try:
            manifest = refresh_scan_manifest(ref)
        except ManifestValidationError as exc:
            print(f"Refresh failed: {exc}")
            sys.exit(1)
        print(
            "Scan manifest refreshed: "
            f"commit={manifest['snapshot']['commit_sha']} "
            f"eligible={manifest['snapshot']['eligible_entry_count']} "
            f"canonical={manifest['canonical_manifest_sha256']}"
        )
        return

    if args.snapshot_ref and not args.refresh_scan_manifest:
        print("Error: --snapshot-ref requires --refresh-scan-manifest")
        sys.exit(2)

    try:
        report = generate_report_from_frozen_manifest()
    except ManifestValidationError as exc:
        print(f"Check failed: {exc}" if args.check else f"Error: {exc}")
        sys.exit(1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    report_bytes = dump_json_bytes(report)

    if args.check:
        if not REPORT_PATH.exists():
            print("Check failed: Report does not exist")
            sys.exit(1)
        existing = REPORT_PATH.read_bytes()
        if existing != report_bytes:
            print("Check failed: Report drift detected")
            sys.exit(1)
        print("Check passed")
    else:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_bytes(report_bytes)
        print("Report written")


def _install_network_block():
    import http.client
    import socket
    import urllib.request

    def block_network(*args, **kwargs):
        raise RuntimeError("Network calls are forbidden in this script.")

    socket.socket.connect = block_network  # type: ignore[method-assign]
    urllib.request.urlopen = block_network
    http.client.HTTPConnection.request = block_network  # type: ignore[assignment]
    http.client.HTTPSConnection.request = block_network  # type: ignore[assignment]
    try:
        import requests

        requests.get = block_network
        requests.post = block_network
    except ImportError:
        pass


if __name__ == "__main__":
    _install_network_block()
    main()
