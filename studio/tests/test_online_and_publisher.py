"""
Unit tests for OnlineFetcher and GitHubPublisher.
"""

import tempfile
from pathlib import Path
import pytest

from studio.h3h_studio.core.online_fetcher import OnlineFetcher, is_valid_image
from studio.h3h_studio.core.github_publisher import GitHubPublisher


class TestOnlineFetcher:
    def test_search_games_returns_large_catalog(self):
        total = OnlineFetcher.get_total_titles_count()
        assert total > 5000
        first_batch = OnlineFetcher.search_switch_games("", category="all")
        assert len(first_batch) == 200

    def test_search_homebrew_filter(self):
        hb_games = OnlineFetcher.search_switch_games("", category="homebrew")
        assert len(hb_games) > 0
        for g in hb_games[:10]:
            assert g.get("isHomebrew") is True

    def test_search_official_filter(self):
        official_games = OnlineFetcher.search_switch_games("Zelda", category="official")
        assert len(official_games) > 0
        for g in official_games:
            assert g.get("isHomebrew") is False

    def test_image_magic_bytes_validation(self):
        assert is_valid_image(b"\xff\xd8\xff\xe0" + b"\x00" * 20) is True  # JPEG
        assert is_valid_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20) is True  # PNG
        assert is_valid_image(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20) is True  # WebP
        assert is_valid_image(b"<html><head><title>404</title></html>") is False  # HTML error

    def test_download_real_image(self):
        results = OnlineFetcher.search_switch_games("Zelda")
        assert len(results) > 0
        top = results[0]
        temp_dir = Path(tempfile.gettempdir()) / "test_fetcher_unit"
        img = OnlineFetcher.download_image(top.get("artUrl"), temp_dir, top.get("titleId", "zelda"), fallback_title=top["title"])
        assert img is not None
        assert img.exists()
        assert img.stat().st_size > 1000


class TestGitHubPublisher:
    def test_get_stored_credentials(self):
        token, user = GitHubPublisher.get_stored_credentials()
        # On this developer machine, token is configured in Credential Manager
        assert token is not None
        assert token.startswith("ghp_")
        assert user == "Holy3holy-dev"

    def test_compute_sha256(self):
        temp_dir = Path(tempfile.gettempdir())
        dummy_file = temp_dir / "test_sha.bin"
        with open(dummy_file, "wb") as f:
            f.write(b"H3H_BACKGROUNDS_TEST_DATA")
        
        sha = GitHubPublisher.compute_sha256(dummy_file)
        import hashlib
        expected = hashlib.sha256(b"H3H_BACKGROUNDS_TEST_DATA").hexdigest()
        assert sha == expected
