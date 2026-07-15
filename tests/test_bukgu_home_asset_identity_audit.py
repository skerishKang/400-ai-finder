import pytest
import os
import tempfile
import json
import hashlib
from scripts.audit_bukgu_home_asset_identity import classify_evidence, build_repo_index, audit_inventory, get_tracked_files

def test_classify_evidence():
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a"*64}) == "full_body_equivalent_hash"
    assert classify_evidence({"size_bytes": 200, "hashed_byte_count": 100, "sha256": "a"*64}) == "partial_prefix_hash"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100}) == "unhashed"
    assert classify_evidence({"size_bytes": -1, "hashed_byte_count": 100, "sha256": "a"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 200, "sha256": "a"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "A"*64}) == "invalid_capture_evidence"
    assert classify_evidence({"size_bytes": 100, "hashed_byte_count": 100, "sha256": "a"*63}) == "invalid_capture_evidence"

def test_exact_matching():
    with tempfile.TemporaryDirectory() as td:
        file1 = os.path.join(td, "a.png")
        file2 = os.path.join(td, "b.png")
        file3 = os.path.join(td, "c.png")

        with open(file1, "wb") as f: f.write(b"content")
        with open(file2, "wb") as f: f.write(b"content")
        with open(file3, "wb") as f: f.write(b"different")

        hasher = hashlib.sha256()
        hasher.update(b"content")
        h1 = hasher.hexdigest()

        hasher = hashlib.sha256()
        hasher.update(b"different")
        h3 = hasher.hexdigest()

        repo_data = build_repo_index(tracked_files=[file1, file2, file3])

        # Test 1: one exact candidate
        item1 = {
            "size_bytes": 9,
            "hashed_byte_count": 9,
            "sha256": h3,
            "asset_type": "image"
        }
        inventory1 = {"item_count": 1, "items": [item1]}
        report1 = audit_inventory(inventory1, repo_data, "dummy_hash")
        assert report1["items"][0]["match_status"] == "one_repo_exact_match_candidate"
        assert report1["items"][0]["candidate_paths"] == [file3]

        # Test 2: multiple candidates
        item2 = {
            "size_bytes": 7,
            "hashed_byte_count": 7,
            "sha256": h1,
            "asset_type": "image"
        }
        inventory2 = {"item_count": 1, "items": [item2]}
        report2 = audit_inventory(inventory2, repo_data, "dummy_hash")
        assert report2["items"][0]["match_status"] == "multiple_repo_exact_match_candidates"
        assert len(report2["items"][0]["candidate_paths"]) == 2

        # Test 3: no match
        item3 = {
            "size_bytes": 7,
            "hashed_byte_count": 7,
            "sha256": "a"*64,
            "asset_type": "image"
        }
        inventory3 = {"item_count": 1, "items": [item3]}
        report3 = audit_inventory(inventory3, repo_data, "dummy_hash")
        assert report3["items"][0]["match_status"] == "no_repo_exact_match"
        assert report3["items"][0]["candidate_paths"] == []

        # Test 4: never exact if partial
        item4 = {
            "size_bytes": 100,
            "hashed_byte_count": 7,
            "sha256": h1,
            "asset_type": "image"
        }
        inventory4 = {"item_count": 1, "items": [item4]}
        report4 = audit_inventory(inventory4, repo_data, "dummy_hash")
        assert report4["items"][0]["match_status"] == "non_authoritative_candidates"
        assert report4["items"][0]["candidate_paths"] == []

def test_determinism():
    with tempfile.TemporaryDirectory() as td:
        f1 = os.path.join(td, "f1")
        with open(f1, "wb") as f: f.write(b"foo")
        repo_data = build_repo_index(tracked_files=[f1])
        item = {"size_bytes": 3, "hashed_byte_count": 3, "sha256": hashlib.sha256(b"foo").hexdigest(), "asset_type": "img"}
        inventory = {"item_count": 1, "items": [item]}
        report1 = audit_inventory(inventory, repo_data, "dummy")
        report2 = audit_inventory(inventory, repo_data, "dummy")
        assert json.dumps(report1) == json.dumps(report2)
        assert "timestamp" not in json.dumps(report1)

def test_real_committed_inventory():
    with open("data/official_captures/bukgu_gwangju/home/asset-inventory.json", "r", encoding="utf-8") as f:
        inventory = json.loads(f.read())
    assert inventory["item_count"] == 174
    assert inventory["partial_hash_count"] == 40
    assert len(inventory["items"]) == 174

