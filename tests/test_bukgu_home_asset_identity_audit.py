import pytest
import os
import tempfile
import json
import hashlib
import subprocess
from pathlib import Path
from scripts.audit_bukgu_home_asset_identity import classify_evidence, build_repo_index, audit_inventory

def test_classify_evidence():
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a"*64}) == "full_body_equivalent_hash"
    assert classify_evidence({"size_bytes": 200, "hashed_byte_count": 100, "sha256": "0123456789abcdef"*4}) == "partial_prefix_hash"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100}) == "unhashed"

    # Invalid tests
    assert classify_evidence({"size_bytes": -1, "hashed_byte_count": 100, "sha256": "a"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 200, "sha256": "a"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "g"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "A"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a"*63}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a"*65}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "-"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a"*63 + " "}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": 123}) == "invalid_capture_evidence"

def test_exact_matching():
    import scripts.audit_bukgu_home_asset_identity as audit_module
    old_root = audit_module.ROOT

    with tempfile.TemporaryDirectory() as td:
        audit_module.ROOT = Path(td)

        file1 = "a.png"
        file2 = "b.png"
        file3 = "c.png"
        file4 = "d.png"

        with open(os.path.join(td, file1), "wb") as f: f.write(b"content")
        with open(os.path.join(td, file2), "wb") as f: f.write(b"content")
        with open(os.path.join(td, file3), "wb") as f: f.write(b"different")
        with open(os.path.join(td, file4), "wb") as f: f.write(b"a.png") # same filename trick, different bytes

        hasher = hashlib.sha256()
        hasher.update(b"content")
        h1 = hasher.hexdigest()

        hasher = hashlib.sha256()
        hasher.update(b"different")
        h3 = hasher.hexdigest()

        repo_data = build_repo_index(tracked_files=[file2, file1, file3, file4]) # shuffled

        # Candidate ordering test
        assert repo_data["index"][(7, h1)] == [file1, file2]

        # Test 1: one exact candidate
        item1 = {
            "size_bytes": 9,
            "hashed_byte_count": 9,
            "sha256": h3,
            "asset_type": "image"
        }
        report1 = audit_inventory({"item_count": 1, "items": [item1]}, repo_data, "dummy")
        assert report1["items"][0]["match_status"] == "one_repo_exact_match_candidate"
        assert report1["items"][0]["candidate_paths"] == [file3]

        # Test 2: multiple candidates
        item2 = {
            "size_bytes": 7,
            "hashed_byte_count": 7,
            "sha256": h1,
            "asset_type": "image"
        }
        report2 = audit_inventory({"item_count": 1, "items": [item2]}, repo_data, "dummy")
        assert report2["items"][0]["match_status"] == "multiple_repo_exact_match_candidates"
        assert len(report2["items"][0]["candidate_paths"]) == 2

        # Test 3: no match (different size + same filename -> no exact match)
        item3 = {
            "size_bytes": 100,
            "hashed_byte_count": 100,
            "sha256": h1,
            "asset_type": "image",
            "resolved_url": "http://e/a.png"
        }
        report3 = audit_inventory({"item_count": 1, "items": [item3]}, repo_data, "dummy")
        assert report3["items"][0]["match_status"] == "no_repo_exact_match"

        # Test 4: no match (same filename + different bytes)
        item4 = {
            "size_bytes": 5,
            "hashed_byte_count": 5,
            "sha256": "0"*64,
            "asset_type": "image",
            "resolved_url": "http://e/a.png"
        }
        report4 = audit_inventory({"item_count": 1, "items": [item4]}, repo_data, "dummy")
        assert report4["items"][0]["match_status"] == "no_repo_exact_match"

        # Test 5: Prefix collision
        item5 = {
            "size_bytes": 100,
            "hashed_byte_count": 7,
            "sha256": h1, # same prefix hash
            "asset_type": "image"
        }
        report5 = audit_inventory({"item_count": 1, "items": [item5]}, repo_data, "dummy")
        assert report5["items"][0]["match_status"] == "not_evaluated_partial_hash"
        assert report5["items"][0]["candidate_paths"] == []

    audit_module.ROOT = old_root

def test_lfs():
    import scripts.audit_bukgu_home_asset_identity as audit_module
    old_root = audit_module.ROOT

    with tempfile.TemporaryDirectory() as td:
        audit_module.ROOT = Path(td)
        lfs_file = "lfs.png"
        with open(os.path.join(td, lfs_file), "w") as f:
            f.write("version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n")

        repo_data = build_repo_index(tracked_files=[lfs_file])
        assert repo_data["lfs_count"] == 1
        assert repo_data["eligible_count"] == 0

    audit_module.ROOT = old_root

def test_drift():
    # manual report edit
    result = subprocess.run(["python", "scripts/audit_bukgu_home_asset_identity.py", "--check"], capture_output=True)
    assert result.returncode == 0

    # modify report
    with open("data/official_clone_asset_audits/bukgu_gwangju/home-repository-match-audit.json", "r+", encoding="utf-8", newline="\n") as f:
        content = f.read()
        f.seek(0)
        f.write(content.replace("asset_total", "asset_totax"))
        f.truncate()
        
    try:
        result = subprocess.run(["python", "scripts/audit_bukgu_home_asset_identity.py", "--check"], capture_output=True)
        assert result.returncode != 0
    finally:
        with open("data/official_clone_asset_audits/bukgu_gwangju/home-repository-match-audit.json", "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

def test_inventory_mutation():
    import scripts.audit_bukgu_home_asset_identity as audit_module
    old_inv = audit_module.INVENTORY_PATH

    with tempfile.TemporaryDirectory() as td:
        # Create a mutated inventory
        with open(old_inv, "r", encoding="utf-8") as f:
            inv = json.loads(f.read())
        inv["item_count"] += 1
        inv["items"].append(inv["items"][0].copy())

        mut_path = Path(td) / "mut.json"
        with open(mut_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(inv))

        audit_module.INVENTORY_PATH = mut_path
        try:
            import sys
            sys.argv.append('--check')
            with pytest.raises(SystemExit) as exc:
                audit_module.main()
            assert exc.value.code != 0
        finally:
            sys.argv.remove('--check')
            audit_module.INVENTORY_PATH = old_inv

def test_final_committed_consistency():
    result = subprocess.run(["python", "scripts/audit_bukgu_home_asset_identity.py", "--check"], capture_output=True)
    assert result.returncode == 0
