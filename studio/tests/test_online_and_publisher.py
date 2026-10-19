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
        assert total > 7000
        all_games = OnlineFetcher.search_switch_games("", category="all")
        assert len(all_games) >= total
        limited = OnlineFetcher.search_switch_games("", category="all", limit=50)
        assert len(limited) == 50

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

    def test_delete_published_variants_empty(self):
        count = GitHubPublisher.delete_published_variants([], token="fake_token")
        assert count == 0

    def test_delete_published_variants_mocked(self, monkeypatch, tmp_path):
        mock_catalog = {
            "schemaVersion": 1,
            "totalGames": 2,
            "totalVariants": 3,
            "games": [
                {
                    "titleId": "0100000000010000",
                    "title": "Super Mario Odyssey",
                    "variants": [
                        {"id": "default", "name": "Default"},
                        {"id": "trailer", "name": "Trailer"}
                    ]
                },
                {
                    "titleId": "01007EF00011E000",
                    "title": "Zelda BOTW",
                    "variants": [
                        {"id": "cinematic", "name": "Cinematic"}
                    ]
                }
            ]
        }
        monkeypatch.setattr(GitHubPublisher, "fetch_catalog", lambda token, repo: mock_catalog)

        # Mock urllib to intercept release asset fetch, release asset delete, and PUT commit
        import urllib.request
        class DummyResponse:
            def __init__(self, data=b"{}"):
                self.data = data
            def read(self):
                return self.data
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        def mock_urlopen(req, timeout=15):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "releases/tags" in url:
                return DummyResponse(b'{"assets": []}')
            elif "contents/catalog" in url:
                return DummyResponse(b'{"sha": "dummy_sha"}')
            return DummyResponse(b"{}")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        # Delete 1 variant from Mario and 1 from Zelda (which leaves Mario with 1, Zelda with 0 -> removed)
        items = [
            {"titleId": "0100000000010000", "variantId": "default"},
            {"titleId": "01007EF00011E000", "variantId": "cinematic"}
        ]
        temp_catalog_file = tmp_path / "catalog.json"
        deleted_count = GitHubPublisher.delete_published_variants(
            items,
            token="ghp_dummy",
            local_catalog_path=temp_catalog_file
        )
        assert deleted_count == 2
        # After deletion, games list should only have Mario with remaining variant 'trailer'
        assert len(mock_catalog["games"]) == 1
        assert mock_catalog["games"][0]["titleId"] == "0100000000010000"
        assert len(mock_catalog["games"][0]["variants"]) == 1
        assert mock_catalog["games"][0]["variants"][0]["id"] == "trailer"
        assert mock_catalog["totalGames"] == 1
        assert mock_catalog["totalVariants"] == 1
        assert temp_catalog_file.exists()

