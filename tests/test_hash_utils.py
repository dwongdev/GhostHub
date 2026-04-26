"""
Tests for Hash Utilities
------------------------
Data integrity foundation. If hashes are non-deterministic or collide
unexpectedly, the entire media library versioning and deduplication system
breaks. Files show as "changed" every scan → infinite re-indexing.
"""
import pytest
import hashlib
from app.utils.hash_utils import (
    generate_file_hash,
    generate_collection_hash,
    generate_dict_hash,
)


class TestGenerateFileHash:
    """Tests for metadata-based file hashing."""

    def test_produces_valid_sha256_hex(self):
        """Hash output must be a 64-char hex string."""
        h = generate_file_hash("/media/video.mp4", 1024000, 1709000000.0)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic_for_same_inputs(self):
        """Same metadata → same hash (critical for cache invalidation)."""
        a = generate_file_hash("/media/a.mp4", 5000, 1700000000.0)
        b = generate_file_hash("/media/a.mp4", 5000, 1700000000.0)
        assert a == b

    def test_different_path_produces_different_hash(self):
        a = generate_file_hash("/media/a.mp4", 5000, 1700000000.0)
        b = generate_file_hash("/media/b.mp4", 5000, 1700000000.0)
        assert a != b

    def test_different_size_produces_different_hash(self):
        a = generate_file_hash("/media/a.mp4", 5000, 1700000000.0)
        b = generate_file_hash("/media/a.mp4", 5001, 1700000000.0)
        assert a != b

    def test_different_mtime_produces_different_hash(self):
        a = generate_file_hash("/media/a.mp4", 5000, 1700000000.0)
        b = generate_file_hash("/media/a.mp4", 5000, 1700000001.0)
        assert a != b

    def test_handles_unicode_paths(self):
        """Paths with unicode characters (e.g. Japanese folders) must hash correctly."""
        h = generate_file_hash("/media/映画/test.mp4", 1024, 1700000000.0)
        assert len(h) == 64

    def test_handles_zero_size_file(self):
        """Empty files are valid (e.g. touch-created placeholders)."""
        h = generate_file_hash("/media/empty.txt", 0, 1700000000.0)
        assert len(h) == 64

    def test_handles_large_size(self):
        """10GB file metadata must hash correctly."""
        h = generate_file_hash("/media/huge.mkv", 10_737_418_240, 1700000000.0)
        assert len(h) == 64

    def test_handles_float_mtime_precision(self):
        """mtime precision matters — floating point must not alias."""
        a = generate_file_hash("/f", 1, 1700000000.123456)
        b = generate_file_hash("/f", 1, 1700000000.123457)
        assert a != b


class TestGenerateCollectionHash:
    """Tests for collection/category versioning hash."""

    def test_deterministic_for_same_hashes(self):
        hashes = ["aaa", "bbb", "ccc"]
        assert generate_collection_hash(hashes) == generate_collection_hash(hashes)

    def test_order_independent(self):
        """Input order must not affect output — critical for scanning where
        filesystem order is non-deterministic."""
        a = generate_collection_hash(["hash1", "hash2", "hash3"])
        b = generate_collection_hash(["hash3", "hash1", "hash2"])
        assert a == b

    def test_different_hashes_produce_different_result(self):
        a = generate_collection_hash(["hash1", "hash2"])
        b = generate_collection_hash(["hash1", "hash3"])
        assert a != b

    def test_empty_collection(self):
        """Empty collection should produce a valid hash (e.g. empty category)."""
        h = generate_collection_hash([])
        assert len(h) == 64

    def test_single_item_collection(self):
        h = generate_collection_hash(["only_hash"])
        assert len(h) == 64

    def test_handles_duplicate_hashes(self):
        """Duplicate file hashes in collection should produce different
        result than deduped version (collection might have duplicates)."""
        a = generate_collection_hash(["aaa", "aaa"])
        b = generate_collection_hash(["aaa"])
        assert a != b


class TestGenerateDictHash:
    """Tests for dictionary hashing (used for config/metadata versioning)."""

    def test_deterministic_for_same_dict(self):
        d = {"key": "value", "count": 42}
        assert generate_dict_hash(d) == generate_dict_hash(d)

    def test_key_order_independent(self):
        """JSON sort_keys=True should make key order irrelevant."""
        a = generate_dict_hash({"z": 1, "a": 2})
        b = generate_dict_hash({"a": 2, "z": 1})
        assert a == b

    def test_different_values_produce_different_hash(self):
        a = generate_dict_hash({"key": "value1"})
        b = generate_dict_hash({"key": "value2"})
        assert a != b

    def test_nested_dict(self):
        d = {"outer": {"inner": "value"}}
        h = generate_dict_hash(d)
        assert len(h) == 64

    def test_empty_dict(self):
        h = generate_dict_hash({})
        assert len(h) == 64

    def test_handles_various_types(self):
        """Dicts with int, float, bool, None, list values."""
        d = {
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
        }
        h = generate_dict_hash(d)
        assert len(h) == 64

    def test_different_types_same_value_produce_different_hash(self):
        """String "1" vs int 1 must not collide."""
        a = generate_dict_hash({"val": "1"})
        b = generate_dict_hash({"val": 1})
        assert a != b
