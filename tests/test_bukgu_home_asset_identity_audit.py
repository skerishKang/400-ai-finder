"""#1172 / #1177 home asset identity audit contracts.

Normal generation and --check use a frozen Git-blob scan manifest.
Unrelated tracked files must not cause report drift. Explicit refresh is the
only path that reads Git trees/blobs for a new snapshot.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

import scripts.audit_bukgu_home_asset_identity as audit_module
from scripts.audit_bukgu_home_asset_identity import (
    DEFAULT_SNAPSHOT_COMMIT,
    EXCLUDED_PATHS,
    HISTORICAL_CANONICAL_MANIFEST_SHA256,
    LEGACY_WORKING_TREE_MANIFEST_SHA256,
    MANIFEST_KIND,
    MANIFEST_SCHEMA_VERSION,
    ManifestValidationError,
    SCAN_MANIFEST_PATH,
    SCAN_MANIFEST_REL,
    audit_inventory,
    build_repo_index,
    build_scan_manifest_from_git,
    classify_evidence,
    compute_canonical_manifest_sha256,
    dump_json_bytes,
    generate_report_from_frozen_manifest,
    load_scan_manifest,
    main,
    repo_data_from_scan_manifest,
    validate_scan_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _valid_manifest_skeleton(entries=None, **snapshot_overrides):
    if entries is None:
        entries = [
            {
                "path": "a.txt",
                "size_bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            },
            {
                "path": "b.txt",
                "size_bytes": 2,
                "sha256": hashlib.sha256(b"yy").hexdigest(),
            },
        ]
    entries = sorted(entries, key=lambda e: e["path"])
    canonical = compute_canonical_manifest_sha256(entries)
    snapshot = {
        "repository": "skerishKang/400-ai-finder",
        "commit_sha": DEFAULT_SNAPSHOT_COMMIT,
        "enumerated_tracked_path_count": len(entries) + 1,
        "eligible_entry_count": len(entries),
        "excluded_path_count": 1,
        "lfs_pointer_count": 0,
        "missing_or_unreadable_count": 0,
    }
    snapshot.update(snapshot_overrides)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_kind": MANIFEST_KIND,
        "snapshot": snapshot,
        "canonical_manifest_sha256": canonical,
        "entries": entries,
    }


# ── classify / inventory matching (legacy contracts) ─────────────────────


def test_classify_evidence():
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a" * 64}
        )
        == "full_body_equivalent_hash"
    )
    assert (
        classify_evidence(
            {
                "size_bytes": 200,
                "hashed_byte_count": 100,
                "sha256": "0123456789abcdef" * 4,
            }
        )
        == "partial_prefix_hash"
    )
    assert (
        classify_evidence({"size_bytes": 100, "hashed_byte_count": 100})
        == "unhashed"
    )

    assert (
        classify_evidence(
            {"size_bytes": -1, "hashed_byte_count": 100, "sha256": "a" * 64}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 200, "sha256": "a" * 64}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "g" * 64}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "A" * 64}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a" * 63}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a" * 65}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "-" * 64}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a" * 63 + " "}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 100, "sha256": 123}
        )
        == "invalid_evidence"
    )

    assert (
        classify_evidence(
            {"size_bytes": True, "hashed_byte_count": 100, "sha256": "a" * 64}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": False, "sha256": "a" * 64}
        )
        == "invalid_evidence"
    )

    assert (
        classify_evidence(
            {"size_bytes": -1, "hashed_byte_count": 100, "sha256": None}
        )
        == "invalid_evidence"
    )
    assert (
        classify_evidence(
            {"size_bytes": 100, "hashed_byte_count": 200, "sha256": None}
        )
        == "invalid_evidence"
    )


def test_audit_inventory_invalid_item():
    item = {
        "size_bytes": -1,
        "hashed_byte_count": 100,
        "sha256": "a" * 64,
        "asset_type": "image",
    }
    repo_data = {
        "enumerated_count": 0,
        "eligible_count": 0,
        "excluded_count": 0,
        "lfs_count": 0,
        "missing_unreadable_count": 0,
        "manifest_sha256": "dummy",
        "index": {},
        "scan_meta": {
            "method": "test",
            "frozen_manifest_path": SCAN_MANIFEST_REL,
            "manifest_schema_version": 1,
            "snapshot_commit_sha": DEFAULT_SNAPSHOT_COMMIT,
            "entry_count": 0,
            "canonical_manifest_sha256": "dummy",
            "semantics": "test",
        },
    }
    report = audit_inventory({"item_count": 1, "items": [item]}, repo_data, "dummy")
    summary = report["summary"]

    assert summary["invalid_evidence_count"] == 1
    assert summary["not_evaluated_invalid_count"] == 1
    assert report["items"][0]["match_status"] == "not_evaluated_invalid_evidence"
    assert "invalid_capture_evidence_count" not in summary

    assert (
        summary["full_body_equivalent_hash_count"]
        + summary["partial_prefix_hash_count"]
        + summary["unhashed_count"]
        + summary["invalid_evidence_count"]
        == summary["asset_total"]
    )
    assert (
        summary["one_exact_candidate_count"]
        + summary["multiple_exact_candidates_count"]
        + summary["no_exact_match_count"]
        == summary["evaluated_full_hash_count"]
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
    assert set(summary.keys()) == expected_keys


def test_exact_matching():
    old_root = audit_module.ROOT
    with tempfile.TemporaryDirectory() as td:
        audit_module.ROOT = Path(td)
        file1, file2, file3, file4 = "a.png", "b.png", "c.png", "d.png"
        (Path(td) / file1).write_bytes(b"content")
        (Path(td) / file2).write_bytes(b"content")
        (Path(td) / file3).write_bytes(b"different")
        (Path(td) / file4).write_bytes(b"a.png")

        h1 = hashlib.sha256(b"content").hexdigest()
        h3 = hashlib.sha256(b"different").hexdigest()
        repo_data = build_repo_index(tracked_files=[file2, file1, file3, file4])
        assert repo_data["index"][(7, h1)] == [file1, file2]

        report1 = audit_inventory(
            {
                "item_count": 1,
                "items": [
                    {
                        "size_bytes": 9,
                        "hashed_byte_count": 9,
                        "sha256": h3,
                        "asset_type": "image",
                    }
                ],
            },
            repo_data,
            "dummy",
        )
        assert report1["items"][0]["match_status"] == "one_repo_exact_match_candidate"
        assert report1["items"][0]["candidate_paths"] == [file3]

        report2 = audit_inventory(
            {
                "item_count": 1,
                "items": [
                    {
                        "size_bytes": 7,
                        "hashed_byte_count": 7,
                        "sha256": h1,
                        "asset_type": "image",
                    }
                ],
            },
            repo_data,
            "dummy",
        )
        assert (
            report2["items"][0]["match_status"]
            == "multiple_repo_exact_match_candidates"
        )
        assert len(report2["items"][0]["candidate_paths"]) == 2

        report3 = audit_inventory(
            {
                "item_count": 1,
                "items": [
                    {
                        "size_bytes": 100,
                        "hashed_byte_count": 100,
                        "sha256": h1,
                        "asset_type": "image",
                        "resolved_url": "http://e/a.png",
                    }
                ],
            },
            repo_data,
            "dummy",
        )
        assert report3["items"][0]["match_status"] == "no_repo_exact_match"

        report4 = audit_inventory(
            {
                "item_count": 1,
                "items": [
                    {
                        "size_bytes": 5,
                        "hashed_byte_count": 5,
                        "sha256": "0" * 64,
                        "asset_type": "image",
                        "resolved_url": "http://e/a.png",
                    }
                ],
            },
            repo_data,
            "dummy",
        )
        assert report4["items"][0]["match_status"] == "no_repo_exact_match"

        report5 = audit_inventory(
            {
                "item_count": 1,
                "items": [
                    {
                        "size_bytes": 100,
                        "hashed_byte_count": 7,
                        "sha256": h1,
                        "asset_type": "image",
                    }
                ],
            },
            repo_data,
            "dummy",
        )
        assert report5["items"][0]["match_status"] == "not_evaluated_partial_hash"
        assert report5["items"][0]["candidate_paths"] == []
    audit_module.ROOT = old_root


def test_lfs():
    old_root = audit_module.ROOT
    with tempfile.TemporaryDirectory() as td:
        audit_module.ROOT = Path(td)
        lfs_file = "lfs.png"
        (Path(td) / lfs_file).write_text(
            "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n",
            encoding="utf-8",
        )
        repo_data = build_repo_index(tracked_files=[lfs_file])
        assert repo_data["lfs_count"] == 1
        assert repo_data["eligible_count"] == 0
    audit_module.ROOT = old_root


def test_build_repo_index_requires_explicit_paths():
    with pytest.raises(RuntimeError, match="explicit tracked_files"):
        build_repo_index(tracked_files=None)


# ── manifest validation (fail closed) ────────────────────────────────────


def test_validate_manifest_happy_path():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    # non-default commit skips historical pin check
    validate_scan_manifest(m)


def test_validate_manifest_malformed_schema_version():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["schema_version"] = True
    with pytest.raises(ManifestValidationError, match="schema_version"):
        validate_scan_manifest(m)


def test_validate_manifest_unknown_critical_key():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["extra_critical"] = 1
    with pytest.raises(ManifestValidationError, match="unknown top-level"):
        validate_scan_manifest(m)


def test_validate_manifest_duplicate_path():
    e = {
        "path": "a.txt",
        "size_bytes": 1,
        "sha256": hashlib.sha256(b"x").hexdigest(),
    }
    m = _valid_manifest_skeleton(
        entries=[e, dict(e)],
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        enumerated_tracked_path_count=3,
        eligible_entry_count=2,
        excluded_path_count=1,
    )
    with pytest.raises(ManifestValidationError, match="duplicate"):
        validate_scan_manifest(m)


def test_validate_manifest_unsorted_path():
    e1 = {
        "path": "b.txt",
        "size_bytes": 1,
        "sha256": hashlib.sha256(b"x").hexdigest(),
    }
    e2 = {
        "path": "a.txt",
        "size_bytes": 1,
        "sha256": hashlib.sha256(b"y").hexdigest(),
    }
    m = {
        "schema_version": 1,
        "manifest_kind": MANIFEST_KIND,
        "snapshot": {
            "repository": "skerishKang/400-ai-finder",
            "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "enumerated_tracked_path_count": 3,
            "eligible_entry_count": 2,
            "excluded_path_count": 1,
            "lfs_pointer_count": 0,
            "missing_or_unreadable_count": 0,
        },
        "canonical_manifest_sha256": compute_canonical_manifest_sha256([e1, e2]),
        "entries": [e1, e2],
    }
    with pytest.raises(ManifestValidationError, match="sorted"):
        validate_scan_manifest(m)


def test_validate_manifest_blank_path():
    m = _valid_manifest_skeleton(
        entries=[
            {
                "path": "   ",
                "size_bytes": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            }
        ],
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        enumerated_tracked_path_count=2,
        eligible_entry_count=1,
        excluded_path_count=1,
    )
    with pytest.raises(ManifestValidationError, match="blank|path"):
        validate_scan_manifest(m)


def test_validate_manifest_absolute_path():
    m = _valid_manifest_skeleton(
        entries=[
            {
                "path": "/etc/passwd",
                "size_bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        ],
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        enumerated_tracked_path_count=2,
        eligible_entry_count=1,
        excluded_path_count=1,
    )
    with pytest.raises(ManifestValidationError, match="absolute"):
        validate_scan_manifest(m)


def test_validate_manifest_dotdot_path():
    m = _valid_manifest_skeleton(
        entries=[
            {
                "path": "foo/../bar",
                "size_bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        ],
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        enumerated_tracked_path_count=2,
        eligible_entry_count=1,
        excluded_path_count=1,
    )
    with pytest.raises(ManifestValidationError, match="invalid path"):
        validate_scan_manifest(m)


def test_validate_manifest_backslash_path():
    m = _valid_manifest_skeleton(
        entries=[
            {
                "path": "foo\\bar",
                "size_bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        ],
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        enumerated_tracked_path_count=2,
        eligible_entry_count=1,
        excluded_path_count=1,
    )
    with pytest.raises(ManifestValidationError, match="backslash"):
        validate_scan_manifest(m)


def test_validate_manifest_bool_size():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["entries"][0]["size_bytes"] = True
    m["canonical_manifest_sha256"] = compute_canonical_manifest_sha256(m["entries"])
    with pytest.raises(ManifestValidationError, match="size_bytes"):
        validate_scan_manifest(m)


def test_validate_manifest_negative_size():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["entries"][0]["size_bytes"] = -1
    m["canonical_manifest_sha256"] = compute_canonical_manifest_sha256(m["entries"])
    with pytest.raises(ManifestValidationError, match="size_bytes"):
        validate_scan_manifest(m)


def test_validate_manifest_uppercase_sha():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["entries"][0]["sha256"] = "A" * 64
    m["canonical_manifest_sha256"] = compute_canonical_manifest_sha256(m["entries"])
    with pytest.raises(ManifestValidationError, match="sha256"):
        validate_scan_manifest(m)


def test_validate_manifest_malformed_sha():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["entries"][0]["sha256"] = "z" * 64
    m["canonical_manifest_sha256"] = compute_canonical_manifest_sha256(m["entries"])
    with pytest.raises(ManifestValidationError, match="sha256"):
        validate_scan_manifest(m)


def test_validate_manifest_count_mismatch():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["snapshot"]["eligible_entry_count"] = 99
    with pytest.raises(ManifestValidationError, match="eligible_entry_count"):
        validate_scan_manifest(m)


def test_validate_manifest_canonical_sha_mismatch():
    m = _valid_manifest_skeleton(
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    m["canonical_manifest_sha256"] = "0" * 64
    with pytest.raises(ManifestValidationError, match="canonical_manifest_sha256"):
        validate_scan_manifest(m)


def test_validate_manifest_excluded_path_in_entries():
    excluded = next(iter(EXCLUDED_PATHS))
    m = _valid_manifest_skeleton(
        entries=[
            {
                "path": excluded,
                "size_bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            }
        ],
        commit_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        enumerated_tracked_path_count=2,
        eligible_entry_count=1,
        excluded_path_count=1,
    )
    with pytest.raises(ManifestValidationError, match="excluded audit path"):
        validate_scan_manifest(m)


def test_load_missing_manifest(tmp_path):
    with pytest.raises(ManifestValidationError, match="missing"):
        load_scan_manifest(tmp_path / "nope.json")


# ── committed frozen manifest + report contracts ─────────────────────────


def test_committed_scan_manifest_validates():
    m = load_scan_manifest()
    assert m["snapshot"]["commit_sha"] == DEFAULT_SNAPSHOT_COMMIT
    assert m["snapshot"]["eligible_entry_count"] == 622
    assert m["snapshot"]["enumerated_tracked_path_count"] == 626
    assert m["snapshot"]["excluded_path_count"] == 4
    assert m["canonical_manifest_sha256"] == HISTORICAL_CANONICAL_MANIFEST_SHA256
    assert m["canonical_manifest_sha256"] != LEGACY_WORKING_TREE_MANIFEST_SHA256


def test_final_committed_consistency():
    result = subprocess.run(
        [sys.executable, "scripts/audit_bukgu_home_asset_identity.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()


def test_report_summary_counts_stable():
    report = generate_report_from_frozen_manifest()
    s = report["summary"]
    assert s["asset_total"] == 174
    assert s["full_body_equivalent_hash_count"] == 35
    assert s["partial_prefix_hash_count"] == 5
    assert s["unhashed_count"] == 134
    assert s["invalid_evidence_count"] == 0
    assert s["evaluated_full_hash_count"] == 35
    assert s["one_exact_candidate_count"] == 0
    assert s["multiple_exact_candidates_count"] == 0
    assert s["no_exact_match_count"] == 35
    assert report["schema_version"] == 2
    assert report["audit_generator"]["version"] == "2.0.0"
    assert report["scan"]["method"] == "frozen_repository_scan_manifest"
    assert report["scan"]["snapshot_commit_sha"] == DEFAULT_SNAPSHOT_COMMIT
    assert report["scan"]["entry_count"] == 622
    assert (
        report["scan"]["canonical_manifest_sha256"]
        == HISTORICAL_CANONICAL_MANIFEST_SHA256
    )


# ── refresh isolation ────────────────────────────────────────────────────


def test_normal_and_check_do_not_call_git_scanners(monkeypatch):
    calls = {"ls_tree": 0, "cat": 0, "batch": 0, "ls_files": 0}

    real_run = subprocess.run

    def guarded_run(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            if "ls-tree" in cmd:
                calls["ls_tree"] += 1
            if "cat-file" in cmd:
                calls["cat"] += 1
            if "ls-files" in cmd:
                calls["ls_files"] += 1
            raise AssertionError(f"git must not run during normal/check: {cmd}")
        return real_run(cmd, *a, **kw)

    def guarded_popen(cmd, *a, **kw):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            calls["batch"] += 1
            raise AssertionError(f"git Popen must not run during normal/check: {cmd}")
        raise AssertionError("unexpected Popen")

    monkeypatch.setattr(subprocess, "run", guarded_run)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)

    # generation
    report = generate_report_from_frozen_manifest()
    assert report["summary"]["asset_total"] == 174

    # --check via main
    main(["--check"])
    assert calls == {"ls_tree": 0, "cat": 0, "batch": 0, "ls_files": 0}


def test_explicit_refresh_uses_git_tree_blob_scanner():
    # Real git objects for default snapshot; must succeed and match pin.
    m = build_scan_manifest_from_git(DEFAULT_SNAPSHOT_COMMIT)
    assert m["snapshot"]["eligible_entry_count"] == 622
    assert m["canonical_manifest_sha256"] == HISTORICAL_CANONICAL_MANIFEST_SHA256


# ── unrelated tracked file regression (isolated temp git repo) ───────────


def _init_tiny_git_repo(td: Path):
    subprocess.run(["git", "init"], cwd=td, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=td,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=td,
        check=True,
        capture_output=True,
    )
    # Keep LF for predictable blob bytes.
    subprocess.run(
        ["git", "config", "core.autocrlf", "false"],
        cwd=td,
        check=True,
        capture_output=True,
    )


def test_unrelated_tracked_file_does_not_break_check(tmp_path, monkeypatch):
    """
    Isolated temporary Git repository: baseline frozen manifest/report check
    still PASSes after an unrelated tracked file is added.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_tiny_git_repo(repo)

    inv_dir = repo / "data" / "official_captures" / "bukgu_gwangju" / "home"
    audit_dir = repo / "data" / "official_clone_asset_audits" / "bukgu_gwangju"
    inv_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)

    # Minimal inventory: one full-hash asset matching tracked file content.
    payload = b"asset-bytes-v1"
    (repo / "tracked-asset.bin").write_bytes(payload)
    inv = {
        "captured_at": "2026-07-15T17:12:33+09:00",
        "item_count": 1,
        "items": [
            {
                "asset_type": "image",
                "section": "document",
                "resolved_url": "https://example.invalid/a.png",
                "size_bytes": len(payload),
                "hashed_byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "hash_scope": "full",
            }
        ],
    }
    inv_path = inv_dir / "asset-inventory.json"
    inv_path.write_bytes(dump_json_bytes(inv))

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    commit = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .lower()
    )

    # Point module paths at the temp repo and build frozen manifest from git.
    monkeypatch.setattr(audit_module, "ROOT", repo)
    monkeypatch.setattr(audit_module, "INVENTORY_PATH", inv_path)
    monkeypatch.setattr(
        audit_module,
        "REPORT_PATH",
        audit_dir / "home-repository-match-audit.json",
    )
    monkeypatch.setattr(
        audit_module,
        "SCAN_MANIFEST_PATH",
        audit_dir / "home-repository-scan-manifest.json",
    )

    # Refresh exclusion set is empty-ish for this tiny repo (no self-artifacts yet).
    # Temporarily shrink exclusions so the tracked asset is eligible.
    monkeypatch.setattr(audit_module, "EXCLUDED_PATHS", frozenset())
    monkeypatch.setattr(
        audit_module, "DEFAULT_SNAPSHOT_COMMIT", commit
    )
    # Avoid historical pin mismatch for this disposable commit.
    monkeypatch.setattr(
        audit_module,
        "HISTORICAL_CANONICAL_MANIFEST_SHA256",
        "0" * 64,
    )

    # Bypass historical pin in validate by using a non-default commit check:
    # patch validate to skip historical pin only for this test via commit match.
    def _validate_no_hist(manifest):
        # temporarily clear historical pin enforcement
        orig = audit_module.HISTORICAL_CANONICAL_MANIFEST_SHA256
        audit_module.HISTORICAL_CANONICAL_MANIFEST_SHA256 = "SKIP"
        try:
            # reimplement soft pin: only enforce when equal to DEFAULT and pin is 64 hex of real
            if not isinstance(manifest, dict):
                raise ManifestValidationError("manifest root must be an object")
            # call original after disabling pin by setting commit != DEFAULT
            snap = dict(manifest.get("snapshot") or {})
            # force pin skip by rewriting commit to non-default during validation
            # Actually simpler: call original validate after monkeypatching constant to recomputed
            return None
        finally:
            audit_module.HISTORICAL_CANONICAL_MANIFEST_SHA256 = orig

    # Build manifest using git blobs in temp repo.
    manifest = build_scan_manifest_from_git(commit, cwd=repo)
    # Write without historical pin (commit != DEFAULT_SNAPSHOT_COMMIT after our monkeypatch DEFAULT=commit
    # so pin will fire). Temporarily set HISTORICAL to the computed value.
    monkeypatch.setattr(
        audit_module,
        "HISTORICAL_CANONICAL_MANIFEST_SHA256",
        manifest["canonical_manifest_sha256"],
    )
    audit_module.write_scan_manifest(manifest)
    report = audit_module.generate_report_from_frozen_manifest()
    audit_module.REPORT_PATH.write_bytes(dump_json_bytes(report))

    # Baseline check passes.
    main(["--check"])

    # Add unrelated tracked file; do NOT refresh manifest or report.
    (repo / "unrelated-feature.txt").write_text("hello from future PR\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "unrelated-feature.txt"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "unrelated"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Frozen --check must still pass (no working-tree rescan).
    main(["--check"])
    assert report["summary"]["one_exact_candidate_count"] == 1


# ── tamper detection (temp copies, no real worktree mutation) ────────────


def test_tamper_manifest_entry_fails_check(tmp_path, monkeypatch):
    man = load_scan_manifest()
    man2 = copy.deepcopy(man)
    man2["entries"][0]["sha256"] = "f" * 64
    # leave canonical as-is so validation fails on recompute
    man_path = tmp_path / "m.json"
    # Write raw invalid (skip write_scan_manifest validation)
    man_path.write_bytes(dump_json_bytes(man2))
    monkeypatch.setattr(audit_module, "SCAN_MANIFEST_PATH", man_path)
    with pytest.raises((ManifestValidationError, SystemExit)):
        try:
            main(["--check"])
        except ManifestValidationError:
            raise
        except SystemExit as exc:
            assert exc.code != 0
            raise


def test_tamper_manifest_canonical_sha_fails(tmp_path, monkeypatch):
    man = load_scan_manifest()
    man2 = copy.deepcopy(man)
    man2["canonical_manifest_sha256"] = "a" * 64
    man_path = tmp_path / "m.json"
    man_path.write_bytes(dump_json_bytes(man2))
    monkeypatch.setattr(audit_module, "SCAN_MANIFEST_PATH", man_path)
    with pytest.raises(SystemExit) as exc:
        main(["--check"])
    assert exc.value.code != 0


def test_tamper_inventory_fails_check(tmp_path, monkeypatch):
    inv_raw = audit_module.INVENTORY_PATH.read_bytes()
    inv = json.loads(inv_raw.decode("utf-8"))
    inv["item_count"] += 1
    inv["items"].append(inv["items"][0].copy())
    mut = tmp_path / "inv.json"
    mut.write_bytes(dump_json_bytes(inv))
    monkeypatch.setattr(audit_module, "INVENTORY_PATH", mut)
    with pytest.raises(SystemExit) as exc:
        main(["--check"])
    assert exc.value.code != 0


def test_tamper_report_fails_check(tmp_path, monkeypatch):
    report_bytes = audit_module.REPORT_PATH.read_bytes()
    # Mutated copy only.
    bad = tmp_path / "report.json"
    bad.write_bytes(report_bytes.replace(b"asset_total", b"asset_totax", 1))
    monkeypatch.setattr(audit_module, "REPORT_PATH", bad)
    with pytest.raises(SystemExit) as exc:
        main(["--check"])
    assert exc.value.code != 0


def test_tamper_snapshot_count_fails_validation():
    man = load_scan_manifest()
    man2 = copy.deepcopy(man)
    man2["snapshot"]["enumerated_tracked_path_count"] += 1
    with pytest.raises(ManifestValidationError, match="partition"):
        validate_scan_manifest(man2)


# ── cross-platform canonical bytes ───────────────────────────────────────


def test_json_output_utf8_lf():
    report = generate_report_from_frozen_manifest()
    raw = dump_json_bytes(report)
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    raw.decode("utf-8")
    assert raw == audit_module.REPORT_PATH.read_bytes()


def test_canonical_manifest_lines_use_explicit_lf():
    entries = [
        {
            "path": "a.txt",
            "size_bytes": 1,
            "sha256": "a" * 64,
        }
    ]
    line = audit_module.canonical_manifest_line("a.txt", 1, "a" * 64)
    assert line.endswith("\n")
    assert "\r" not in line
    h = compute_canonical_manifest_sha256(entries)
    assert len(h) == 64


def test_git_blob_bytes_not_working_tree_crlf():
    """Blob pin differs from legacy working-tree CRLF pin on this platform."""
    assert HISTORICAL_CANONICAL_MANIFEST_SHA256 != LEGACY_WORKING_TREE_MANIFEST_SHA256
    m = load_scan_manifest()
    # Recompute from entries must match stored blob pin.
    assert (
        compute_canonical_manifest_sha256(m["entries"])
        == HISTORICAL_CANONICAL_MANIFEST_SHA256
    )


def test_refresh_without_ref_uses_default(monkeypatch, tmp_path):
    # Don't overwrite real manifest: redirect path.
    out = tmp_path / "home-repository-scan-manifest.json"
    monkeypatch.setattr(audit_module, "SCAN_MANIFEST_PATH", out)
    # Allow historical pin write
    main(["--refresh-scan-manifest"])
    loaded = load_scan_manifest(out)
    assert loaded["snapshot"]["commit_sha"] == DEFAULT_SNAPSHOT_COMMIT
    assert loaded["canonical_manifest_sha256"] == HISTORICAL_CANONICAL_MANIFEST_SHA256


def test_check_cannot_refresh():
    with pytest.raises(SystemExit) as exc:
        main(["--check", "--refresh-scan-manifest"])
    assert exc.value.code == 2


def test_snapshot_ref_requires_refresh():
    with pytest.raises(SystemExit) as exc:
        main(["--snapshot-ref", DEFAULT_SNAPSHOT_COMMIT])
    assert exc.value.code == 2
