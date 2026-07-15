import sys
import json
import hashlib
import os
import subprocess
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home" / "asset-inventory.json"
REPORT_PATH = ROOT / "data" / "official_clone_asset_audits" / "bukgu_gwangju" / "home-repository-match-audit.json"

EXCLUDED_PATHS = {
    "data/official_clone_asset_audits/bukgu_gwangju/home-repository-match-audit.json",
    "docs/artifacts/1172-home-asset-identity-audit.md",
    "scripts/audit_bukgu_home_asset_identity.py",
    "tests/test_bukgu_home_asset_identity_audit.py",
}

def is_lfs_pointer(filepath):
    with open(filepath, "rb") as f:
        header = f.read(100)
        return header.startswith(b"version https://git-lfs.github.com/spec/v1")

def get_tracked_files():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    files = result.stdout.split(b'\0')
    tracked = []
    for f in files:
        if not f:
            continue
        try:
            path = f.decode('utf-8').replace("\\", "/")
            tracked.append(path)
        except UnicodeDecodeError:
            print("Failed to decode path: ", f)
            sys.exit(1)
    return sorted(tracked)

def build_repo_index(tracked_files=None):
    if tracked_files is None:
        tracked_files = get_tracked_files()

    enumerated_count = len(tracked_files)
    eligible_count = 0
    excluded_count = 0
    lfs_count = 0
    missing_unreadable_count = 0

    size_hash_index = {}
    manifest_hasher = hashlib.sha256()

    for relative_path in tracked_files:
        if relative_path in EXCLUDED_PATHS:
            excluded_count += 1
            continue

        full_path = ROOT / relative_path

        if not full_path.exists() or not full_path.is_file():
            missing_unreadable_count += 1
            continue

        try:
            if is_lfs_pointer(full_path):
                lfs_count += 1
                continue
        except OSError:
            missing_unreadable_count += 1
            continue

        try:
            size = full_path.stat().st_size
            hasher = hashlib.sha256()
            with open(full_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            file_hash = hasher.hexdigest()
        except OSError:
            missing_unreadable_count += 1
            continue

        manifest_str = f"{relative_path}|{size}|{file_hash}\n"
        manifest_hasher.update(manifest_str.encode('utf-8'))

        key = (size, file_hash)
        if key not in size_hash_index:
            size_hash_index[key] = []
        size_hash_index[key].append(relative_path)
        eligible_count += 1

    for k in size_hash_index:
        size_hash_index[k].sort()

    if eligible_count + excluded_count + lfs_count + missing_unreadable_count != enumerated_count:
        print("Invariant violation: eligible + excluded + lfs + missing_or_unreadable != enumerated tracked paths")
        sys.exit(1)

    return {
        "enumerated_count": enumerated_count,
        "eligible_count": eligible_count,
        "excluded_count": excluded_count,
        "lfs_count": lfs_count,
        "missing_unreadable_count": missing_unreadable_count,
        "manifest_sha256": manifest_hasher.hexdigest(),
        "index": size_hash_index
    }

def classify_evidence(item):
    sha = item.get("sha256")
    size = item.get("size_bytes")
    hashed_byte_count = item.get("hashed_byte_count")

    if sha is None:
        return "unhashed"

    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return "invalid_capture_evidence"

    if size is None or not isinstance(size, int) or size < 0:
        return "invalid_capture_evidence"

    if hashed_byte_count is None or not isinstance(hashed_byte_count, int) or hashed_byte_count < 0:
        return "invalid_capture_evidence"

    if hashed_byte_count > size:
        return "invalid_capture_evidence"

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
        "by_source_section": {}
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
            reason = f"full hash evaluated; matched {len(candidates)} exact repository files" if candidates else "full hash evaluated; no equal-size/equal-sha tracked file"

            summary["evaluated_full_hash_count"] += 1
            if match_status == "one_repo_exact_match_candidate":
                summary["one_exact_candidate_count"] += 1
            elif match_status == "multiple_repo_exact_match_candidates":
                summary["multiple_exact_candidates_count"] += 1
            elif match_status == "no_repo_exact_match":
                summary["no_exact_match_count"] += 1

        elif evidence_class == "partial_prefix_hash":
            match_status = "not_evaluated_partial_hash"
            reason = "partial prefix hash cannot establish full-file identity"
            summary["not_evaluated_partial_count"] += 1
        elif evidence_class == "unhashed":
            match_status = "not_evaluated_unhashed"
            reason = "no captured hash available"
            summary["not_evaluated_unhashed_count"] += 1
        elif evidence_class == "invalid_capture_evidence":
            match_status = "not_evaluated_invalid_evidence"
            reason = "capture evidence is invalid"
            summary["not_evaluated_invalid_count"] += 1

        candidate_count = len(candidate_paths)
        summary[evidence_class + "_count"] = summary.get(evidence_class + "_count", 0) + 1

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

        out_items.append({
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
            "reason": reason
        })

    report = {
        "schema_version": 1,
        "audit_kind": "official_home_asset_repository_identity_audit",
        "audit_generator": {
            "id": "scripts/audit_bukgu_home_asset_identity.py",
            "version": "1.0.0"
        },
        "source": {
            "path": "data/official_captures/bukgu_gwangju/home/asset-inventory.json",
            "sha256": inventory_hash,
            "captured_at": inventory.get("captured_at"),
            "item_count": inventory.get("item_count")
        },
        "scan": {
            "method": "git_ls_files",
            "enumerated_tracked_path_count": repo_data["enumerated_count"],
            "eligible_tracked_file_count": repo_data["eligible_count"],
            "excluded_path_count": repo_data["excluded_count"],
            "lfs_pointer_count": repo_data["lfs_count"],
            "missing_or_unreadable_count": repo_data["missing_unreadable_count"],
            "manifest_sha256": repo_data["manifest_sha256"]
        },
        "summary": summary,
        "items": out_items
    }
    return report

def main():
    is_check = "--check" in sys.argv

    with open(INVENTORY_PATH, "r", encoding="utf-8") as f:
        inventory_content = f.read()

    inventory = json.loads(inventory_content)
    inventory_hash = hashlib.sha256(inventory_content.encode('utf-8')).hexdigest()

    if inventory.get("item_count") != len(inventory.get("items", [])):
        print("Error: inventory item_count mismatch")
        sys.exit(1)

    repo_data = build_repo_index()
    report = audit_inventory(inventory, repo_data, inventory_hash)

    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode('utf-8')

    if is_check:
        if not REPORT_PATH.exists():
            print("Check failed: Report does not exist")
            sys.exit(1)
        with open(REPORT_PATH, "rb") as f:
            existing = f.read()
        if existing != report_bytes:
            print("Check failed: Report drift detected")
            sys.exit(1)
        print("Check passed")
    else:
        os.makedirs(REPORT_PATH.parent, exist_ok=True)
        with open(REPORT_PATH, "wb") as f:
            f.write(report_bytes)
        print("Report written")

if __name__ == "__main__":
    import socket
    import urllib.request
    import http.client
    def block_network(*args, **kwargs):
        raise RuntimeError("Network calls are forbidden in this script.")
    socket.socket.connect = block_network
    urllib.request.urlopen = block_network
    http.client.HTTPConnection.request = block_network
    http.client.HTTPSConnection.request = block_network
    try:
        import requests
        requests.get = block_network
        requests.post = block_network
    except ImportError:
        pass

    main()
