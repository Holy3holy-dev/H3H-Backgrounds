#!/usr/bin/env python3
"""
Unit tests for catalog validation logic.
Tests boundary enforcement, path traversal rejection, and schema compliance.
"""

import copy
import json
import unittest
from pathlib import Path
from validate_catalog import validate_catalog_data, ValidationError


class TestCatalogValidation(unittest.TestCase):
    def setUp(self):
        fixture_path = Path(__file__).parent.parent / "fixtures" / "test_catalog.json"
        with open(fixture_path, "r", encoding="utf-8") as f:
            self.valid_data = json.load(f)

    def test_valid_catalog_passes(self):
        games, variants = validate_catalog_data(self.valid_data)
        self.assertEqual(games, 2)
        self.assertEqual(variants, 3)

    def test_reject_invalid_title_id_short(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["titleId"] = "01005CA0158"  # too short
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("invalid Title ID", str(ctx.exception))

    def test_reject_invalid_title_id_non_hex(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["titleId"] = "01005CA01580E00Z"  # Z is not hex
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("invalid Title ID", str(ctx.exception))

    def test_accept_homebrew_title_id(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["titleId"] = "03DB117EE17B6000"  # Homebrew forwarder
        games, variants = validate_catalog_data(data)
        self.assertEqual(games, 2)

    def test_reject_invalid_title_id_length(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["titleId"] = "01005CA01580E0000"  # 17 chars
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("invalid Title ID", str(ctx.exception))

    def test_reject_insecure_http_url(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["variants"][0]["url"] = "http://insecure-site.com/video.mp4"
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("url must start with https://", str(ctx.exception))

    def test_reject_path_traversal_variant_id(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["variants"][0]["id"] = "../../../etc/passwd"
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("invalid 'id'", str(ctx.exception))

    def test_reject_oversized_file(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["variants"][0]["sizeBytes"] = 200 * 1024 * 1024  # 200 MB > 100 MB limit
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("out of safe range", str(ctx.exception))

    def test_reject_duplicate_title_id(self):
        data = copy.deepcopy(self.valid_data)
        data["games"].append(copy.deepcopy(data["games"][0]))
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("Duplicate Title ID", str(ctx.exception))

    def test_reject_invalid_codec(self):
        data = copy.deepcopy(self.valid_data)
        data["games"][0]["variants"][0]["codec"] = "vp9"
        with self.assertRaises(ValidationError) as ctx:
            validate_catalog_data(data)
        self.assertIn("codec 'vp9' not in", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
